"""Tesla cost tracking for a personal Tesla (charging + car expenses).

Three protected write endpoints, used by iPhone Shortcuts, each with a
delete-the-latest counterpart for undoing a mistake, plus the read queries
behind the dashboard. The reads are plain functions rather than routes: the only
thing that wants them is the server-rendered dashboard, which calls
get_dashboard() directly (see app/main.py). They were HTTP endpoints while the
page fetched its own data — nothing did after that, so the routes went.

This is the only router left, so it sits beside main.py instead of in a
package of its own.

All monetary values are stored as integers and kWh as floats. The id column
(SERIAL) provides stable ordering for the recent-record queries.
"""

from calendar import monthrange
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import verify_shortcut_api_key
from app.utils import (
    create_record,
    delete_latest_record,
    fetch_recent,
    get_today,
    serialize_row,
)

# Every route here is a write, so the key check sits on the router: a new
# endpoint is protected without having to remember to ask for it.
router = APIRouter(dependencies=[Depends(verify_shortcut_api_key)])
RecordLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ChargingRecordCreate(BaseModel):
    """Payload for creating a charging record (Tesla Supercharger, etc.)."""
    charge_date: date
    provider: RecordLabel
    amount: int = Field(ge=0)
    kwh: float = Field(ge=0, allow_inf_nan=False)


class CarExpenseCreate(BaseModel):
    """Payload for recording a car-related expense (insurance, maintenance, etc.)."""
    date: date
    item: RecordLabel
    amount: int = Field(ge=0)


class OdometerReadingCreate(BaseModel):
    """Payload for logging a total-odometer reading (the number shown on the car screen)."""
    reading_km: int = Field(ge=0)
    # get_today (not date.today) so the default respects APP_TIMEZONE, matching
    # every other date computation in the app (server clock runs on UTC).
    reading_date: date = Field(default_factory=get_today)


# The columns each table shows on the dashboard and echoes back from an undo.
CHARGING_COLUMNS = "charge_date, provider, amount, kwh"
EXPENSE_COLUMNS = "date, item, amount"
ODOMETER_COLUMNS = "reading_km, reading_date"


def _ratio(amount: float, divisor: float | None, empty=None):
    """amount / divisor to two decimals, or `empty` with nothing to divide by."""
    return round(amount / divisor, 2) if divisor else empty


def get_latest_odometer(db: Session) -> int:
    """Return the most recent odometer reading, or 0 if none have been logged yet."""
    reading = db.execute(text("""
        SELECT reading_km
        FROM odometer_readings
        ORDER BY reading_date DESC, id DESC
        LIMIT 1
    """)).scalar()
    return int(reading) if reading is not None else 0


def get_stats(db: Session):
    """Return high-level Tesla cost statistics.

    Includes lifetime totals, average price per kWh, and cost per km based on
    the latest odometer reading. All queries are simple aggregates over the
    entire history (personal use, tables stay small).
    """
    totals_query = text("""
        SELECT
            (SELECT COALESCE(SUM(amount), 0) FROM car_expenses) AS car_expense_total,
            COALESCE(SUM(amount), 0) AS charging_cost,
            COALESCE(SUM(kwh), 0) AS energy_kwh
        FROM charging_records
    """)

    totals = db.execute(totals_query).mappings().one()

    car_expense_total = float(totals["car_expense_total"])
    charging_cost = float(totals["charging_cost"])
    energy_kwh = float(totals["energy_kwh"])

    total_cost = car_expense_total + charging_cost
    odometer_km = get_latest_odometer(db)

    return {
        "total_cost": total_cost,
        "charging_cost": charging_cost,
        "non_charging_cost": car_expense_total,
        "avg_price_per_kwh": _ratio(charging_cost, energy_kwh, empty=0),
        "odometer_km": odometer_km,
        "cost_per_km": _ratio(total_cost, odometer_km, empty=0),
        "charging_cost_per_km": _ratio(charging_cost, odometer_km, empty=0),
        "non_charging_cost_per_km": _ratio(car_expense_total, odometer_km, empty=0),
    }


def get_data_coverage(db: Session):
    """Return collection start dates and the most recent recorded activity."""
    row = db.execute(text("""
        SELECT
            (SELECT MIN(charge_date) FROM charging_records) AS charging_start_date,
            (SELECT MIN(date) FROM car_expenses) AS expenses_start_date,
            (SELECT MIN(reading_date) FROM odometer_readings) AS odometer_start_date,
            GREATEST(
                (SELECT MAX(charge_date) FROM charging_records),
                (SELECT MAX(date) FROM car_expenses),
                (SELECT MAX(reading_date) FROM odometer_readings)
            ) AS last_updated
    """)).mappings().one()
    return serialize_row(row)


