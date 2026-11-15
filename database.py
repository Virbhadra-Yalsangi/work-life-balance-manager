
from contextlib import contextmanager
import os
import sqlite3
from pathlib import Path
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv


# Read ENABLED_CHANNELS etc. from .env, even when only the dashboard runs.
load_dotenv(Path(__file__).resolve().parent / ".env")

ALL_CHANNELS = ("sms", "voice", "email", "telegram")


def get_enabled_channels():
    """
    Channels that should get reminders, from ENABLED_CHANNELS in .env
    (comma separated, e.g. "email,telegram"). Default: sms, voice and email.
    """
    raw = os.getenv("ENABLED_CHANNELS")
    if raw is None or not raw.strip():
        return ("sms", "voice", "email")
    chosen = [c.strip().lower() for c in raw.split(",")]
    return tuple(c for c in ALL_CHANNELS if c in chosen)


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
        # Links a dashboard record to the completed plan that created it.
        if "planned_activity_id" not in activity_columns:
            conn.execute("ALTER TABLE activities ADD COLUMN planned_activity_id INTEGER")

        # The user's own weekly goals (hours per week per category).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS category_goals (
                category TEXT PRIMARY KEY,
                weekly_hours REAL NOT NULL,
                updated_at TEXT NOT NULL DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS planned_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_date TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                notes TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Planned',
                created_at TEXT NOT NULL DEFAULT '',
                activity_failure_reason TEXT DEFAULT ''
            )
        """)

        # Add the activity-level failure reason without changing existing records.
        planned_columns = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(planned_activities)"
            ).fetchall()
        }
        if "activity_failure_reason" not in planned_columns:
            conn.execute(
                "ALTER TABLE planned_activities "
                "ADD COLUMN activity_failure_reason TEXT DEFAULT ''"
            )

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
    """Build one reminder row per enabled channel if the 5-minute reminder is still ahead."""
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
        for channel in sorted(get_enabled_channels())
    ]


def load_goal_hours():
    """Return the user's saved weekly goals as {category: hours}."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT category, weekly_hours FROM category_goals"
        ).fetchall()
    return {category: hours for category, hours in rows}


def save_goal_hours(hours_by_category):
    """Save (insert or overwrite) weekly goals in one transaction."""
    stamp = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO category_goals (category, weekly_hours, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(category) DO UPDATE SET
                weekly_hours = excluded.weekly_hours,
                updated_at = excluded.updated_at
            """,
            [(c, float(h), stamp) for c, h in hours_by_category.items()],
        )
        conn.commit()


def reset_goal_hours():
    """Delete the saved goals so the defaults apply again."""
    with get_connection() as conn:
        conn.execute("DELETE FROM category_goals")
        conn.commit()


def _sync_completed_activity(conn, record_id):
    """
    Keep the dashboard activity log in step with a planned activity.

    Completed plan  -> one dashboard record (duration = end - start).
    Any other status -> that auto-created record is removed.
    Returns a warning string when hours could not be logged, else "".
    """
    conn.execute(
        "DELETE FROM activities WHERE planned_activity_id = ?", (record_id,)
    )
    plan = conn.execute(
        """
        SELECT activity_date, activity_type, start_time, end_time, notes, status
        FROM planned_activities WHERE id = ?
        """,
        (record_id,),
    ).fetchone()
    if not plan or plan[5] != "Completed":
        return ""

    activity_date, activity_type, start_time, end_time, notes, _ = plan
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    hours = round((end - start).total_seconds() / 3600, 2)

    existing = conn.execute(
        "SELECT COALESCE(SUM(duration_hours), 0) FROM activities WHERE activity_date = ?",
        (activity_date,),
    ).fetchone()[0]
    if existing + hours > 24:
        return (
            f" Note: {hours:.2f} h were NOT added to the dashboard because "
            f"{activity_date} already has {existing:.2f} h logged (24 h limit)."
        )

    note_text = f"Completed plan #{record_id}"
    if notes:
        note_text += f": {notes}"
    conn.execute(
        """
        INSERT INTO activities (
            activity_date, activity_type, duration_hours, notes,
            created_at, planned_activity_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            activity_date, activity_type, hours, note_text,
            datetime.now().isoformat(timespec="seconds"), record_id,
        ),
    )
    return f" {hours:.2f} h added to the dashboard activity log."


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
                created_at,
                COALESCE(activity_failure_reason, '') AS activity_failure_reason
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


def update_planned_activity_status(record_id, new_status, failure_reason=""):
    """Update the activity status independently from notification statuses."""
    allowed_statuses = ["Planned", "Completed", "Failed", "Cancelled"]
    if new_status not in allowed_statuses:
        return False, "Invalid activity status."

    try:
        record_id = int(record_id)
    except (ValueError, TypeError):
        return False, "Invalid activity ID."

    with get_connection() as conn:
        reason = (failure_reason or "").strip()[:500]
        if new_status == "Failed" and not reason:
            reason = "Marked Failed manually."
        elif new_status != "Failed":
            reason = ""
        cursor = conn.execute(
            """
            UPDATE planned_activities
            SET status = ?, activity_failure_reason = ?
            WHERE id = ?
            """,
            (new_status, reason, record_id),
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
        extra = _sync_completed_activity(conn, record_id)
        conn.commit()

    return True, "Activity status updated successfully!" + extra


def mark_overdue_activities_failed(now=None):
    """
    Mark activities as Failed when their planned end time has passed
    and they are still Planned. This does not alter notification outcomes.
    """
    timezone = ZoneInfo("Asia/Kolkata")
    current_time = now or datetime.now(timezone)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone)
    else:
        current_time = current_time.astimezone(timezone)

    current_iso = current_time.isoformat(timespec="seconds")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE planned_activities
            SET status = 'Failed',
                activity_failure_reason =
                    'Planned ' || start_time || ' to ' || end_time || ' on '
                    || activity_date || '. End time passed and it was not '
                    || 'marked Completed, so it was auto-marked Failed. '
                    || 'If you did it, set status to Completed.'
            WHERE status = 'Planned'
              AND (activity_date || 'T' || end_time) <= ?
            """,
            (current_iso,),
        )
        # Do not send notifications for activities that have already failed.
        conn.execute(
            """
            UPDATE reminders
            SET status = 'Cancelled',
                failure_reason = 'Activity was marked Failed after its end time.'
            WHERE status = 'Pending'
              AND planned_activity_id IN (
                  SELECT id FROM planned_activities WHERE status = 'Failed'
              )
            """
        )
        conn.commit()
        return cursor.rowcount


def delete_planned_activity(record_id):
    """Delete a planned activity and its associated reminder rows."""
    try:
        record_id = int(record_id)
    except (ValueError, TypeError):
        return False

    with get_connection() as conn:
        # Hours already logged on the dashboard are real history: keep them.
        conn.execute(
            "UPDATE activities SET planned_activity_id = NULL WHERE planned_activity_id = ?",
            (record_id,),
        )
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
