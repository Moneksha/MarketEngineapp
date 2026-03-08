"""
Market Engine — Bulk Email Campaign Script
==========================================
Reads contacts from an Excel file and sends a marketing email.
Run in DRY RUN mode first to verify everything looks correct before sending live emails.

Usage:
    # Preview only — do NOT send emails:
    python send_campaign_email.py --dry-run --limit 10

    # Send to first 10 real contacts (verify everything is OK first):
    python send_campaign_email.py --limit 10

    # Send to ALL contacts:
    python send_campaign_email.py
"""

import smtplib
import time
import argparse
import logging
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import openpyxl

# ── Configuration ──────────────────────────────────────────────────────────────
EXCEL_FILE    = "/Users/dmoneksh/Desktop/client contact spreads sheet.xlsx"
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = "monty.1907@gmail.com"
SMTP_PASSWORD = "sxsgdejxkwmzstqn"
FROM_NAME     = "Moneksha Dangat | Market Engine"
DELAY_SECONDS = 1.5   # wait between each email to avoid rate limits

# ── Email Template ─────────────────────────────────────────────────────────────
SUBJECT = "Build & Automate Your Trading Strategy with Market Engine 📈"

def build_html_body(name: str) -> str:
    """Generate a rich HTML email body personalized with the recipient's name."""
    greeting = f"Hi {name.strip().title()}," if name and name not in ("-", "", "a", "1.0") else "Hi there,"
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    body {{
      margin: 0; padding: 0;
      font-family: 'Segoe UI', Arial, sans-serif;
      background-color: #f4f6f8;
      color: #1a1a2e;
    }}
    .wrapper {{
      max-width: 620px; margin: 30px auto;
      background: #ffffff;
      border-radius: 12px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08);
      overflow: hidden;
    }}
    .header {{
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      padding: 32px 40px;
      text-align: center;
    }}
    .header h1 {{
      color: #05e07d; font-size: 26px; margin: 0;
      letter-spacing: -0.5px; font-weight: 700;
    }}
    .header p {{
      color: #94a3b8; font-size: 13px; margin: 6px 0 0;
      letter-spacing: 1px; text-transform: uppercase;
    }}
    .body {{
      padding: 36px 40px;
    }}
    .body p {{
      font-size: 15px; line-height: 1.8; color: #334155; margin: 0 0 16px;
    }}
    .features {{
      background: #f8fafc; border-left: 4px solid #05e07d;
      border-radius: 8px; padding: 20px 24px; margin: 24px 0;
    }}
    .features ul {{
      margin: 0; padding: 0; list-style: none;
    }}
    .features ul li {{
      font-size: 14px; color: #334155; padding: 4px 0;
    }}
    .features ul li::before {{
      content: "✅ "; 
    }}
    .cta-btn {{
      display: block; width: fit-content; margin: 28px auto;
      background: linear-gradient(135deg, #05e07d, #00c86a);
      color: #0f172a !important; text-decoration: none;
      padding: 14px 36px; border-radius: 50px;
      font-size: 15px; font-weight: 700; letter-spacing: 0.3px;
      box-shadow: 0 4px 14px rgba(5,224,125,0.35);
    }}
    .footer {{
      background: #f1f5f9; padding: 24px 40px; text-align: center;
    }}
    .footer p {{
      font-size: 12px; color: #94a3b8; margin: 0;
    }}
    .footer a {{
      color: #05e07d; text-decoration: none;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>📊 Market Engine</h1>
      <p>Institutional-Grade Trading Platform</p>
    </div>
    <div class="body">
      <p>{greeting}</p>
      <p>
        I'm <strong>Moneksha Dangat</strong> from <strong>Market Engine</strong> — a professional platform built for serious traders who want to develop, backtest, and automate their trading strategies for Indian markets.
      </p>
      <p>Whether you trade Nifty options, equity, or run systematic strategies, Market Engine helps you:</p>
      <div class="features">
        <ul>
          <li>Build and backtest custom intraday & positional strategies</li>
          <li>Paper trade live with real-time Zerodha Kite data</li>
          <li>Automate EMA crossovers, straddles, and credit spreads</li>
          <li>Get real-time PnL tracking and strategy performance reports</li>
          <li>Use institutional-grade risk management tools</li>
        </ul>
      </div>
      <p>
        We're helping traders move from <em>"guessing"</em> to <em>"systematic, data-driven decisions"</em>.
      </p>
      <a class="cta-btn" href="https://marketengine.in" target="_blank">
        Visit Market Engine →
      </a>
      <p style="font-size: 13px; color: #64748b;">
        Have questions? Simply reply to this email or chat with me on WhatsApp at <strong>+91 93722 25072</strong>. I typically respond within minutes. 😊
      </p>
    </div>
    <div class="footer">
      <p>
        Market Engine · <a href="https://marketengine.in">marketengine.in</a><br/>
        You received this because your details were in our network. 
        To unsubscribe, reply with "Unsubscribe".
      </p>
    </div>
  </div>
</body>
</html>
"""

# ── Logging Setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("email_campaign.log"),
    ]
)
log = logging.getLogger(__name__)


# ── Load Contacts from Excel ───────────────────────────────────────────────────
def load_contacts(limit: int = None):
    """Load contacts from Excel. Returns list of (name, email) tuples, skipping invalid rows."""
    path = Path(EXCEL_FILE)
    if not path.exists():
        log.error(f"Excel file not found: {EXCEL_FILE}")
        sys.exit(1)

    wb = openpyxl.load_workbook(str(path))
    ws = wb.active

    contacts = []
    skipped = 0
    for row in ws.iter_rows(min_row=2, values_only=True):  # Skip header row
        name  = str(row[0]).strip() if row[0] else ""
        email = str(row[1]).strip() if row[1] else ""

        # Basic email validation
        if "@" not in email or "." not in email.split("@")[-1]:
            skipped += 1
            continue

        contacts.append((name, email))
        if limit and len(contacts) >= limit:
            break

    log.info(f"✅ Loaded {len(contacts)} valid contacts (skipped {skipped} invalid rows)")
    return contacts


# ── Send a Single Email ────────────────────────────────────────────────────────
def send_email(server: smtplib.SMTP, to_email: str, name: str, dry_run: bool) -> bool:
    """Build and send (or preview) a single email. Returns True on success."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = SUBJECT
    msg["From"]    = f"{FROM_NAME} <{SMTP_USER}>"
    msg["To"]      = to_email

    html_body = build_html_body(name)
    msg.attach(MIMEText(html_body, "html"))

    if dry_run:
        log.info(f"  [DRY RUN] Would send to: {name!r} <{to_email}>")
        return True

    try:
        server.sendmail(SMTP_USER, to_email, msg.as_string())
        log.info(f"  ✉️  Sent → {name!r} <{to_email}>")
        return True
    except Exception as e:
        log.error(f"  ❌ FAILED → {to_email}: {e}")
        return False


# ── Main Campaign Runner ───────────────────────────────────────────────────────
def run_campaign(limit: int = None, dry_run: bool = True):
    mode = "DRY RUN (preview only)" if dry_run else "LIVE SEND"
    log.info(f"{'='*60}")
    log.info(f"Market Engine Email Campaign — Mode: {mode}")
    log.info(f"Limit: {limit or 'ALL'} contacts")
    log.info(f"{'='*60}")

    contacts = load_contacts(limit=limit)

    if not contacts:
        log.error("No valid contacts found. Exiting.")
        return

    # Preview first 5 rows
    log.info("--- Sample contacts to be emailed ---")
    for name, email in contacts[:5]:
        log.info(f"  Name: {name!r:30} | Email: {email}")
    if len(contacts) > 5:
        log.info(f"  ... and {len(contacts) - 5} more.")
    log.info("-------------------------------------")

    if dry_run:
        log.info("DRY RUN complete. No emails were sent. Run without --dry-run to send real emails.")
        return

    # Connect to SMTP
    success_count = 0
    fail_count = 0

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            log.info(f"✅ SMTP authenticated successfully as {SMTP_USER}")

            for i, (name, email) in enumerate(contacts, 1):
                log.info(f"[{i}/{len(contacts)}] Sending...")
                ok = send_email(server, email, name, dry_run=False)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                time.sleep(DELAY_SECONDS)  # Rate limiting

    except Exception as e:
        log.error(f"SMTP Connection error: {e}")
        return

    log.info(f"{'='*60}")
    log.info(f"Campaign done! ✅ Sent: {success_count} | ❌ Failed: {fail_count}")
    log.info(f"{'='*60}")


# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Market Engine Bulk Email Campaign")
    parser.add_argument("--dry-run",  action="store_true",  help="Preview only, do NOT send emails")
    parser.add_argument("--limit",    type=int, default=None, help="Max number of contacts to process")
    args = parser.parse_args()

    run_campaign(limit=args.limit, dry_run=args.dry_run)