def period_windows(today: date) -> tuple[tuple[str, date, date], ...]:
    """The date windows get_period_summary() reports on, as (key, start, end).

    previous_month is only there for the month-over-month comparison: it ends
    on the same day of the month as today (clamped to the month's length), so
    month-to-date is compared with the same number of elapsed days.
    """
    this_month = today.replace(day=1)
    previous_month = (this_month - timedelta(days=1)).replace(day=1)
    previous_comparable_end = previous_month.replace(
        day=min(today.day, monthrange(previous_month.year, previous_month.month)[1])
    )
    return (
        ("current_month", this_month, today),
        ("previous_month", previous_month, previous_comparable_end),
        ("trailing_90_days", today - timedelta(days=89), today),
        # A full year holds every annual charge (insurance, license tax) exactly
        # once, which shorter windows can't promise.
        ("trailing_365_days", today - timedelta(days=364), today),
    )


def odometer_span(
    readings: list[tuple[date, int]], start: date, end: date
) -> tuple[date, date, int] | None:
    """Return (from_date, to_date, km) for the readings that bracket a window.

    readings are (reading_date, reading_km), oldest first. The span runs from
    the last reading before the window to the last reading within it, and is
    None when either is missing or the car did not move between them.
    """
    before = [reading for reading in readings if reading[0] < start]
    upto = [reading for reading in readings if reading[0] <= end]
    if not before or not upto:
        return None
    (from_date, from_km), (to_date, to_km) = before[-1], upto[-1]
    km = to_km - from_km
    return (from_date, to_date, km) if km > 0 else None


def get_period_summary(db: Session):
    """Summarize every period the dashboard can switch between, keyed by name.

    All three are rendered into the page at once and the switch only toggles
    which one is visible, so there is no ?period to choose from. The prior
    month is also queried, but only to derive the current month's
    cost_per_km_change_pct — that row is dropped before returning.

    total_cost covers the calendar window. The per-km figures do not: distance
    is only known between two odometer readings, so they divide the costs
    recorded between those readings (after the first, up to and including the
    second) by the distance between them. Dividing calendar-window costs by
    that distance would mix two different spans whenever a reading does not
    fall exactly on the window's edge. They are null when no span is available.
    """
    today = get_today()
    readings = [
        (row.reading_date, int(row.reading_km))
        for row in db.execute(text("""
            SELECT reading_date, reading_km
            FROM odometer_readings
            ORDER BY reading_date, id
        """))
    ]
    query = text("""
        SELECT
            (SELECT COALESCE(SUM(amount), 0) FROM charging_records
             WHERE charge_date BETWEEN :start_date AND :end_date) AS charging_cost,
            (SELECT COALESCE(SUM(amount), 0) FROM car_expenses
             WHERE date BETWEEN :start_date AND :end_date) AS non_charging_cost,
            (SELECT COALESCE(SUM(amount), 0) FROM charging_records
             WHERE charge_date > :span_from AND charge_date <= :span_to) AS span_charging_cost,
            (SELECT COALESCE(SUM(kwh), 0) FROM charging_records
             WHERE charge_date > :span_from AND charge_date <= :span_to) AS span_energy_kwh,
            (SELECT COALESCE(SUM(amount), 0) FROM car_expenses
             WHERE date > :span_from AND date <= :span_to) AS span_non_charging_cost
    """)
    result = {}
    # Unrounded total cost per km, kept aside for the month-over-month change.
    cost_per_km = {}
    for key, start, end in period_windows(today):
        span_from, span_to, km = odometer_span(readings, start, end) or (None, None, None)
        row = db.execute(query, {
            "start_date": start, "end_date": end,
            "span_from": span_from, "span_to": span_to,
        }).mappings().one()
        span_charging_cost = float(row["span_charging_cost"])
        span_total_cost = span_charging_cost + float(row["span_non_charging_cost"])
        cost_per_km[key] = span_total_cost / km if km else None
        result[key] = {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "is_partial": end == today,
            "total_cost": float(row["charging_cost"]) + float(row["non_charging_cost"]),
            "km_driven": km,
            "measured_from": span_from.isoformat() if km else None,
            "measured_to": span_to.isoformat() if km else None,
            "energy_cost_per_km": _ratio(span_charging_cost, km),
            "total_cost_per_km": _ratio(span_total_cost, km),
            "kwh_per_100km": (
                round(float(row["span_energy_kwh"]) / km * 100, 1) if km else None
            ),
        }
    # Only the comparison survives; the template never reads the prior month.
    result.pop("previous_month")
    current, previous = cost_per_km["current_month"], cost_per_km["previous_month"]
    result["current_month"]["cost_per_km_change_pct"] = (
        round((current / previous - 1) * 100, 1)
        if current is not None and previous
        else None
    )
    return result


