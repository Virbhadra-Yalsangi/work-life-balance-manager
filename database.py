from contextlib import contextmanager
import os
import sqlite3
from pathlib import Path
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")

ALL_CHANNELS = ("sms", "voice", "email", "telegram")


def get_enabled_channels():
    """
    Channels that should get reminders, from ENABLED_CHANNELS in .env
    (comma separated, e.g. "email,telegram").
    Checks app_settings in SQLite only when ENABLED_CHANNELS is not explicitly overridden in env,
    or if UI saved a preference and WLB_DB_PATH is not a test override.
    """
    if not os.environ.get("WLB_DB_PATH"):
        try:
            if DB_PATH.exists():
                with get_connection() as conn:
                    row = conn.execute(
                        "SELECT value FROM app_settings WHERE key = 'enabled_channels'"
                    ).fetchone()
                    if row and row[0] is not None:
                        chosen = [c.strip().lower() for c in row[0].split(",") if c.strip()]
                        return tuple(c for c in ALL_CHANNELS if c in chosen)
        except sqlite3.Error:
            pass

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
                energy_level INTEGER DEFAULT 3,
                created_at TEXT NOT NULL DEFAULT ''
            )
        """)

        activity_columns = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(activities)"
            ).fetchall()
        }
        if "notes" not in activity_columns:
            conn.execute("ALTER TABLE activities ADD COLUMN notes TEXT DEFAULT ''")
        if "created_at" not in activity_columns:
            conn.execute("ALTER TABLE activities ADD COLUMN created_at TEXT DEFAULT ''")
        if "planned_activity_id" not in activity_columns:
            conn.execute("ALTER TABLE activities ADD COLUMN planned_activity_id INTEGER")
        if "energy_level" not in activity_columns:
            conn.execute("ALTER TABLE activities ADD COLUMN energy_level INTEGER DEFAULT 3")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            )
        """)

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
# APP SETTINGS HELPERS
# --------------------------------------------------

def get_setting(key, default=""):
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else default
    except sqlite3.Error:
        return default


def set_setting(key, value):
    stamp = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, str(value), stamp),
        )
        conn.commit()


# --------------------------------------------------
# DAILY TOTAL & STREAKS
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
        result = conn.execute(query, params).fetchone()

    return float(result[0])


def get_logging_streak(reference_date=None):
    """Calculate consecutive days with logged activities ending today or yesterday."""
    ref = reference_date or date.today()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT activity_date FROM activities ORDER BY activity_date DESC"
        ).fetchall()
    logged_dates = {date.fromisoformat(r[0]) for r in rows if r[0]}
    if not logged_dates:
        return 0
    cursor = ref if ref in logged_dates else (ref - timedelta(days=1))
    streak = 0
    while cursor in logged_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


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
                COALESCE(energy_level, 3) AS energy_level,
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

