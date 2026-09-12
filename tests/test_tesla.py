"""Tests for the Tesla router: /stats math, /period-summary windows, writes.

The interesting logic is pure-Python post-processing (odometer deltas, derived
per-km metrics); FakeSession supplies the query results in call order.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.routers import tesla
from app.utils import get_today
from tests.conftest import TEST_API_KEY, FakeResult, FakeSession


class TestStats:
    def test_combines_totals_with_latest_odometer(self, client_for):
        session = FakeSession(results=[
            FakeResult(rows=[{
                "car_expense_total": 30000, "charging_cost": 12000, "energy_kwh": 2400.5,
            }]),
            FakeResult(scalar_value=24000),  # latest odometer reading
        ])
        body = client_for(session).get("/api/tesla/stats").json()
        assert body == {
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

    def test_empty_history_falls_back_to_seed_odometer(self, client_for, monkeypatch):
        monkeypatch.setattr(tesla.settings, "tesla_odometer_km", 21000)
        session = FakeSession(results=[
            FakeResult(rows=[{"car_expense_total": 0, "charging_cost": 0, "energy_kwh": 0}]),
            FakeResult(scalar_value=None),  # no odometer rows yet
        ])
        body = client_for(session).get("/api/tesla/stats").json()
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


class TestReadEndpoints:
    """The read endpoints share the query -> serialize_row pipeline. The
    parametrized check catches route-level wiring errors; the shape tests pin
    serialization of real DB types (Decimal, date) through each query shape."""

    @pytest.mark.parametrize("path", [
        "/api/tesla/charging/providers",
        "/api/tesla/charging/recent",
        "/api/tesla/expenses/recent",
        "/api/tesla/odometer/recent",
    ])
    def test_read_endpoints_respond_with_lists(self, client, path):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == []

    def test_providers_serialize_db_decimals(self, client_for):
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
        body = client_for(session).get("/api/tesla/charging/providers").json()
        assert body == [{
            "provider": "Supercharger",
            "total_kwh": 240.5,
            "total_amount": 1200,       # integral Decimal -> int
            "avg_price_per_kwh": 4.99,  # rounded to 2 decimals
            "paid_kwh": 200,
            "paid_avg_price_per_kwh": 6,
            "free_kwh": 40.5,
            "free_sessions": 2,
        }]

    def test_data_coverage_serializes_dates(self, client_for):
        session = FakeSession(rows=[{
            "charging_start_date": date(2024, 12, 28),
            "expenses_start_date": date(2024, 12, 1),
            "odometer_start_date": date(2026, 6, 1),
            "last_updated": date(2026, 8, 28),
        }])
        assert client_for(session).get("/api/tesla/data-coverage").json() == {
            "charging_start_date": "2024-12-28",
            "expenses_start_date": "2024-12-01",
            "odometer_start_date": "2026-06-01",
            "last_updated": "2026-08-28",
        }

    def test_odometer_current_returns_latest_reading(self, client_for):
        body = client_for(FakeSession(scalar_value=24123)).get(
            "/api/tesla/odometer/current"
        ).json()
        assert body == {"odometer_km": 24123}


class TestPeriodSummary:
    def test_period_metrics_and_month_over_month_change(self, client_for):
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
        body = client_for(session).get("/api/tesla/period-summary").json()
        assert body["current_month"]["energy_cost_per_km"] == 2.0
        assert body["current_month"]["total_cost_per_km"] == 3.0
        assert body["current_month"]["cost_per_km_change_pct"] == 50.0
        assert body["trailing_90_days"]["km_driven"] == 300

    def test_missing_odometer_boundary_returns_null_efficiency(self, client_for):
        row = {"charging_cost": 100, "energy_kwh": 20, "non_charging_cost": 0,
               "starting_odometer": None, "ending_odometer": 1000}
        session = FakeSession(results=[
            FakeResult(rows=[row]), FakeResult(rows=[row]), FakeResult(rows=[row]),
        ])
        body = client_for(session).get("/api/tesla/period-summary").json()
        assert body["current_month"]["km_driven"] is None
        assert body["current_month"]["total_cost_per_km"] is None


class TestDashboardAggregate:
    """The /dashboard endpoint the page actually fetches, which folds the six
    per-widget endpoints into one response served from a single DB session."""

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

    def test_returns_every_widget_payload_in_one_response(self, client_for):
        body = client_for(self._session()).get("/api/tesla/dashboard").json()

        assert list(body) == [
            "stats", "data_coverage", "period_summary",
            "charging_providers", "recent_charging", "recent_expenses",
        ]
        # Each slice keeps the exact shape its own endpoint returns.
        assert body["stats"]["total_cost"] == 2500
        assert body["stats"]["odometer_km"] == 10000
        assert body["data_coverage"]["last_updated"] == "2026-03-09"
        assert body["period_summary"]["current_month"]["total_cost_per_km"] == 3.0
        assert body["charging_providers"][0]["provider"] == "Tesla"
        assert body["recent_charging"][0]["id"] == 1
        assert body["recent_expenses"][0]["item"] == "Insurance"

    def test_the_dashboard_page_renders_from_the_same_payload(self, client_for):
        """GET /mytesla/ and GET /api/tesla/dashboard run the same builder over
        one session, so the HTML can never show numbers the JSON disagrees with.
        No dependency override here — this is the real path."""
        session = self._session()
        html = client_for(session).get("/mytesla/").text

        assert len(session.calls) == 9
        assert "NT$ 2,500" in html   # stats.total_cost
        assert "10,000 km" in html   # odometer
        assert "Insurance" in html   # recent expenses row

    def test_page_load_costs_one_session_and_nine_queries(self, client_for):
        """Every widget the page still draws, in one round of queries. The
        month-bucketing aggregates went out with the charts — a DATE_TRUNC over
        charge_date coming back here means a dropped chart came back with it."""
        session = self._session()
        client_for(session).get("/api/tesla/dashboard")

        assert len(session.calls) == 9
        assert not [
            call for call in session.calls
            if "DATE_TRUNC('month', charge_date)" in str(call[0])
        ]
