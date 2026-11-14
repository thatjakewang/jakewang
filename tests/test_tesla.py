from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import tesla, utils
from app.dependencies import verify_shortcut_api_key
from app.tesla import (
    CarExpenseCreate, ChargingRecordCreate, OdometerReadingCreate, axis_ticks,
    month_starts, odometer_span, period_windows,
)
from app.utils import create_record, delete_latest_record


class FakeResult:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def one(self):
        return self.row

    def first(self):
        return self.row

    def __iter__(self):
        return iter(self.row)


class FakeSession:
    """Answers each execute() with the next queued row and records the SQL."""

    def __init__(self, *rows):
        self.rows = list(rows)
        self.statements = []
        self.commits = 0

    def execute(self, statement, params=None):
        self.statements.append(str(statement))
        return FakeResult(self.rows.pop(0))

    def commit(self):
        self.commits += 1


def windows(today):
    return {key: (start, end) for key, start, end in period_windows(today)}


def test_period_windows_mid_month():
    w = windows(date(2026, 11, 10))
    assert w["current_month"] == (date(2026, 11, 1), date(2026, 11, 10))
    assert w["previous_month"] == (date(2026, 10, 1), date(2026, 10, 10))
    assert w["trailing_90_days"] == (date(2026, 8, 13), date(2026, 11, 10))
    assert w["trailing_365_days"] == (date(2025, 11, 11), date(2026, 11, 10))


def test_previous_month_is_clamped_to_its_length():
    assert windows(date(2026, 3, 31))["previous_month"] == (date(2026, 2, 1), date(2026, 2, 28))
    assert windows(date(2028, 3, 31))["previous_month"] == (date(2028, 2, 1), date(2028, 2, 29))


def test_previous_month_crosses_the_year():
    assert windows(date(2026, 1, 15))["previous_month"] == (date(2025, 12, 1), date(2025, 12, 15))


READINGS = [
    (date(2026, 9, 25), 20000),
    (date(2026, 10, 28), 21000),
    (date(2026, 11, 8), 21400),
]


def test_odometer_span_brackets_the_window():
    assert odometer_span(READINGS, date(2026, 11, 1), date(2026, 11, 10)) == (
        date(2026, 10, 28), date(2026, 11, 8), 400,
    )


def test_odometer_span_ignores_readings_after_the_window():
    assert odometer_span(READINGS, date(2026, 10, 1), date(2026, 10, 10)) is None
    assert odometer_span(READINGS, date(2026, 10, 1), date(2026, 10, 31)) == (
        date(2026, 9, 25), date(2026, 10, 28), 1000,
    )


def test_odometer_span_needs_a_reading_before_the_window():
    assert odometer_span(READINGS, date(2026, 9, 1), date(2026, 11, 10)) is None
    assert odometer_span([], date(2026, 11, 1), date(2026, 11, 10)) is None


def test_odometer_span_without_movement_is_none():
    readings = READINGS + [(date(2026, 11, 9), 21400)]
    assert odometer_span(readings, date(2026, 11, 9), date(2026, 11, 10)) is None


def test_period_summary_divides_span_costs_by_span_distance(monkeypatch):
    monkeypatch.setattr(tesla, "get_today", lambda: date(2026, 11, 10))
    sums = {"charging_cost": 900, "non_charging_cost": 100, "span_charging_cost": 1200,
            "span_energy_kwh": 60.0, "span_non_charging_cost": 400}
    previous = {**sums, "span_charging_cost": 600, "span_non_charging_cost": 200}
    db = FakeSession(
        [SimpleNamespace(reading_date=d, reading_km=km) for d, km in READINGS
         + [(date(2026, 10, 9), 20600)]],
        sums, previous, sums, sums,
    )
    db.rows[0].sort(key=lambda row: row.reading_date)
    summary = tesla.get_period_summary(db)

    assert set(summary) == {"current_month", "trailing_90_days", "trailing_365_days"}
    current = summary["current_month"]
    assert current["total_cost"] == 1000
    assert (current["measured_from"], current["measured_to"]) == ("2026-10-28", "2026-11-08")
    assert current["km_driven"] == 400
    assert current["energy_cost_per_km"] == 3.0
    assert current["total_cost_per_km"] == 4.0
    assert current["kwh_per_100km"] == 15.0
    # Prior month: 800 over the 600 km between 09-25 and 10-09 -> 1.33/km.
    assert current["cost_per_km_change_pct"] == 200.0
    # Only the month is partial; the trailing windows are always full length.
    assert current["is_partial"] is True
    assert summary["trailing_90_days"]["is_partial"] is False
    assert summary["trailing_365_days"]["is_partial"] is False
    # No reading before the 90-day window opens, so nothing to divide by.
    assert summary["trailing_365_days"]["km_driven"] is None
    assert summary["trailing_365_days"]["total_cost_per_km"] is None
    assert summary["trailing_365_days"]["measured_from"] is None


def test_month_starts_cover_twelve_months_ending_with_this_one():
    months = month_starts(date(2026, 3, 31))
    assert len(months) == 12
    assert (months[0], months[-1]) == (date(2025, 4, 1), date(2026, 3, 1))
    assert months == sorted(months)


@pytest.mark.parametrize("max_value, ticks", [
    (0, [0]),
    (7, [0, 2, 4, 6, 8]),
    (999, [0, 500, 1000]),
    (4200, [0, 2000, 4000, 6000]),
    (30250, [0, 10000, 20000, 30000, 40000]),
])
def test_axis_ticks_are_round_and_reach_the_maximum(max_value, ticks):
    assert axis_ticks(max_value) == ticks


