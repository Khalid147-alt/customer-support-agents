"""asyncpg connection-pool lifecycle.

Use `init_db_pool()` at app startup (FastAPI lifespan) and `close_db_pool()` at shutdown.
Anywhere else in the codebase, call `get_pool()` to acquire connections.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import asyncpg

from config import get_settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Per-connection setup: register JSON/JSONB codecs so they round-trip as Python dicts/lists."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_db_pool(min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    """Create the global asyncpg pool. Idempotent."""
    global _pool
    if _pool is not None:
        return _pool

    settings = get_settings()
    logger.info("Initializing asyncpg pool")
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=min_size,
        max_size=max_size,
        command_timeout=30,
        init=_init_connection,
    )
    return _pool


async def close_db_pool() -> None:
    """Close the global pool. Safe to call multiple times."""
    global _pool
    if _pool is None:
        return
    logger.info("Closing asyncpg pool")
    await _pool.close()
    _pool = None


def get_pool() -> asyncpg.Pool:
    """Return the active pool. Raises if not yet initialized."""
    if _pool is None:
        raise RuntimeError(
            "DB pool not initialized. Call init_db_pool() during app startup."
        )
    return _pool
