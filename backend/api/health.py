"""Liveness/readiness probe."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from db.connection import get_pool

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, Any]:
    """Lightweight health check — confirms the API is up and DB is reachable."""
    db_state = "disconnected"
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            one = await conn.fetchval("SELECT 1")
            if one == 1:
                db_state = "connected"
    except Exception as exc:  # noqa: BLE001
        logger.warning("health: DB probe failed: %s", exc)

    return {"status": "ok", "db": db_state}
