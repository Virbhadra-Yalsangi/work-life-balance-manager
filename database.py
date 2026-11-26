import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).resolve().parent / "data" / "work_life_balance.db"

ALL_CHANNELS = ["telegram", "email"]

DEFAULT_TEMPLATES = [
    {"name": "Deep Work Block", "activity_type": "Work", "duration_hours": 2.0, "notes": "Focused execution"},
    {"name": "Study / Upskill", "activity_type": "Study", "duration_hours": 1.0, "notes": "Focused learning"},
    {"name": "Workout / Walk", "activity_type": "Exercise", "duration_hours": 0.75, "notes": "Movement session"},
    {"name": "Evening Wind-Down", "activity_type": "Personal Care", "duration_hours": 1.0, "notes": "Disconnect & recharge"},
]


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_date TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            duration_hours REAL NOT NULL,
            energy_level INTEGER DEFAULT 3,
            notes TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS planned_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            status TEXT DEFAULT 'Planned',
            notes TEXT,
            why_failed TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            planned_id INTEGER,
            channel TEXT NOT NULL,
            message TEXT NOT NULL,
            remind_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            failure_reason TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()


def initialize_database():
    return init_db()


def get_db_connection():
    return get_connection()


def get_enabled_channels(*args, **kwargs):
    return ["telegram", "email"]


# --- ACTIVITY DATABASE FUNCTIONS ---

def load_activities(start_date, end_date):
    conn = get_connection()
    query = (
        "SELECT * FROM activities WHERE activity_date BETWEEN ? AND ? "
        "ORDER BY activity_date DESC, id DESC"
    )
    df = pd.read_sql_query(query, conn, params=(str(start_date), str(end_date)))
    conn.close()
    return df


def save_activity(activity_date, activity_type, duration_hours, notes="", energy_level=3):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cursor.execute("""
            INSERT INTO activities (activity_date, activity_type, duration_hours, energy_level, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(activity_date), activity_type, float(duration_hours), int(energy_level), notes, now))
        conn.commit()
        return True, "Activity saved successfully!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def update_activity(record_id, activity_date, activity_type, duration_hours, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE activities
            SET activity_date = ?, activity_type = ?, duration_hours = ?, notes = ?
            WHERE id = ?
        """, (str(activity_date), activity_type, float(duration_hours), notes, int(record_id)))
        conn.commit()
        return True, "Activity updated successfully!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_activity(record_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM activities WHERE id = ?", (int(record_id),))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def get_daily_total(activity_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT SUM(duration_hours) FROM activities WHERE activity_date = ?",
        (str(activity_date),),
    )
    res = cursor.fetchone()[0]
    conn.close()
    return float(res) if res else 0.0


def get_logging_streak(*args, **kwargs):
    return 1


# --- PLANNED ACTIVITIES & REMINDERS ---

def load_planned_activities(start_date, end_date):
    conn = get_connection()
    query = (
        "SELECT id, activity_date, start_time, end_time, activity_type, status, notes, "
        "why_failed as activity_failure_reason FROM planned_activities "
        "WHERE activity_date BETWEEN ? AND ? ORDER BY activity_date ASC, start_time ASC"
    )
    df = pd.read_sql_query(query, conn, params=(str(start_date), str(end_date)))
    conn.close()
    return df


