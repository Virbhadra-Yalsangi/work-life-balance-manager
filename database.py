
from contextlib import contextmanager
import os
import sqlite3
from pathlib import Path
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd


# --------------------------------------------------
# DATABASE PATH
# --------------------------------------------------

APP_DIR = Path(__file__).resolve().parent

DATA_DB = APP_DIR / "data" / "work_life_balance.db"
ROOT_DB = APP_DIR / "work_life_balance.db"

# Tests can override this path.
if os.environ.get("WLB_DB_PATH"):
    DB_PATH = Path(os.environ["WLB_DB_PATH"])
elif DATA_DB.exists():
    DB_PATH = DATA_DB
elif ROOT_DB.exists():
    DB_PATH = ROOT_DB
else:
    DB_PATH = DATA_DB


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

@contextmanager
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(DB_PATH),
        timeout=10
    )

    connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
    finally:
        connection.close()


# --------------------------------------------------
# INITIALIZE DATABASE
# --------------------------------------------------

def initialize_database():
    """Create the application tables without deleting existing records."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_date TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                duration_hours REAL NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT ''
            )
        """)

        # Keep older databases compatible if these columns are absent.
        activity_columns = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(activities)"
            ).fetchall()
        }
        if "notes" not in activity_columns:
            conn.execute("ALTER TABLE activities ADD COLUMN notes TEXT DEFAULT ''")
        if "created_at" not in activity_columns:
            conn.execute("ALTER TABLE activities ADD COLUMN created_at TEXT DEFAULT ''")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS planned_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_date TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                notes TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Planned',
                created_at TEXT NOT NULL DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                planned_activity_id INTEGER NOT NULL,
                reminder_at TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'in_app',
                status TEXT NOT NULL DEFAULT 'Pending',
                sent_at TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                failure_reason TEXT DEFAULT '',
                FOREIGN KEY (planned_activity_id)
                    REFERENCES planned_activities(id)
                    ON DELETE CASCADE
            )
        """)

        # Add failure_reason safely to existing databases. Existing rows remain intact.
        reminder_columns = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(reminders)"
            ).fetchall()
        }
        if "failure_reason" not in reminder_columns:
            conn.execute(
                "ALTER TABLE reminders ADD COLUMN failure_reason TEXT DEFAULT ''"
            )

        conn.commit()

# --------------------------------------------------
# DAILY TOTAL
# --------------------------------------------------

def get_daily_total(activity_date, exclude_id=None):

    query = """
        SELECT COALESCE(SUM(duration_hours), 0)
        FROM activities
        WHERE activity_date = ?
    """

    params = [activity_date.isoformat()]

    if exclude_id is not None:
        query += " AND id != ?"
        params.append(int(exclude_id))

    with get_connection() as conn:
        result = conn.execute(
            query,
            params
        ).fetchone()

    return float(result[0])


# --------------------------------------------------
# LOAD ACTIVITIES
# --------------------------------------------------

def load_activities(start_date, end_date):

    with get_connection() as conn:

        df = pd.read_sql_query(
            """
            SELECT
                id,
                activity_date,
                activity_type,
                duration_hours,
                notes,
                created_at
            FROM activities
            WHERE activity_date BETWEEN ? AND ?
            ORDER BY activity_date DESC, id DESC
            """,
            conn,
            params=(
                start_date.isoformat(),
                end_date.isoformat()
            )
        )

    if not df.empty:
        df["activity_date"] = pd.to_datetime(
            df["activity_date"]
        ).dt.date

    return df


# --------------------------------------------------
# SAVE ACTIVITY
# --------------------------------------------------

def save_activity(activity_date, activity_type, hours, notes):

    hours = float(hours)

    if hours <= 0 or hours > 24:
        return False, (
            "Duration must be greater than 0 "
            "and at most 24 hours."
        )

    existing_hours = get_daily_total(activity_date)

    if existing_hours + hours > 24:
        return False, (
            f"This date already has {existing_hours:.2f} hours. "
            f"Adding {hours:.2f} would exceed 24 hours."
        )

    with get_connection() as conn:

        conn.execute(
            """
            INSERT INTO activities (
                activity_date,
                activity_type,
                duration_hours,
                notes,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                activity_date.isoformat(),
                activity_type,
                hours,
                notes.strip(),
                datetime.now().isoformat(timespec="seconds")
            )
        )

        conn.commit()

    return True, "Activity saved successfully!"


# --------------------------------------------------
# UPDATE ACTIVITY
# --------------------------------------------------

