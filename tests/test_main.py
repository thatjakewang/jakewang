import asyncio
import json
from datetime import date
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from app import posts
from app.config import get_settings
from app.database import get_db
from app.main import CONTENT_SECURITY_POLICY, app
from app.templating import absolute_url


def request(method, path, headers=None):
    """Send one request straight to the ASGI app and collect the response.

    The test client that ships with FastAPI needs an HTTP package this project
    doesn't otherwise use, so this speaks ASGI directly instead.
    """
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "root_path": "",
        "headers": [(b"host", b"testserver")]
        + [(name.encode(), value.encode()) for name, value in (headers or {}).items()],
        "client": ("127.0.0.1", 1234), "server": ("testserver", 80),
    }
    response = SimpleNamespace(status=None, headers={}, body=b"")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            response.status = message["status"]
            response.headers = {k.decode().lower(): v.decode() for k, v in message["headers"]}
        elif message["type"] == "http.response.body":
            response.body += message.get("body", b"")

    try:
        asyncio.run(app(scope, receive, send))
    except Exception:
        # Starlette re-raises an unhandled error after sending the 500, so the
        # server can log it. Only swallow it once that response has gone out.
        if response.status is None:
            raise
    return response


class FakeDb:
    """Stands in for the request's session; fails every query when given an error."""

    def __init__(self, error=None):
        self.error = error

    def execute(self, statement, params=None):
        if self.error:
            raise self.error

    def rollback(self):
        pass


@pytest.fixture
def use_db():
    def install(db):
        app.dependency_overrides[get_db] = lambda: db

    yield install
    app.dependency_overrides.clear()


def test_pages_carry_the_security_headers():
    headers = request("GET", "/").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in headers["permissions-policy"]


def test_only_the_articles_are_indexable():
    assert request("GET", "/nope").headers["x-robots-tag"] == "noindex, nofollow"
    assert request("GET", "/static/css/style.css").headers["x-robots-tag"] == "noindex, nofollow"
    assert request("GET", "/").headers["x-robots-tag"] == "noindex, follow"
    assert request("GET", "/kintone/").headers["x-robots-tag"] == "all"
    assert request("GET", "/kintone/nope/").headers["x-robots-tag"] == "noindex, nofollow"


def test_pages_are_cached_briefly_and_static_files_for_a_year():
    assert request("GET", "/").headers["cache-control"] == "public, max-age=60"
    static = request("GET", "/static/css/style.css")
    assert static.headers["cache-control"] == "public, max-age=31536000"


@pytest.mark.parametrize("method, path, headers", [
    ("GET", "/", {"x-api-key": "anything"}),   # fetched with a personal key
    ("GET", "/nope", None),                    # not a 200
    ("GET", "/robots.txt", None),              # neither a page nor a static file
    ("POST", "/", None),                       # not a GET
])
def test_other_responses_are_not_marked_cacheable(method, path, headers):
    assert "cache-control" not in request(method, path, headers).headers


def test_head_answers_like_get_without_a_body():
    get, head = request("GET", "/"), request("HEAD", "/")
    assert head.status == 200
    assert head.body == b""
    assert head.headers["content-type"] == get.headers["content-type"]
    assert head.headers["content-length"] == str(len(get.body))
    assert head.headers["cache-control"] == get.headers["cache-control"]


def test_head_on_a_route_without_get_is_still_405():
    assert request("HEAD", "/api/tesla/odometer").status == 405


def test_missing_trailing_slash_redirects_permanently():
    response = request("GET", "/kintone")
    assert response.status == 308
    assert urlsplit(response.headers["location"]).path == "/kintone/"


def test_unknown_page_gets_the_html_error_page():
    response = request("GET", "/nope")
    assert response.status == 404
    assert response.headers["content-type"].startswith("text/html")
    assert b"Page Not Found" in response.body


def test_unknown_api_path_stays_json():
    response = request("GET", "/api/nope")
    assert response.status == 404
    assert json.loads(response.body) == {"detail": "Not Found"}


def test_status_codes_without_an_error_page_stay_json():
    response = request("POST", "/")
    assert response.status == 405
    assert json.loads(response.body) == {"detail": "Method Not Allowed"}


def test_unhandled_error_on_a_page_is_a_generic_html_500(use_db):
    use_db(FakeDb(error=RuntimeError("secret detail")))
    response = request("GET", "/mytesla/")
    assert response.status == 500
    assert response.headers["content-type"].startswith("text/html")
    assert b"Internal Server Error" in response.body
    assert b"secret detail" not in response.body
    assert response.headers["cache-control"] == "no-store"
    # The handler runs outside the header middleware and sets these itself.
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_unhandled_error_on_the_api_is_a_generic_json_500(use_db):
    use_db(FakeDb(error=RuntimeError("secret detail")))
    response = request(
        "DELETE", "/api/tesla/odometer/latest",
        {"x-api-key": get_settings().shortcut_api_key},
    )
    assert response.status == 500
    assert json.loads(response.body) == {"detail": "Internal Server Error"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_health_reports_ok_when_the_database_answers(use_db):
    use_db(FakeDb())
    response = request("GET", "/health")
    assert response.status == 200
    assert json.loads(response.body) == {"status": "ok", "database": "ok"}


def test_health_is_503_when_the_database_is_unreachable(use_db):
    use_db(FakeDb(error=ConnectionError("down")))
    response = request("GET", "/health")
    assert response.status == 503
    assert json.loads(response.body) == {"status": "degraded", "database": "unreachable"}


def test_robots_txt_blocks_ai_training_crawlers_but_not_search():
    response = request("GET", "/robots.txt")
    assert response.status == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.body.decode()
    blocked, _, everyone = text.partition("User-agent: *")
    assert "User-agent: GPTBot\n" in blocked and "Disallow: /\n" in blocked
    assert "OAI-SearchBot" not in text and "PerplexityBot" not in text
    assert "Allow: /\n" in everyone
    assert f"Sitemap: {absolute_url('/sitemap.xml')}\n" in everyone


def test_sitemap_lists_the_indexable_pages_with_escaped_urls(monkeypatch):
    monkeypatch.setattr(posts, "sitemap_entries", lambda: [
        ("/kintone/", date(2026, 11, 10)),
        ("/kintone/a&b/", date(2026, 11, 4)),
    ])
    response = request("GET", "/sitemap.xml")
    assert response.status == 200
    assert response.headers["content-type"] == "application/xml"
    xml = response.body.decode()
    assert (f"<url><loc>{absolute_url('/kintone/')}</loc>"
            "<lastmod>2026-11-10</lastmod></url>") in xml
    assert "/kintone/a&amp;b/</loc><lastmod>2026-11-04</lastmod>" in xml


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_are_not_served(path):
    assert request("GET", path).status == 404


def test_large_responses_are_compressed_on_request():
    response = request("GET", "/", {"accept-encoding": "gzip"})
    assert response.headers["content-encoding"] == "gzip"
    assert response.body[:2] == b"\x1f\x8b"
