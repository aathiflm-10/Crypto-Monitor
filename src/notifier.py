import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load variables from the local .env file (if it exists)
load_dotenv()

# Read configurations from environment variables
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
ENABLE_EMAIL = os.getenv("ENABLE_EMAIL", "False").lower() in ("true", "1", "yes")

def send_alert(coin_id, price_usd, anomaly_type, percent_deviation):
    """
    Sends an email notification when a price anomaly is detected.
    If email notifications are disabled or environment configurations are missing,
    it will log the alert details to the console instead.
    """
    subject = f"🚨 CRYPTO ALERT: {coin_id.upper()} {anomaly_type.upper()} Detected!"
    
    # Format the message body with details about the price movement
    body = f"""
    Hello,
    
    This is an automated alert from your Crypto Price Tracker Pipeline.
    
    An anomaly has been detected for: {coin_id.upper()}
    - Event Type: Price {anomaly_type}
    - Current Price: ${price_usd:,.2f} USD
    - Deviation from Average: {percent_deviation:+.2f}%
    
    Check your local dashboard to view the historical charts.
    
    Best regards,
    Your Crypto Pipeline
    """
    
    # 1. Console Log fall-back (Always active)
    print(f"\n[Notifier] Alert generated: [ALERT] CRYPTO ALERT: {coin_id.upper()} {anomaly_type.upper()} Detected!")
    print(f"[Notifier] Details: Price = ${price_usd:,.2f}, Dev = {percent_deviation:+.2f}%")
    
    # 2. Check if email sending is enabled
    if not ENABLE_EMAIL:
        print("[Notifier] Email sending is disabled in .env (ENABLE_EMAIL=False). Skipping SMTP dispatch.")
        return False
        
    # 3. Check for missing credentials
    if not all([SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL]):
        print("[Notifier] WARNING: Email config missing in .env file. Please check SENDER_EMAIL, SENDER_PASSWORD, and RECEIVER_EMAIL.")
        return False

    # 4. Construct and send the email
    try:
        # Create a container message (multipart email)
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject
        
        # Attach the body text to the message
        msg.attach(MIMEText(body, 'plain'))
        
        print(f"[Notifier] Connecting to SMTP server {SMTP_SERVER}:{SMTP_PORT}...")
        
        # Connect to Gmail SMTP server
        # We start with an unencrypted connection on port 587, then upgrade to secure SSL/TLS
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Secure the connection using TLS
        
        # Log in with the App Password
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        # Send the email
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        
        print(f"[Notifier] Alert email successfully sent to {RECEIVER_EMAIL}!")
        return True
        
    except Exception as e:
        print(f"[Notifier] ERROR: Failed to send email alert: {e}")
        return False
    finally:
        # Ensure the server connection is always closed if initialized
        try:
            server.quit()
        except NameError:
            pass # server was never initialized

# Direct execution for a mock test
if __name__ == "__main__":
    print("[Notifier] Executing notifier test check...")
    send_alert("bitcoin", 68500.0, "spike", 3.24)
