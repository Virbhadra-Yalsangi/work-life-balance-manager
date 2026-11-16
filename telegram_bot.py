"""
Two-Way Interactive Telegram Bot Worker.

Allows the user to:
1. Tap "✅ Mark Completed" or "❌ Mark Missed" directly on reminder notifications.
2. Send free-text activity updates on Telegram (e.g., "Worked 2 hours on SQL and 1 hr gym")
   which get parsed via AI Quick-Log (if GEMINI_API_KEY is set) and saved to SQLite.

Run:
    python telegram_bot.py
"""

import os
import time
from datetime import date
from pathlib import Path
import requests
from dotenv import load_dotenv

import database
from ai_coach import parse_natural_language_activities

load_dotenv(Path(__file__).resolve().parent / ".env")


def _api_url(token, method):
    return f"https://api.telegram.org/bot{token}/{method}"


def handle_callback(token, callback_query):
    cq_id = callback_query.get("id")
    data = callback_query.get("data", "")
    message = callback_query.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")

    if ":" not in data:
        return

    action, raw_id = data.split(":", 1)
    try:
        plan_id = int(raw_id)
    except ValueError:
        return

    if action == "plan_done":
        ok, reply = database.update_planned_activity_status(plan_id, "Completed")
        status_banner = f"✅ Plan #{plan_id} marked Completed! ({reply})"
    elif action == "plan_fail":
        ok, reply = database.update_planned_activity_status(
            plan_id, "Failed", "Marked Missed via Telegram button."
        )
        status_banner = f"❌ Plan #{plan_id} marked Missed."
    else:
        return

    requests.post(
        _api_url(token, "answerCallbackQuery"),
        json={"callback_query_id": cq_id, "text": status_banner[:190]},
        timeout=10,
    )
    if chat_id and message_id:
        orig_text = message.get("text", "")
        requests.post(
            _api_url(token, "editMessageText"),
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": f"{orig_text}\n\n{status_banner}",
            },
            timeout=10,
        )


def handle_text_message(token, message):
    chat_id = (message.get("chat") or {}).get("id")
    allowed_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if allowed_chat and str(chat_id) != allowed_chat:
        return

    text = (message.get("text") or "").strip()
    if not text or text.startswith("/start"):
        requests.post(
            _api_url(token, "sendMessage"),
            json={
                "chat_id": chat_id,
                "text": "👋 Send me what you did today (e.g., 'Studied 2 hours and 1 hour exercise') and I will log it to your dashboard!",
            },
            timeout=10,
        )
        return

    items, err = parse_natural_language_activities(text, date.today())
    if err or not items:
        requests.post(
            _api_url(token, "sendMessage"),
            json={"chat_id": chat_id, "text": f"⚠️ Could not log: {err or 'No activities detected.'}"},
            timeout=10,
        )
        return

    lines = []
    for item in items:
        act_date = date.fromisoformat(item["activity_date"])
        ok, msg = database.save_activity(
            act_date,
            item["activity_type"],
            item["duration_hours"],
            item["notes"],
            item["energy_level"],
        )
        icon = "✅" if ok else "⚠️"
        lines.append(f"{icon} {item['activity_type']} ({item['duration_hours']}h) - {msg}")

    requests.post(
        _api_url(token, "sendMessage"),
        json={"chat_id": chat_id, "text": "\n".join(lines)},
        timeout=10,
    )


def run_polling():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN missing in .env. Exiting.")
        return

    database.initialize_database()
    print("Two-way Telegram bot listening for button taps and quick-logs... (Ctrl+C to stop)")
    offset = 0

    while True:
        try:
            resp = requests.get(
                _api_url(token, "getUpdates"),
                params={"timeout": 25, "offset": offset},
                timeout=35,
            ).json()
            for update in resp.get("result", []):
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    handle_callback(token, update["callback_query"])
                elif "message" in update:
                    handle_text_message(token, update["message"])
        except KeyboardInterrupt:
            print("Stopped Telegram bot.")
            break
        except Exception as exc:
            print(f"Polling error: {exc}")
            time.sleep(5)


if __name__ == "__main__":
    run_polling()
