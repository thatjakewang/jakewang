"""HTTP-level tests for the API half: health, api-key auth, cache headers, gzip,
rate limiting. The HTML pages are covered in test_pages.py, and browser login in
test_auth.py.

All DB access goes through FakeSession — no real database is involved.
TestRateLimit stays last in the file: it deliberately exhausts the budget
for one path, and the limiter's in-memory window spans the whole test run.
"""

from datetime import date

import pytest

from app.main import app
from tests.conftest import TEST_API_KEY, TEST_PASSWORD, FakeResult, FakeSession


class TestHealth:
    def test_health_ok_when_db_reachable(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok"}

    def test_health_503_when_db_down(self, client_for):
        client = client_for(FakeSession(execute_error=RuntimeError("connection refused")))
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["database"] == "unreachable"



class TestAuth:
    """Every protected endpoint is a POST, so the key check is pinned on one of them."""

    PROTECTED_PATH = "/api/tesla/car-expenses"
    PAYLOAD = {"date": "2026-07-06", "item": "Insurance", "amount": 25000}

    def test_missing_api_key_is_401_not_422(self, client):
        response = client.post(self.PROTECTED_PATH, json=self.PAYLOAD)
        assert response.status_code == 401

    def test_wrong_api_key_is_401(self, client):
        response = client.post(
            self.PROTECTED_PATH, json=self.PAYLOAD, headers={"x-api-key": "nope"}
        )
        assert response.status_code == 401

    def test_missing_key_beats_invalid_body(self, client):
        # Auth runs before payload validation: a bad body still yields 401, not 422.
        response = client.post(self.PROTECTED_PATH, json={"nonsense": True})
        assert response.status_code == 401

    def test_correct_key_reaches_handler(self, client_for):
        # The INSERT ... RETURNING id is the single query the handler runs.
        session = FakeSession(results=[FakeResult(rows=[{"id": 1}])])
        client = client_for(session)
        response = client.post(
            self.PROTECTED_PATH, json=self.PAYLOAD, headers={"x-api-key": TEST_API_KEY}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["data"]["id"] == 1


class TestApiKeyIsIndependentOfLogin:
    """The two halves of auth must never become entangled.

    Browser login (test_auth.py) exists for private pages; the write endpoints
    are driven by iPhone Shortcuts and, later, an automated collector. Putting
    those behind the session would mean teaching a script to POST a login form.
    """

    PROTECTED_PATH = "/api/tesla/car-expenses"
    PAYLOAD = {"date": "2026-07-06", "item": "Insurance", "amount": 25000}

    def test_write_succeeds_with_no_session_cookie(self, client_for):
        session = FakeSession(results=[FakeResult(rows=[{"id": 2}])])
        client = client_for(session)
        assert "session" not in client.cookies
        response = client.post(
            self.PROTECTED_PATH, json=self.PAYLOAD, headers={"x-api-key": TEST_API_KEY}
        )
        assert response.status_code == 200

    def test_a_session_alone_does_not_authorize_a_write(self, client_for):
        """Being signed in must not silently grant the API key's privileges."""
        client = client_for(FakeSession())
        assert client.post("/login", data={"password": TEST_PASSWORD}).status_code == 200
        response = client.post(self.PROTECTED_PATH, json=self.PAYLOAD)
        assert response.status_code == 401


def test_the_api_is_write_only():
    """Every Tesla route is a POST from iPhone Shortcuts. The read endpoints
    went when the dashboard stopped fetching itself — a GET reappearing here is
    an endpoint nothing asked for, and it would need a cache rule of its own.

    Asserted against the router rather than app.routes: test_auth mounts its
    own /api/ route on the shared app to exercise the login guard.
    """
    from app.routers.tesla import router

    assert {
        (route.path, method)
        for route in router.routes
        for method in route.methods - {"HEAD", "OPTIONS"}
    } == {
        ("/charging-records", "POST"),
        ("/car-expenses", "POST"),
        ("/odometer", "POST"),
    }


class TestCacheHeaders:
    def test_api_writes_are_never_cacheable(self, client_for):
        """The API is write-only now, and a POST result is nobody else's to
        reuse — no public window may appear on one."""
        response = client_for(FakeSession(results=[FakeResult(rows=[{"id": 1}])])).post(
            "/api/tesla/odometer",
            headers={"x-api-key": TEST_API_KEY},
            json={"reading_km": 24500},
        )
        assert response.status_code == 200
        assert "Cache-Control" not in response.headers

    def test_health_is_not_cacheable(self, client):
        response = client.get("/health")
        assert "Cache-Control" not in response.headers

    def test_keyed_request_is_not_publicly_cacheable(self, client):
        """A response fetched with a personal key is not shared-cacheable, even
        when the path itself would otherwise get a public window."""
        response = client.get("/", headers={"x-api-key": TEST_API_KEY})
        assert response.status_code == 200
        assert "Cache-Control" not in response.headers

    def test_error_responses_are_not_cacheable(self, client):
        response = client.get("/api/tesla/nope")
        assert response.status_code == 404
        assert "Cache-Control" not in response.headers


class TestNoCORS:
    """The page and the API share an origin, so no CORS layer should exist.

    If one gets added back, it would silently re-open the API to other
    origins — the thing merging the two services removed. Uses /health
    (limiter-exempt) so these can never eat rate-limit budget.
    """

    def test_no_cors_headers_for_any_origin(self, client):
        for origin in ("https://jakewang.dev", "https://evil.example"):
            response = client.get("/health", headers={"origin": origin})
            assert "access-control-allow-origin" not in response.headers, origin

    def test_preflight_is_not_answered(self, client):
        response = client.options("/api/tesla/odometer", headers={
            "origin": "https://jakewang.dev",
            "access-control-request-method": "POST",
        })
        assert "access-control-allow-origin" not in response.headers


class TestGZip:
    def test_large_responses_are_compressed(self, client):
        """The dashboard page is the biggest thing the site serves now that the
        API is write-only — several KB of rendered HTML, well past the 500-byte
        minimum."""
        response = client.get("/mytesla/", headers={"accept-encoding": "gzip"})
        assert response.headers.get("content-encoding") == "gzip"
        # httpx transparently decompresses, so the body is readable here
        assert "Tesla Cost Tracker" in response.text

    def test_small_responses_stay_uncompressed(self, client):
        response = client.get("/health", headers={"accept-encoding": "gzip"})
        assert "content-encoding" not in response.headers


class TestRateLimit:
    """The limiter's window is in-memory and per (client IP, endpoint), so a
    burst here would otherwise starve every later test that shares the path.
    `spent_budget` resets it, which also frees these from running last.
    """

    # 600/minute now, since the cap also covers page loads and static assets.
    BURST = 605

    @pytest.fixture
    def spent_budget(self):
        yield
        app.state.limiter.reset()

    def test_burst_beyond_limit_returns_429(self, client, spent_budget):
        path = "/"  # cheap: the home page touches no database
        statuses = [client.get(path).status_code for _ in range(self.BURST)]
        assert 429 in statuses
        # Everything before the first 429 succeeded normally
        assert statuses[0] == 200

    def test_health_is_exempt(self, client, spent_budget):
        statuses = {client.get("/health").status_code for _ in range(self.BURST)}
        assert statuses == {200}
