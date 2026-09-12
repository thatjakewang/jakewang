"""Main FastAPI application entrypoint.

Serves the whole site from one origin: the HTML pages (Jinja templates in
templates/, assets in static/) and the write-only API at /api/tesla/*, which
exists for iPhone Shortcuts. Same-origin means no CORS is involved at all.

Assembly lives here — middleware, cache policy, the rate limiter, error pages,
and the page routes. The queries are in app/tesla.py: /mytesla/ calls
get_dashboard() and hands the result straight to the template, so the numbers
are rendered into the HTML rather than fetched by the browser.
"""

from datetime import timedelta

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import get_db
from app import tesla

from app.templating import STATIC_DIR, templates

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

# Per-client-IP cap on every endpoint (in-memory — fine for a single-process
# deployment). /health and /robots.txt are exempted at their definitions below,
# so monitors and crawlers are never throttled. The cap covers pages and static
# assets too, and one page load pulls fewer than 10 requests, so it sits well
# above a browser's burst rather than at an API-only value.
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


@app.middleware("http")
async def add_response_headers(request: Request, call_next):
    """Baseline security headers on everything, plus per-kind Cache-Control.

    setdefault() throughout, so nginx can override any of these without a
    code change. Requests carrying x-api-key are never marked publicly
    cacheable, since those responses are fetched with a personal key, and
    neither is anything that set a cookie on its way out.
    """
    response = await call_next(request)

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    # Disallow embedding the site in iframes (clickjacking protection)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    # Keep the whole site out of search indexes. As a header rather than only a
    # <meta> tag, this also covers the JSON API and static assets, which cannot
    # carry meta tags. robots.txt deliberately still allows search engines to
    # fetch pages — a crawler that is blocked can never read this directive, and
    # already-indexed URLs would linger instead of being dropped.
    response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")

    if (
        request.method == "GET"
        and response.status_code == 200
        and "x-api-key" not in request.headers
        # Nothing sets a cookie today, but a response that ever does is by
        # definition not shared-cacheable — keep the guard ahead of the need.
        and "set-cookie" not in response.headers
    ):
        path = request.url.path
        if path.startswith("/static/"):
            max_age = STATIC_CACHE_MAX_AGE
        elif path in ("/", "/mytesla/"):
            max_age = PAGE_CACHE_MAX_AGE
        else:
            max_age = None
        if max_age is not None:
            response.headers.setdefault("Cache-Control", f"public, max-age={max_age}")

    return response


@app.exception_handler(StarletteHTTPException)
async def html_error_handler(request: Request, exc: StarletteHTTPException):
    """Friendly HTML error pages for page requests; JSON for the API.

    Without this, a mistyped URL would return FastAPI's bare JSON detail
    instead of the site's 404 page.
    """
    if request.url.path.startswith("/api/") or exc.status_code not in ERROR_PAGES:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return templates.TemplateResponse(
        request=request,
        name="error.html",
        status_code=exc.status_code,
        context={"code": exc.status_code, "message": ERROR_PAGES[exc.status_code]},
    )


# Crawlers that exist to collect training/retrieval corpora. Blocked by name,
# because the blanket "Disallow: /" that would stop them also stops the search
# engines from ever reading the noindex directive above.
AI_CRAWLERS = (
    "GPTBot",              # OpenAI, training
    "OAI-SearchBot",       # OpenAI, search index
    "ChatGPT-User",        # OpenAI, user-triggered fetch
    "ClaudeBot",           # Anthropic
    "Claude-Web",
    "anthropic-ai",
    "Google-Extended",     # Google, Gemini training (separate from Googlebot)
    "Applebot-Extended",   # Apple, training (separate from Applebot)
    "CCBot",               # Common Crawl, feeds many training sets
    "PerplexityBot",
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
    "# Personal project site. It wants no search traffic, and does not permit\n"
    "# its content to be used for AI training or retrieval.\n"
    "#\n"
    "# Search engines may crawl: every response carries X-Robots-Tag: noindex,\n"
    "# and a blocked crawler could never read that. Crawling is how these pages\n"
    "# get dropped from the index.\n"
    "\n"
    + "".join(f"User-agent: {bot}\n" for bot in AI_CRAWLERS)
    + "Disallow: /\n"
    "\n"
    "User-agent: *\n"
    "Allow: /\n"
)


@app.get("/robots.txt", response_class=PlainTextResponse)
@limiter.exempt
def robots_txt():
    """Block the AI crawlers by name; let search engines through to the noindex."""
    return ROBOTS_TXT


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
    """Landing page: intro, projects, and skills."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"meta_title": "Jake Wang – Data Projects"},
    )


# The two windows the dashboard's period switch offers, named as
# get_period_summary() keys them.
DASHBOARD_PERIODS = ("current_month", "trailing_90_days")


@app.get("/mytesla/")
def tesla_dashboard(
    request: Request,
    period: str = "current_month",
    db: Session = Depends(get_db),
):
    """Tesla cost dashboard, rendered server-side in one DB session.

    tesla.get_dashboard() resolves every widget from one session, so the whole
    page costs nine queries and no HTTP round trip. An unknown ?period falls
    back to the current month rather than 404ing: it is a display toggle, not a
    resource.
    """
    if period not in DASHBOARD_PERIODS:
        period = DASHBOARD_PERIODS[0]
    return templates.TemplateResponse(
        request=request,
        name="tesla.html",
        context={
            "meta_title": "Tesla Cost Tracker – Jake Wang",
            "period_key": period,
            **tesla.get_dashboard(db),
        },
    )


# Tesla cost tracking (public stats + protected writes for charging/car expenses)
app.include_router(tesla.router, prefix="/api/tesla", tags=["Tesla"])
