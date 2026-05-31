# Data Pipeline: MySQL → Logstash → RabbitMQ → Python Consumer → Email

A fully Dockerized event-driven data pipeline built with Logstash, RabbitMQ, FastAPI, and Gmail SMTP.
Now uses an **external MySQL database** (`test_logstash`) instead of SQLite.

## Architecture

```
MySQL DB (host: 127.0.0.1:3306 / test_logstash.orders)
    │  (JDBC input, polls every 30s via MySQL Connector/J)
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
| `logstash` | — | MySQL → RabbitMQ pipeline |
| `consumer` | 8000 | FastAPI app + RabbitMQ consumer |
| MySQL | 3306 | **Host machine** — `test_logstash` DB |

## Prerequisites

MySQL must be running on the host with the `test_logstash` database and `orders` table:

```sql
-- Connect
mysql -h 127.0.0.1 -P 3306 -u root -p'password' --ssl-mode=DISABLED test_logstash

-- Table (already created if you followed setup)
CREATE TABLE IF NOT EXISTS orders (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  customer_name  VARCHAR(255) NOT NULL,
  customer_email VARCHAR(255) NOT NULL,
  product        VARCHAR(255) NOT NULL,
  amount         DECIMAL(10,2) NOT NULL,
  status         VARCHAR(50) NOT NULL,
  created_at     DATETIME NOT NULL
);

-- Insert a test row
INSERT INTO orders (customer_name, customer_email, product, amount, status, created_at)
VALUES ('Alice Smith', 'alice.smith@example.com', 'Laptop Pro 15', 1299.99, 'shipped', NOW());
```

## Quick Start

```bash
# 1. Clone and enter the project
cd docker-logstash-rabitmq-project

# 2. Build and launch all services
docker compose up --build

# 3. Watch the logs
docker compose logs -f
```

> **First run takes ~3–5 minutes** — Logstash image is large and the MySQL JDBC driver is downloaded during build.

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

### Insert a new order (Logstash picks it up within 30s)
```bash
mysql -h 127.0.0.1 -P 3306 -u root -p'password' --ssl-mode=DISABLED test_logstash -e "
  INSERT INTO orders (customer_name, customer_email, product, amount, status, created_at)
  VALUES ('Bob Johnson', 'bob.johnson@example.com', 'Mechanical Keyboard', 89.99, 'pending', NOW());
"
```

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
├── logstash/
│   ├── Dockerfile           ← Downloads MySQL Connector/J JDBC driver
│   ├── config/logstash.yml
│   └── pipeline/logstash.conf  ← MySQL JDBC → RabbitMQ
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
| `MYSQL_HOST` | MySQL host (`host-gateway` for Docker→host) |
| `MYSQL_PORT` | MySQL port (default: 3306) |
| `MYSQL_USER` | MySQL username |
| `MYSQL_PASS` | MySQL password |
| `MYSQL_DB` | MySQL database name |
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
docker compose up --build logstash
```

## Notes

- Logstash polls MySQL every **30 seconds** using `WHERE id > :sql_last_value` for incremental reads
- Each consumed message triggers **one email** to `som.python@gmail.com`
- The consumer retries RabbitMQ connection automatically on failure
- RabbitMQ messages are **durable** and survive broker restarts
- MySQL runs on the **host machine** — Docker containers reach it via `host-gateway`
