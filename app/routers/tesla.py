"""Tesla router - cost tracking for a personal Tesla (charging + car expenses).

Public read-only stats endpoints plus protected write endpoints (used by iPhone
Shortcuts / automation). All monetary values are stored as integers and kWh as
floats. The id column (SERIAL) provides stable ordering for /recent endpoints.
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


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Return high-level Tesla cost statistics (public).

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


@router.get("/data-coverage")
def get_data_coverage(db: Session = Depends(get_db)):
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


@router.get("/period-summary")
def get_period_summary(db: Session = Depends(get_db)):
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


@router.get("/expenses")
def get_expenses(db: Session = Depends(get_db)):
    """Return car expenses grouped by item (e.g. Insurance, Tires), sorted by total desc. Public."""
    query = text("""
        SELECT item, COALESCE(SUM(amount), 0) AS total_amount
        FROM car_expenses
        GROUP BY item
        ORDER BY total_amount DESC
    """)
    rows = db.execute(query).mappings().all()

    return [serialize_row(row) for row in rows]


@router.get("/charging/providers")
def get_charging_by_provider(db: Session = Depends(get_db)):
    """Return charging statistics grouped by provider (Supercharger, Home, etc.).

    Includes total kWh, total cost, and average price per kWh per provider.
    Public endpoint. NULLIF protects against division by zero.
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


def charging_by_month(db: Session):
    """Return raw month-bucketed totals over charging_records, oldest month first.

    Shared by /charging/monthly-trend and /monthly-summary, which used to run
    near-identical GROUP BY queries; /dashboard fetches these rows once and
    hands them to both. Rows are unserialized on purpose, so each caller keeps
    its own rounding (the trend serializes; the summary divides first).
    """
    return db.execute(text("""
        SELECT
            TO_CHAR(DATE_TRUNC('month', charge_date), 'YYYY-MM') AS month,
            COALESCE(SUM(kwh), 0) AS total_kwh,
            COALESCE(SUM(amount), 0) AS total_amount,
            COALESCE(SUM(amount) / NULLIF(SUM(kwh), 0), 0) AS avg_price_per_kwh
        FROM charging_records
        GROUP BY DATE_TRUNC('month', charge_date)
        ORDER BY DATE_TRUNC('month', charge_date)
    """)).mappings().all()


@router.get("/charging/monthly-trend")
def get_monthly_charging_trend(db: Session = Depends(get_db)):
    """Return month-by-month charging totals and average price per kWh.

    Uses Postgres DATE_TRUNC for monthly bucketing. Ordered chronologically. Public.
    """
    # serialize_row already rounds floats/Decimals to 2 decimals for JSON
    return [serialize_row(row) for row in charging_by_month(db)]


@router.get("/monthly-summary")
def get_monthly_summary(db: Session = Depends(get_db)):
    """Return month-by-month cost & efficiency summary (public).

    Combines all three tables per calendar month:
    - charging_records : charging cost + energy charged
    - car_expenses     : all other car spending
    - odometer_readings: km driven = this month's last reading minus the
      previous reading-month's last reading (gaps between reading months are
      attributed to the later month)

    Derived fields (cost_per_km, kwh_per_100km) are null when a month has no
    odometer delta to divide by; months with no activity at all are absent.
    No page renders this any more — the dashboard's monthly charts were removed
    with Chart.js. Kept as a slice for anything that wants the history.
    """
    return build_monthly_summary(db, charging_by_month(db))


