"""
Step-by-step checker for live notifications.

Usage (from the project folder):
    .venv/Scripts/python.exe scripts/check_notifications.py            # check .env only (sends nothing)
    .venv/Scripts/python.exe scripts/check_notifications.py email      # send 1 test email
    .venv/Scripts/python.exe scripts/check_notifications.py sms        # send 1 test SMS and watch delivery
    .venv/Scripts/python.exe scripts/check_notifications.py voice      # place 1 test call and watch it
    .venv/Scripts/python.exe scripts/check_notifications.py telegram   # send 1 Telegram test
    .venv/Scripts/python.exe scripts/check_notifications.py telegram-id # find your TELEGRAM_CHAT_ID
    .venv/Scripts/python.exe scripts/check_notifications.py all

Secrets are never printed. SMS and calls use your Twilio credit.
"""

import os
import re
import sys
import time
from pathlib import Path

_here = Path(__file__).resolve().parent
# Works whether this file sits in scripts/ or directly in the project folder.
ROOT = _here if (_here / "notifications.py").exists() else _here.parent
sys.path.insert(0, str(ROOT))

import notifications as n  # noqa: E402  (loads .env)

REQUIRED = {
    "email": ["SENDGRID_API_KEY", "SENDGRID_FROM_EMAIL", "NOTIFICATION_TO_EMAIL"],
    "sms": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "NOTIFICATION_TO_PHONE"],
    "voice": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "NOTIFICATION_TO_PHONE"],
    "telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
}


def mask(name, value):
    if not value:
        return "MISSING"
    if "KEY" in name or "TOKEN" in name or "SID" in name or "CHAT_ID" in name:
        return f"set ({len(value)} characters)"
    if "PHONE" in name:
        return value[:3] + "*" * max(len(value) - 5, 0) + value[-2:]
    return value


def check_config():
    problems = []
    print("\n== .env check ==")
    print(f"File: {ROOT / '.env'} ({'found' if (ROOT / '.env').exists() else 'NOT FOUND'})")
    import database
    print(f"Channels that will get reminders (ENABLED_CHANNELS): {', '.join(database.get_enabled_channels()) or 'none'}")
    for channel, names in REQUIRED.items():
        missing = [k for k in names if not os.getenv(k)]
        print(f"\n[{channel.upper()}] " + ("ready" if not missing else "missing: " + ", ".join(missing)))
        for k in names:
            print(f"   {k:24} {mask(k, os.getenv(k))}")
        if missing:
            problems.append(channel)

    to_phone = n.normalize_phone(os.getenv("NOTIFICATION_TO_PHONE"))
    from_phone = os.getenv("TWILIO_PHONE_NUMBER", "")
    if os.getenv("NOTIFICATION_TO_PHONE") and not to_phone:
        print("\n! NOTIFICATION_TO_PHONE does not look like a valid phone number.")
        problems.append("phone")
    elif to_phone:
        print(f"\nReminders will go to: {mask('PHONE', to_phone)}")
    if from_phone and not re.fullmatch(r"\+\d{8,15}", from_phone):
        print("! TWILIO_PHONE_NUMBER must be in +countrycode format, e.g. +12025550123")
        problems.append("from")
    if to_phone and from_phone and to_phone == from_phone:
        print("! Your own number and the Twilio number are the same. Use two different numbers.")
        problems.append("same")
    return problems


def _twilio_client():
    from twilio.rest import Client
    return Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))


def test_email():
    print("\n== Email test ==")
    ok, msg = n.send_email(
        os.getenv("NOTIFICATION_TO_EMAIL"),
        "WLB test email",
        "If you can read this, SendGrid is working for your Work-Life Balance Manager.",
    )
    print(("OK: " if ok else "FAILED: ") + msg)
    if ok:
        print("Now check your inbox AND spam folder. 'Accepted' only means SendGrid took it.")


def test_telegram():
    print("\n== Telegram test ==")
    ok, msg = n.send_telegram("WLB test: Telegram reminders are working.")
    print(("OK: " if ok else "FAILED: ") + msg)
    if ok:
        print("Check Telegram on your phone now.")


def telegram_chat_id():
    import requests
    print("\n== Find your Telegram chat id ==")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Put TELEGRAM_BOT_TOKEN in .env first.")
        return
    try:
        data = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15).json()
    except Exception as error:
        print("Request failed:", str(error).replace(token, "***"))
        return
    if not data.get("ok"):
        print("Telegram said:", data.get("description"))
        return
    chats = {}
    for update in data.get("result", []):
        chat = (update.get("message") or {}).get("chat") or {}
        if chat.get("id") is not None:
            chats[chat["id"]] = chat.get("first_name") or chat.get("title") or ""
    if not chats:
        print("No messages found. Open your bot in Telegram, press START, send 'hi', then run this again.")
    for chat_id, name in chats.items():
        print(f"TELEGRAM_CHAT_ID={chat_id}   ({name})")


def test_sms():
    print("\n== SMS test ==")
    ok, msg = n.send_sms(os.getenv("NOTIFICATION_TO_PHONE"), "WLB test SMS: notifications are working.")
    print(("OK: " if ok else "FAILED: ") + msg)
    match = re.search(r"ID: (\w+)", msg)
    if not ok or not match:
        return
    print("Watching delivery for up to 30 seconds...")
    client, last = _twilio_client(), None
    for _ in range(10):
        time.sleep(3)
        m = client.messages(match.group(1)).fetch()
        if m.status != last:
            print(f"   status: {m.status}")
            last = m.status
        if m.status in ("delivered", "undelivered", "failed"):
            if m.error_code:
                print(f"   Twilio error {m.error_code}: {m.error_message}")
                print(f"   Look it up: https://www.twilio.com/docs/api/errors/{m.error_code}")
            break
    else:
        print("   Still not final. Check Twilio Console > Monitor > Logs > Messaging.")


def test_voice():
    print("\n== Voice call test ==")
    ok, msg = n.send_voice_call(os.getenv("NOTIFICATION_TO_PHONE"), "This is a test call from your work life balance manager.")
    print(("OK: " if ok else "FAILED: ") + msg)
    match = re.search(r"ID: (\w+)", msg)
    if not ok or not match:
        return
    print("Your phone should ring now. Watching for up to 60 seconds...")
    client, last = _twilio_client(), None
    for _ in range(20):
        time.sleep(3)
        call = client.calls(match.group(1)).fetch()
        if call.status != last:
            print(f"   status: {call.status}")
            last = call.status
        if call.status in ("completed", "busy", "no-answer", "failed", "canceled"):
            break


if __name__ == "__main__":
    what = sys.argv[1].lower() if len(sys.argv) > 1 else "config"
    if what not in ("config", "email", "sms", "voice", "telegram", "telegram-id", "all"):
        sys.exit("Use one of: config, email, sms, voice, telegram, telegram-id, all")
    if what == "telegram-id":
        telegram_chat_id()
        sys.exit(0)
    problems = check_config()
    tests = {"email": test_email, "sms": test_sms, "voice": test_voice, "telegram": test_telegram}
    import database
    wanted = [c for c in tests if c in database.get_enabled_channels()] if what == "all" else ([what] if what in tests else [])
    for channel in wanted:
        if channel in problems or ("phone" in problems and channel in ("sms", "voice")):
            print(f"\nSkipping {channel}: fix the .env problems above first.")
            continue
        tests[channel]()
    if not wanted:
        print("\nNothing was sent. Run again with: email, sms, voice or all.")
