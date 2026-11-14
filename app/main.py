"""Main FastAPI application entrypoint.

Serves the whole site from one origin: the HTML pages (Jinja templates in
templates/, assets in static/) and the write-only API at /api/tesla/*, which
exists for iPhone Shortcuts. Same-origin means no CORS is involved at all.

Assembly lives here — middleware, cache policy, the rate limiter, error pages,
and the page routes. The queries are in app/tesla.py: /mytesla/ calls
get_dashboard() and hands the result straight to the template, so the numbers
are rendered into the HTML rather than fetched by the browser.
"""

import logging
from datetime import timedelta
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import posts, tesla
from app.database import get_db
from app.templating import STATIC_DIR, absolute_url, templates

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Jake Wang",
    version="0.2.0",
    # Hide API docs/schema in production — no need to hand attackers a map
    # of every endpoint (including the protected ones).
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Compress responses over 500 bytes (HTML pages and the growing JSON payloads).
app.add_middleware(GZipMiddleware, minimum_size=500)

# Per-client-IP cap on every route (in-memory — fine for a single-process
# deployment). /health, /robots.txt and /sitemap.xml are exempted at their definitions below,
# so monitors and crawlers are never throttled. It covers the pages and the
# API; slowapi only limits requests that match a route, so the /static mount
# and 404s pass through uncounted.
#
# Behind a reverse proxy, uvicorn needs --proxy-headers (and
# --forwarded-allow-ips) or get_remote_address sees the proxy for every client.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["600/minute"],
    headers_enabled=True,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


class HeadAsGetMiddleware:
    """Answer HEAD wherever GET is routed, with the same headers and no body.

    FastAPI only registers the GET, so a HEAD got 405 and link checkers and
    preview bots saw working pages as broken. The scope is copied rather than
    edited, so the server still knows the request was a HEAD.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "HEAD":
            await self.app(scope, receive, send)
            return

        async def send_without_body(message):
            if message["type"] == "http.response.body":
                message = {**message, "body": b""}
            await send(message)

        await self.app({**scope, "method": "GET"}, receive, send_without_body)


# How long browsers/proxies may cache public GET responses (seconds).
# The page window is kept short because the dashboard's numbers are rendered
# into it: entries added via iPhone Shortcuts should show up right away, and
# the browser cache can't be invalidated remotely, so this is the maximum
# staleness. Static assets carry a versioned URL and can be cached for a year.
# There is no /api/ window: every remaining API route is a POST.
PAGE_CACHE_MAX_AGE = 60
STATIC_CACHE_MAX_AGE = int(timedelta(days=365).total_seconds())

# Status codes that get the HTML error page, and the line it shows. Anything
# not listed here stays JSON, whatever the client is.
ERROR_PAGES = {404: "Page Not Found", 500: "Internal Server Error"}


# Everything the pages load is same-origin: two scripts, one stylesheet, the
# favicons. Inline style attributes stay allowed because the Markdown tables
# extension emits them for column alignment; inline scripts do not.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


def set_security_headers(response) -> None:
    """Baseline security headers, shared by the middleware and the 500 handler.

    setdefault() throughout, so nginx can override any of these without a
    code change.
    """
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    # Disallow embedding the site in iframes (clickjacking protection)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    # Keep the site out of search indexes by default. As a header rather than
    # only a <meta> tag, this also covers the JSON API and static assets, which
    # cannot carry meta tags. The article pages are the exception: they set
    # their own X-Robots-Tag (app/posts.py), which setdefault() leaves alone.
    # robots.txt deliberately still allows search engines to fetch every page —
    # a crawler that is blocked can never read this directive, and
    # already-indexed URLs would linger instead of being dropped.
    response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")


def cache_max_age(request: Request, response) -> int | None:
    """Seconds a response may be publicly cached, or None to leave it alone.

    Only successful GETs qualify. Requests carrying x-api-key are never marked
    publicly cacheable, since those responses are fetched with a personal key,
    and neither is anything that set a cookie on its way out.
    """
    if (
        request.method != "GET"
        or response.status_code != 200
        or "x-api-key" in request.headers
        # Nothing sets a cookie today, but a response that ever does is by
        # definition not shared-cacheable — keep the guard ahead of the need.
        or "set-cookie" in response.headers
    ):
        return None
    if request.url.path.startswith("/static/"):
        return STATIC_CACHE_MAX_AGE
    # Every HTML page: home, the dashboard, and the article pages.
    if response.headers.get("content-type", "").startswith("text/html"):
        return PAGE_CACHE_MAX_AGE
    return None


@app.middleware("http")
async def add_response_headers(request: Request, call_next):
    """Baseline security headers on everything, plus per-kind Cache-Control."""
    response = await call_next(request)
    set_security_headers(response)

    # Starlette redirects /kintone to /kintone/ with a temporary 307. The
    # slashed URL is the permanent address, so say so: search engines then
    # move the link's weight to it instead of keeping both.
    if (
        response.status_code == 307
        and request.method == "GET"
        and urlsplit(response.headers.get("location", "")).path == f"{request.url.path}/"
    ):
        response.status_code = 308

    max_age = cache_max_age(request, response)
    if max_age is not None:
        response.headers.setdefault("Cache-Control", f"public, max-age={max_age}")

    return response


# Added after every other middleware, so it is outermost and all of them,
# including the one above, see a GET.
app.add_middleware(HeadAsGetMiddleware)


def is_api_request(request: Request) -> bool:
    """API clients get JSON errors; everything else gets the HTML error page."""
    return request.url.path.startswith("/api/")


def error_page(request: Request, status_code: int, headers: dict | None = None):
    """The site's HTML error page for one of the ERROR_PAGES status codes."""
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        status_code=status_code,
        context={"code": status_code, "message": ERROR_PAGES[status_code]},
        headers=headers,
    )


