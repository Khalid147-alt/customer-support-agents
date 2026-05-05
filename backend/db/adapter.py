"""Database backend dispatcher.

Re-exports `init_db_pool`, `close_db_pool`, and `get_pool` from either the
asyncpg implementation (Postgres, local dev) or the aiosqlite shim
(SQLite, HuggingFace Spaces) based on the `USE_SQLITE` environment variable.

All other modules should import from `db.adapter` rather than from
`db.connection` or `db.sqlite_connection` directly.
"""
from __future__ import annotations

import os


def _use_sqlite() -> bool:
    return os.environ.get("USE_SQLITE", "").lower() in {"1", "true", "yes"}


if _use_sqlite():
    from db.sqlite_connection import (  # noqa: F401
        close_db_pool,
        get_pool,
        init_db_pool,
        init_schema,
    )
else:
    from db.connection import (  # noqa: F401
        close_db_pool,
        get_pool,
        init_db_pool,
    )

    async def init_schema() -> None:  # type: ignore[no-redef]
        """No-op for the asyncpg path: schema.sql is applied by docker-entrypoint-initdb.d."""
        return None


USE_SQLITE = _use_sqlite()