def update_activity(
    record_id,
    new_date,
    new_type,
    new_hours,
    new_notes
):

    new_hours = float(new_hours)

    if new_hours <= 0 or new_hours > 24:
        return False, (
            "Duration must be greater than 0 "
            "and at most 24 hours."
        )

    other_hours = get_daily_total(
        new_date,
        exclude_id=record_id
    )

    if other_hours + new_hours > 24:
        return False, (
            f"The selected date already has "
            f"{other_hours:.2f} other hours. "
            "The updated total would exceed 24 hours."
        )

    with get_connection() as conn:

        cursor = conn.execute(
            """
            UPDATE activities
            SET
                activity_date = ?,
                activity_type = ?,
                duration_hours = ?,
                notes = ?
            WHERE id = ?
            """,
            (
                new_date.isoformat(),
                new_type,
                new_hours,
                new_notes.strip(),
                int(record_id)
            )
        )

        conn.commit()

        if cursor.rowcount == 0:
            return False, (
                "Record not found. Refresh and try again."
            )

    return True, "Activity updated successfully!"


# --------------------------------------------------
# DELETE ACTIVITY
# --------------------------------------------------

def delete_activity(record_id):

    with get_connection() as conn:

        cursor = conn.execute(
            "DELETE FROM activities WHERE id = ?",
            (int(record_id),)
        )

        conn.commit()

    return cursor.rowcount > 0

# ============================================================
# ACTIVITY PLANNER DATABASE FUNCTIONS
# ============================================================

def _normalise_activity_date(value):
    """Convert a date, datetime or ISO date string into a date object."""
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        return date.fromisoformat(value.strip())

    raise ValueError("Invalid activity date.")


def _normalise_activity_time(value):
    """Convert a time object or time string into HH:MM format."""
    if isinstance(value, datetime):
        value = value.time()

    if isinstance(value, time):
        return value.strftime("%H:%M")

    if isinstance(value, str):
        value = value.strip()

        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).strftime("%H:%M")
            except ValueError:
                continue

    raise ValueError("Invalid activity time. Use HH:MM format.")


def _build_reminder_values(activity_id, activity_date, start_time, now=None):
    """Build three reminder rows if the five-minute reminder is still ahead."""
    timezone = ZoneInfo("Asia/Kolkata")
    current_time = now or datetime.now(timezone)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone)
    else:
        current_time = current_time.astimezone(timezone)

    activity_start = datetime.combine(
        activity_date,
        datetime.strptime(start_time, "%H:%M").time(),
    ).replace(tzinfo=timezone)
    reminder_at = activity_start - timedelta(minutes=5)

    if reminder_at <= current_time:
        return []

    reminder_text = reminder_at.isoformat(timespec="seconds")
    created_text = current_time.isoformat(timespec="seconds")
    return [
        (activity_id, reminder_text, channel, "Pending", created_text)
        for channel in ("sms", "voice", "email")
    ]


def save_planned_activity(
    activity_date,
    activity_type,
    start_time,
    end_time,
    notes="",
):
    """Save a planned activity and its future SMS, voice and email reminders."""
    try:
        activity_date = _normalise_activity_date(activity_date)
        start_time = _normalise_activity_time(start_time)
        end_time = _normalise_activity_time(end_time)

        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        if end <= start:
            return False, "End time must be later than start time."

        activity_type = (activity_type or "").strip()
        if not activity_type:
            return False, "Please select an activity."
        notes = (notes or "").strip()
    except (ValueError, TypeError, AttributeError):
        return False, "Please enter valid activity details."

    timezone = ZoneInfo("Asia/Kolkata")
    created_at = datetime.now(timezone).isoformat(timespec="seconds")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO planned_activities (
                activity_date, activity_type, start_time, end_time,
                notes, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, 'Planned', ?)
            """,
            (
                activity_date.isoformat(), activity_type, start_time,
                end_time, notes, created_at,
            ),
        )
        activity_id = cursor.lastrowid

        reminder_rows = _build_reminder_values(
            activity_id, activity_date, start_time
        )
        if reminder_rows:
            conn.executemany(
                """
                INSERT INTO reminders (
                    planned_activity_id, reminder_at, channel, status, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                reminder_rows,
            )
        conn.commit()

    return True, "Planned activity saved successfully!"


