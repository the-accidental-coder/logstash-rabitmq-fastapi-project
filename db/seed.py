"""
seed.py — Creates and populates the SQLite orders database.
Writes to /data/orders.db (Docker volume shared with Logstash).
"""

import sqlite3
import random
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "/data/orders.db")

PRODUCTS = [
    "Laptop Pro 15",
    "Wireless Earbuds",
    "Mechanical Keyboard",
    "4K Monitor",
    "USB-C Hub",
    "Webcam HD",
    "Standing Desk",
    "Ergonomic Chair",
    "External SSD 1TB",
    "Smart Speaker",
    "Graphics Tablet",
    "LED Desk Lamp",
    "Noise-Cancelling Headphones",
    "Gaming Mouse",
    "Portable Charger 20000mAh",
]

CUSTOMERS = [
    ("Alice Smith",   "alice.smith@example.com"),
    ("Bob Johnson",   "bob.johnson@example.com"),
    ("Charlie Brown", "charlie.brown@example.com"),
    ("Diana Prince",  "diana.prince@example.com"),
    ("Eve Wilson",    "eve.wilson@example.com"),
    ("Frank Miller",  "frank.miller@example.com"),
    ("Grace Lee",     "grace.lee@example.com"),
    ("Henry Davis",   "henry.davis@example.com"),
    ("Iris Chen",     "iris.chen@example.com"),
    ("James Walker",  "james.walker@example.com"),
]

STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]


def seed_database() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name  TEXT    NOT NULL,
            customer_email TEXT    NOT NULL,
            product        TEXT    NOT NULL,
            amount         REAL    NOT NULL,
            status         TEXT    NOT NULL,
            created_at     TEXT    NOT NULL
        )
    """)

    # Skip if already seeded
    cursor.execute("SELECT COUNT(*) FROM orders")
    existing = cursor.fetchone()[0]
    if existing > 0:
        print(f"[seeder] DB already has {existing} orders — skipping seed.")
        conn.close()
        return

    # Insert 50 dummy orders spread across the last 30 days
    base_time = datetime.utcnow() - timedelta(days=30)
    rows = []
    for i in range(1):
        name, email = random.choice(CUSTOMERS)
        product      = random.choice(PRODUCTS)
        amount       = round(random.uniform(9.99, 1499.99), 2)
        status       = random.choices(STATUSES, weights=[3, 3, 2, 2, 1])[0]
        created_at   = (base_time + timedelta(hours=i * 14, minutes=random.randint(0, 59))).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        rows.append((name, email, product, amount, status, created_at))

    cursor.executemany(
        "INSERT INTO orders (customer_name, customer_email, product, amount, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()

    print(f"[seeder] ✅  Seeded {len(rows)} orders into {DB_PATH}")

    # Show a preview
    cursor.execute("SELECT id, customer_name, product, amount, status FROM orders LIMIT 5")
    print("[seeder] Preview:")
    for row in cursor.fetchall():
        print(f"  {row}")

    conn.close()


if __name__ == "__main__":
    seed_database()
