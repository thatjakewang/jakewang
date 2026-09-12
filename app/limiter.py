"""The shared rate limiter.

Lives in its own module rather than in app/main.py because the routers need to
decorate their endpoints with it (see app/routers/auth.py) and main.py imports
the routers — importing back the other way would be circular.

Per-client-IP cap on every endpoint (in-memory storage — fine for a
single-process deployment). /health and /robots.txt are exempted at their
definitions so monitors and crawlers are never throttled. The cap covers static
assets too, and one page load pulls fewer than 10 requests (CSS, JS, favicons,
then the dashboard's single API call), so it is set well above a browser's
burst rather than at the old API-only value.

Note: behind a reverse proxy, uvicorn needs --proxy-headers (and
--forwarded-allow-ips) so get_remote_address sees the real client IP.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["600/minute"],
    headers_enabled=True,
)

# Login is the one endpoint where an attacker gains something by retrying, so it
# gets a budget far below the site-wide one. Applied in app/routers/auth.py.
LOGIN_RATE_LIMIT = "5/minute"
