"""The Jinja environment, its globals, and the filters the templates call.

Kept out of app/main.py because it is a self-contained unit — how numbers are
formatted and how asset URLs are versioned has nothing to do with wiring up an
application. It once had to live here to avoid a circular import with the page
routers; that constraint is gone, and this is now a choice.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _static_version(filename: str) -> int:
    """File mtime, used as the ?v= cache-buster. 0 when the file is missing."""
    try:
        return int((STATIC_DIR / filename).stat().st_mtime)
    except OSError:
        return 0


# stat() once per process; assets only change on redeploy, which restarts it.
_cached_static_version = lru_cache(maxsize=None)(_static_version)


def static_url(filename: str) -> str:
    """/static URL plus ?v=<mtime>, which is what makes the long max-age safe."""
    return f"/static/{filename}?v={_cached_static_version(filename)}"


def _format_number(value: float | int) -> str:
    """Thousands-separated, with a float's trailing ".0" dropped.

    Matches what Number.toLocaleString() produced back when these numbers were
    formatted in the browser, so the rendered page reads the same as before.
    """
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}"


# What a null metric renders as. Nulls are meaningful here: a month with no
# odometer delta has no cost per km, and saying so beats printing a zero that
# looks like a real measurement.
NO_DATA = "Not enough data"


def number(value, suffix: str = "") -> str:
    """Render a metric, or NO_DATA when the query left it null.

    No fallback parameter: every unitless metric on the dashboard means the
    same thing by a null. money() takes one because a provider with no paid
    sessions wants to say that, not "not enough data".
    """
    if value is None:
        return NO_DATA
    return f"{_format_number(value)}{suffix}"


def money(value, fallback: str = NO_DATA, suffix: str = "") -> str:
    """Same, prefixed with the currency these tables are all denominated in."""
    if value is None:
        return fallback
    return f"NT$ {_format_number(value)}{suffix}"


def current_year() -> int:
    """Footer copyright year. A function, not a value, so a long-running
    process doesn't keep serving the year it booted in."""
    return date.today().year


templates.env.globals["static_url"] = static_url
templates.env.globals["current_year"] = current_year
templates.env.filters["number"] = number
templates.env.filters["money"] = money