def test_monthly_costs_fill_empty_months_and_skip_future_ones(monkeypatch):
    monkeypatch.setattr(tesla, "get_today", lambda: date(2026, 11, 10))
    db = FakeSession([
        SimpleNamespace(month="2026-11", kind="charging_cost", amount=760),
        SimpleNamespace(month="2026-11", kind="non_charging_cost", amount=300),
        SimpleNamespace(month="2026-03", kind="non_charging_cost", amount=28500),
        SimpleNamespace(month="2026-12", kind="charging_cost", amount=99999),
    ])
    chart = tesla.get_monthly_costs(db)

    months = chart["months"]
    assert [m["month"] for m in months] == [
        "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
        "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11",
    ]
    assert (months[-1]["label"], months[-1]["name"]) == ("Nov", "November 2026")
    assert (months[-1]["charging_cost"], months[-1]["non_charging_cost"], months[-1]["total"]) == (760, 300, 1060)
    assert months[3]["total"] == 28500
    assert months[1]["total"] == 0
    assert chart["axis"]["max"] == 30000
    assert [tick["label"] for tick in chart["axis"]["ticks"]] == ["0", "10K", "20K", "30K"]
    # The charging view is scaled to charging alone, not to the big expense.
    assert chart["charging_axis"]["max"] == 800
    assert [tick["label"] for tick in chart["charging_axis"]["ticks"]] == ["0", "200", "400", "600", "800"]


def test_monthly_costs_without_records_have_no_axis(monkeypatch):
    monkeypatch.setattr(tesla, "get_today", lambda: date(2026, 11, 10))
    chart = tesla.get_monthly_costs(FakeSession([]))
    assert chart["axis"]["max"] == 0
    assert chart["charging_axis"]["max"] == 0
    assert len(chart["months"]) == 12


def reading(km):
    return OdometerReadingCreate(reading_km=km, reading_date=date(2026, 11, 10))


def test_odometer_reading_below_an_earlier_one_is_refused():
    db = FakeSession({"floor_km": 23000, "ceiling_km": None})
    with pytest.raises(HTTPException) as exc:
        tesla.create_odometer_reading(reading(2312), db=db)
    assert exc.value.status_code == 422
    assert db.commits == 0


def test_odometer_reading_above_a_later_one_is_refused():
    db = FakeSession({"floor_km": 23000, "ceiling_km": 23500})
    with pytest.raises(HTTPException) as exc:
        tesla.create_odometer_reading(reading(231200), db=db)
    assert exc.value.status_code == 422


def test_odometer_reading_in_range_is_inserted():
    db = FakeSession({"floor_km": 23000, "ceiling_km": None}, None, {"id": 7})
    response = tesla.create_odometer_reading(reading(23120), db=db)
    assert response["data"] == {"id": 7, "reading_km": 23120, "reading_date": "2026-11-10"}
    assert db.commits == 1


def test_values_too_large_for_their_columns_are_refused():
    with pytest.raises(ValidationError):
        reading(2**31)
    with pytest.raises(ValidationError):
        CarExpenseCreate(date=date(2026, 11, 10), item="Toll", amount=2**63)
    with pytest.raises(ValidationError):
        ChargingRecordCreate(
            charge_date=date(2026, 11, 10), provider="Home", amount=2**63, kwh=10,
        )
    assert reading(2**31 - 1).reading_km == 2**31 - 1


def test_labels_with_a_nul_byte_are_refused():
    with pytest.raises(ValidationError):
        CarExpenseCreate(date=date(2026, 11, 10), item="To\x00ll", amount=40)
    expense = CarExpenseCreate(date=date(2026, 11, 10), item="  Toll\n(ETC) ", amount=40)
    assert expense.item == "Toll\n(ETC)"


@pytest.mark.parametrize("timezone", ["", "../etc", "Asia/Nowhere"])
def test_today_falls_back_when_the_timezone_is_invalid(monkeypatch, timezone):
    monkeypatch.setattr(
        utils, "get_settings", lambda: SimpleNamespace(app_timezone=timezone),
    )
    assert isinstance(utils.get_today(), date)


def test_create_record_returns_a_recent_identical_row_instead_of_inserting():
    db = FakeSession({"id": 7})
    response = create_record(db, "odometer_readings", reading(23120), "ok")
    assert response["data"]["id"] == 7
    assert db.commits == 0
    assert len(db.statements) == 1 and "INSERT" not in db.statements[0]


def test_delete_latest_record():
    row = {"id": 7, "reading_km": 23120, "reading_date": date(2026, 11, 10)}
    db = FakeSession(row)
    response = delete_latest_record(db, "odometer_readings", "reading_km, reading_date", "gone")
    assert response["data"] == {"id": 7, "reading_km": 23120, "reading_date": "2026-11-10"}
    assert db.commits == 1


def test_delete_latest_record_on_an_empty_table_is_404():
    with pytest.raises(HTTPException) as exc:
        delete_latest_record(FakeSession(None), "odometer_readings", "reading_km", "gone")
    assert exc.value.status_code == 404


@pytest.mark.parametrize("key", [None, "wrong", "café"])
def test_bad_api_keys_are_401(key):
    with pytest.raises(HTTPException) as exc:
        verify_shortcut_api_key(key)
    assert exc.value.status_code == 401


def test_the_configured_api_key_passes():
    from app.config import get_settings
    assert verify_shortcut_api_key(get_settings().shortcut_api_key) is None