def build_monthly_summary(db: Session, charging_rows) -> list[dict]:
    """Body of /monthly-summary, with the charging aggregate passed in.

    Split out so /dashboard can reuse rows already fetched for the monthly
    trend instead of querying charging_records a second time.
    """
    expense_rows = db.execute(text("""
        SELECT
            TO_CHAR(DATE_TRUNC('month', date), 'YYYY-MM') AS month,
            SUM(amount) AS amount
        FROM car_expenses
        GROUP BY DATE_TRUNC('month', date)
    """)).mappings().all()

    odometer_rows = db.execute(text("""
        SELECT DISTINCT ON (DATE_TRUNC('month', reading_date))
            TO_CHAR(DATE_TRUNC('month', reading_date), 'YYYY-MM') AS month,
            reading_km
        FROM odometer_readings
        ORDER BY DATE_TRUNC('month', reading_date), reading_date DESC, id DESC
    """)).mappings().all()

    # km driven per month: delta between consecutive reading months
    km_by_month: dict[str, int] = {}
    prev_reading = None
    for row in odometer_rows:
        reading = int(row["reading_km"])
        if prev_reading is not None:
            km_by_month[row["month"]] = reading - prev_reading
        prev_reading = reading

    charging_months = {row["month"]: row for row in charging_rows}
    expenses_by_month = {row["month"]: int(row["amount"] or 0) for row in expense_rows}

    months = sorted(set(charging_months) | set(expenses_by_month) | set(km_by_month))

    result = []
    for month in months:
        charging = charging_months.get(month)
        charging_amount = int(charging["total_amount"] or 0) if charging else 0
        kwh = float(charging["total_kwh"] or 0) if charging else 0.0
        total_cost = charging_amount + expenses_by_month.get(month, 0)
        km = km_by_month.get(month)

        result.append({
            "month": month,
            "km_driven": km,
            "total_cost": total_cost,
            "charging_cost": charging_amount,
            "non_charging_cost": expenses_by_month.get(month, 0),
            "cost_per_km": round(total_cost / km, 2) if km else None,
            "energy_cost_per_km": round(charging_amount / km, 2) if km else None,
            "kwh": round(kwh, 1),
            "kwh_per_100km": round(kwh / km * 100, 1) if km else None,
        })

    return result


@router.get("/charging/sessions")
def get_charging_sessions(db: Session = Depends(get_db)):
    """Return every charging session (date, provider, amount, kWh). Public.

    Unlike /charging/recent (capped at 10), this returns the full history so the
    frontend can plot the per-session cost distribution (kWh vs. amount scatter).
    Personal use keeps this table small, so returning every row is fine.
    """
    query = text("""
        SELECT charge_date, provider, amount, kwh
        FROM charging_records
        ORDER BY charge_date
    """)
    rows = db.execute(query).mappings().all()

    return [serialize_row(row) for row in rows]


@router.get("/charging/recent")
def get_recent_charging_records(db: Session = Depends(get_db)):
    """Return the 10 most recent charging records (newest first). Public."""
    return fetch_recent(
        db, "charging_records", "id, charge_date, provider, amount, kwh",
        order_col="charge_date",
    )


@router.get("/expenses/recent")
def get_recent_car_expenses(db: Session = Depends(get_db)):
    """Return the 10 most recent car expense records (newest first). Public."""
    return fetch_recent(db, "car_expenses", "id, date, item, amount")


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    """Return every payload the Tesla dashboard needs, in one response (public).

    The Tesla frontend used to fire ten parallel requests on page load, each
    opening its own DB session for a handful of small aggregates. This endpoint
    is what the page actually fetches now: one request, one session, and the
    charging-by-month aggregate is shared between the trend and the summary
    instead of being run twice (15 queries -> 14).

    The individual endpoints below each key are all still routed and tested;
    they stay the stable public API for anything that wants one slice (iPhone
    Shortcuts, ad-hoc curl). Handlers are called directly with the session
    rather than through FastAPI, so Depends(get_db) never fires a second time.

    Keys mirror the paths they replace, so tests that assert on a single
    endpoint's shape cover the aggregate's contents too.
    """
    monthly_charging = charging_by_month(db)
    return {
        "stats": get_stats(db),
        "data_coverage": get_data_coverage(db),
        "period_summary": get_period_summary(db),
        "expenses": get_expenses(db),
        "charging_providers": get_charging_by_provider(db),
        "charging_sessions": get_charging_sessions(db),
        "charging_monthly_trend": [serialize_row(row) for row in monthly_charging],
        "monthly_summary": build_monthly_summary(db, monthly_charging),
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


@router.get("/odometer/current")
def get_current_odometer(db: Session = Depends(get_db)):
    """Return the latest known total odometer in km (public, for the dashboard)."""
    return {"odometer_km": get_latest_odometer(db)}


@router.get("/odometer/recent")
def get_recent_odometer_readings(db: Session = Depends(get_db)):
    """Return the 10 most recent odometer readings (newest first). Public."""
    return fetch_recent(
        db, "odometer_readings", "id, reading_km, reading_date",
        order_col="reading_date",
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
