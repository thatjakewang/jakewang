"""Query and response helpers, used by app/tesla.py.

Keeps the endpoints thin and their responses consistent:
- serialize_value / serialize_row : convert raw DB values into JSON-friendly ones
- create_record                   : shared INSERT -> commit -> envelope flow for POST endpoints
- fetch_recent                    : shared "10 most recent rows" query for the dashboard tables
- get_today                       : timezone-aware "today" helper
"""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings


def serialize_value(value):
    """Convert a single DB value into a JSON-friendly Python value.

    - date / datetime -> ISO-8601 string
    - Decimal         -> int when integral, otherwise float rounded to 2 decimals
    - float           -> rounded to 2 decimals
    - everything else (str, int, None) is returned unchanged
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        number = float(value)
        return int(number) if number.is_integer() else round(number, 2)
    if isinstance(value, float):
        return round(value, 2)
    return value


def serialize_row(row) -> dict:
    """Convert one SQLAlchemy RowMapping into a JSON-friendly dict."""
    return {key: serialize_value(value) for key, value in row.items()}


def _success_response(message: str, data: dict) -> dict:
    """Standard success envelope returned by all write (POST) endpoints.

    Private: every endpoint reaches it through create_record below.
    """
    return {"status": "success", "message": message, "data": data}


def create_record(db: Session, insert_sql: str, payload: BaseModel, message: str) -> dict:
    """Shared body of every write (POST) endpoint.

    Executes an INSERT ... RETURNING statement (parameters come from the
    payload's fields, so the :placeholders must match the model field names),
    commits, and returns the standard success envelope echoing the generated
    columns (id, ...) plus the submitted payload.
    """
    fields = payload.model_dump()
    returned = db.execute(text(insert_sql), fields).mappings().one()
    db.commit()

    return _success_response(
        message,
        {**serialize_row(returned), **serialize_row(fields)},
    )


def fetch_recent(db: Session, table: str, columns: str, order_col: str = "date") -> list[dict]:
    """Return the 10 most recent rows of a table (newest first), JSON-ready.

    Both recent-record tables on the dashboard share this exact shape: order by
    the record's date column, then id (SERIAL, so insertion order) as the
    tie-breaker. `table` / `columns` / `order_col` are hardcoded by callers
    (never user input), so building the SQL with an f-string is safe here.
    """
    rows = db.execute(text(f"""
        SELECT {columns}
        FROM {table}
        ORDER BY {order_col} DESC, id DESC
        LIMIT 10
    """)).mappings().all()

    return [serialize_row(row) for row in rows]


def get_today() -> date:
    """Return today's date in the configured APP_TIMEZONE.

    Falls back to Asia/Taipei if the configured timezone is invalid.
    Used to determine 'today' and 'current month' consistently with the user's
    local time rather than server UTC or DB CURRENT_DATE.
    """
    settings = get_settings()
    try:
        timezone = ZoneInfo(settings.app_timezone)
    except ZoneInfoNotFoundError:
        timezone = ZoneInfo("Asia/Taipei")

    return datetime.now(timezone).date()
