"""Idempotent SQLite seed for HuggingFace Spaces deployment.

Inserts the same fixture data as `db/seed.py` (5 users, 10 products, 15 orders,
0 tickets) into the SQLite database. Skips if data already exists.

Called automatically from `main.py` lifespan when USE_SQLITE=true so the
container is usable on cold start.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, timedelta

import aiosqlite

from db.sqlite_connection import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


USERS = [
    ("Alice Johnson",   "alice.johnson@example.com"),
    ("Bob Martinez",    "bob.martinez@example.com"),
    ("Carla Nguyen",    "carla.nguyen@example.com"),
    ("Daniel O'Brien",  "daniel.obrien@example.com"),
    ("Emma Schmidt",    "emma.schmidt@example.com"),
]


PRODUCTS = [
    ("SKU-001", "Wireless Noise-Cancelling Headphones",
     "Over-ear Bluetooth 5.3 headphones with 40h battery and active noise cancellation.",
     249.00, 1, "30 days"),
    ("SKU-002", "Mechanical Keyboard — Hot-Swap",
     "75% layout, hot-swappable switches, RGB backlight, USB-C, aluminum case.",
     139.00, 1, "30 days"),
    ("SKU-003", "4K USB-C Webcam",
     "Auto-focus, HDR, dual mics, plug-and-play webcam for streaming and meetings.",
     89.00, 1, "30 days"),
    ("SKU-004", "Standing Desk Mat",
     "Anti-fatigue ergonomic mat, 20\" x 32\", non-slip backing.",
     49.00, 1, "30 days"),
    ("SKU-005", "Smart LED Desk Lamp",
     "App-controlled tunable white + RGB, USB charging port, timer.",
     69.00, 0, "30 days"),
    ("SKU-006", "Portable SSD 1TB",
     "USB-C 3.2 Gen 2, 1050 MB/s read, shock-resistant aluminum chassis.",
     129.00, 1, "30 days"),
    ("SKU-007", "Ergonomic Vertical Mouse",
     "Reduces wrist strain; 6 programmable buttons; 2.4 GHz wireless.",
     59.00, 1, "30 days"),
    ("SKU-008", "Dual-Monitor Arm",
     "VESA 75/100, gas-spring counterbalance, supports up to 32\" monitors.",
     119.00, 1, "30 days"),
    ("SKU-009", "USB-C Hub 8-in-1",
     "HDMI 4K@60, 100W PD pass-through, SD/microSD, Ethernet, 3x USB-A.",
     79.00, 1, "30 days"),
    ("SKU-010", "Premium Software License (Digital)",
     "Annual subscription. Digital delivery via email — non-refundable.",
     199.00, 1, "Non-refundable"),
]


def _orders_seed() -> list[tuple]:
    today = date.today()

    def od(days: int) -> str | None:
        return (today + timedelta(days=days)).isoformat()

    return [
        ("ORD-2024-0001", "alice.johnson@example.com", "delivered",
         [{"sku": "SKU-001", "name": "Wireless Noise-Cancelling Headphones", "qty": 1, "price": "249.00"}],
         249.00, "1Z999AA10123456784", od(-3)),

        ("ORD-2024-0002", "bob.martinez@example.com", "shipped",
         [{"sku": "SKU-002", "name": "Mechanical Keyboard — Hot-Swap", "qty": 1, "price": "139.00"},
          {"sku": "SKU-007", "name": "Ergonomic Vertical Mouse",       "qty": 1, "price": "59.00"}],
         198.00, "1Z999AA10123456785", od(2)),

        ("ORD-2024-0003", "carla.nguyen@example.com", "processing",
         [{"sku": "SKU-006", "name": "Portable SSD 1TB", "qty": 2, "price": "129.00"}],
         258.00, None, od(5)),

        ("ORD-2024-0004", "daniel.obrien@example.com", "pending",
         [{"sku": "SKU-008", "name": "Dual-Monitor Arm", "qty": 1, "price": "119.00"}],
         119.00, None, od(7)),

        ("ORD-2024-0005", "emma.schmidt@example.com", "delivered",
         [{"sku": "SKU-003", "name": "4K USB-C Webcam",  "qty": 1, "price": "89.00"},
          {"sku": "SKU-009", "name": "USB-C Hub 8-in-1", "qty": 1, "price": "79.00"}],
         168.00, "1Z999AA10123456786", od(-7)),

        ("ORD-2024-0006", "alice.johnson@example.com", "shipped",
         [{"sku": "SKU-004", "name": "Standing Desk Mat", "qty": 1, "price": "49.00"}],
         49.00, "1Z999AA10123456787", od(1)),

        ("ORD-2024-0007", "bob.martinez@example.com", "cancelled",
         [{"sku": "SKU-005", "name": "Smart LED Desk Lamp", "qty": 1, "price": "69.00"}],
         69.00, None, None),

        ("ORD-2024-0008", "carla.nguyen@example.com", "delivered",
         [{"sku": "SKU-010", "name": "Premium Software License (Digital)", "qty": 1, "price": "199.00"}],
         199.00, None, od(-14)),

        ("ORD-2024-0009", "daniel.obrien@example.com", "shipped",
         [{"sku": "SKU-001", "name": "Wireless Noise-Cancelling Headphones", "qty": 1, "price": "249.00"},
          {"sku": "SKU-009", "name": "USB-C Hub 8-in-1",                     "qty": 1, "price": "79.00"}],
         328.00, "1Z999AA10123456788", od(3)),

        ("ORD-2024-0010", "emma.schmidt@example.com", "processing",
         [{"sku": "SKU-002", "name": "Mechanical Keyboard — Hot-Swap", "qty": 2, "price": "139.00"}],
         278.00, None, od(6)),

        ("ORD-2024-0011", "alice.johnson@example.com", "pending",
         [{"sku": "SKU-007", "name": "Ergonomic Vertical Mouse", "qty": 3, "price": "59.00"}],
         177.00, None, od(8)),

        ("ORD-2024-0012", "bob.martinez@example.com", "delivered",
         [{"sku": "SKU-008", "name": "Dual-Monitor Arm", "qty": 1, "price": "119.00"},
          {"sku": "SKU-004", "name": "Standing Desk Mat", "qty": 1, "price": "49.00"}],
         168.00, "1Z999AA10123456789", od(-2)),

        ("ORD-2024-0013", "carla.nguyen@example.com", "shipped",
         [{"sku": "SKU-003", "name": "4K USB-C Webcam", "qty": 1, "price": "89.00"}],
         89.00, "1Z999AA10123456790", od(2)),

        ("ORD-2024-0014", "daniel.obrien@example.com", "processing",
         [{"sku": "SKU-006", "name": "Portable SSD 1TB",       "qty": 1, "price": "129.00"},
          {"sku": "SKU-009", "name": "USB-C Hub 8-in-1",       "qty": 1, "price": "79.00"},
          {"sku": "SKU-007", "name": "Ergonomic Vertical Mouse","qty": 1, "price": "59.00"}],
         267.00, None, od(5)),

        ("ORD-2024-0015", "emma.schmidt@example.com", "pending",
         [{"sku": "SKU-001", "name": "Wireless Noise-Cancelling Headphones", "qty": 1, "price": "249.00"}],
         249.00, None, od(9)),
    ]


async def seed_sqlite() -> None:
    """Idempotent SQLite seed. Skips entirely if users table is already populated."""
    async with aiosqlite.connect(DEFAULT_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        async with conn.execute("SELECT COUNT(*) FROM users") as cur:
            (existing,) = await cur.fetchone()
        if existing and existing > 0:
            logger.info("SQLite seed skipped — %d users already present", existing)
            return

        # Users
        user_ids: dict[str, str] = {}
        for name, email in USERS:
            uid = str(uuid.uuid4())
            user_ids[email] = uid
            await conn.execute(
                "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
                (uid, name, email),
            )
        logger.info("Inserted %d users", len(USERS))

        # Products
        for sku, name, desc, price, in_stock, return_policy in PRODUCTS:
            await conn.execute(
                """
                INSERT INTO products (id, sku, name, description, price, in_stock, return_policy)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), sku, name, desc, price, in_stock, return_policy),
            )
        logger.info("Inserted %d products", len(PRODUCTS))

        # Orders
        inserted = 0
        for (order_id, email, status, items, total, tracking, est_delivery) in _orders_seed():
            uid = user_ids.get(email)
            if uid is None:
                logger.warning("Skipping order %s — user %s not found", order_id, email)
                continue
            await conn.execute(
                """
                INSERT INTO orders
                    (id, order_id, user_id, status, items, total_amount, tracking_number, estimated_delivery)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), order_id, uid, status, json.dumps(items), total, tracking, est_delivery),
            )
            inserted += 1
        logger.info("Inserted %d orders", inserted)

        await conn.commit()
