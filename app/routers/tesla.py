"""Tesla cost tracking for a personal Tesla (charging + car expenses).

Three protected write endpoints, used by iPhone Shortcuts, plus the read
queries behind them. The reads are plain functions rather than routes: the
only thing that wants them is the server-rendered dashboard, which calls
get_dashboard() directly (see app/main.py). They were HTTP endpoints while the
page fetched its own data — nothing did after that, so the routes went.

All monetary values are stored as integers and kWh as floats. The id column
(SERIAL) provides stable ordering for the recent-record queries.
"""

from calendar import monthrange
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import verify_shortcut_api_key
from app.utils import create_record, fetch_recent, get_today, serialize_row

router = APIRouter()
settings = get_settings()


class ChargingRecordCreate(BaseModel):
    """Payload for creating a charging record (Tesla Supercharger, etc.)."""
    charge_date: date
    provider: str = Field(min_length=1, max_length=100)
    amount: int = Field(ge=0)
    kwh: float = Field(ge=0)


class CarExpenseCreate(BaseModel):
    """Payload for recording a car-related expense (insurance, maintenance, etc.)."""
    date: date
    item: str = Field(min_length=1, max_length=100)
    amount: int = Field(ge=0)


class OdometerReadingCreate(BaseModel):
    """Payload for logging a total-odometer reading (the number shown on the car screen)."""
    reading_km: int = Field(ge=0)
    # get_today (not date.today) so the default respects APP_TIMEZONE, matching
    # every other date computation in the app (server clock runs on UTC).
    reading_date: date = Field(default_factory=get_today)


def get_latest_odometer(db: Session) -> int:
    """Return the most recent odometer reading, or the config seed if none exist yet."""
    reading = db.execute(text("""
        SELECT reading_km
        FROM odometer_readings
        ORDER BY reading_date DESC, id DESC
        LIMIT 1
    """)).scalar()
    return int(reading) if reading is not None else settings.tesla_odometer_km


