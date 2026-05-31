"""
main.py — FastAPI application.

Serves as the control plane for the pipeline:
  • Starts the RabbitMQ consumer in a background thread on startup
  • Exposes REST endpoints to inspect status, view messages, send test emails

Access the interactive docs at: http://localhost:8000/docs
"""

import logging
import os
import threading
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import consumer as consumer_module
from consumer import start_consuming, get_stats, get_messages
from emailer import send_email

# ─── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt= "%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("main")


# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "Pipeline Consumer API",
    description = (
        "Control plane for the **SQLite → Logstash → RabbitMQ → Email** pipeline.\n\n"
        "- View real-time consumer stats\n"
        "- Browse processed messages\n"
        "- Trigger test emails manually"
    ),
    version = "1.0.0",
    docs_url= "/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)


# ─── Startup: launch consumer thread ─────────────────────────────────────────
@app.on_event("startup")
async def startup_event() -> None:
    logger.info("🚀  Starting consumer background thread…")
    thread = threading.Thread(
        target  = start_consuming,
        name    = "rabbitmq-consumer",
        daemon  = True,
    )
    thread.start()
    logger.info("✅  Consumer thread launched")


# ─── Pydantic Models ─────────────────────────────────────────────────────────
class TestEmailRequest(BaseModel):
    customer_name : str  = "Test Customer"
    product       : str  = "Demo Product"
    amount        : float= 99.99
    status        : str  = "test"
    customer_email: str  = "test@example.com"
    created_at    : str  = ""

    class Config:
        json_schema_extra = {
            "example": {
                "customer_name":  "John Doe",
                "product":        "Laptop Pro 15",
                "amount":         1299.99,
                "status":         "shipped",
                "customer_email": "john@example.com",
                "created_at":     "2024-01-15 10:30:00",
            }
        }


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> str:
    """Visual HTML dashboard."""
    stats = get_stats()
    msgs  = get_messages()[:5]

    status_color = {
        "connected":   "#22c55e",
        "connecting":  "#f59e0b",
        "reconnecting":"#f59e0b",
        "error":       "#ef4444",
        "starting":    "#8b5cf6",
    }.get(stats.get("status", ""), "#6b7280")

    rows = ""
    for m in msgs:
        rows += f"""
        <tr>
          <td>#{m.get('order_id','—')}</td>
          <td>{m.get('customer','—')}</td>
          <td>{m.get('product','—')}</td>
          <td>${m.get('amount','—')}</td>
          <td><span class="badge">{m.get('status','—')}</span></td>
          <td>{m.get('received_at','—')}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <meta name="description" content="Real-time pipeline monitoring dashboard"/>
  <title>Pipeline Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet"/>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Inter',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}}
    header{{background:linear-gradient(135deg,#667eea,#764ba2);padding:28px 40px;display:flex;align-items:center;gap:16px}}
    header h1{{font-size:24px;color:#fff;font-weight:700}}
    header p{{font-size:13px;color:rgba(255,255,255,.75);margin-top:4px}}
    .badge-header{{background:rgba(255,255,255,.2);color:#fff;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600}}
    main{{padding:32px 40px;max-width:1200px;margin:0 auto}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-bottom:32px}}
    .card{{background:#1e293b;border-radius:12px;padding:24px;border:1px solid #334155}}
    .card .label{{font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px}}
    .card .value{{font-size:32px;font-weight:700;color:#f1f5f9}}
    .card .value.green{{color:#22c55e}}
    .card .value.blue{{color:#60a5fa}}
    .card .value.red{{color:#f87171}}
    .status-dot{{display:inline-block;width:10px;height:10px;border-radius:50%;background:{status_color};
                 margin-right:8px;animation:pulse 2s ease-in-out infinite}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
    h2{{font-size:18px;font-weight:600;margin-bottom:16px;color:#f1f5f9}}
    table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden;
           border:1px solid #334155}}
    th{{background:#0f172a;padding:12px 16px;text-align:left;font-size:12px;color:#94a3b8;
        text-transform:uppercase;letter-spacing:.6px}}
    td{{padding:12px 16px;font-size:13px;border-top:1px solid #334155;color:#cbd5e1}}
    .badge{{background:#312e81;color:#a5b4fc;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600}}
    .links{{margin-top:24px;display:flex;gap:12px}}
    .btn{{display:inline-block;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;
          text-decoration:none;transition:opacity .2s}}
    .btn-purple{{background:#7c3aed;color:#fff}}.btn-purple:hover{{opacity:.85}}
    .btn-gray{{background:#334155;color:#e2e8f0}}.btn-gray:hover{{opacity:.85}}
    .meta{{font-size:12px;color:#64748b;margin-top:6px}}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>⚡ Pipeline Dashboard</h1>
      <p>SQLite → Logstash → RabbitMQ → Python Consumer → Email</p>
    </div>
    <span class="badge-header" style="margin-left:auto">
      <span class="status-dot"></span>{stats.get('status','unknown').upper()}
    </span>
  </header>
  <main>
    <div class="grid">
      <div class="card">
        <div class="label">Messages Processed</div>
        <div class="value blue">{stats.get('messages_processed',0)}</div>
      </div>
      <div class="card">
        <div class="label">Emails Sent</div>
        <div class="value green">{stats.get('emails_sent',0)}</div>
      </div>
      <div class="card">
        <div class="label">Errors</div>
        <div class="value red">{stats.get('errors',0)}</div>
      </div>
      <div class="card">
        <div class="label">Consumer Status</div>
        <div class="value" style="font-size:18px;margin-top:4px">
          <span class="status-dot"></span>{stats.get('status','—').capitalize()}
        </div>
        <div class="meta">Connected at: {stats.get('connected_at','—')}</div>
      </div>
    </div>

    <h2>Recent Messages (last 5)</h2>
    <table>
      <thead>
        <tr>
          <th>Order ID</th><th>Customer</th><th>Product</th>
          <th>Amount</th><th>Status</th><th>Received At</th>
        </tr>
      </thead>
      <tbody>
        {'<tr><td colspan="6" style="text-align:center;color:#64748b;padding:24px">No messages yet — waiting for Logstash…</td></tr>' if not rows else rows}
      </tbody>
    </table>

    <div class="links">
      <a class="btn btn-purple" href="/docs">📖 API Docs</a>
      <a class="btn btn-gray"   href="/status">📊 JSON Status</a>
      <a class="btn btn-gray"   href="/messages">📨 All Messages</a>
    </div>
  </main>
</body>
</html>"""


@app.get("/health", tags=["System"])
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "service": "consumer", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.get("/status", tags=["Consumer"])
async def status() -> dict:
    """
    Returns current consumer statistics:
    - Connection status
    - Messages processed
    - Emails sent
    - Error count
    - Timestamps
    """
    return get_stats()


@app.get("/messages", tags=["Consumer"])
async def messages(limit: int = 50) -> list[dict]:
    """
    Returns the last `limit` messages consumed from RabbitMQ (newest first).
    
    - **limit**: Max number of messages to return (default: 50, max: 100)
    """
    limit = min(max(limit, 1), 100)
    return get_messages()[:limit]


@app.post("/send-test", tags=["Testing"])
async def send_test(req: TestEmailRequest) -> dict:
    """
    Manually trigger a test email without going through RabbitMQ.

    Useful to verify Gmail SMTP credentials are working.
    """
    data = req.model_dump()
    if not data.get("created_at"):
        data["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    data["id"] = "TEST"

    try:
        send_email(data)
        return {
            "success":  True,
            "message":  f"Test email sent to {os.getenv('SMTP_TO')}",
            "order":    data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
