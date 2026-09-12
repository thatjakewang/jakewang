"""The browser-login half of auth: hashing, the login flow, and the route guard.

The x-api-key half (iPhone Shortcuts and any automated collector) is covered in
test_endpoints.py::TestAuth, and the two must stay independent — see
test_endpoints.py::TestApiKeyIsIndependentOfLogin.

Protected routes are registered on the real app below rather than on a stub, so
these tests exercise the actual middleware stack: SessionMiddleware, the
LoginRequired handler, and the Cache-Control rules in add_response_headers.
"""

import pytest
from fastapi import Depends

from app.auth import (
    LoginRequired,
    hash_password,
    is_logged_in,
    require_login,
    safe_next,
    verify_password,
)
from app.limiter import limiter
from app.main import app, is_private_path
from tests.conftest import TEST_PASSWORD

PRIVATE_PAGE = "/testonly-private-page"
PRIVATE_API = "/api/testonly-private"


@app.get(PRIVATE_PAGE)
def _private_page(_=Depends(require_login)):
    return {"secret": "page"}


@app.get(PRIVATE_API)
def _private_api(_=Depends(require_login)):
    return {"secret": "api"}


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Login is capped at 5/minute and the limiter's window spans the whole run.

    Reset on both sides: before, so the tests here cannot starve each other; and
    after, so TestLoginRateLimit does not leave an exhausted budget behind for
    the other test modules (test_endpoints.py signs in too).
    """
    limiter.reset()
    yield
    limiter.reset()


class TestPasswordHashing:
    def test_hash_verifies_against_its_own_password(self):
        assert verify_password("hunter2", hash_password("hunter2"))

    def test_wrong_password_fails(self):
        assert not verify_password("hunter3", hash_password("hunter2"))

    def test_two_hashes_of_one_password_differ(self):
        """Each hash carries its own salt, so a leak of one says nothing about the other."""
        assert hash_password("hunter2") != hash_password("hunter2")

    @pytest.mark.parametrize(
        "stored",
        ["", "not-a-hash", "scrypt$only-two-parts", "scrypt$zz$zz",
         "bcrypt$aabb$ccdd", "scrypt$$", "$$"],
    )
    def test_broken_stored_hash_denies_instead_of_raising(self, stored):
        # A corrupted ADMIN_PASSWORD_HASH must lock the door, not 500 and leak why.
        assert verify_password("hunter2", stored) is False


class TestSafeNext:
    @pytest.mark.parametrize("target", ["/", "/mytesla/", "/papers/?tag=ml"])
    def test_same_site_paths_pass_through(self, target):
        assert safe_next(target) == target

    @pytest.mark.parametrize(
        "target",
        ["//evil.com", "/\\evil.com", "https://evil.com", "http://evil.com",
         "evil.com", "", None],
    )
    def test_offsite_targets_fall_back_to_root(self, target):
        """?next= must never become an open redirect off the site."""
        assert safe_next(target) == "/"


class TestLoginFlow:
    def test_login_page_renders(self, client):
        response = client.get("/login")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert 'name="password"' in response.text

    def test_correct_password_signs_in(self, client):
        response = client.post(
            "/login", data={"password": TEST_PASSWORD}, follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"
        assert "session" in response.cookies

    def test_wrong_password_is_rejected(self, client):
        response = client.post(
            "/login", data={"password": "wrong"}, follow_redirects=False
        )
        assert response.status_code == 401
        assert "session" not in response.cookies
        assert "Incorrect password." in response.text

    def test_failure_message_gives_nothing_away(self, client):
        text = client.post("/login", data={"password": "wrong"}).text
        for leak in (TEST_PASSWORD, "scrypt", "hash", "ADMIN_PASSWORD"):
            assert leak not in text, f"login failure page leaked {leak!r}"

    def test_session_cookie_is_httponly_and_lax(self, client):
        response = client.post(
            "/login", data={"password": TEST_PASSWORD}, follow_redirects=False
        )
        cookie = response.headers["set-cookie"].lower()
        # HttpOnly keeps it out of document.cookie; Lax is what stands in for a
        # CSRF token here (a cross-site POST never carries the cookie).
        assert "httponly" in cookie
        assert "samesite=lax" in cookie

    def test_secure_cookie_is_the_default_outside_tests(self):
        """conftest turns this off for http TestClient; production must not inherit that."""
        from app.config import Settings

        assert Settings.model_fields["session_cookie_secure"].default is True

    def test_login_redirects_to_next(self, client):
        response = client.post(
            "/login",
            data={"password": TEST_PASSWORD, "next": "/mytesla/"},
            follow_redirects=False,
        )
        assert response.headers["location"] == "/mytesla/"

    def test_login_refuses_to_redirect_offsite(self, client):
        response = client.post(
            "/login",
            data={"password": TEST_PASSWORD, "next": "//evil.com"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_login_page_bounces_an_already_signed_in_user(self, logged_in_client):
        response = logged_in_client.get("/login", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_logout_ends_the_session(self, logged_in_client):
        assert logged_in_client.get(PRIVATE_PAGE).status_code == 200
        response = logged_in_client.post("/logout", follow_redirects=False)
        assert response.status_code == 303
        assert logged_in_client.get(PRIVATE_PAGE, follow_redirects=False).status_code == 303

    def test_logout_is_not_reachable_by_get(self, logged_in_client):
        """A prefetched link or a crawler must not be able to sign you out."""
        assert logged_in_client.get("/logout").status_code == 405


class TestRouteGuard:
    def test_signed_out_page_redirects_to_login_with_next(self, client):
        response = client.get(PRIVATE_PAGE, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/login?next={PRIVATE_PAGE.replace('/', '%2F')}"

    def test_next_keeps_the_original_query_string(self, client):
        response = client.get(f"{PRIVATE_PAGE}?tag=ml", follow_redirects=False)
        assert "tag%3Dml" in response.headers["location"]

    def test_signed_out_api_gets_json_401(self, client):
        """API callers must not be handed an HTML login page."""
        response = client.get(PRIVATE_API)
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/json")
        assert response.json()["detail"] == "Login required"

    def test_signed_in_reaches_both(self, logged_in_client):
        assert logged_in_client.get(PRIVATE_PAGE).json() == {"secret": "page"}
        assert logged_in_client.get(PRIVATE_API).json() == {"secret": "api"}

    def test_public_pages_stay_public(self, client):
        """This change must not have quietly put the existing site behind a login."""
        for path in ("/", "/mytesla/", "/health"):
            assert client.get(path).status_code == 200, path

    def test_is_logged_in_reads_the_session(self, client):
        assert client.get(PRIVATE_API).status_code == 401
        client.post("/login", data={"password": TEST_PASSWORD})
        assert client.get(PRIVATE_API).status_code == 200

    def test_login_required_carries_the_target(self):
        assert LoginRequired("/papers/").next_path == "/papers/"


class TestPrivateResponsesAreNotCacheable:
    """Public paths get a shared-cacheable window — private paths must opt out."""

    @pytest.mark.parametrize("path", ["/login", "/logout", "/login/anything"])
    def test_private_prefixes_are_recognized(self, path):
        assert is_private_path(path)

    @pytest.mark.parametrize(
        "path", ["/", "/mytesla/", "/api/tesla/charging-records", "/logout-ish"]
    )
    def test_public_paths_are_not(self, path):
        assert not is_private_path(path)

    def test_login_page_is_no_store(self, client):
        assert client.get("/login").headers["Cache-Control"] == "private, no-store"

    def test_a_response_that_sets_a_session_cookie_is_never_public(self, client):
        """Belt and braces: whatever the path, a Set-Cookie response is not shared."""
        response = client.get("/", follow_redirects=False)
        assert response.headers["Cache-Control"].startswith("public")

        client.post("/login", data={"password": TEST_PASSWORD})
        # The signed-in dashboard still refreshes its cookie; that must not be cached.
        signed_in = client.get("/mytesla/")
        if "set-cookie" in signed_in.headers:
            assert "public" not in signed_in.headers.get("Cache-Control", "")


class TestLoginRateLimit:
    """Kept last: it deliberately exhausts the login budget for this window."""

    def test_repeated_failures_are_throttled(self, client):
        statuses = [
            client.post("/login", data={"password": "wrong"}).status_code
            for _ in range(8)
        ]
        assert 429 in statuses, statuses
        # Far below the site-wide 600/minute, and it bites well before 8 tries.
        assert statuses.index(429) <= 5, statuses

    def test_the_cap_is_lower_than_the_site_wide_one(self, client):
        limiter.reset()
        for _ in range(6):
            client.post("/login", data={"password": "wrong"})
        # The throttle is on login, not on the whole site.
        assert client.get("/").status_code == 200