def get_stats(db: Session):
    """Return high-level Tesla cost statistics.

    Includes lifetime totals, average price per kWh, and cost per km based on
    the latest odometer reading. All queries are simple aggregates over the
    entire history (personal use, tables stay small).
    """
    totals_query = text("""
        SELECT
            (SELECT COALESCE(SUM(amount), 0) FROM car_expenses) AS car_expense_total,
            (SELECT COALESCE(SUM(amount), 0) FROM charging_records) AS charging_cost,
            (SELECT COALESCE(SUM(kwh), 0) FROM charging_records) AS energy_kwh
    """)

    totals = db.execute(totals_query).mappings().one()

    car_expense_total = float(totals["car_expense_total"])
    charging_cost = float(totals["charging_cost"])
    energy_kwh = float(totals["energy_kwh"])

    total_cost = car_expense_total + charging_cost
    avg_price_per_kwh = round(charging_cost / energy_kwh, 2) if energy_kwh else 0

    odometer_km = get_latest_odometer(db)
    cost_per_km = round(total_cost / odometer_km, 2) if odometer_km else 0

    return {
        "total_cost": total_cost,
        "charging_cost": charging_cost,
        "non_charging_cost": car_expense_total,
        "energy_kwh": round(energy_kwh, 2),
        "avg_price_per_kwh": avg_price_per_kwh,
        "odometer_km": odometer_km,
        "cost_per_km": cost_per_km,
        "charging_cost_per_km": (
            round(charging_cost / odometer_km, 2) if odometer_km else 0
        ),
        "non_charging_cost_per_km": (
            round(car_expense_total / odometer_km, 2) if odometer_km else 0
        ),
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


def get_period_summary(db: Session):
    """Summarize this month, the previous month, and the trailing 90 days.

    Distance is measured between the last odometer reading before a period and
    the last reading within it. It is null when either boundary is unavailable.
    """
    today = get_today()
    this_month = today.replace(day=1)
    previous_month_end = this_month - timedelta(days=1)
    previous_month = previous_month_end.replace(day=1)
    # Compare MTD with the same number of elapsed days in the prior month.
    previous_comparable_end = previous_month.replace(
        day=min(today.day, monthrange(previous_month.year, previous_month.month)[1])
    )
    periods = (
        ("current_month", this_month, today),
        ("previous_month", previous_month, previous_comparable_end),
        ("trailing_90_days", today - timedelta(days=89), today),
    )
    result = {}
    query = text("""
        SELECT
            COALESCE((SELECT SUM(amount) FROM charging_records
                      WHERE charge_date BETWEEN :start_date AND :end_date), 0) AS charging_cost,
            COALESCE((SELECT SUM(kwh) FROM charging_records
                      WHERE charge_date BETWEEN :start_date AND :end_date), 0) AS energy_kwh,
            COALESCE((SELECT SUM(amount) FROM car_expenses
                      WHERE date BETWEEN :start_date AND :end_date), 0) AS non_charging_cost,
            (SELECT reading_km FROM odometer_readings
             WHERE reading_date <= :end_date
             ORDER BY reading_date DESC, id DESC LIMIT 1) AS ending_odometer,
            (SELECT reading_km FROM odometer_readings
             WHERE reading_date < :start_date
             ORDER BY reading_date DESC, id DESC LIMIT 1) AS starting_odometer
    """)
    for key, start, end in periods:
        row = db.execute(
            query, {"start_date": start, "end_date": end}
        ).mappings().one()
        charging_cost = float(row["charging_cost"] or 0)
        non_charging_cost = float(row["non_charging_cost"] or 0)
        energy_kwh = float(row["energy_kwh"] or 0)
        start_km = row["starting_odometer"]
        end_km = row["ending_odometer"]
        km = (
            int(end_km) - int(start_km)
            if start_km is not None and end_km is not None
            else None
        )
        if km is not None and km <= 0:
            km = None
        total_cost = charging_cost + non_charging_cost
        result[key] = {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "is_partial": end == today,
            "charging_cost": charging_cost,
            "non_charging_cost": non_charging_cost,
            "total_cost": total_cost,
            "energy_kwh": round(energy_kwh, 2),
            "km_driven": km,
            "energy_cost_per_km": round(charging_cost / km, 2) if km else None,
            "total_cost_per_km": round(total_cost / km, 2) if km else None,
            "kwh_per_100km": round(energy_kwh / km * 100, 1) if km else None,
        }
    current = result["current_month"]
    previous = result["previous_month"]
    current["cost_per_km_change_pct"] = (
        round((current["total_cost_per_km"] / previous["total_cost_per_km"] - 1) * 100, 1)
        if current["total_cost_per_km"] is not None
        and previous["total_cost_per_km"] not in (None, 0)
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
            COALESCE(SUM(kwh), 0) AS total_kwh,
            COALESCE(SUM(amount), 0) AS total_amount,
            COALESCE(SUM(amount) / NULLIF(SUM(kwh), 0), 0) AS avg_price_per_kwh,
            COALESCE(SUM(kwh) FILTER (WHERE amount > 0), 0) AS paid_kwh,
            SUM(amount) FILTER (WHERE amount > 0)
                / NULLIF(SUM(kwh) FILTER (WHERE amount > 0), 0) AS paid_avg_price_per_kwh,
            COALESCE(SUM(kwh) FILTER (WHERE amount = 0), 0) AS free_kwh,
            COUNT(*) FILTER (WHERE amount = 0) AS free_sessions
        FROM charging_records
        GROUP BY provider
        ORDER BY total_amount DESC
    """)
    rows = db.execute(query).mappings().all()

    # serialize_row already rounds floats/Decimals to 2 decimals for JSON
    return [serialize_row(row) for row in rows]


def get_recent_charging_records(db: Session):
    """Return the 10 most recent charging records (newest first)."""
    return fetch_recent(
        db, "charging_records", "id, charge_date, provider, amount, kwh",
        order_col="charge_date",
    )


def get_recent_car_expenses(db: Session):
    """Return the 10 most recent car expense records (newest first)."""
    return fetch_recent(db, "car_expenses", "id, date, item, amount")


def get_dashboard(db: Session):
    """Return every number the dashboard shows, from one session: nine queries.

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
def create_charging_record(
    payload: ChargingRecordCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_shortcut_api_key),
):
    """Insert a new charging record (protected by x-api-key).

    Used by iPhone Shortcuts or other trusted clients to log a charge session.
    """
    return create_record(
        db,
        """
        INSERT INTO charging_records (charge_date, provider, amount, kwh)
        VALUES (:charge_date, :provider, :amount, :kwh)
        RETURNING id
        """,
        payload,
        "Charging record created",
    )


@router.post("/car-expenses")
def create_car_expense(
    payload: CarExpenseCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_shortcut_api_key),
):
    """Insert a new car expense record (protected by x-api-key).

    Used by Shortcuts etc. to log one-off car costs (tires, insurance, etc.).
    """
    return create_record(
        db,
        """
        INSERT INTO car_expenses (date, item, amount)
        VALUES (:date, :item, :amount)
        RETURNING id
        """,
        payload,
        "Car expense created",
    )


@router.post("/odometer")
def create_odometer_reading(
    payload: OdometerReadingCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_shortcut_api_key),
):
    """Log a total-odometer reading (protected by x-api-key).

    reading_km is the cumulative number shown on the Tesla screen; cost-per-km
    in /stats automatically follows the latest reading.
    """
    return create_record(
        db,
        """
        INSERT INTO odometer_readings (reading_km, reading_date)
        VALUES (:reading_km, :reading_date)
        RETURNING id
        """,
        payload,
        "Odometer reading created",
    )
