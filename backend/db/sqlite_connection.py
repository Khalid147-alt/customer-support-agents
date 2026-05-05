"""aiosqlite-backed connection shim for HuggingFace Spaces deployment.

Mirrors the asyncpg API surface (`fetchrow`, `fetchval`, `execute`, `executemany`,
`transaction`, `acquire`) so the rest of the codebase doesn't have to branch on
which database is in use. The adapter in `db.adapter` decides which backend to
return based on `USE_SQLITE`.

Notes:
- aiosqlite has no pool — a fresh connection is opened per acquire.
- Postgres-style positional placeholders (`$1`, `$2`, ...) are translated to
  SQLite's `?` so existing tool SQL keeps working unchanged.
- JSON columns (orders.items) are stored as TEXT containing JSON; rows that
  come back from `fetchrow` decode them transparently when accessed by the
  `items` key. We achieve this by wrapping aiosqlite.Row in a small dict-like.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

import aiosqlite

logger = logging.getLogger(__name__)

# Default SQLite location: a writable path on HuggingFace Spaces (/tmp).
# Override with SQLITE_DB_PATH if needed.
DEFAULT_DB_PATH = os.environ.get("SQLITE_DB_PATH", "/tmp/support_agent.db")

# Columns that contain JSON-encoded text and should be decoded on read.
_JSON_COLUMNS = {"items"}

_PG_PLACEHOLDER_RE = re.compile(r"\$(\d+)")
_PG_SUBSTRING_REGEX_RE = re.compile(
    r"SUBSTRING\s*\(\s*([A-Za-z_][A-Za-z_0-9]*)\s+FROM\s+('[^']*')\s*\)",
    re.IGNORECASE,
)


def _regex_extract(value: str | None, pattern: str) -> str | None:
    """SQLite UDF: return the first regex match of `pattern` in `value`."""
    if value is None:
        return None
    match = re.search(pattern, value)
    return match.group(0) if match else None


def _translate_sql(sql: str) -> str:
    """Translate Postgres-isms to SQLite-compatible SQL.

    - `$1`, `$2` → `?` (qmark placeholders)
    - `SUBSTRING(col FROM 'pattern')` → `regex_extract(col, 'pattern')`
      (a UDF registered on each connection)
    """
    sql = _PG_SUBSTRING_REGEX_RE.sub(r"regex_extract(\1, \2)", sql)
    sql = _PG_PLACEHOLDER_RE.sub("?", sql)
    return sql


def _encode_params(params: Iterable[Any]) -> tuple[Any, ...]:
    """Adapt Python values to SQLite-compatible types.

    - dict/list → JSON text (for the `items` column)
    - bool → 0/1 (SQLite has no native boolean)
    - Decimal → float (SQLite REAL)
    - date/datetime → ISO-8601 text
    """
    out: list[Any] = []
    for p in params:
        if isinstance(p, (dict, list)):
            out.append(json.dumps(p))
        elif isinstance(p, bool):
            out.append(1 if p else 0)
        elif isinstance(p, Decimal):
            out.append(float(p))
        elif isinstance(p, (_dt.date, _dt.datetime)):
            out.append(p.isoformat())
        else:
            out.append(p)
    return tuple(out)


class _Row(dict):
    """dict subclass that adapts SQLite-stored values to the Python types
    the rest of the codebase expects from asyncpg.

    - JSON columns (items) decode to list/dict.
    - `in_stock` integer becomes bool.
    - `created_at` text becomes datetime (ticket_creator.py calls .isoformat()).
    - `estimated_delivery` text becomes date.
    """

    def __getitem__(self, key: str) -> Any:
        value = super().__getitem__(key)
        if value is None:
            return None
        if key in _JSON_COLUMNS and isinstance(value, str):
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return value
        if key == "in_stock" and isinstance(value, int):
            return bool(value)
        if key == "created_at" and isinstance(value, str):
            try:
                return _dt.datetime.fromisoformat(value)
            except ValueError:
                return value
        if key == "estimated_delivery" and isinstance(value, str):
            try:
                return _dt.date.fromisoformat(value)
            except ValueError:
                return value
        return value


def _row_to_dict(row: aiosqlite.Row | None) -> _Row | None:
    if row is None:
        return None
    return _Row({k: row[k] for k in row.keys()})


class _Transaction:
    """Async context manager that wraps BEGIN/COMMIT/ROLLBACK."""

    def __init__(self, conn: "_AsyncpgLikeConnection") -> None:
        self._conn = conn

    async def __aenter__(self) -> "_Transaction":
        await self._conn._raw.execute("BEGIN")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            await self._conn._raw.commit()
        else:
            await self._conn._raw.rollback()


class _AsyncpgLikeConnection:
    """Wraps an aiosqlite.Connection to look like an asyncpg.Connection."""

    def __init__(self, raw: aiosqlite.Connection) -> None:
        self._raw = raw

    async def fetchrow(self, sql: str, *params: Any) -> _Row | None:
        translated = _translate_sql(sql)
        async with self._raw.execute(translated, _encode_params(params)) as cur:
            row = await cur.fetchone()
        return _row_to_dict(row)

    async def fetchval(self, sql: str, *params: Any) -> Any:
        translated = _translate_sql(sql)
        async with self._raw.execute(translated, _encode_params(params)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return row[0]

    async def fetch(self, sql: str, *params: Any) -> list[_Row]:
        translated = _translate_sql(sql)
        async with self._raw.execute(translated, _encode_params(params)) as cur:
            rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]  # type: ignore[misc]

    async def execute(self, sql: str, *params: Any) -> str:
        translated = _translate_sql(sql)
        cur = await self._raw.execute(translated, _encode_params(params))
        rowcount = cur.rowcount
        await cur.close()
        # Mimic asyncpg's "INSERT 0 N" / "UPDATE N" status strings — only the
        # trailing number matters for the codebase (seed.py looks for " 1").
        verb = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
        if verb == "INSERT":
            return f"INSERT 0 {rowcount}"
        return f"{verb} {rowcount}"

    async def executemany(self, sql: str, args: Iterable[Iterable[Any]]) -> None:
        translated = _translate_sql(sql)
        await self._raw.executemany(
            translated, [_encode_params(a) for a in args]
        )

    def transaction(self) -> _Transaction:
        return _Transaction(self)


class _PoolShim:
    """Stand-in for asyncpg.Pool — `.acquire()` opens a fresh aiosqlite conn."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[_AsyncpgLikeConnection]:
        # isolation_level=None puts the driver in autocommit mode; explicit
        # BEGIN/COMMIT inside _Transaction control transactions instead of
        # aiosqlite's implicit DML autocommit (which would conflict with
        # nested explicit transactions used by ticket_creator).
        conn = await aiosqlite.connect(self.db_path, isolation_level=None)
        conn.row_factory = aiosqlite.Row
        # Foreign keys are off by default in SQLite.
        await conn.execute("PRAGMA foreign_keys = ON")
        # Register a regex-substring helper so Postgres-style
        # SUBSTRING(col FROM 'pattern') translations work transparently.
        await conn.create_function("regex_extract", 2, _regex_extract, deterministic=True)
        try:
            yield _AsyncpgLikeConnection(conn)
        finally:
            await conn.close()

    async def close(self) -> None:  # pragma: no cover - parity stub
        return None


_pool: _PoolShim | None = None


async def init_db_pool(min_size: int = 1, max_size: int = 1) -> _PoolShim:
    """Create the shared SQLite pool shim. Idempotent.

    The min_size/max_size kwargs are accepted for parity with the asyncpg
    initializer but are not used (aiosqlite has no pool).
    """
    global _pool
    if _pool is not None:
        return _pool
    Path(DEFAULT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    logger.info("Initializing SQLite pool shim at %s", DEFAULT_DB_PATH)
    _pool = _PoolShim(DEFAULT_DB_PATH)
    return _pool


async def close_db_pool() -> None:
    global _pool
    _pool = None


def get_pool() -> _PoolShim:
    if _pool is None:
        raise RuntimeError(
            "SQLite pool not initialized. Call init_db_pool() during app startup."
        )
    return _pool


async def init_schema() -> None:
    """Apply sqlite_schema.sql to the database. Safe to call repeatedly."""
    schema_path = Path(__file__).parent / "sqlite_schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    Path(DEFAULT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DEFAULT_DB_PATH) as conn:
        await conn.executescript(sql)
        await conn.commit()
    logger.info("SQLite schema applied at %s", DEFAULT_DB_PATH)