@app.exception_handler(StarletteHTTPException)
async def html_error_handler(request: Request, exc: StarletteHTTPException):
    """Friendly HTML error pages for page requests; JSON for the API.

    Without this, a mistyped URL would return FastAPI's bare JSON detail
    instead of the site's 404 page.
    """
    if is_api_request(request) or exc.status_code not in ERROR_PAGES:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return error_page(request, exc.status_code)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    """Log unexpected failures and return a generic error without internal details."""
    logger.error(
        "Unhandled error on %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    headers = {"Cache-Control": "no-store"}
    if is_api_request(request):
        response = JSONResponse(
            status_code=500,
            content={"detail": ERROR_PAGES[500]},
            headers=headers,
        )
    else:
        response = error_page(request, 500, headers)
    # This handler runs outside the middleware above, so set them here too.
    set_security_headers(response)
    return response


# Crawlers that collect training corpora or fetch pages for a chat session.
# Blocked by name, because the blanket "Disallow: /" that would stop them also
# stops the search engines from ever reading the noindex directive above.
# The AI search indexes (OAI-SearchBot, PerplexityBot) are deliberately not
# here: they cite and link to the articles the way a search engine does.
AI_CRAWLERS = (
    "GPTBot",              # OpenAI, training
    "ChatGPT-User",        # OpenAI, user-triggered fetch
    "ClaudeBot",           # Anthropic
    "Claude-Web",
    "anthropic-ai",
    "Google-Extended",     # Google, Gemini training (separate from Googlebot)
    "Applebot-Extended",   # Apple, training (separate from Applebot)
    "CCBot",               # Common Crawl, feeds many training sets
    "Bytespider",          # ByteDance
    "Amazonbot",
    "meta-externalagent",  # Meta
    "FacebookBot",
    "Diffbot",
    "cohere-ai",
    "YouBot",
    "ImagesiftBot",
    "Omgilibot",
    "Timpibot",
)

ROBOTS_TXT = (
    "# Personal project site. Only the articles are meant to be indexed, by\n"
    "# search engines and AI search alike. None of its content may be used for\n"
    "# AI training.\n"
    "#\n"
    "# Search engines may crawl everything: the pages that should stay out of\n"
    "# the index say so with X-Robots-Tag: noindex, and a blocked crawler\n"
    "# could never read that.\n"
    "\n"
    + "".join(f"User-agent: {bot}\n" for bot in AI_CRAWLERS)
    + "Disallow: /\n"
    "\n"
    "User-agent: *\n"
    "Allow: /\n"
    "\n"
    f"Sitemap: {absolute_url('/sitemap.xml')}\n"
)


@app.get("/robots.txt", response_class=PlainTextResponse)
@limiter.exempt
def robots_txt():
    """Block the AI training crawlers by name; let search engines and AI
    search through to read each page's own index/noindex directive."""
    return ROBOTS_TXT


@app.get("/sitemap.xml")
@limiter.exempt
def sitemap_xml():
    """The indexable pages only: the article lists and the articles."""
    urls = "".join(
        f"<url><loc>{escape(absolute_url(path))}</loc>"
        f"<lastmod>{modified.isoformat()}</lastmod></url>\n"
        for path, modified in posts.sitemap_entries()
    )
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n",
        media_type="application/xml",
    )


@app.get("/health")
@limiter.exempt
def health_check(db: Session = Depends(get_db)):
    """Health check for the whole service (used by monitors).

    Pings the database with SELECT 1 so a dead DB shows up as 503 instead of a
    green health check in front of a broken service.
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unreachable"},
        )
    return {"status": "ok", "database": "ok"}


@app.get("/")
def home(request: Request):
    """Landing page: intro, projects, and skills.

    Indexable like the articles, so a search for the name finds the site, and
    crawlers follow its links on to the articles.
    """
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        headers=posts.INDEXABLE_HEADERS,
        context={
            "meta_title": "Jake Wang – Data Projects",
            "meta_description": (
                "Jake Wang's data projects: a live Tesla Model 3 cost tracker "
                "and how-to posts on customizing Kintone apps with JavaScript and CSS."
            ),
            "indexable": True,
        },
    )


@app.get("/mytesla/")
def tesla_dashboard(request: Request, db: Session = Depends(get_db)):
    """Tesla cost dashboard, rendered server-side in one DB session.

    tesla.get_dashboard() resolves every widget from one session, so the whole
    page costs twelve queries and no HTTP round trip. Every period is rendered;
    the period switch only changes which one is shown.
    """
    return templates.TemplateResponse(
        request=request,
        name="tesla.html",
        context={
            "meta_title": "Tesla Cost Tracker – Jake Wang",
            **tesla.get_dashboard(db),
        },
    )


# Tesla cost tracking (protected writes for charging, car expenses, odometer)
app.include_router(tesla.router, prefix="/api/tesla", tags=["Tesla"])
posts.register_routes(app)
