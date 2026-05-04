"""FastAPI entry point.

Lifespan boots the asyncpg pool once for the lifetime of the process and
closes it on shutdown. The graph and embedding model are lazy-loaded on first
request to keep startup fast.

Run locally:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.chat import router as chat_router
from api.health import router as health_router
from config import get_settings
from db.connection import close_db_pool, init_db_pool

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pool the DB at startup, close it on shutdown."""
    settings = get_settings()
    logger.info("Starting up (env=%s, model=%s)", settings.environment, settings.gemini_model)
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

# Open CORS in dev — frontend runs on a different port (Vite at :5173).
# Tighten this to a known origin list before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, tags=["meta"])
app.include_router(chat_router, tags=["chat"])
