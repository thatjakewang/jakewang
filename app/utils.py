"""Query and response helpers, used by app/tesla.py.

Keeps the endpoints thin and their responses consistent:
- serialize_value / serialize_row : convert raw DB values into JSON-friendly ones
- create_record                   : shared INSERT -> commit -> envelope flow for POST endpoints
- delete_latest_record            : shared undo for the DELETE .../latest endpoints
- fetch_recent                    : shared "10 most recent rows" query for the dashboard tables
- get_today                       : timezone-aware "today" helper
"""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
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


def create_record(db: Session, table: str, payload: BaseModel, message: str) -> dict:
    """Shared body of every write (POST) endpoint.

    Inserts the payload (its field names are the column names), commits, and
    returns the standard success envelope echoing the generated id plus the
    submitted payload. `table` is hardcoded by callers and the columns come
    from the model, never from user input, so the f-strings are safe here.

    A Shortcut that times out retries, and nothing in the tables can tell a
    retry from a second record. So an identical row created in the last two
    minutes is treated as the same request: its id is returned and nothing is
    inserted. Logging a true duplicate (two identical tolls) means waiting
    out the window.
    """
    fields = payload.model_dump()
    columns = list(fields)
    returned = db.execute(text(f"""
        SELECT id
        FROM {table}
        WHERE {" AND ".join(f"{column} = :{column}" for column in columns)}
          AND created_at > CURRENT_TIMESTAMP - INTERVAL '2 minutes'
        ORDER BY id DESC
        LIMIT 1
    """), fields).mappings().first()
    if returned is None:
        returned = db.execute(text(f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({", ".join(f":{column}" for column in columns)})
            RETURNING id
        """), fields).mappings().one()
        db.commit()

    return _success_response(
        message,
        {**serialize_row(returned), **serialize_row(fields)},
    )


def delete_latest_record(db: Session, table: str, columns: str, message: str) -> dict:
    """Shared body of every DELETE .../latest endpoint.

    Removes the most recently inserted row (highest id, so the last thing a
    Shortcut logged, whatever date it carries) and returns it in the standard
    envelope, so the caller can see exactly what went. 404 on an empty table.
    `table` / `columns` are hardcoded by callers, as in fetch_recent.
    """
    deleted = db.execute(text(f"""
        DELETE FROM {table}
        WHERE id = (SELECT MAX(id) FROM {table})
        RETURNING id, {columns}
    """)).mappings().first()
    if deleted is None:
        raise HTTPException(status_code=404, detail="No records to delete")
    db.commit()

    return _success_response(message, serialize_row(deleted))


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
