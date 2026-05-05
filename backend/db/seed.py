"""Seed the database with realistic fake data.

Idempotent: re-runs cleanly thanks to ON CONFLICT DO NOTHING on unique fields
(email, sku, order_id). Run with:

    python -m db.seed

from inside the backend/ directory (with .env present and Postgres running).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, timedelta
from decimal import Decimal

from db.adapter import close_db_pool, get_pool, init_db_pool

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("seed")


USERS = [
    ("Alice Johnson",   "alice.johnson@example.com"),
    ("Bob Martinez",    "bob.martinez@example.com"),
    ("Carla Nguyen",    "carla.nguyen@example.com"),
    ("Daniel O'Brien",  "daniel.obrien@example.com"),
    ("Emma Schmidt",    "emma.schmidt@example.com"),
]


PRODUCTS = [
    # (sku, name, description, price, in_stock, return_policy)
    ("SKU-001", "Wireless Noise-Cancelling Headphones",
     "Over-ear Bluetooth 5.3 headphones with 40h battery and active noise cancellation.",
     Decimal("249.00"), True,  "30 days"),
    ("SKU-002", "Mechanical Keyboard — Hot-Swap",
     "75% layout, hot-swappable switches, RGB backlight, USB-C, aluminum case.",
     Decimal("139.00"), True,  "30 days"),
    ("SKU-003", "4K USB-C Webcam",
     "Auto-focus, HDR, dual mics, plug-and-play webcam for streaming and meetings.",
     Decimal("89.00"),  True,  "30 days"),
    ("SKU-004", "Standing Desk Mat",
     "Anti-fatigue ergonomic mat, 20\" x 32\", non-slip backing.",
     Decimal("49.00"),  True,  "30 days"),
    ("SKU-005", "Smart LED Desk Lamp",
     "App-controlled tunable white + RGB, USB charging port, timer.",
     Decimal("69.00"),  False, "30 days"),
    ("SKU-006", "Portable SSD 1TB",
     "USB-C 3.2 Gen 2, 1050 MB/s read, shock-resistant aluminum chassis.",
     Decimal("129.00"), True,  "30 days"),
    ("SKU-007", "Ergonomic Vertical Mouse",
     "Reduces wrist strain; 6 programmable buttons; 2.4 GHz wireless.",
     Decimal("59.00"),  True,  "30 days"),
    ("SKU-008", "Dual-Monitor Arm",
     "VESA 75/100, gas-spring counterbalance, supports up to 32\" monitors.",
     Decimal("119.00"), True,  "30 days"),
    ("SKU-009", "USB-C Hub 8-in-1",
     "HDMI 4K@60, 100W PD pass-through, SD/microSD, Ethernet, 3x USB-A.",
     Decimal("79.00"),  True,  "30 days"),
    ("SKU-010", "Premium Software License (Digital)",
     "Annual subscription. Digital delivery via email — non-refundable.",
     Decimal("199.00"), True,  "Non-refundable"),
]


def _orders_seed() -> list[tuple]:
    """Return 15 orders spread across statuses, with realistic JSONB items."""
    today = date.today()

    def od(days: int) -> date:
        return today + timedelta(days=days)

    # (order_id, user_email, status, items, total_amount, tracking, est_delivery)
    return [
        ("ORD-2024-0001", "alice.johnson@example.com",  "delivered",
         [{"sku": "SKU-001", "name": "Wireless Noise-Cancelling Headphones", "qty": 1, "price": "249.00"}],
         Decimal("249.00"), "1Z999AA10123456784", od(-3)),

        ("ORD-2024-0002", "bob.martinez@example.com",   "shipped",
         [{"sku": "SKU-002", "name": "Mechanical Keyboard — Hot-Swap", "qty": 1, "price": "139.00"},
          {"sku": "SKU-007", "name": "Ergonomic Vertical Mouse",       "qty": 1, "price": "59.00"}],
         Decimal("198.00"), "1Z999AA10123456785", od(2)),

        ("ORD-2024-0003", "carla.nguyen@example.com",   "processing",
         [{"sku": "SKU-006", "name": "Portable SSD 1TB", "qty": 2, "price": "129.00"}],
         Decimal("258.00"), None, od(5)),

        ("ORD-2024-0004", "daniel.obrien@example.com",  "pending",
         [{"sku": "SKU-008", "name": "Dual-Monitor Arm", "qty": 1, "price": "119.00"}],
         Decimal("119.00"), None, od(7)),

        ("ORD-2024-0005", "emma.schmidt@example.com",   "delivered",
         [{"sku": "SKU-003", "name": "4K USB-C Webcam",  "qty": 1, "price": "89.00"},
          {"sku": "SKU-009", "name": "USB-C Hub 8-in-1", "qty": 1, "price": "79.00"}],
         Decimal("168.00"), "1Z999AA10123456786", od(-7)),

        ("ORD-2024-0006", "alice.johnson@example.com",  "shipped",
         [{"sku": "SKU-004", "name": "Standing Desk Mat", "qty": 1, "price": "49.00"}],
         Decimal("49.00"),  "1Z999AA10123456787", od(1)),

        ("ORD-2024-0007", "bob.martinez@example.com",   "cancelled",
         [{"sku": "SKU-005", "name": "Smart LED Desk Lamp", "qty": 1, "price": "69.00"}],
         Decimal("69.00"),  None, None),

        ("ORD-2024-0008", "carla.nguyen@example.com",   "delivered",
         [{"sku": "SKU-010", "name": "Premium Software License (Digital)", "qty": 1, "price": "199.00"}],
         Decimal("199.00"), None, od(-14)),

        ("ORD-2024-0009", "daniel.obrien@example.com",  "shipped",
         [{"sku": "SKU-001", "name": "Wireless Noise-Cancelling Headphones", "qty": 1, "price": "249.00"},
          {"sku": "SKU-009", "name": "USB-C Hub 8-in-1",                     "qty": 1, "price": "79.00"}],
         Decimal("328.00"), "1Z999AA10123456788", od(3)),

        ("ORD-2024-0010", "emma.schmidt@example.com",   "processing",
         [{"sku": "SKU-002", "name": "Mechanical Keyboard — Hot-Swap", "qty": 2, "price": "139.00"}],
         Decimal("278.00"), None, od(6)),

        ("ORD-2024-0011", "alice.johnson@example.com",  "pending",
         [{"sku": "SKU-007", "name": "Ergonomic Vertical Mouse", "qty": 3, "price": "59.00"}],
         Decimal("177.00"), None, od(8)),

        ("ORD-2024-0012", "bob.martinez@example.com",   "delivered",
         [{"sku": "SKU-008", "name": "Dual-Monitor Arm", "qty": 1, "price": "119.00"},
          {"sku": "SKU-004", "name": "Standing Desk Mat", "qty": 1, "price": "49.00"}],
         Decimal("168.00"), "1Z999AA10123456789", od(-2)),

        ("ORD-2024-0013", "carla.nguyen@example.com",   "shipped",
         [{"sku": "SKU-003", "name": "4K USB-C Webcam", "qty": 1, "price": "89.00"}],
         Decimal("89.00"),  "1Z999AA10123456790", od(2)),

        ("ORD-2024-0014", "daniel.obrien@example.com",  "processing",
         [{"sku": "SKU-006", "name": "Portable SSD 1TB",       "qty": 1, "price": "129.00"},
          {"sku": "SKU-009", "name": "USB-C Hub 8-in-1",       "qty": 1, "price": "79.00"},
          {"sku": "SKU-007", "name": "Ergonomic Vertical Mouse","qty": 1, "price": "59.00"}],
         Decimal("267.00"), None, od(5)),

        ("ORD-2024-0015", "emma.schmidt@example.com",   "pending",
         [{"sku": "SKU-001", "name": "Wireless Noise-Cancelling Headphones", "qty": 1, "price": "249.00"}],
         Decimal("249.00"), None, od(9)),
    ]


async def seed() -> None:
    pool = await init_db_pool(min_size=1, max_size=4)
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Users
                await conn.executemany(
                    """
                    INSERT INTO users (name, email)
                    VALUES ($1, $2)
                    ON CONFLICT (email) DO NOTHING
                    """,
                    USERS,
                )
                logger.info("Upserted %d users", len(USERS))

                # Products
                await conn.executemany(
                    """
                    INSERT INTO products (sku, name, description, price, in_stock, return_policy)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (sku) DO NOTHING
                    """,
                    PRODUCTS,
                )
                logger.info("Upserted %d products", len(PRODUCTS))

                # Orders — need to look up user_id from email
                inserted = 0
                for (order_id, email, status, items, total, tracking, est_delivery) in _orders_seed():
                    user_id = await conn.fetchval(
                        "SELECT id FROM users WHERE email = $1", email
                    )
                    if user_id is None:
                        logger.warning("Skipping order %s — user %s not found", order_id, email)
                        continue
                    result = await conn.execute(
                        """
                        INSERT INTO orders
                            (order_id, user_id, status, items, total_amount, tracking_number, estimated_delivery)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (order_id) DO NOTHING
                        """,
                        order_id, user_id, status, items, total, tracking, est_delivery,
                    )
                    # asyncpg returns "INSERT 0 1" or "INSERT 0 0"
                    if result.endswith(" 1"):
                        inserted += 1
                logger.info("Inserted %d new orders (idempotent skip on existing)", inserted)

        # Quick read-back so the user sees something useful in the terminal.
        async with pool.acquire() as conn:
            counts = await conn.fetchrow(
                """
                SELECT
                    (SELECT COUNT(*) FROM users)    AS users,
                    (SELECT COUNT(*) FROM products) AS products,
                    (SELECT COUNT(*) FROM orders)   AS orders,
                    (SELECT COUNT(*) FROM tickets)  AS tickets
                """
            )
            logger.info(
                "DB totals — users=%s, products=%s, orders=%s, tickets=%s",
                counts["users"], counts["products"], counts["orders"], counts["tickets"],
            )
    finally:
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(seed())