def save_activity(activity_date, activity_type, hours, notes, energy_level=3):
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

    energy_level = max(1, min(5, int(energy_level)))

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO activities (
                activity_date,
                activity_type,
                duration_hours,
                notes,
                energy_level,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                activity_date.isoformat(),
                activity_type,
                hours,
                notes.strip(),
                energy_level,
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
    new_notes,
    new_energy=3
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

    new_energy = max(1, min(5, int(new_energy)))

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE activities
            SET
                activity_date = ?,
                activity_type = ?,
                duration_hours = ?,
                notes = ?,
                energy_level = ?
            WHERE id = ?
            """,
            (
                new_date.isoformat(),
                new_type,
                new_hours,
                new_notes.strip(),
                new_energy,
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
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value.strip())
    raise ValueError("Invalid activity date.")


def _normalise_activity_time(value):
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


def _calculate_plan_hours(start_time_str, end_time_str):
    """Calculate duration in hours, supporting overnight crossover (e.g., 23:00 to 06:00)."""
    start = datetime.strptime(start_time_str, "%H:%M")
    end = datetime.strptime(end_time_str, "%H:%M")
    if end <= start:
        end += timedelta(days=1)
    return round((end - start).total_seconds() / 3600, 2)


def _build_reminder_values(activity_id, activity_date, start_time, now=None):
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
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT category, weekly_hours FROM category_goals"
        ).fetchall()
    return {category: hours for category, hours in rows}


def save_goal_hours(hours_by_category):
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
    with get_connection() as conn:
        conn.execute("DELETE FROM category_goals")
        conn.commit()


def _sync_completed_activity(conn, record_id):
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
    hours = _calculate_plan_hours(start_time, end_time)

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
            energy_level, created_at, planned_activity_id
        )
        VALUES (?, ?, ?, ?, 3, ?, ?)
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
    allow_overnight=False,
):
    """
    Save a planned activity and its reminders.
    Set allow_overnight=True for plans that cross midnight (e.g. 23:00 to 06:00).
    """
    try:
        activity_date = _normalise_activity_date(activity_date)
        start_time = _normalise_activity_time(start_time)
        end_time = _normalise_activity_time(end_time)

        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        if start_time == end_time:
            return False, "End time must be later than start time."
        if end <= start and not allow_overnight:
            return False, "End time must be later than start time (enable Overnight for past-midnight plans)."

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


def save_recurring_planned_activities(
    start_date,
    activity_type,
    start_time,
    end_time,
    notes="",
    repeat_mode="None",
    days_count=7,
    allow_overnight=False,
):
    """Save single or recurring planned activities (Daily or Weekdays)."""
    start_date = _normalise_activity_date(start_date)
    if repeat_mode == "None":
        return save_planned_activity(
            start_date, activity_type, start_time, end_time, notes, allow_overnight=allow_overnight
        )

    saved_count = 0
    for offset in range(days_count):
        target_date = start_date + timedelta(days=offset)
        if repeat_mode == "Weekdays (Mon-Fri)" and target_date.weekday() >= 5:
            continue
        ok, msg = save_planned_activity(
            target_date, activity_type, start_time, end_time, notes, allow_overnight=allow_overnight
        )
        if ok:
            saved_count += 1
        elif saved_count == 0:
            return False, msg

    return True, f"Saved {saved_count} planned activities ({repeat_mode})!"


def load_planned_activities(start_date, end_date):
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
    allow_overnight=False,
):
    try:
        record_id = int(record_id)
        activity_date = _normalise_activity_date(activity_date)
        start_time = _normalise_activity_time(start_time)
        end_time = _normalise_activity_time(end_time)

        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        if start_time == end_time:
            return False, "End time must be later than start time."
        if end <= start and not allow_overnight:
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
    timezone = ZoneInfo("Asia/Kolkata")
    current_time = now or datetime.now(timezone)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone)
    else:
        current_time = current_time.astimezone(timezone)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, activity_date, start_time, end_time FROM planned_activities WHERE status = 'Planned'"
        ).fetchall()

        overdue_ids = []
        for row_id, act_date_str, start_str, end_str in rows:
            act_date = date.fromisoformat(act_date_str)
            start_t = datetime.strptime(start_str, "%H:%M").time()
            end_t = datetime.strptime(end_str, "%H:%M").time()
            end_date = act_date + timedelta(days=1) if end_t <= start_t else act_date
            end_dt = datetime.combine(end_date, end_t).replace(tzinfo=timezone)
            if end_dt <= current_time:
                overdue_ids.append((row_id, start_str, end_str, act_date_str))

        for row_id, start_str, end_str, act_date_str in overdue_ids:
            reason = (
                f"Planned {start_str} to {end_str} on {act_date_str}. "
                "End time passed and it was not marked Completed, so it was auto-marked Failed. "
                "If you did it, set status to Completed."
            )
            conn.execute(
                "UPDATE planned_activities SET status = 'Failed', activity_failure_reason = ? WHERE id = ?",
                (reason, row_id),
            )
            conn.execute(
                """
                UPDATE reminders
                SET status = 'Cancelled',
                    failure_reason = 'Activity was marked Failed after its end time.'
                WHERE status = 'Pending' AND planned_activity_id = ?
                """,
                (row_id,),
            )
        conn.commit()
        return len(overdue_ids)


def delete_planned_activity(record_id):
    try:
        record_id = int(record_id)
    except (ValueError, TypeError):
        return False

    with get_connection() as conn:
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
