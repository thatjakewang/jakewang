"""Main FastAPI application entrypoint.

Serves the whole site from one origin: the HTML pages (Jinja templates in
templates/, assets in static/) and the JSON API the dashboard fetches from
(/api/tesla/*). Same-origin means no CORS is involved at all.

The real business logic lives in the routers; the page routes below only
pick a template — every number on the dashboard is fetched client-side.
"""

from datetime import timedelta
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.auth import LoginRequired
from app.config import get_settings
from app.database import get_db
from app.limiter import limiter
from app.routers import auth, tesla

# The Jinja environment and the rate limiter live in their own modules so the
# routers can use them without importing this one back. static_url is re-exported
# here because it was defined here historically.
from app.templating import STATIC_DIR, static_url, templates  # noqa: F401

settings = get_settings()

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

# Browser login sessions: a signed cookie, no server-side session store. Lax
# is what stands in for CSRF tokens here — a cross-site POST never carries the
# cookie, and every form on this site is same-origin. https_only comes from
# config because a local http dev server would otherwise never see the cookie
# come back. See app/auth.py for the rest of the login story.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="session",
    max_age=settings.session_max_age,
    same_site="lax",
    https_only=settings.session_cookie_secure,
)

# Rate limiting: configured in app/limiter.py (the routers need it too).
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

# Paths whose responses belong to the signed-in user alone: they get no-store
# instead of any public window. Add every private prefix here at the same time
# as the route that serves it — a private page that only matched the generic
# page rule below would be handed to a shared proxy.
PRIVATE_PATH_PREFIXES = ("/login", "/logout")

# Status codes that get the HTML error page, and the line it shows. Anything
# not listed here stays JSON, whatever the client is.
ERROR_PAGES = {404: "Page Not Found", 500: "Internal Server Error"}


def is_private_path(path: str) -> bool:
    """True for paths served only to a logged-in user (never publicly cacheable)."""
    return any(
        path == prefix or path.startswith(f"{prefix}/")
        for prefix in PRIVATE_PATH_PREFIXES
    )


@app.middleware("http")
async def add_response_headers(request: Request, call_next):
    """Baseline security headers on everything, plus per-kind Cache-Control.

    setdefault() throughout, so nginx can override any of these without a
    code change. Requests carrying x-api-key are never marked publicly
    cacheable, since those responses are fetched with a personal key; neither
    are private paths, nor anything that just issued a session cookie.
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

    path = request.url.path
    if is_private_path(path):
        response.headers.setdefault("Cache-Control", "private, no-store")
    elif (
        request.method == "GET"
        and response.status_code == 200
        and "x-api-key" not in request.headers
        # SessionMiddleware sits inside this one, so a Set-Cookie is already on
        # the response by now: whatever it is, it is not shared-cacheable.
        and "set-cookie" not in response.headers
    ):
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


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, exc: LoginRequired):
    """Send a signed-out browser to the login page, remembering where it wanted to go.

    require_login raises this instead of an HTTPException because
    html_error_handler above would turn a 303 into a JSON body and drop the
    Location header with it.
    """
    return RedirectResponse(
        f"/login?{urlencode({'next': exc.next_path})}", status_code=303
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


def dashboard_payload(db: Session = Depends(get_db)) -> dict:
    """Every number the dashboard page shows, from one session.

    A dependency rather than a direct call so the page can be rendered against
    a canned payload in tests without also faking nine queries.
    """
    return tesla.get_dashboard(db)


@app.get("/mytesla/")
def tesla_dashboard(
    request: Request,
    period: str = "current_month",
    data: dict = Depends(dashboard_payload),
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
            **data,
        },
    )


# Browser login/logout. No prefix: these are site-level pages, not API endpoints.
app.include_router(auth.router, tags=["Auth"])

# Tesla cost tracking (public stats + protected writes for charging/car expenses)
app.include_router(tesla.router, prefix="/api/tesla", tags=["Tesla"])
