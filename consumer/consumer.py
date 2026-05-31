"""
consumer.py — RabbitMQ consumer thread.

Runs in a background thread (started by FastAPI on startup).
Consumes messages from 'orders_queue', triggers email on each.
Exposes shared state (stats, message log) to the FastAPI app.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any

import pika
import pika.exceptions

from emailer import send_email

logger = logging.getLogger("consumer")

# ─── Shared State (thread-safe via lock) ─────────────────────────────────────
_lock = threading.Lock()

_stats: dict[str, Any] = {
    "status":             "starting",
    "messages_processed": 0,
    "emails_sent":        0,
    "errors":             0,
    "last_message_at":    None,
    "connected_at":       None,
}

_messages: list[dict] = []          # ring-buffer — last 100 messages
MAX_MESSAGES = 100


def get_stats() -> dict:
    with _lock:
        return dict(_stats)


def get_messages() -> list[dict]:
    with _lock:
        return list(reversed(_messages))   # newest first


# ─── Consumer Loop ────────────────────────────────────────────────────────────

def _build_params() -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        host        = os.getenv("RABBITMQ_HOST", "rabbitmq"),
        port        = int(os.getenv("RABBITMQ_PORT", "5672")),
        credentials = pika.PlainCredentials(
            username = os.getenv("RABBITMQ_USER", "guest"),
            password = os.getenv("RABBITMQ_PASS", "guest"),
        ),
        heartbeat                 = 600,
        blocked_connection_timeout= 300,
        connection_attempts       = 3,
        retry_delay               = 5,
    )


def _on_message(ch, method, properties, body: bytes) -> None:
    """Callback executed for every message received from RabbitMQ."""
    now = datetime.utcnow().isoformat() + "Z"
    try:
        data = json.loads(body.decode("utf-8"))
        logger.info(f"📨  Received order #{data.get('id')} — {data.get('product')}")

        # Send email
        send_email(data)

        # Update shared state
        with _lock:
            _stats["messages_processed"] += 1
            _stats["emails_sent"]         += 1
            _stats["last_message_at"]     = now

            _messages.append({
                "received_at": now,
                "order_id":    data.get("id"),
                "customer":    data.get("customer_name"),
                "product":     data.get("product"),
                "amount":      data.get("amount"),
                "status":      data.get("status"),
                "raw":         data,
            })
            if len(_messages) > MAX_MESSAGES:
                _messages.pop(0)

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON body: {e}")
        with _lock:
            _stats["errors"] += 1
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        with _lock:
            _stats["errors"] += 1
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consuming() -> None:
    """
    Entry-point for the background thread.
    Retries indefinitely on connection failure.
    """
    exchange     = os.getenv("RABBITMQ_EXCHANGE",    "orders_exchange")
    queue        = os.getenv("RABBITMQ_QUEUE",        "orders_queue")
    routing_key  = os.getenv("RABBITMQ_ROUTING_KEY", "order")

    while True:
        try:
            logger.info("🔌  Connecting to RabbitMQ…")
            with _lock:
                _stats["status"] = "connecting"

            connection = pika.BlockingConnection(_build_params())
            channel    = connection.channel()

            # Declare exchange + queue + binding (idempotent)
            channel.exchange_declare(
                exchange      = exchange,
                exchange_type = "direct",
                durable       = True,
            )
            channel.queue_declare(queue=queue, durable=True)
            channel.queue_bind(
                queue       = queue,
                exchange    = exchange,
                routing_key = routing_key,
            )

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue, on_message_callback=_on_message)

            now = datetime.utcnow().isoformat() + "Z"
            with _lock:
                _stats["status"]       = "connected"
                _stats["connected_at"] = now

            logger.info(f"✅  Connected — consuming from '{queue}'")
            channel.start_consuming()          # blocks until connection drops

        except pika.exceptions.AMQPConnectionError as e:
            logger.warning(f"RabbitMQ connection failed: {e}. Retrying in 5s…")
            with _lock:
                _stats["status"] = "reconnecting"
            time.sleep(5)

        except Exception as e:
            logger.error(f"Unexpected error in consumer: {e}. Retrying in 10s…")
            with _lock:
                _stats["status"] = "error"
            time.sleep(10)
