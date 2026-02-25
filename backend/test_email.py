import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

smtp_user = "monty.1907@gmail.com"
smtp_password = "sxsgdejxkwmzstqn"
to_email = "dmoneksh@yahoo.com"

msg = MIMEMultipart("alternative")
msg["Subject"] = "Market Engine - Email Connected!"
msg["From"] = smtp_user
msg["To"] = to_email

html = """
<div style="font-family:Arial,sans-serif;background:#0a0e1a;color:#e2e8f0;padding:32px;border-radius:12px;border:1px solid #1e293b;max-width:500px;">
  <h2 style="color:#00d4ff;margin-top:0;">Market Engine Connected!</h2>
  <p>SMTP email is working. Strategy requests will now be delivered to this inbox.</p>
  <p style="color:#94a3b8;font-size:12px;">From: monty.1907@gmail.com</p>
</div>
"""
msg.attach(MIMEText(html, "html"))

try:
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_email, msg.as_string())
    print("Email sent successfully to", to_email)
except Exception as e:
    print("Failed:", e)
