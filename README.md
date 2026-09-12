# jakewang.dev

Personal project site and its backend, served as one app from one origin: the
pages at `/` and `/mytesla/`, rendered server-side from the database. The only
API is `/api/tesla/*`, and it is write-only — iPhone Shortcuts log records
there with an API key.

Not a traffic-facing site: there is no analytics, no sitemap/robots, and no SEO
metadata.

## Stack

- **FastAPI** — web framework (pages *and* API)
- **Jinja2** — server-rendered page shells
- **PostgreSQL** + **SQLAlchemy** — storage
- **uvicorn** — ASGI server

## Authentication

Two separate mechanisms, on purpose. They must not be merged.

| Client | What it is | Mechanism |
|--------|-----------|-----------|
| **Human**, in a browser | Reading private pages | Signed session cookie (`/login`) |
| **Machine**, headless | iPhone Shortcuts, automated collectors | `x-api-key` header |

An automated writer must never be pushed through the login form — that would
only mean teaching a script to POST one. Conversely a session cookie grants no
write access: `x-api-key` is still required for every POST.

There is exactly one user, so there is **no users table** and no registration.
The password lives in `.env` as an scrypt hash (`hashlib.scrypt`, standard
library) and the session is a signed cookie, so nothing is stored server-side.
CSRF is handled by `SameSite=Lax` rather than tokens: every form here is
same-origin, and a cross-site POST never carries the cookie. `POST /login` is
capped at 5/minute, far below the site-wide 600/minute.

Generate the two secrets and paste them into `.env`:

```bash
python -m app.auth
```

Guard a new private route by depending on `require_login`; add its path prefix to
`PRIVATE_PATH_PREFIXES` in `app/main.py` at the same time, or the generic
`/api/*` cache rule will mark its responses publicly cacheable:

```python
from app.auth import require_login

@router.get("/api/papers")
def list_papers(_=Depends(require_login)):
    ...
```

Signed-out requests are split by client, matching the error handling: a page
request gets a 303 to `/login?next=…`, an `/api/` request gets a JSON 401.

## Project Layout

```text
app/
  main.py          # FastAPI app: static mount, page routes, middleware, router mounting
  config.py        # pydantic-settings configuration (.env)
  database.py      # engine + per-request session
  dependencies.py  # x-api-key verification (machine clients)
  auth.py          # browser login: password hashing, session, require_login guard
  limiter.py       # the shared rate limiter (routers need it, so not in main.py)
  templating.py    # the Jinja environment + its globals (same reason)
  utils.py         # row serialization, response envelope, date helpers
  routers/         # auth pages, the Tesla writes, and the queries behind them
templates/         # Jinja page shells (base + home + dashboard + login + errors)
static/            # The JS/CSS the browser gets, plus favicons — no build step
tests/             # pytest suite (no real DB)
schema.sql         # reference DDL for rebuilding the database
```

The dashboard is rendered server-side: `/mytesla/` calls `get_dashboard()`,
which resolves all nine queries in one session, and Jinja prints the numbers
straight into the HTML. The page
ships no JavaScript of its own — the only script on the site is
`static/js/nav.js` for the mobile menu. Nothing needs a redeploy when new
records land, and nothing needs a second round trip either. It is KPI figures
and tables only; tests pin both the absence of a charting library and the
presence of real numbers in the served HTML.

The period switch (`This month` / `Last 90 days`) is a link to
`?period=trailing_90_days`, not a client-side toggle: `get_period_summary()`
already returns both windows in the same query.

## Environment Variables

All configuration is loaded via `pydantic-settings` from `.env` (or environment variables). Create a `.env` file with the following (defaults exist for some):

```env
DATABASE_URL=postgresql://user:password@host:port/dbname
SHORTCUT_API_KEY=your_api_key
SESSION_SECRET=your_session_secret          # signs the session cookie
ADMIN_PASSWORD_HASH=scrypt$<salt>$<hash>    # from `python -m app.auth`
SESSION_COOKIE_SECURE=true                  # set false for local http only
APP_TIMEZONE=Asia/Taipei
TESLA_ODOMETER_KM=21471
```

`SESSION_SECRET` and `ADMIN_PASSWORD_HASH` have no defaults — the app refuses to
boot without them rather than running on a guessable secret. `SESSION_MAX_AGE`
is optional and defaults to 14 days.

When developing locally over `http://`, set `SESSION_COOKIE_SECURE=false`;
otherwise the browser will not send the cookie back and login silently never
sticks.

## Setup & Run

```bash
python -m venv .venv          # Python version pinned in .python-version (3.14)
source .venv/bin/activate
pip install -r requirements.lock   # fully pinned; use requirements.txt for top-level only
uvicorn app.main:app --reload
```

The site is then at **http://localhost:8000** and the API under `/api/`.

Interactive API docs (`/docs`, `/redoc`, `/openapi.json`) are disabled on purpose —
see `app/main.py`. Use the endpoint tables below as the reference.

Dependencies: `requirements.txt` and `requirements-dev.txt` list top-level packages;
the `.lock` files beside them are the fully pinned sets that actually get installed.
Re-generate both, in this order, after changing either:

```bash
uv pip compile requirements.txt -o requirements.lock
uv pip compile requirements-dev.txt -c requirements.lock -o requirements-dev.lock
```

The `-c` flag constrains every shared package to the version `requirements.lock`
deploys, so the only difference between the two locks is the test-only tree —
tests never run against a different dependency set than production.

### Frontend assets

