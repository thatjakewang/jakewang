# jakewang.dev

Personal project site and its backend, served as one app from one origin: the
home page at `/`, the Tesla dashboard at `/mytesla/` (rendered server-side from
the database), and Markdown articles under `/kintone/`. The only API is
`/api/tesla/*`, and it is write-only — iPhone Shortcuts log records there with
an API key.

Mostly not a traffic-facing site: there is no analytics and no sitemap. Every
response is `noindex` except the articles under `/kintone/`, which search
engines may index. `/robots.txt` exists only to turn the AI crawlers away.

## Stack

- **FastAPI** — web framework (pages *and* API)
- **Jinja2** — server-rendered page shells
- **PostgreSQL** + **SQLAlchemy** — storage
- **uvicorn** — ASGI server
- **python-frontmatter** + **Markdown** + **Pygments** — the articles

## Authentication

One credential, one direction: `x-api-key` on the write endpoints, used
by iPhone Shortcuts. Everything the site serves to a browser is public, so
there is no login, no session, and no user table.

There used to be a browser login — a signed session cookie and an scrypt
password hash — built for private pages that were never added. It guarded
nothing, so it went. Reintroducing it means bringing back `itsdangerous`,
`python-multipart`, a session middleware, and two required secrets in `.env`;
worth knowing before adding a page that needs it.

```env
SHORTCUT_API_KEY=<the key your Shortcuts send>
```

A request without the header — or with the wrong one — gets a JSON 401 before
the payload is even validated.

## Project Layout

```text
app/
  main.py          # FastAPI app: static mount, page routes, middleware, rate limiter
  config.py        # pydantic-settings configuration (.env)
  database.py      # engine + per-request session
  dependencies.py  # x-api-key verification (the only credential)
  templating.py    # the Jinja environment, its globals, and the number filters
  utils.py         # row serialization, response envelope, date helpers
  tesla.py         # the writes and their undo, and the queries behind the dashboard
  posts.py         # Markdown articles: parsing, validation, category routes
posts/             # the articles, one folder per category (posts/kintone/*.md)
templates/         # Jinja page shells (base, home, dashboard, article list + page, error)
static/            # The JS/CSS the browser gets, plus favicons — no build step
tests/             # pytest: period maths, write rules, article parsing
schema.sql         # reference DDL for rebuilding the database
```

The dashboard is rendered server-side: `/mytesla/` calls `get_dashboard()`,
which resolves eleven queries in one session, and Jinja prints the numbers
straight into the HTML. The page
ships one small script of its own, `static/js/tesla.js` for the period
switch; the only other script on the site is `static/js/nav.js` for the
mobile menu. Nothing needs a redeploy when new
records land, and nothing needs a second round trip either. It is KPI figures
and tables only.

The period switch (`This month` / `Last 90 days` / `Last 12 months`) is a
client-side toggle: `get_period_summary()` queries every window up front (plus
the prior month for the comparison), all of them are rendered, and
`static/js/tesla.js` only shows the selected one. The URL never changes.

A period's total cost covers its calendar window. Its distance and per-km
figures cover the span between two odometer readings — the last one before the
window and the last one inside it — and count only the costs recorded in that
span, so numerator and denominator always describe the same stretch of driving.
The panel prints the reading dates it used.

### Articles

An article is a Markdown file under `posts/<category>/` with `title`, `date`
and `category` in its front matter; `slug` and `tags` are optional. Categories
are declared in `CATEGORIES` in `app/posts.py` (currently just `kintone`), and
each gets a list page and one page per article. A file that fails validation is
logged and skipped rather than breaking the list. Files are re-read when they
change, so publishing is `git pull` — no restart.

The article list and article pages are the only indexable responses: their
routes send `X-Robots-Tag: all` and pass `indexable` to the template, which
drops the `noindex` meta tag. Everything else, including a 404 under
`/kintone/`, keeps the site-wide `noindex, nofollow`.

## Environment Variables

All configuration is loaded via `pydantic-settings` from `.env` (or environment variables). Create a `.env` file with the following (defaults exist for some):

```env
DATABASE_URL=postgresql://user:password@host:port/dbname
SHORTCUT_API_KEY=your_api_key
APP_TIMEZONE=Asia/Taipei
```

`DATABASE_URL` and `SHORTCUT_API_KEY` have no defaults — a deployment that
forgot either fails to boot instead of running against the wrong database or
an open write API. `APP_TIMEZONE` falls back to the value above.

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

Dependencies: `requirements.txt` lists the ten packages this app actually
chose; `requirements.lock` is the fully pinned set — those ten plus everything
they pull in — and is what gets installed. Regenerate it after changing a pin:

```bash
uv pip compile requirements.txt -o requirements.lock
```

There is a small test suite and no CI: `git push` runs nothing. Run the tests
and the app locally before deploying:

```bash
pip install -r requirements-dev.txt   # pytest; local only, never on the server
pytest tests
```

The tests need no database — they cover the period date windows, the odometer
span, the write rules, and article parsing, all without a query.

### Frontend assets

There is no build step and no Node.js anywhere: `static/` holds the actual
JavaScript and CSS the browser receives, and editing a file there is the whole
deployment. esbuild used to minify sources from a `frontend/` directory into
committed `.min.*` files; that saved ~3KB gzipped per first visit and cost a
rebuild-and-commit step on every change, so it was dropped along with Chart.js.

Assets are served with a one-year `Cache-Control` and a `?v=<mtime>`
cache-buster, so an edit reaches browsers on the next page load.

## Deployment

