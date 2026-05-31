"""
emailer.py — Gmail SMTP email sender.

Sends a rich HTML email notification for each order consumed from RabbitMQ.
Uses Gmail App Password (not your account password).
"""

import os
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger("emailer")


# ─── HTML Template ────────────────────────────────────────────────────────────

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Order Notification</title>
  <style>
    body {{
      margin: 0; padding: 0;
      font-family: 'Segoe UI', Arial, sans-serif;
      background: #f0f4f8;
    }}
    .wrapper {{
      max-width: 600px; margin: 30px auto; background: #ffffff;
      border-radius: 12px; overflow: hidden;
      box-shadow: 0 4px 20px rgba(0,0,0,.12);
    }}
    .header {{
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      padding: 32px 40px; text-align: center;
    }}
    .header h1 {{
      margin: 0; color: #fff; font-size: 26px; letter-spacing: .5px;
    }}
    .header p {{
      margin: 6px 0 0; color: rgba(255,255,255,.85); font-size: 14px;
    }}
    .body {{ padding: 36px 40px; }}
    .badge {{
      display: inline-block; padding: 4px 14px; border-radius: 20px;
      font-size: 12px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .8px;
    }}
    .badge-pending    {{ background:#fef3c7; color:#92400e; }}
    .badge-processing {{ background:#dbeafe; color:#1e40af; }}
    .badge-shipped    {{ background:#e0f2fe; color:#0369a1; }}
    .badge-delivered  {{ background:#dcfce7; color:#166534; }}
    .badge-cancelled  {{ background:#fee2e2; color:#991b1b; }}
    .badge-test       {{ background:#f3e8ff; color:#6b21a8; }}
    table.details {{
      width: 100%; border-collapse: collapse; margin-top: 20px;
    }}
    table.details td {{
      padding: 12px 16px; border-bottom: 1px solid #e5e7eb; font-size: 14px;
    }}
    table.details td:first-child {{
      color: #6b7280; font-weight: 600; width: 40%;
    }}
    table.details td:last-child {{ color: #111827; }}
    .amount {{ font-size: 22px; font-weight: 700; color: #667eea; }}
    .footer {{
      background: #f9fafb; padding: 20px 40px; text-align: center;
      color: #9ca3af; font-size: 12px; border-top: 1px solid #e5e7eb;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>📦 Order Notification</h1>
      <p>Processed via Logstash → RabbitMQ Pipeline</p>
    </div>
    <div class="body">
      <p style="margin:0 0 8px;color:#374151;font-size:15px;">
        A new order has been received and processed:
      </p>
      <span class="badge badge-{status_class}">{status_label}</span>

      <table class="details">
        <tr><td>Order ID</td>      <td><strong>#{order_id}</strong></td></tr>
        <tr><td>Customer</td>      <td>{customer_name}</td></tr>
        <tr><td>Email</td>         <td>{customer_email}</td></tr>
        <tr><td>Product</td>       <td>{product}</td></tr>
        <tr><td>Amount</td>        <td><span class="amount">${amount}</span></td></tr>
        <tr><td>Order Date</td>    <td>{created_at}</td></tr>
        <tr><td>Processed At</td>  <td>{processed_at}</td></tr>
      </table>
    </div>
    <div class="footer">
      This email was sent automatically by the Data Pipeline system.<br/>
      Logstash &rarr; RabbitMQ &rarr; Python Consumer &rarr; Gmail
    </div>
  </div>
</body>
</html>
"""

PLAIN_TEMPLATE = """
New Order Notification
======================
Order ID    : #{order_id}
Customer    : {customer_name}
Email       : {customer_email}
Product     : {product}
Amount      : ${amount}
Status      : {status_label}
Order Date  : {created_at}
Processed At: {processed_at}

---
Sent by the Data Pipeline (Logstash → RabbitMQ → Consumer)
"""


# ─── Public API ───────────────────────────────────────────────────────────────

def send_email(data: dict) -> None:
    """Send an order notification email using Gmail SMTP over SSL."""
    smtp_from  = os.getenv("SMTP_FROM", "").strip()
    smtp_to    = os.getenv("SMTP_TO",   "").strip()
    app_pass   = os.getenv("SMTP_APP_PASS", "").replace(" ", "").strip()

    if not all([smtp_from, smtp_to, app_pass]):
        logger.error("SMTP credentials missing — skipping email.")
        return

    status_raw   = str(data.get("status", "unknown")).lower()
    status_label = status_raw.capitalize()
    status_class = status_raw if status_raw in {"pending","processing","shipped","delivered","cancelled"} else "test"
    order_id     = data.get("id", "N/A")
    processed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    ctx = {
        "order_id":       order_id,
        "customer_name":  data.get("customer_name",  "N/A"),
        "customer_email": data.get("customer_email", "N/A"),
        "product":        data.get("product",        "N/A"),
        "amount":         f"{float(data.get('amount', 0)):.2f}",
        "status_label":   status_label,
        "status_class":   status_class,
        "created_at":     data.get("created_at",     "N/A"),
        "processed_at":   processed_at,
    }

    subject = f"[Order #{order_id}] {ctx['product']} — {status_label}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_from
    msg["To"]      = smtp_to

    msg.attach(MIMEText(PLAIN_TEMPLATE.format(**ctx), "plain"))
    msg.attach(MIMEText(HTML_TEMPLATE.format(**ctx),  "html"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(smtp_from, app_pass)
            server.sendmail(smtp_from, smtp_to, msg.as_string())
        logger.info(f"✉️  Email sent → {smtp_to}  |  Order #{order_id}  |  {ctx['product']}")
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP Authentication failed — check your Gmail App Password.")
    except Exception as e:
        logger.error(f"Failed to send email for order #{order_id}: {e}")
