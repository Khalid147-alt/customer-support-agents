"""Shared Gemini client.

`langchain-google-genai` recognizes `GEMINI_API_KEY` natively, so we don't have
to pass the key explicitly — but we do anyway for clarity and so a missing
key fails loudly at startup rather than at first call.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_settings


@lru_cache(maxsize=1)
def get_llm() -> ChatGoogleGenerativeAI:
    """Default Gemini client for response generation. Streaming-capable."""
    s = get_settings()
    return ChatGoogleGenerativeAI(
        model=s.gemini_model,
        google_api_key=s.gemini_api_key,
        temperature=0.4,
        max_retries=2,
        # Enable token-level streaming so per-chunk on_chat_model_stream events
        # surface through LangGraph's astream_events(v2). Without this, the
        # underlying Google client buffers and emits one final message, which
        # makes the UI look like nothing is happening until the response is done.
        disable_streaming=False,
    )


@lru_cache(maxsize=1)
def get_router_llm() -> ChatGoogleGenerativeAI:
    """Deterministic Gemini client for the router.

    Uses `gemini-2.5-flash-lite` — a separate free-tier quota pool from `flash`,
    so router calls don't burn the budget reserved for response generation.
    Temperature 0 so the routing decision is stable across runs.
    """
    s = get_settings()
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=s.gemini_api_key,
        temperature=0.0,
        max_retries=2,
    )
