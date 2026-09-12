"""Tests for the Tesla module: the cost math, the write endpoints, the payload.

Only the three writes are HTTP endpoints; the reads are plain functions the
dashboard calls while rendering, so they are tested by calling them with a
FakeSession rather than through a client. The interesting logic is pure-Python
post-processing (odometer deltas, derived per-km metrics); FakeSession supplies
the query results in call order.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.routers import tesla
from app.utils import get_today
from tests.conftest import TEST_API_KEY, FakeResult, FakeSession


class TestStats:
    def test_combines_totals_with_latest_odometer(self):
        session = FakeSession(results=[
            FakeResult(rows=[{
                "car_expense_total": 30000, "charging_cost": 12000, "energy_kwh": 2400.5,
            }]),
            FakeResult(scalar_value=24000),  # latest odometer reading
        ])
        assert tesla.get_stats(session) == {
            "total_cost": 42000.0,
            "charging_cost": 12000.0,
            "non_charging_cost": 30000.0,
            "energy_kwh": 2400.5,
            "avg_price_per_kwh": 5.0,
            "odometer_km": 24000,
            "cost_per_km": 1.75,
            "charging_cost_per_km": 0.5,
            "non_charging_cost_per_km": 1.25,
        }

    def test_empty_history_falls_back_to_seed_odometer(self, monkeypatch):
        monkeypatch.setattr(tesla.settings, "tesla_odometer_km", 21000)
        session = FakeSession(results=[
            FakeResult(rows=[{"car_expense_total": 0, "charging_cost": 0, "energy_kwh": 0}]),
            FakeResult(scalar_value=None),  # no odometer rows yet
        ])
        body = tesla.get_stats(session)
        assert body["odometer_km"] == 21000
        assert body["avg_price_per_kwh"] == 0  # zero kWh must not divide
        assert body["cost_per_km"] == 0


class TestWrites:
    def test_create_charging_record_envelope(self, client_for):
        session = FakeSession(results=[FakeResult(rows=[{"id": 7}])])
        response = client_for(session).post(
            "/api/tesla/charging-records",
            headers={"x-api-key": TEST_API_KEY},
            json={"charge_date": "2026-07-01", "provider": "Tesla Supercharger",
                  "amount": 150, "kwh": 30.5},
        )
        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "message": "Charging record created",
            "data": {"id": 7, "charge_date": "2026-07-01",
                     "provider": "Tesla Supercharger", "amount": 150, "kwh": 30.5},
        }

    def test_negative_amount_is_rejected(self, client_for):
        response = client_for(FakeSession()).post(
            "/api/tesla/charging-records",
            headers={"x-api-key": TEST_API_KEY},
            json={"charge_date": "2026-07-01", "provider": "x", "amount": -1, "kwh": 1},
        )
        assert response.status_code == 422

    def test_create_car_expense_envelope(self, client_for):
        session = FakeSession(results=[FakeResult(rows=[{"id": 3}])])
        response = client_for(session).post(
            "/api/tesla/car-expenses",
            headers={"x-api-key": TEST_API_KEY},
            json={"date": "2026-07-01", "item": "Tires", "amount": 8000},
        )
        assert response.status_code == 200
        assert response.json()["data"] == {
            "id": 3, "date": "2026-07-01", "item": "Tires", "amount": 8000,
        }

    def test_odometer_reading_date_defaults_to_app_timezone_today(self, client_for):
        session = FakeSession(results=[FakeResult(rows=[{"id": 9}])])
        before = get_today()
        response = client_for(session).post(
            "/api/tesla/odometer",
            headers={"x-api-key": TEST_API_KEY},
            json={"reading_km": 24500},
        )
        after = get_today()

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == 9
        assert data["reading_km"] == 24500
        # before/after so a run that crosses midnight can't flake
        assert data["reading_date"] in {before.isoformat(), after.isoformat()}


class TestReadQueries:
    """The read queries share the query -> serialize_row pipeline. The
    parametrized check catches a query that stops returning a list; the shape
    tests pin serialization of real DB types (Decimal, date) per query shape."""

    @pytest.mark.parametrize("query", [
        tesla.get_charging_by_provider,
        tesla.get_recent_charging_records,
        tesla.get_recent_car_expenses,
    ])
    def test_read_queries_return_lists(self, query):
        assert query(FakeSession(rows=[])) == []

    def test_providers_serialize_db_decimals(self):
        # Postgres SUM/aggregates come back as Decimal, never int/float.
        session = FakeSession(rows=[{
            "provider": "Supercharger",
            "total_kwh": Decimal("240.50"),
            "total_amount": Decimal("1200"),
            "avg_price_per_kwh": Decimal("4.9896"),
            "paid_kwh": Decimal("200.00"),
            "paid_avg_price_per_kwh": Decimal("6.00"),
            "free_kwh": Decimal("40.50"),
            "free_sessions": 2,
        }])
        assert tesla.get_charging_by_provider(session) == [{
            "provider": "Supercharger",
            "total_kwh": 240.5,
            "total_amount": 1200,       # integral Decimal -> int
            "avg_price_per_kwh": 4.99,  # rounded to 2 decimals
            "paid_kwh": 200,
            "paid_avg_price_per_kwh": 6,
            "free_kwh": 40.5,
            "free_sessions": 2,
        }]

    def test_data_coverage_serializes_dates(self):
        session = FakeSession(rows=[{
            "charging_start_date": date(2024, 12, 28),
            "expenses_start_date": date(2024, 12, 1),
            "odometer_start_date": date(2026, 6, 1),
            "last_updated": date(2026, 8, 28),
        }])
        assert tesla.get_data_coverage(session) == {
            "charging_start_date": "2024-12-28",
            "expenses_start_date": "2024-12-01",
            "odometer_start_date": "2026-06-01",
            "last_updated": "2026-08-28",
        }

    def test_latest_odometer_falls_back_to_the_configured_seed(self, monkeypatch):
        assert tesla.get_latest_odometer(FakeSession(scalar_value=24123)) == 24123
        monkeypatch.setattr(tesla.settings, "tesla_odometer_km", 21000)
        assert tesla.get_latest_odometer(FakeSession(scalar_value=None)) == 21000


class TestPeriodSummary:
    def test_period_metrics_and_month_over_month_change(self):
        session = FakeSession(results=[
            FakeResult(rows=[{"charging_cost": 200, "energy_kwh": 40,
                              "non_charging_cost": 100, "starting_odometer": 1000,
                              "ending_odometer": 1100}]),
            FakeResult(rows=[{"charging_cost": 150, "energy_kwh": 30,
                              "non_charging_cost": 50, "starting_odometer": 900,
                              "ending_odometer": 1000}]),
            FakeResult(rows=[{"charging_cost": 500, "energy_kwh": 100,
                              "non_charging_cost": 100, "starting_odometer": 800,
                              "ending_odometer": 1100}]),
        ])
        body = tesla.get_period_summary(session)
        assert body["current_month"]["energy_cost_per_km"] == 2.0
        assert body["current_month"]["total_cost_per_km"] == 3.0
        assert body["current_month"]["cost_per_km_change_pct"] == 50.0
        assert body["trailing_90_days"]["km_driven"] == 300

    def test_missing_odometer_boundary_returns_null_efficiency(self):
        row = {"charging_cost": 100, "energy_kwh": 20, "non_charging_cost": 0,
               "starting_odometer": None, "ending_odometer": 1000}
        session = FakeSession(results=[
            FakeResult(rows=[row]), FakeResult(rows=[row]), FakeResult(rows=[row]),
        ])
        body = tesla.get_period_summary(session)
        assert body["current_month"]["km_driven"] is None
        assert body["current_month"]["total_cost_per_km"] is None


class TestDashboardPayload:
    """get_dashboard(): the six widget payloads the page renders, folded into
    one dict resolved from a single DB session."""

    # Query order inside get_dashboard, one FakeResult each: the handlers run
    # in key order.
    @staticmethod
    def _session():
        return FakeSession(results=[
            # stats: lifetime totals, then the latest odometer reading
            FakeResult(rows=[{"car_expense_total": 2000, "charging_cost": 500,
                              "energy_kwh": 100.0}]),
            FakeResult(scalar_value=10000),
            # data coverage
            FakeResult(rows=[{"charging_start_date": date(2026, 1, 5),
                              "expenses_start_date": date(2026, 1, 1),
                              "odometer_start_date": date(2026, 1, 1),
                              "last_updated": date(2026, 3, 9)}]),
            # period summary: current month, previous month, trailing 90 days
            *[FakeResult(rows=[{"charging_cost": 200, "energy_kwh": 40,
                                "non_charging_cost": 100, "starting_odometer": 1000,
                                "ending_odometer": 1100}]) for _ in range(3)],
            # charging by provider
            FakeResult(rows=[{"provider": "Tesla", "total_kwh": 100.0,
                              "total_amount": 500, "avg_price_per_kwh": 5.0,
                              "paid_kwh": 100.0, "paid_avg_price_per_kwh": 5.0,
                              "free_kwh": 0.0, "free_sessions": 0}]),
            # recent charging, then recent car expenses
            FakeResult(rows=[{"id": 1, "charge_date": date(2026, 1, 5),
                              "provider": "Tesla", "amount": 500, "kwh": 100.0}]),
            FakeResult(rows=[{"id": 1, "date": date(2026, 1, 1),
                              "item": "Insurance", "amount": 2000}]),
        ])

    def test_returns_every_widget_payload_in_one_dict(self):
        body = tesla.get_dashboard(self._session())

        assert list(body) == [
            "stats", "data_coverage", "period_summary",
            "charging_providers", "recent_charging", "recent_expenses",
        ]
        # Each slice keeps the exact shape its own query returns.
        assert body["stats"]["total_cost"] == 2500
        assert body["stats"]["odometer_km"] == 10000
        assert body["data_coverage"]["last_updated"] == "2026-03-09"
        assert body["period_summary"]["current_month"]["total_cost_per_km"] == 3.0
        assert body["charging_providers"][0]["provider"] == "Tesla"
        assert body["recent_charging"][0]["id"] == 1
        assert body["recent_expenses"][0]["item"] == "Insurance"

    def test_the_dashboard_page_renders_from_this_payload(self, client_for):
        """The page renders straight out of get_dashboard() over one session.
        No dependency override here — this is the real path, the only one left
        now that nothing fetches this data over HTTP."""
        session = self._session()
        html = client_for(session).get("/mytesla/").text

        assert len(session.calls) == 9
        assert "NT$ 2,500" in html   # stats.total_cost
        assert "10,000 km" in html   # odometer
        assert "Insurance" in html   # recent expenses row

    def test_the_whole_dashboard_costs_nine_queries(self):
        """Every widget the page still draws, in one round of queries. The
        month-bucketing aggregates went out with the charts — a DATE_TRUNC over
        charge_date coming back here means a dropped chart came back with it."""
        session = self._session()
        tesla.get_dashboard(session)

        assert len(session.calls) == 9
        assert not [
            call for call in session.calls
            if "DATE_TRUNC('month', charge_date)" in str(call[0])
        ]