def get_charging_by_provider(db: Session):
    """Return charging statistics grouped by provider (Supercharger, Home, etc.).

    Includes total kWh, total cost, and average price per kWh per provider.
    NULLIF protects against division by zero.
    """
    query = text("""
        SELECT
            provider,
            COALESCE(SUM(amount) / NULLIF(SUM(kwh), 0), 0) AS avg_price_per_kwh,
            SUM(amount) FILTER (WHERE amount > 0)
                / NULLIF(SUM(kwh) FILTER (WHERE amount > 0), 0) AS paid_avg_price_per_kwh,
            COALESCE(SUM(kwh) FILTER (WHERE amount = 0), 0) AS free_kwh,
            COUNT(*) FILTER (WHERE amount = 0) AS free_sessions
        FROM charging_records
        GROUP BY provider
        ORDER BY SUM(amount) DESC
    """)
    rows = db.execute(query).mappings().all()

    # serialize_row already rounds floats/Decimals to 2 decimals for JSON
    return [serialize_row(row) for row in rows]


def get_recent_charging_records(db: Session):
    """Return the 10 most recent charging records (newest first)."""
    return fetch_recent(db, "charging_records", CHARGING_COLUMNS, order_col="charge_date")


def get_recent_car_expenses(db: Session):
    """Return the 10 most recent car expense records (newest first)."""
    return fetch_recent(db, "car_expenses", EXPENSE_COLUMNS)


def get_dashboard(db: Session):
    """Return all dashboard data in eleven queries.

    The page used to fetch this over HTTP, one request per widget before that.
    Now app/main.py calls it directly while rendering, so the whole dashboard
    costs one session and no round trip. Every caller passes its own session —
    there is no Depends here, because this is no longer a route.

    Keys are named after the queries that fill them; the template reads them
    straight out of its context.
    """
    return {
        "stats": get_stats(db),
        "data_coverage": get_data_coverage(db),
        "period_summary": get_period_summary(db),
        "charging_providers": get_charging_by_provider(db),
        "recent_charging": get_recent_charging_records(db),
        "recent_expenses": get_recent_car_expenses(db),
    }


@router.post("/charging-records")
def create_charging_record(payload: ChargingRecordCreate, db: Session = Depends(get_db)):
    """Insert a new charging record (protected by x-api-key).

    Used by iPhone Shortcuts or other trusted clients to log a charge session.
    """
    return create_record(db, "charging_records", payload, "Charging record created")


@router.post("/car-expenses")
def create_car_expense(payload: CarExpenseCreate, db: Session = Depends(get_db)):
    """Insert a new car expense record (protected by x-api-key).

    Used by Shortcuts etc. to log one-off car costs (tires, insurance, etc.).
    """
    return create_record(db, "car_expenses", payload, "Car expense created")


@router.post("/odometer")
def create_odometer_reading(payload: OdometerReadingCreate, db: Session = Depends(get_db)):
    """Log a total-odometer reading (protected by x-api-key).

    reading_km is the cumulative number shown on the Tesla screen; the
    dashboard's cost-per-km automatically follows the latest reading. An
    odometer only counts up, so a reading that is lower than an earlier one or
    higher than a later one is a typo and is refused — one bad reading would
    otherwise skew every per-km figure on the dashboard.
    """
    bounds = db.execute(text("""
        SELECT
            (SELECT MAX(reading_km) FROM odometer_readings
             WHERE reading_date <= :reading_date) AS floor_km,
            (SELECT MIN(reading_km) FROM odometer_readings
             WHERE reading_date > :reading_date) AS ceiling_km
    """), {"reading_date": payload.reading_date}).mappings().one()
    if bounds["floor_km"] is not None and payload.reading_km < bounds["floor_km"]:
        raise HTTPException(
            status_code=422,
            detail=f"reading_km is below an earlier reading ({bounds['floor_km']} km)",
        )
    if bounds["ceiling_km"] is not None and payload.reading_km > bounds["ceiling_km"]:
        raise HTTPException(
            status_code=422,
            detail=f"reading_km is above a later reading ({bounds['ceiling_km']} km)",
        )
    return create_record(db, "odometer_readings", payload, "Odometer reading created")


@router.delete("/charging-records/latest")
def delete_latest_charging_record(db: Session = Depends(get_db)):
    """Delete the most recently logged charging record (protected by x-api-key)."""
    return delete_latest_record(
        db, "charging_records", CHARGING_COLUMNS, "Charging record deleted"
    )


@router.delete("/car-expenses/latest")
def delete_latest_car_expense(db: Session = Depends(get_db)):
    """Delete the most recently logged car expense (protected by x-api-key)."""
    return delete_latest_record(db, "car_expenses", EXPENSE_COLUMNS, "Car expense deleted")


@router.delete("/odometer/latest")
def delete_latest_odometer_reading(db: Session = Depends(get_db)):
    """Delete the most recently logged odometer reading (protected by x-api-key)."""
    return delete_latest_record(
        db, "odometer_readings", ODOMETER_COLUMNS, "Odometer reading deleted"
    )
