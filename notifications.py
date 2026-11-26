import os
import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv(Path(__file__).resolve().parent / ".env")


def get_db_connection():
    db_path = Path(__file__).resolve().parent / "data" / "work_life_balance.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def send_telegram(message, planned_id=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False, "Telegram token or chat_id missing."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}

    if planned_id is not None:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {"text": "✅ Mark Completed", "callback_data": f"plan_done:{planned_id}"},
                    {"text": "❌ Mark Missed", "callback_data": f"plan_fail:{planned_id}"},
                ]
            ]
        }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True, None
        return False, f"Telegram API error: {resp.text}"
    except Exception as e:
        return False, str(e)


def send_email(*args, **kwargs):
    api_key = os.getenv("SENDGRID_API_KEY", "").strip()
    from_email = os.getenv("SENDGRID_FROM_EMAIL", "").strip()
    default_to_email = os.getenv("NOTIFICATION_TO_EMAIL", "").strip()

    to_email = default_to_email
    subject = "Work-Life Balance Alert"
    body = ""

    if len(args) == 3:
        to_email, subject, body = args
    elif len(args) == 2:
        subject, body = args
    elif len(args) == 1:
        body = args[0]

    if "to_email" in kwargs:
        to_email = kwargs["to_email"]
    if "subject" in kwargs:
        subject = kwargs["subject"]
    if "body" in kwargs:
        body = kwargs["body"]

    if not to_email:
        to_email = default_to_email

    if not api_key or not from_email or not to_email:
        return False, "SendGrid credentials missing."

    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        if resp.status_code in [200, 202]:
            return True, None
        return False, f"SendGrid API error: {resp.text}"
    except Exception as e:
        return False, str(e)


def process_pending_reminders():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now_iso = datetime.now().isoformat()

        query = """
            SELECT r.id, r.planned_id, r.channel, p.activity_type, p.activity_date, p.start_time, p.notes
            FROM reminders r
            JOIN planned_activities p ON r.planned_id = p.id
            WHERE r.status = 'pending'
        """
        cursor.execute(query)
        reminders = cursor.fetchall()

        for rem in reminders:
            rem_id = rem["id"]
            planned_id = rem["planned_id"]
            channel = rem["channel"]
            activity_type = rem["activity_type"]
            activity_date = rem["activity_date"]
            start_time = rem["start_time"]
            notes = rem["notes"] if rem["notes"] else "No additional notes"

            msg = (
                f"🔔 *WORK-LIFE BALANCE REMINDER*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 *Activity:* {activity_type}\n"
                f"📅 *Date:* {activity_date}\n"
                f"⏰ *Starts at:* {start_time}\n"
                f"📝 *Notes:* {notes}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 *Tip:* Stay focused, you've got this! Take short breaks when needed."
            )

            success = False
            err_msg = None

            if channel == "telegram":
                success, err_msg = send_telegram(msg, planned_id=planned_id)
            elif channel == "email":
                success, err_msg = send_email(
                    subject=f"⏰ Reminder: {activity_type} starting soon!",
                    body=msg.replace("*", ""),
                )

            if success:
                cursor.execute(
                    "UPDATE reminders SET status = 'sent', updated_at = ? WHERE id = ?",
                    (now_iso, rem_id),
                )
            else:
                cursor.execute(
                    "UPDATE reminders SET status = 'failed', failure_reason = ?, updated_at = ? WHERE id = ?",
                    (str(err_msg)[:255], now_iso, rem_id),
                )
        conn.commit()
    except Exception as e:
        print(f"Error in process_pending_reminders: {e}")
    finally:
        conn.close()