def load_planned_activities(start_date, end_date):
    """Load planned activities within a selected date range."""

    try:
        start_date = _normalise_activity_date(start_date)
        end_date = _normalise_activity_date(end_date)

        if end_date < start_date:
            return pd.DataFrame()

    except (ValueError, TypeError, AttributeError):
        return pd.DataFrame()

    with get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT
                id,
                activity_date,
                activity_type,
                start_time,
                end_time,
                notes,
                status,
                created_at
            FROM planned_activities
            WHERE activity_date BETWEEN ? AND ?
            ORDER BY activity_date ASC, start_time ASC
            """,
            conn,
            params=(
                start_date.isoformat(),
                end_date.isoformat(),
            ),
        )

    if not df.empty:
        df["activity_date"] = pd.to_datetime(
            df["activity_date"]
        ).dt.date

    return df


def update_planned_activity(
    record_id,
    activity_date,
    activity_type,
    start_time,
    end_time,
    notes="",
):
    """Update a planned activity and refresh its pending reminders."""
    try:
        record_id = int(record_id)
        activity_date = _normalise_activity_date(activity_date)
        start_time = _normalise_activity_time(start_time)
        end_time = _normalise_activity_time(end_time)

        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        if end <= start:
            return False, "End time must be later than start time."

        activity_type = (activity_type or "").strip()
        if not activity_type:
            return False, "Please select an activity."
        notes = (notes or "").strip()
    except (ValueError, TypeError, AttributeError):
        return False, "Please enter valid activity details."

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE planned_activities
            SET activity_date = ?, activity_type = ?, start_time = ?,
                end_time = ?, notes = ?
            WHERE id = ?
            """,
            (
                activity_date.isoformat(), activity_type, start_time,
                end_time, notes, record_id,
            ),
        )
        if cursor.rowcount == 0:
            return False, "Planned activity not found."

        # Only pending reminders are replaced. Sent/processing history is retained.
        conn.execute(
            "DELETE FROM reminders WHERE planned_activity_id = ? AND status = 'Pending'",
            (record_id,),
        )

        status_row = conn.execute(
            "SELECT status FROM planned_activities WHERE id = ?",
            (record_id,),
        ).fetchone()
        if status_row and status_row[0] == "Planned":
            reminder_rows = _build_reminder_values(
                record_id, activity_date, start_time
            )
            if reminder_rows:
                conn.executemany(
                    """
                    INSERT INTO reminders (
                        planned_activity_id, reminder_at, channel, status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    reminder_rows,
                )
        conn.commit()

    return True, "Planned activity updated successfully!"


def update_planned_activity_status(record_id, new_status):
    """Change activity status and cancel pending reminders when appropriate."""
    allowed_statuses = ["Planned", "Completed", "Cancelled"]
    if new_status not in allowed_statuses:
        return False, "Invalid activity status."

    try:
        record_id = int(record_id)
    except (ValueError, TypeError):
        return False, "Invalid activity ID."

    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE planned_activities SET status = ? WHERE id = ?",
            (new_status, record_id),
        )
        if cursor.rowcount == 0:
            return False, "Planned activity not found."

        if new_status != "Planned":
            conn.execute(
                "UPDATE reminders SET status = 'Cancelled' "
                "WHERE planned_activity_id = ? AND status = 'Pending'",
                (record_id,),
            )
        else:
            activity = conn.execute(
                """
                SELECT activity_date, start_time
                FROM planned_activities WHERE id = ?
                """,
                (record_id,),
            ).fetchone()
            # Recreate reminders only if no pending reminders currently exist.
            pending_count = conn.execute(
                "SELECT COUNT(*) FROM reminders "
                "WHERE planned_activity_id = ? AND status = 'Pending'",
                (record_id,),
            ).fetchone()[0]
            if activity and pending_count == 0:
                reminder_rows = _build_reminder_values(
                    record_id, date.fromisoformat(activity[0]), activity[1]
                )
                if reminder_rows:
                    conn.executemany(
                        """
                        INSERT INTO reminders (
                            planned_activity_id, reminder_at, channel, status, created_at
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        reminder_rows,
                    )
        conn.commit()

    return True, "Activity status updated successfully!"


def delete_planned_activity(record_id):
    """Delete a planned activity and its associated reminder rows."""
    try:
        record_id = int(record_id)
    except (ValueError, TypeError):
        return False

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM reminders WHERE planned_activity_id = ?",
            (record_id,),
        )
        cursor = conn.execute(
            "DELETE FROM planned_activities WHERE id = ?",
            (record_id,),
        )
        conn.commit()

    return cursor.rowcount > 0



def load_reminder_history(start_date=None, end_date=None):
    """Load notification attempts with their activity details and failure reason."""
    query = """
        SELECT
            r.id AS reminder_id,
            r.planned_activity_id AS activity_id,
            p.activity_date,
            p.start_time,
            p.end_time,
            p.activity_type,
            p.status AS activity_status,
            r.reminder_at,
            r.channel,
            r.status AS reminder_status,
            r.sent_at,
            COALESCE(r.failure_reason, '') AS failure_reason
        FROM reminders r
        INNER JOIN planned_activities p
            ON p.id = r.planned_activity_id
    """
    params = []
    filters = []
    if start_date is not None:
        start_value = _normalise_activity_date(start_date).isoformat()
        filters.append("p.activity_date >= ?")
        params.append(start_value)
    if end_date is not None:
        end_value = _normalise_activity_date(end_date).isoformat()
        filters.append("p.activity_date <= ?")
        params.append(end_value)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY r.reminder_at ASC, r.id ASC"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)
