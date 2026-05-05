"""FastAPI entry point.

Lifespan boots the database (pool for Postgres, file-init for SQLite) once for
the lifetime of the process and closes it on shutdown. The graph and embedding
model are lazy-loaded on first request to keep startup fast.

When USE_SQLITE=true (HuggingFace Spaces deployment), lifespan also:
  1. Applies the SQLite schema (idempotent CREATE TABLE IF NOT EXISTS).
  2. Seeds the database with users / products / orders (idempotent — skips if data exists).
  3. Ingests the /docs RAG knowledge base into ChromaDB at CHROMA_DIR.

Run locally:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Run on HuggingFace Spaces:
    USE_SQLITE=true ENVIRONMENT=production uvicorn main:app --host 0.0.0.0 --port 7860
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.chat import router as chat_router
from api.health import router as health_router
from config import get_settings
from db.adapter import USE_SQLITE, close_db_pool, init_db_pool

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("main")


async def _bootstrap_sqlite() -> None:
    """One-time setup for HuggingFace cold start: schema + seed + RAG ingest."""
    from db.sqlite_connection import init_schema
    from db.sqlite_seed import seed_sqlite

    logger.info("SQLite bootstrap: applying schema...")
    await init_schema()

    logger.info("SQLite bootstrap: seeding fixtures...")
    await seed_sqlite()

    logger.info("SQLite bootstrap: ingesting RAG knowledge base...")
    # rag.ingest is synchronous; run it in a thread to avoid blocking the loop.
    import asyncio

    from rag.ingest import ingest_docs

    await asyncio.to_thread(ingest_docs)
    logger.info("SQLite bootstrap complete.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Database setup at startup, teardown at shutdown."""
    settings = get_settings()
    logger.info(
        "Starting up (env=%s, model=%s, use_sqlite=%s)",
        settings.environment,
        settings.gemini_model,
        USE_SQLITE,
    )

    if USE_SQLITE:
        # SQLite: do not call init_db_pool() for asyncpg — it would try to
        # connect to a Postgres DSN that doesn't exist on HuggingFace.
        await _bootstrap_sqlite()
        # Initialize the SQLite pool shim so get_pool() works for the tools.
        await init_db_pool()
    else:
        await init_db_pool()

    try:
        yield
    finally:
        await close_db_pool()
        logger.info("Shutdown complete")


app = FastAPI(
    title="Customer Support Agent API",
    description="LangGraph + Gemini + RAG + MCP tools, streaming over SSE.",
    version="0.6.0",
    lifespan=lifespan,
)

# Open CORS so the Vercel-hosted frontend can call this API across origins.
# Tighten to a known origin list before high-traffic production use.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, tags=["meta"])
app.include_router(chat_router, tags=["chat"])
