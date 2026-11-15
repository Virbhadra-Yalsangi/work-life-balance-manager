
import os
from pathlib import Path
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Load environment variables
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

api_key = os.getenv("SENDGRID_API_KEY")
from_email = os.getenv("SENDGRID_FROM_EMAIL")

# Basic configuration check
if not api_key or not from_email:
    raise ValueError("SendGrid configuration is missing in .env")

# Send test email to your verified email
to_email = from_email

message = Mail(
    from_email=from_email,
    to_emails=to_email,
    subject="Sales Automation - Email Test",
    plain_text_content=(
        "Congratulations! Your SendGrid email integration "
        "is working and ready for testing."
    )
)

try:
    client = SendGridAPIClient(api_key)
    response = client.send(message)

    print("HTTP Status:", response.status_code)

    if response.status_code == 202:
        print("SUCCESS: SendGrid accepted the test email.")
    else:
        print("Email was not accepted. Check SendGrid settings.")

except Exception as error:
    print("Email sending failed.")
    print("Error:", str(error))
