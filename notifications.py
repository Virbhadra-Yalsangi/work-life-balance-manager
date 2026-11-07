
import os
from dotenv import load_dotenv
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from xml.sax.saxutils import escape

# Load credentials from the local .env file
load_dotenv()


def send_sms(to_number, message):
    """Send an SMS reminder using Twilio."""

    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_PHONE_NUMBER")

        if not all([account_sid, auth_token, from_number, to_number]):
            return False, "SMS configuration is incomplete."

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

        if not all([account_sid, auth_token, from_number, to_number]):
            return False, "Voice call configuration is incomplete."

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
