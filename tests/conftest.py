"""Shared test fixtures.

Environment variables are set BEFORE any app module is imported so the cached
Settings instance (and the module-level `settings` in tesla) is built from test
values, never from the developer's real .env (real env vars take priority over
the .env file in pydantic-settings).

No test ever touches a real database: endpoints get a FakeSession via
dependency_overrides, and the engine created at import time never connects.
"""

import os

os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_never_connected"
os.environ["SHORTCUT_API_KEY"] = "test-api-key"
os.environ["APP_TIMEZONE"] = "Asia/Taipei"

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app, dashboard_payload

TEST_API_KEY = "test-api-key"


class FakeResult:
    """Mimics the subset of SQLAlchemy's Result used by the app (mappings/one/all/scalar)."""

    def __init__(self, rows=None, scalar_value=None):
        self._rows = rows or []
        self._scalar = scalar_value

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def one(self):
        return self._rows[0]

    def scalar(self):
        return self._scalar


class FakeSession:
    """A DB session double: returns canned rows, records close/rollback calls.

    `results` (a list of FakeResult) makes consecutive execute() calls return
    different result sets, for endpoints that run several queries. Every
    execute()'s positional args land in `calls`, so tests can assert the
    parameters bound to each query (calls[i][1] is the params dict, if any).
    """

    def __init__(self, rows=None, scalar_value=None, execute_error=None, results=None):
        self.rows = rows
        self.scalar_value = scalar_value
        self.execute_error = execute_error
        self.results = list(results) if results else None
        self.closed = False
        self.rolled_back = False
        self.calls = []

    def execute(self, *args, **kwargs):
        self.calls.append(args)
        if self.execute_error is not None:
            raise self.execute_error
        if self.results is not None:
            return self.results.pop(0)
        return FakeResult(self.rows, self.scalar_value)

    def commit(self):
        pass

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


# What GET /mytesla/ renders. The page is server-rendered now, so tests that
# only care about headers or markup would otherwise have to fake all nine of
# the dashboard's queries; overriding the dependency keeps them to the point.
# Shapes mirror tesla.get_dashboard() exactly — a key renamed there must be
# renamed here, or the template silently renders a blank.
DASHBOARD_PAYLOAD = {
    "stats": {
        "total_cost": 2500.0, "charging_cost": 500.0, "non_charging_cost": 2000.0,
        "energy_kwh": 100.0, "avg_price_per_kwh": 5.0, "odometer_km": 10000,
        "cost_per_km": 0.25, "charging_cost_per_km": 0.05,
        "non_charging_cost_per_km": 0.2,
    },
    "data_coverage": {
        "charging_start_date": "2026-01-05", "expenses_start_date": "2026-01-01",
        "odometer_start_date": "2026-01-01", "last_updated": "2026-03-09",
    },
    "period_summary": {
        "current_month": {
            "start_date": "2026-03-01", "end_date": "2026-03-09", "is_partial": True,
            "charging_cost": 200.0, "non_charging_cost": 100.0, "total_cost": 300.0,
            "energy_kwh": 40.0, "km_driven": 100, "energy_cost_per_km": 2.0,
            "total_cost_per_km": 3.0, "kwh_per_100km": 40.0,
            "cost_per_km_change_pct": -12.5,
        },
        "trailing_90_days": {
            "start_date": "2025-12-10", "end_date": "2026-03-09", "is_partial": True,
            "charging_cost": 500.0, "non_charging_cost": 2000.0, "total_cost": 2500.0,
            "energy_kwh": 100.0, "km_driven": None, "energy_cost_per_km": None,
            "total_cost_per_km": None, "kwh_per_100km": None,
        },
    },
    "charging_providers": [
        {"provider": "Tesla", "total_kwh": 100.0, "total_amount": 500,
         "avg_price_per_kwh": 5.0, "paid_kwh": 100.0, "paid_avg_price_per_kwh": 5.0,
         "free_kwh": 0.0, "free_sessions": 0},
    ],
    "recent_charging": [
        {"id": 1, "charge_date": "2026-01-05", "provider": "Tesla",
         "amount": 500, "kwh": 100.0},
    ],
    "recent_expenses": [
        {"id": 1, "date": "2026-01-01", "item": "Insurance", "amount": 2000},
    ],
}


@pytest.fixture
def fake_db():
    """Default healthy fake session returning no rows."""
    return FakeSession(rows=[])


@pytest.fixture
def client(fake_db):
    """TestClient wired to the fake session; override is removed after each test.

    The dashboard page also gets its canned payload here, so every test that
    merely visits /mytesla/ keeps working without staging queries.
    """
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[dashboard_payload] = lambda: DASHBOARD_PAYLOAD
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client_for():
    """Factory: build a TestClient whose get_db yields the given fake session."""

    def factory(session: FakeSession) -> TestClient:
        app.dependency_overrides[get_db] = lambda: session
        return TestClient(app)

    yield factory
    app.dependency_overrides.clear()
