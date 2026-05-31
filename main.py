"""
main.py (project root)
──────────────────────
This file is the root entry point marker for the project.
The actual FastAPI application lives in:  consumer/main.py

To run the full pipeline:
    docker compose up --build

Services:
  ┌───────────────────────────────────────────────────────┐
  │  db_seeder  → seeds SQLite orders.db (one-shot)       │
  │  logstash   → reads SQLite, publishes to RabbitMQ     │
  │  rabbitmq   → message broker (UI: localhost:15672)    │
  │  consumer   → FastAPI app (UI: localhost:8000)        │
  └───────────────────────────────────────────────────────┘
"""
