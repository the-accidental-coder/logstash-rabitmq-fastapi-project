# Data Pipeline: SQLite → Logstash → RabbitMQ → Python Consumer → Email

A fully Dockerized event-driven data pipeline built with Logstash, RabbitMQ, FastAPI, and Gmail SMTP.

## Architecture

```
SQLite DB (50 seeded orders)
    │  (JDBC input, polls every 30s)
    ▼
Logstash
    │  (logstash-output-rabbitmq)
    ▼
RabbitMQ Exchange (orders_exchange)
    │  (routing_key: order)
    ▼
RabbitMQ Queue (orders_queue)
    │
    ▼
Python Consumer (background thread)
    ├── FastAPI dashboard  →  http://localhost:8000
    └── Gmail SMTP email   →  som.python@gmail.com
```

## Services

| Service | Port | Description |
|---|---|---|
| `rabbitmq` | 5672 / 15672 | AMQP broker + Management UI |
| `logstash` | — | SQLite → RabbitMQ pipeline |
| `consumer` | 8000 | FastAPI app + RabbitMQ consumer |
| `db_seeder` | — | One-shot SQLite seeder |

## Quick Start

```bash
# 1. Clone and enter the project
cd docker-logstash-rabitmq-project

# 2. Build and launch all services
docker compose up --build

# 3. Watch the logs
docker compose logs -f
```

> **First run takes ~3–5 minutes** — Logstash image is large and the plugin/driver are downloaded during build.

## Endpoints

| URL | Description |
|---|---|
| `http://localhost:8000` | Visual dashboard |
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/status` | Consumer stats (JSON) |
| `http://localhost:8000/messages` | Last 50 messages |
| `http://localhost:8000/send-test` | POST — trigger test email |
| `http://localhost:15672` | RabbitMQ Management UI (guest/guest) |

## Testing Manually

### Trigger a test email
```bash
curl -X POST http://localhost:8000/send-test \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "John Doe",
    "product": "Laptop Pro 15",
    "amount": 1299.99,
    "status": "shipped"
  }'
```

### Check consumer status
```bash
curl http://localhost:8000/status
```

### View processed messages
```bash
curl http://localhost:8000/messages | python3 -m json.tool
```

### Check RabbitMQ queue depth
```bash
docker exec rabbitmq rabbitmqctl list_queues
```

## File Structure

```
docker-logstash-rabitmq-project/
├── docker-compose.yml       ← Orchestrates all services
├── .env                     ← Credentials (DO NOT COMMIT)
├── .gitignore
│
├── db/
│   ├── Dockerfile
│   └── seed.py              ← Seeds 50 orders into SQLite
│
├── logstash/
│   ├── Dockerfile           ← Installs RabbitMQ plugin + SQLite JDBC
│   ├── config/logstash.yml
│   └── pipeline/logstash.conf
│
└── consumer/
    ├── Dockerfile
    ├── requirements.txt
    ├── main.py              ← FastAPI app + background thread startup
    ├── consumer.py          ← RabbitMQ consumer (pika)
    └── emailer.py           ← Gmail SMTP sender
```

## Environment Variables (`.env`)

| Variable | Description |
|---|---|
| `RABBITMQ_USER` | RabbitMQ username |
| `RABBITMQ_PASS` | RabbitMQ password |
| `RABBITMQ_PORT` | AMQP port (default: 5672) |
| `SMTP_FROM` | Gmail sender address |
| `SMTP_TO` | Email recipient |
| `SMTP_APP_PASS` | Gmail App Password |

## Useful Commands

```bash
# Stop all services
docker compose down

# Stop and remove volumes (fresh start)
docker compose down -v

# View logs for a specific service
docker compose logs -f logstash
docker compose logs -f consumer

# Rebuild a single service
docker compose up --build consumer
```

## Notes

- Logstash polls SQLite every **30 seconds** — after the first poll, all 50 orders are processed
- Each consumed message triggers **one email** to `som.python@gmail.com`
- The consumer retries RabbitMQ connection automatically on failure
- RabbitMQ messages are **durable** and survive broker restarts
