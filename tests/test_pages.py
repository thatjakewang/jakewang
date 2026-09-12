"""The HTML half: page rendering, error pages, and asset/caching policy.

The dashboard is rendered server-side now, so rendering these pages for real
is the cheapest meaningful check that templates, Jinja filters, globals, and
the routes still line up — and that the numbers actually reach the HTML.
"""

import re

import pytest

from app.main import PAGE_CACHE_MAX_AGE, STATIC_CACHE_MAX_AGE

PAGES = ["/", "/mytesla/"]


@pytest.mark.parametrize("path", PAGES)
def test_pages_render(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "</html>" in response.text


def test_dashboard_renders_its_numbers_server_side(client):
    """The point of dropping the dashboard JS: the figures are in the HTML the
    server sends. A "Loading..." placeholder here means the page went back to
    fetching its own data."""
    html = client.get("/mytesla/").text
    assert "NT$ 2,500" in html      # stats.total_cost, thousands-separated
    assert "10,000 km" in html      # odometer reading
    assert "NT$ 5/kWh" in html      # provider effective price
    assert "Insurance" in html      # recent car expenses table
    assert "Loading..." not in html


def test_dashboard_ships_no_javascript_of_its_own(client):
    """Only the site-wide nav script survives; nothing on this page fetches."""
    html = client.get("/mytesla/").text
    assert "nav.js" in html
    for needle in ("dashboard.js", "tesla.js", "<canvas", "chart", "fetch("):
        assert needle not in html.lower(), f"{needle} came back on /mytesla/"


def test_dashboard_shows_the_coverage_and_period_windows(client):
    html = client.get("/mytesla/").text
    assert "Since 2026-01-05" in html                        # collection start
    assert "2026-03-01 to 2026-03-09 · partial period" in html
    assert "-12.5%" in html                                  # month-over-month


def test_period_switch_is_a_link(client):
    """No JS means the two windows are two URLs, not a client-side toggle."""
    assert 'href="/mytesla/?period=trailing_90_days"' in client.get("/mytesla/").text

    html = client.get("/mytesla/?period=trailing_90_days").text
    assert "2025-12-10 to 2026-03-09" in html
    # That window has no odometer delta, so its per-km metrics stay unmeasured
    assert "Not enough data" in html


def test_unknown_period_falls_back_to_the_current_month(client):
    """?period is a display toggle, not a resource — a bad value is not a 404."""
    response = client.get("/mytesla/?period=nonsense")
    assert response.status_code == 200
    assert "2026-03-01 to 2026-03-09" in response.text


def test_pages_serve_the_source_assets_directly(client):
    """There is no build step: the files in static/ are the files that ship.
    A .min.* URL here means a bundler crept back in without the toolchain."""
    html = client.get("/").text
    assert "css/style.css" in html
    assert "js/nav.js" in html
    assert ".min.css" not in html
    assert ".min.js" not in html


def test_pages_use_svg_favicon_and_keep_apple_touch_icon(client):
    html = client.get("/").text
    assert "images/favicon/favicon.svg" in html
    assert "images/favicon/apple-touch-icon.png" in html
    assert "favicon.ico" not in html
    assert "web-app-manifest-192x192.png" not in html


@pytest.mark.parametrize("path", PAGES)
def test_pages_ship_no_tracking_or_seo_markup(client, path):
    # The site is a personal project, not a traffic funnel — no analytics,
    # no crawler hints. Easy to reintroduce by accident when editing base.html.
    html = client.get(path).text
    for needle in ("googletagmanager", "google-analytics", "dataLayer",
                   "application/ld+json", 'rel="canonical"',
                   'property="og:', 'name="twitter:'):
        assert needle not in html, f"{needle} came back on {path}"


def test_retired_urls_are_gone(client):
    # The blog and the sitemap were removed before the merge. robots.txt came
    # back later, for the opposite reason — see TestNoIndex.
    for path in ("/blog/", "/blog/some-post/", "/feed.xml", "/sitemap.xml"):
        assert client.get(path).status_code == 404, path


class TestNoIndex:
    """The site is deliberately kept out of search indexes and AI corpora.

    The two halves pull in opposite directions and are easy to get wrong:
    a crawler blocked in robots.txt never reads the noindex, which strands
    already-indexed URLs in the results. So search engines stay allowed and
    only the AI crawlers are disallowed.
    """

    @pytest.mark.parametrize(
        "path", PAGES + ["/health", "/static/css/style.css"]
    )
    def test_everything_is_noindex(self, client, path):
        tag = client.get(path).headers["X-Robots-Tag"]
        assert "noindex" in tag and "nofollow" in tag

    @pytest.mark.parametrize("path", PAGES)
    def test_pages_also_carry_the_meta_tag(self, client, path):
        assert '<meta name="robots" content="noindex, nofollow">' in client.get(path).text

    def test_robots_txt_blocks_the_ai_crawlers(self, client):
        body = client.get("/robots.txt").text
        for bot in ("GPTBot", "ClaudeBot", "Google-Extended", "CCBot",
                    "PerplexityBot", "Bytespider", "Applebot-Extended"):
            assert f"User-agent: {bot}\n" in body, bot
        assert "Disallow: /\n" in body

    def test_robots_txt_still_lets_search_engines_in(self, client):
        """Googlebot must be able to fetch a page to see the noindex."""
        body = client.get("/robots.txt").text
        assert body.rstrip().endswith("User-agent: *\nAllow: /")
        # No blanket block that would apply to every crawler
        assert "User-agent: *\nDisallow: /" not in body


class TestErrorPages:
    def test_unknown_page_gets_the_friendly_html_404(self, client):
        response = client.get("/definitely-not-a-page/")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("text/html")
        assert "</html>" in response.text
        # One template serves every error page, so the code and its line come
        # from the handler's context — a broken context renders a blank page
        # that still looks like valid HTML.
        assert "<h1>404</h1>" in response.text
        assert "Page Not Found" in response.text

    def test_unknown_api_path_stays_json(self, client):
        """API clients (iPhone Shortcuts) must not get an HTML error page."""
        response = client.get("/api/tesla/nope")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")
        assert "detail" in response.json()


class TestAssetPolicy:
    @pytest.mark.parametrize("path", PAGES)
    def test_pages_get_a_short_shared_cache(self, client, path):
        response = client.get(path)
        assert response.headers["Cache-Control"] == f"public, max-age={PAGE_CACHE_MAX_AGE}"

    def test_static_files_get_long_max_age(self, client):
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        assert f"max-age={STATIC_CACHE_MAX_AGE}" in response.headers["Cache-Control"]

    def test_pages_version_static_asset_urls(self, client):
        # The ?v= cache-buster is what makes the long max-age safe to serve.
        html = client.get("/").text
        assert re.search(r"/static/css/style\.css\?v=\d+", html)

    def test_missing_asset_versions_to_zero(self):
        from app.main import static_url

        assert static_url("does-not-exist.css").endswith("?v=0")


@pytest.mark.parametrize(
    "path", PAGES + ["/health", "/static/css/style.css"]
)
def test_security_headers_on_everything(client, path):
    """Pages, API and static assets all go through the same middleware."""
    headers = client.get(path).headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