There is no build step and no Node.js anywhere: `static/` holds the actual
JavaScript and CSS the browser receives, and editing a file there is the whole
deployment. esbuild used to minify sources from a `frontend/` directory into
committed `.min.*` files; that saved ~3KB gzipped per first visit and cost a
rebuild-and-commit step on every change, so it was dropped along with Chart.js.
A test asserts no `.min.*` URL comes back, in case a bundler is ever
reintroduced without the toolchain to keep it honest.

Assets are served with a one-year `Cache-Control` and a `?v=<mtime>`
cache-buster, so an edit reaches browsers on the next page load.

## Tests

```bash
pip install -r requirements-dev.lock
python -m pytest tests/
```

Tests never touch a real database — DB sessions are faked.
GitHub Actions (`.github/workflows/ci.yml`) runs the suite on every push and pull request.

## Database Schema & Migrations

`schema.sql` is the reference DDL for every table the API uses. Rebuild an empty
database with:

```bash
psql "$DATABASE_URL" -f schema.sql
```

Schema changes are delivered as migration scripts in `migrations/`.
The workflow:

1. Deploy code that works with both the old and the new schema.
2. Run the script on the production server. `DATABASE_URL` lives in `.env`,
   which the app reads at startup but never exports into the shell — activating
   the venv does *not* set it. Pull it out with the same parser the app uses;
   `source .env` breaks on any line that is not exactly `KEY=value`:

   ```bash
   cd /var/www/main-site
   source .venv/bin/activate
   export DATABASE_URL="$(python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['DATABASE_URL'])")"
   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/<script_name>.sql
   ```

3. Update `schema.sql` to match, then delete the script — git history keeps the
   record. Applied so far: `add_tesla_recent_columns.py` (2026-06-03),
   `add_odometer_readings.py` (2026-06), `drop_payment_method.py` (by 2026-06-28),
   `drop_daily_expenses.py` (2026-08-28),
   `add_data_integrity_constraints.sql` (by 2026-08-29).

No migrations are pending.

To check whether a constraint-adding migration has already been applied, list
what the tables actually carry:

```bash
psql "$DATABASE_URL" -c "SELECT conrelid::regclass AS tbl, conname
  FROM pg_constraint WHERE contype = 'c' ORDER BY 1, 2;"
```

## Endpoints

**The API is write-only.** It exists so iPhone Shortcuts can log records; the
dashboard reads nothing over HTTP, because it is rendered server-side from the
same queries. Those read endpoints existed while the page fetched its own data
and were removed once nothing called them — the queries live on as plain
functions in `app/routers/tesla.py`, called by `get_dashboard()`. A test pins
that `/api/` stays POST-only.

### Public

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (pings the DB; 503 if unreachable) |
| GET | `/login` | Sign-in page (303 to `?next=` if already signed in) |
| POST | `/login` | Form login — `password`, optional `next`. Rate limited 5/min |
| POST | `/logout` | Clear the session (POST only, so no link can sign you out) |
| GET | `/robots.txt` | Allows search engines, blocks the AI crawlers |

> Note: all tables carry an `id` (SERIAL) column, which is what the writes return.

> Rate limiting: everything except `/health` is capped at 600 requests/minute per
> client IP (in-memory, via slowapi). The cap covers pages and static assets too,
> and one page load pulls fewer than 10 requests. Behind a reverse proxy, run uvicorn with
> `--proxy-headers` (and `--forwarded-allow-ips`) so the real client IP is used.

### Protected (Header: `x-api-key`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tesla/charging-records` | Create a charging record |
| POST | `/api/tesla/car-expenses` | Create a car expense |
| POST | `/api/tesla/odometer` | Log a total-odometer reading |

### POST `/api/tesla/charging-records`

```json
{
  "charge_date": "2026-05-09",
  "provider": "Tesla Supercharger",
  "amount": 150,
  "kwh": 30.5
}
```

Response includes `id`:

```json
{
  "status": "success",
  "message": "Charging record created",
  "data": { "id": 123, "charge_date": "2026-05-09", "provider": "...", "amount": 150, "kwh": 30.5 }
}
```

### POST `/api/tesla/car-expenses`

```json
{
  "date": "2026-05-09",
  "item": "Insurance",
  "amount": 25000
}
```

Response includes `id`:

```json
{
  "status": "success",
  "message": "Car expense created",
  "data": { "id": 45, "date": "2026-05-09", "item": "Insurance", "amount": 25000 }
}
```

### POST `/api/tesla/odometer`

```json
{
  "reading_km": 23120,
  "reading_date": "2026-06-09"
}
```

`reading_date` is optional (defaults to today). The dashboard's cost-per-km
automatically follows the latest reading.

## Pages

| Path | Description |
|------|-------------|
| `/` | Home — intro, project cards, skills |
| `/mytesla/` | Tesla cost dashboard, server-rendered (`?period=trailing_90_days` for the 90-day window) |
| `/login` | Sign-in (see Authentication above) |

## Caching

`Cache-Control` is set by one middleware in `app/main.py`, by kind of response:

| Kind | max-age | Why |
|------|---------|-----|
| `/static/*` | 1 year | URLs carry a `?v=<mtime>` cache-buster, so this is safe |
| pages | 60s | The dashboard's numbers are rendered into them |
| private paths | `no-store` | Belong to one signed-in user |

Only `GET`s that return 200 get a window at all, so the API's writes never do.
Requests carrying `x-api-key` are never marked publicly cacheable either, nor
are responses that set a session cookie, nor anything matching
`PRIVATE_PATH_PREFIXES` in `app/main.py`.

There is **no CORS layer**: pages and API share an origin, so nothing cross-origin
happens. A test pins this, since adding CORS back would quietly re-open the API to
other sites.
