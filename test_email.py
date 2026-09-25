import smtplib
from email.message import EmailMessage

SENDER_EMAIL = "sbharathk390@gmail.com"
SENDER_APP_PASSWORD = "xxxxxxxxxxxxxx"
WARDEN_EMAIL = "skbharath390@gmail.com"

print("Connecting to Gmail...")

try:
    msg = EmailMessage()
    msg["Subject"] = "Noise Monitor - Test Alert"
    msg["From"] = SENDER_EMAIL
    msg["To"] = WARDEN_EMAIL

    msg.set_content(
        """This is a test email from the Noise Level Monitor.

Hostel: A-Block
Room: 1
Noise Level: 65.0 dB
Status: NOISY

The email notification system is working correctly.
"""
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        print("Connected to Gmail.")

        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        print("LOGIN SUCCESSFUL")

        server.send_message(msg)
        print("EMAIL SENT SUCCESSFULLY")

except Exception as e:
    print("ERROR:", type(e).__name__)
    print("DETAIL:", e)