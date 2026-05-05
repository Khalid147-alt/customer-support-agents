"""order_status tool — query the orders table by human-readable order_id."""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from db.adapter import get_pool

logger = logging.getLogger(__name__)


def _serialize(value: Any) -> Any:
    """Cast Postgres types into JSON-safe primitives."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


async def get_order_status(order_id: str) -> dict[str, Any]:
    """Look up an order by its human-readable order_id (e.g. 'ORD-2024-0001').

    Returns the order's current state plus the customer name for personalization.
    On miss, returns {"error": "Order not found", "order_id": ...} so the LLM can
    phrase a useful response without crashing.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                o.order_id,
                o.status,
                o.items,
                o.total_amount,
                o.tracking_number,
                o.estimated_delivery,
                o.created_at,
                u.name  AS customer_name,
                u.email AS customer_email
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            WHERE o.order_id = $1
            """,
            order_id,
        )

    if row is None:
        logger.info("order_status — miss for %s", order_id)
        return {"error": "Order not found", "order_id": order_id}

    # asyncpg returns JSONB as parsed Python (list/dict) — pass through.
    return {
        "order_id":           row["order_id"],
        "status":             row["status"],
        "items":              row["items"],
        "total_amount":       _serialize(row["total_amount"]),
        "tracking_number":    row["tracking_number"],
        "estimated_delivery": _serialize(row["estimated_delivery"]),
        "created_at":         _serialize(row["created_at"]),
        "customer_name":      row["customer_name"],
    }
