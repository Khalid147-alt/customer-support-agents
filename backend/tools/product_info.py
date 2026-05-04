"""get_product_info tool — query the products table by SKU."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from db.connection import get_pool

logger = logging.getLogger(__name__)


async def get_product_info(sku: str) -> dict[str, Any]:
    """Look up a product by its SKU (e.g. 'SKU-001').

    Returns product detail or {"error": "Product not found"} on miss.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT sku, name, description, price, in_stock, return_policy
            FROM products
            WHERE sku = $1
            """,
            sku,
        )

    if row is None:
        logger.info("product_info — miss for %s", sku)
        return {"error": "Product not found", "sku": sku}

    return {
        "sku":           row["sku"],
        "name":          row["name"],
        "description":   row["description"],
        "price":         str(row["price"]) if isinstance(row["price"], Decimal) else row["price"],
        "in_stock":      row["in_stock"],
        "return_policy": row["return_policy"],
    }
