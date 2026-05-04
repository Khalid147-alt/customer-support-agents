"""POST /chat/stream — server-sent events streaming endpoint.

Wire path:
    1. Accept {message, session_id} from the client.
    2. Hydrate prior conversation from agent.memory.
    3. Run the LangGraph graph via `astream_events(version='v2')`.
    4. For every on_chat_model_stream event whose source is the `respond` node,
       emit `data: {"type":"token","content":"..."}\\n\\n`.
    5. Capture final state (cited sources, escalation flag, ticket id) at graph end.
    6. Append the turn to memory.
    7. Emit a terminal `data: {"type":"done", ...}\\n\\n` then `data: [DONE]\\n\\n`.

Why filter to the respond node only:
    The router LLM is invoked with `with_structured_output(...)` which still emits
    chat-model-stream events under the hood. We don't want to leak those raw tokens
    to the user — they're not natural language, they're a JSON intent classification.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import memory
from agent.graph import graph

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., min_length=1, max_length=100)


def _sse(payload: dict[str, Any]) -> str:
    """Serialize one SSE event."""
    return f"data: {json.dumps(payload)}\n\n"


async def _event_stream(request: ChatRequest) -> AsyncIterator[str]:
    """Drive the graph and yield SSE-formatted strings."""
    history = memory.get_history(request.session_id)

    initial_state: dict[str, Any] = {
        "session_id":       request.session_id,
        "user_message":     request.message,
        "messages":         history,
        "should_escalate":  False,
    }

    streamed_chunks: list[str] = []
    final_state: dict[str, Any] = {}

    try:
        async for event in graph.astream_events(initial_state, version="v2"):
            kind = event.get("event")

            # Token stream — only from the respond node, not the router's structured-output call.
            if kind == "on_chat_model_stream":
                meta = event.get("metadata") or {}
                node = meta.get("langgraph_node")
                if node != "respond":
                    continue

                chunk = event.get("data", {}).get("chunk")
                content = getattr(chunk, "content", "") if chunk is not None else ""
                if not content:
                    continue
                streamed_chunks.append(content)
                yield _sse({"type": "token", "content": content})

            # Capture the full state at the end of each node so we have final values for `done`.
            elif kind == "on_chain_end":
                data = event.get("data") or {}
                output = data.get("output")
                if isinstance(output, dict):
                    final_state.update(output)

    except Exception as exc:  # noqa: BLE001
        logger.exception("chat stream failed: %s", exc)
        yield _sse({"type": "error", "message": "Stream failed; please retry."})
        yield "data: [DONE]\n\n"
        return

    # Persist the turn for follow-up questions in this session.
    final_text = final_state.get("final_response") or "".join(streamed_chunks)
    if final_text:
        memory.append_turn(request.session_id, request.message, final_text)

    # If no tokens streamed (e.g. LLM call failed and respond_node returned a static
    # fallback string, or the model surfaced a non-streaming response), flush the
    # final text as a single token event so the UI still shows something.
    if not streamed_chunks and final_text:
        yield _sse({"type": "token", "content": final_text})

    # Surface ticket id for the UI escalation banner.
    ticket_id = None
    tool_result = final_state.get("tool_result") or {}
    if tool_result.get("tool") == "create_ticket":
        ticket_id = (tool_result.get("result") or {}).get("ticket_id")

    yield _sse({
        "type":      "done",
        "sources":   final_state.get("cited_sources") or [],
        "escalated": bool(final_state.get("should_escalate")),
        "ticket_id": ticket_id,
    })
    yield "data: [DONE]\n\n"


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """SSE endpoint. Client should set `Accept: text/event-stream` and read line-by-line."""
    return StreamingResponse(
        _event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx/proxy buffering for true streaming
        },
    )
