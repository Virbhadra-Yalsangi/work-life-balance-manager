import os
import re
from pathlib import Path
import requests
from dotenv import load_dotenv
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from xml.sax.saxutils import escape

load_dotenv(Path(__file__).resolve().parent / ".env")


def normalize_phone(number, default_country_code="91"):
    """Return the number in international format (+91XXXXXXXXXX), or None."""
    if not number:
        return None
    text = str(number).strip()
    has_plus = text.startswith("+")
    digits = re.sub(r"\D", "", text)
    if has_plus:
        candidate = digits
    elif len(digits) == 10:
        candidate = default_country_code + digits
    else:
        candidate = digits
    if not 8 <= len(candidate) <= 15:
        return None
    return "+" + candidate


def send_sms(to_number, message):
    """Send an SMS reminder using Twilio."""
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_PHONE_NUMBER")

        to_number = normalize_phone(to_number)
        if not all([account_sid, auth_token, from_number, to_number]):
            return False, "SMS configuration is incomplete or the phone number is invalid."

        client = Client(account_sid, auth_token)
        result = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        return True, f"SMS submitted successfully. ID: {result.sid}"

    except Exception as error:
        return False, f"SMS failed: {error}"


def send_voice_call(to_number, message):
    """Make a voice reminder call using Twilio."""
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_PHONE_NUMBER")

        to_number = normalize_phone(to_number)
        if not all([account_sid, auth_token, from_number, to_number]):
            return False, "Voice call configuration is incomplete or the phone number is invalid."

        safe_message = escape(message)
        twiml_message = (
            "<Response>"
            "<Say>"
            f"{safe_message}"
            "</Say>"
            "</Response>"
        )

        client = Client(account_sid, auth_token)
        result = client.calls.create(
            to=to_number,
            from_=from_number,
            twiml=twiml_message
        )
        return True, f"Voice call submitted successfully. ID: {result.sid}"

    except Exception as error:
        return False, f"Voice call failed: {error}"


def send_email(to_email, subject, message):
    """Send an email reminder using SendGrid."""
    try:
        api_key = os.getenv("SENDGRID_API_KEY")
        from_email = os.getenv("SENDGRID_FROM_EMAIL")

        if not all([api_key, from_email, to_email]):
            return False, "Email configuration is incomplete."

        email = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            plain_text_content=message
        )

        client = SendGridAPIClient(api_key)
        response = client.send(email)

        if response.status_code == 202:
            return True, "Email submitted successfully."

        return False, f"Email submission returned status {response.status_code}."

    except Exception as error:
        return False, f"Email failed: {error}"


def send_telegram(message, planned_activity_id=None):
    """
    Send a reminder to your phone with a Telegram bot.
    If planned_activity_id is provided, attaches inline Completed / Failed buttons.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return False, "Telegram configuration is incomplete."

    payload = {"chat_id": chat_id, "text": message}
    if planned_activity_id is not None:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": "✅ Mark Completed", "callback_data": f"plan_done:{planned_activity_id}"},
                {"text": "❌ Mark Missed", "callback_data": f"plan_fail:{planned_activity_id}"},
            ]]
        }

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=15,
        )
        data = response.json()
        if response.status_code == 200 and data.get("ok"):
            return True, "Telegram message submitted successfully."
        return False, f"Telegram failed: {data.get('description', response.status_code)}"

    except Exception as error:
        return False, f"Telegram failed: {str(error).replace(token, '***')}"
