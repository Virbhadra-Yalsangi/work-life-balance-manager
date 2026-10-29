
from contextlib import contextmanager
import os
import sqlite3
from pathlib import Path
from datetime import date, datetime

import pandas as pd


APP_DIR = Path(__file__).resolve().parent
DATA_DB = APP_DIR / "data" / "work_life_balance.db"
ROOT_DB = APP_DIR / "work_life_balance.db"

# Tests can override this path before importing the module.
if os.environ.get("WLB_DB_PATH"):
    DB_PATH = Path(os.environ["WLB_DB_PATH"])
elif DATA_DB.exists():
    DB_PATH = DATA_DB
elif ROOT_DB.exists():
    DB_PATH = ROOT_DB
else:
    DB_PATH = DATA_DB


@contextmanager
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(DB_PATH),
        timeout=10
    )

    try:
        yield connection
    finally:
        connection.close()


def initialize_database():
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

        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(activities)"
            ).fetchall()
        }

        if "notes" not in columns:
            conn.execute(
                "ALTER TABLE activities ADD COLUMN notes TEXT DEFAULT ''"
            )

        if "created_at" not in columns:
            conn.execute(
                "ALTER TABLE activities ADD COLUMN created_at TEXT DEFAULT ''"
            )

        conn.commit()


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


def load_activities(start_date, end_date):
    with get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT id, activity_date, activity_type,
                   duration_hours, notes, created_at
            FROM activities
            WHERE activity_date BETWEEN ? AND ?
            ORDER BY activity_date DESC, id DESC
            """,
            conn,
            params=(start_date.isoformat(), end_date.isoformat()),
        )

    if not df.empty:
        df["activity_date"] = pd.to_datetime(
            df["activity_date"]
        ).dt.date

    return df


def save_activity(activity_date, activity_type, hours, notes):
    hours = float(hours)

    if hours <= 0 or hours > 24:
        return False, "Duration must be greater than 0 and at most 24 hours."

    existing_hours = get_daily_total(activity_date)

    if existing_hours + hours > 24:
        return False, (
            f"This date already has {existing_hours:.2f} hours. "
            f"Adding {hours:.2f} would exceed 24 hours."
        )

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO activities
            (activity_date, activity_type, duration_hours, notes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                activity_date.isoformat(),
                activity_type,
                hours,
                notes.strip(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()

    return True, "Activity saved successfully!"


def update_activity(record_id, new_date, new_type, new_hours, new_notes):
    new_hours = float(new_hours)

    if new_hours <= 0 or new_hours > 24:
        return False, "Duration must be greater than 0 and at most 24 hours."

    other_hours = get_daily_total(new_date, exclude_id=record_id)

    if other_hours + new_hours > 24:
        return False, (
            f"The selected date already has {other_hours:.2f} other hours. "
            "The updated total would exceed 24 hours."
        )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE activities
            SET activity_date = ?, activity_type = ?,
                duration_hours = ?, notes = ?
            WHERE id = ?
            """,
            (
                new_date.isoformat(),
                new_type,
                new_hours,
                new_notes.strip(),
                int(record_id),
            ),
        )
        conn.commit()

        if cursor.rowcount == 0:
            return False, "Record not found. Refresh and try again."

    return True, "Activity updated successfully!"


def delete_activity(record_id):
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM activities WHERE id = ?",
            (int(record_id),),
        )
        conn.commit()

    return cursor.rowcount > 0