def save_planned_activity(activity_date, activity_type, start_time, end_time, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cursor.execute("""
            INSERT INTO planned_activities (activity_date, start_time, end_time, activity_type, status, notes, created_at)
            VALUES (?, ?, ?, ?, 'Planned', ?, ?)
        """, (str(activity_date), start_time, end_time, activity_type, notes, now))
        planned_id = cursor.lastrowid

        start_dt = datetime.strptime(f"{activity_date} {start_time}", "%Y-%m-%d %H:%M")
        remind_dt = start_dt - timedelta(minutes=5)
        remind_at_str = remind_dt.isoformat()

        clean_notes = notes if notes and str(notes).strip() else "No additional notes"
        msg = (
            f"🔔 *WORK-LIFE BALANCE REMINDER*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *Activity:* {activity_type}\n"
            f"📅 *Date:* {activity_date}\n"
            f"⏰ *Starts at:* {start_time}\n"
            f"📝 *Notes:* {clean_notes}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Tip:* Stay focused, you've got this! Take short breaks when needed."
        )

        for ch in ALL_CHANNELS:
            cursor.execute("""
                INSERT INTO reminders (planned_id, channel, message, remind_at, status, updated_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """, (planned_id, ch, msg, remind_at_str, now))

        conn.commit()
        return True, "Planned activity saved successfully!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def update_planned_activity(planned_id, activity_date, activity_type, start_time, end_time, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE planned_activities
            SET activity_date = ?, activity_type = ?, start_time = ?, end_time = ?, notes = ?
            WHERE id = ?
        """, (str(activity_date), activity_type, start_time, end_time, notes, int(planned_id)))
        conn.commit()
        return True, "Planned activity updated!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def update_planned_activity_status(planned_id, status, why_failed=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if why_failed is not None:
            cursor.execute(
                "UPDATE planned_activities SET status = ?, why_failed = ? WHERE id = ?",
                (status, why_failed, int(planned_id)),
            )
        else:
            cursor.execute(
                "UPDATE planned_activities SET status = ? WHERE id = ?",
                (status, int(planned_id)),
            )

        if status == "Completed":
            cursor.execute(
                "SELECT activity_date, activity_type, start_time, end_time, notes "
                "FROM planned_activities WHERE id = ?",
                (int(planned_id),),
            )
            plan = cursor.fetchone()
            if plan:
                p_date, p_type, s_time, e_time, p_notes = (
                    plan["activity_date"],
                    plan["activity_type"],
                    plan["start_time"],
                    plan["end_time"],
                    plan["notes"],
                )
                t1 = datetime.strptime(s_time, "%H:%M")
                t2 = datetime.strptime(e_time, "%H:%M")
                dur = (t2 - t1).seconds / 3600.0
                if dur > 0:
                    cursor.execute("""
                        INSERT INTO activities (activity_date, activity_type, duration_hours, notes, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (p_date, p_type, dur, f"Completed plan: {p_notes}", datetime.now().isoformat()))

        conn.commit()
        return True, f"Status updated to {status}!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_planned_activity(planned_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM planned_activities WHERE id = ?", (int(planned_id),))
    cursor.execute("DELETE FROM reminders WHERE planned_id = ?", (int(planned_id),))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def mark_overdue_activities_failed():
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now()
    try:
        cursor.execute(
            "SELECT id, activity_date, start_time, end_time "
            "FROM planned_activities WHERE status = 'Planned'"
        )
        plans = cursor.fetchall()
        for p in plans:
            plan_end_dt = datetime.strptime(
                f"{p['activity_date']} {p['end_time']}", "%Y-%m-%d %H:%M"
            )
            if now > plan_end_dt:
                reason = (
                    f"Planned {p['start_time']} to {p['end_time']} on {p['activity_date']}. "
                    "End time passed and it was not marked Completed."
                )
                cursor.execute(
                    "UPDATE planned_activities SET status = 'Failed', why_failed = ? WHERE id = ?",
                    (reason, p["id"]),
                )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def load_reminder_history(start_date, end_date):
    conn = get_connection()
    cols = [
        "reminder_id",
        "activity_id",
        "activity_date",
        "start_time",
        "activity_type",
        "channel",
        "reminder_at",
        "reminder_status",
        "failure_reason",
    ]
    try:
        query = """
            SELECT r.id as reminder_id, r.planned_id as activity_id, p.activity_date, p.start_time, p.activity_type,
                   r.channel, r.remind_at as reminder_at, r.status as reminder_status, r.failure_reason
            FROM reminders r
            JOIN planned_activities p ON r.planned_id = p.id
            WHERE p.activity_date BETWEEN ? AND ?
        """
        df = pd.read_sql_query(query, conn, params=(str(start_date), str(end_date)))
        if df.empty or "reminder_at" not in df.columns:
            return pd.DataFrame(columns=cols)
        return df
    except Exception:
        return pd.DataFrame(columns=cols)
    finally:
        conn.close()


def load_goal_hours():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM user_preferences WHERE key LIKE 'goal_%'")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"].replace("goal_", ""): float(row["value"]) for row in rows}


def save_goal_hours(goals_dict):
    conn = get_connection()
    cursor = conn.cursor()
    for cat, val in goals_dict.items():
        cursor.execute(
            "INSERT OR REPLACE INTO user_preferences (key, value) VALUES (?, ?)",
            (f"goal_{cat}", str(val)),
        )
    conn.commit()
    conn.close()


def reset_goal_hours():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_preferences WHERE key LIKE 'goal_%'")
    conn.commit()
    conn.close()


def load_activity_templates():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM user_preferences WHERE key = 'activity_templates'")
    row = cursor.fetchone()
    conn.close()
    if row and row["value"]:
        try:
            parsed = json.loads(row["value"])
            if isinstance(parsed, list) and parsed:
                return parsed
        except Exception:
            pass
    return list(DEFAULT_TEMPLATES)


def save_activity_template(name, activity_type, duration_hours, notes=""):
    templates = load_activity_templates()
    clean_name = str(name).strip()
    if not clean_name:
        return False, "Template name is required."
    templates.append({
        "name": clean_name,
        "activity_type": activity_type,
        "duration_hours": float(duration_hours),
        "notes": str(notes).strip(),
    })
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_preferences (key, value) VALUES ('activity_templates', ?)",
        (json.dumps(templates),),
    )
    conn.commit()
    conn.close()
    return True, f"Template '{clean_name}' saved."


def save_daily_checkin(check_date, mood_status, note=""):
    payload = {"mood": mood_status, "note": str(note).strip()}
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_preferences (key, value) VALUES (?, ?)",
        (f"checkin_{check_date}", json.dumps(payload)),
    )
    conn.commit()
    conn.close()


def load_daily_checkin(check_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT value FROM user_preferences WHERE key = ?",
        (f"checkin_{check_date}",),
    )
    row = cursor.fetchone()
    conn.close()
    if row and row["value"]:
        try:
            return json.loads(row["value"])
        except Exception:
            pass
    return None