"""Per-session conversation memory.

Phase 6 ships an in-memory dict — sufficient for demo and single-process dev.
The Settings class already has a `redis_url` slot; swap this implementation
for a Redis-backed store when horizontal scaling matters.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

logger = logging.getLogger(__name__)

# Cap each session at 20 messages (10 turns) so prompts don't balloon.
_MAX_MESSAGES_PER_SESSION = 20

_store: dict[str, list[BaseMessage]] = defaultdict(list)


def get_history(session_id: str) -> list[BaseMessage]:
    """Return a copy of the session's message list (safe to mutate locally)."""
    return list(_store.get(session_id, []))


def append_turn(session_id: str, user_message: str, ai_response: str) -> None:
    """Persist one full turn (user + agent) at the end of the conversation."""
    bucket = _store[session_id]
    bucket.append(HumanMessage(content=user_message))
    bucket.append(AIMessage(content=ai_response))
    if len(bucket) > _MAX_MESSAGES_PER_SESSION:
        # Drop the oldest pair so we keep complete turns rather than a half user/half agent.
        del bucket[: len(bucket) - _MAX_MESSAGES_PER_SESSION]
    logger.debug("memory[%s] now has %d messages", session_id, len(bucket))


def clear(session_id: str) -> None:
    """Drop a session's history — useful for tests or a 'reset' button."""
    _store.pop(session_id, None)


def all_sessions() -> Iterable[str]:
    """Diagnostic helper."""
    return list(_store.keys())
