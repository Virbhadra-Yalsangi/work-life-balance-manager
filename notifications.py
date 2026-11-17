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

def send_telegram_alert(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False, "Telegram token or chat_id missing."
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True, None
        else:
            return False, f"Telegram API error: {resp.text}"
    except Exception as e:
        return False, str(e)

def send_email_alert(subject, body):
    api_key = os.getenv("SENDGRID_API_KEY", "").strip()
    from_email = os.getenv("SENDGRID_FROM_EMAIL", "").strip()
    to_email = os.getenv("NOTIFICATION_TO_EMAIL", "").strip()
    
    if not api_key or not from_email or not to_email:
        return False, "SendGrid credentials missing."
    
    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}]
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        if resp.status_code in [200, 202]:
            return True, None
        else:
            return False, f"SendGrid API error: {resp.text}"
    except Exception as e:
        return False, str(e)

# --- ALIASES FOR APP.PY COMPATIBILITY ---
def send_telegram(message):
    return send_telegram_alert(message)

def send_email(subject_or_msg, body=None):
    if body is None:
        return send_email_alert("Work-Life Balance Alert", subject_or_msg)
    return send_email_alert(subject_or_msg, body)
# ----------------------------------------

def process_pending_reminders():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, channel, message FROM reminders WHERE status = 'pending'")
        reminders = cursor.fetchall()
        for rem in reminders:
            rem_id = rem["id"]
            channel = rem["channel"]
            msg = rem["message"]
            success = False
            err_msg = None
            
            if channel == "telegram":
                success, err_msg = send_telegram_alert(msg)
            elif channel == "email":
                success, err_msg = send_email_alert("Work-Life Balance Alert", msg)
                
            if success:
                cursor.execute(
                    "UPDATE reminders SET status = 'sent', updated_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), rem_id)
                )
            else:
                cursor.execute(
                    "UPDATE reminders SET status = 'failed', failure_reason = ?, updated_at = ? WHERE id = ?",
                    (str(err_msg)[:255], datetime.now().isoformat(), rem_id)
                )
        conn.commit()
    except Exception as e:
        print(f"Error in process_pending_reminders: {e}")
    finally:
        conn.close()