The site lives at `/var/www/main-site`, served by uvicorn behind nginx and
managed by systemd. uvicorn needs `--proxy-headers` (and
`--forwarded-allow-ips`), or the rate limiter counts every request as coming
from the proxy's IP.

```bash
cd /var/www/main-site
git pull
source .venv/bin/activate
pip install -r requirements.lock   # only when the lock changed
sudo systemctl restart main-site
```

Then verify, in this order:

```bash
systemctl status main-site --no-pager
curl -fsS https://jakewang.dev/health    # {"status":"ok","database":"ok"}
```

...and open `/mytesla/` in a browser. The dashboard is rendered server-side, so
a missing number means a query that failed while rendering — there is no
client-side fetch to inspect in the console, and the page is either right or
visibly wrong. Finish by logging one record from Shortcuts, which is the only
thing that writes.

To roll back, check out the previous commit and restart; every commit is
deployable on its own.

What this deployment does **not** need:

- **A build step.** `static/` is served exactly as committed — no Node, no npm,
  no bundler. Editing a file under `static/` is the whole frontend deployment.
- **More than two secrets.** `.env` needs `DATABASE_URL` and
  `SHORTCUT_API_KEY`. It is read once at startup, so editing it means a restart.

One thing to watch: **`pip install` never removes anything.** When a dependency
leaves `requirements.lock`, the old package stays in the venv, and the
environment quietly drifts from the file that is supposed to describe it:

```bash
uv pip sync requirements.lock      # or: pip uninstall <package>
```

`itsdangerous` and `python-multipart` left with the browser login and are the
most recent case — harmless if they linger, but the venv no longer matches the
lock until they go.

## Database Schema & Migrations

`schema.sql` is the reference DDL for every table the API uses. Rebuild an empty
database with:

```bash
psql "$DATABASE_URL" -f schema.sql
```

Schema changes are delivered as migration scripts in `migrations/`, a
directory that only exists while a script is pending. The workflow:

1. Deploy code that works with both the old and the new schema (see
   [Deployment](#deployment)).
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

**The API is write-only.** It exists so iPhone Shortcuts can log records (and
take the last one back); the
dashboard reads nothing over HTTP, because it is rendered server-side from the
same queries. Those read endpoints existed while the page fetched its own data
and were removed once nothing called them — the queries live on as plain
functions in `app/tesla.py`, called by `get_dashboard()`.

### Public

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (pings the DB; 503 if unreachable) |
| GET | `/robots.txt` | Allows search engines, blocks the AI crawlers |

> Note: all tables carry an `id` (SERIAL) column, which is what the writes return.

> Rate limiting: pages and the API are capped at 600 requests/minute per client
> IP (in-memory, via slowapi); `/health` and `/robots.txt` are exempt. Static
> assets and 404s are not counted — slowapi only limits requests that match a
> route — so throttle those in nginx if it ever matters. Behind a reverse proxy,
> run uvicorn with `--proxy-headers` (and `--forwarded-allow-ips`) so the real
> client IP is used.

### Protected (Header: `x-api-key`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tesla/charging-records` | Create a charging record |
| POST | `/api/tesla/car-expenses` | Create a car expense |
| POST | `/api/tesla/odometer` | Log a total-odometer reading |
| DELETE | `/api/tesla/charging-records/latest` | Delete the last charging record logged |
| DELETE | `/api/tesla/car-expenses/latest` | Delete the last car expense logged |
| DELETE | `/api/tesla/odometer/latest` | Delete the last odometer reading logged |

**Retries are safe.** A `POST` identical to a record created in the last two
minutes returns that record's `id` and inserts nothing, so a Shortcut that
timed out and ran again does not log the charge twice. Two genuinely identical
records (the same toll twice) have to be logged more than two minutes apart.

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

An odometer only counts up, so a reading lower than an earlier-dated one, or
higher than a later-dated one, is refused with a 422 — it is a typo, and one
bad reading would skew every per-km figure.

### DELETE `/api/tesla/<resource>/latest`

Removes the most recently *inserted* record of that kind (highest `id`,
whatever date it carries) and returns it, so the Shortcut can show what went.
404 when the table is empty. This is the undo for a mistyped entry; unlike the
writes it is not retry-safe — calling it twice deletes two records.

```json
{
  "status": "success",
  "message": "Odometer reading deleted",
  "data": { "id": 88, "reading_km": 2312, "reading_date": "2026-06-09" }
}
```

## Pages

| Path | Description |
|------|-------------|
| `/` | Home — intro, project cards, skills |
| `/mytesla/` | Tesla cost dashboard, server-rendered |
| `/kintone/` | Kintone articles, newest first |
| `/kintone/<slug>/` | One article |

## Caching

`Cache-Control` is set by one middleware in `app/main.py`, by kind of response:

| Kind | max-age | Why |
|------|---------|-----|
| `/static/*` | 1 year | URLs carry a `?v=<mtime>` cache-buster, so this is safe |
| HTML pages | 60s | The dashboard's numbers are rendered into them; articles follow the same window |

Only `GET`s that return 200 get a window at all, so the API's writes never do.
Requests carrying `x-api-key` are never marked publicly cacheable either, nor
is any response that sets a cookie. Nothing on the site is private any more, so
there is no `no-store` tier left.

The same middleware sets the security headers, including a
`Content-Security-Policy` that only allows same-origin scripts, styles and
images. An article that embeds an image or script from another host needs that
policy widened in `app/main.py`.

There is **no CORS layer**: pages and API share an origin, so nothing
cross-origin happens. Adding one back would quietly re-open the write API to
other sites — don't, unless something genuinely needs to call it from elsewhere.
