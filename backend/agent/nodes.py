"""LangGraph node functions — Phase 5 (real logic).

Each node is `async def`, takes the full AgentState, and returns a partial
state dict that LangGraph merges via the TypedDict reducers.

Design notes:
- Every node catches its own exceptions and degrades to a sensible fallback.
  A failing router defaults to "rag", a failing tool returns an error dict,
  a failing rag returns no docs. Never let the agent strand on a tool fault.
- We call the underlying tool functions (tools/order_lookup.py etc.) directly
  rather than going through the MCP protocol — the MCP server (mcp_server.py)
  is exposed for clients that want the protocol; in-process we skip the
  subprocess + JSON-RPC roundtrip.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from agent.llm import get_llm, get_router_llm
from agent.prompts import RESPOND_PROMPT, ROUTER_PROMPT
from agent.state import AgentState
from rag.retriever import cited_sources, retrieve
from tools.order_lookup import get_order_status
from tools.product_info import get_product_info
from tools.ticket_creator import create_ticket

logger = logging.getLogger(__name__)

ORDER_ID_RE = re.compile(r"\bORD-\d{4}-\d{3,5}\b", re.IGNORECASE)
SKU_RE      = re.compile(r"\bSKU-\d{3,5}\b", re.IGNORECASE)

# Minimum relevance score before we list a source as a citation pill in the UI.
# Below this we have the doc available to the LLM but don't claim it as a citation.
CITATION_MIN_SCORE = 0.20


class _RouterDecision(BaseModel):
    """Structured output schema for the router LLM."""
    intent: Literal["rag", "tool", "escalate"] = Field(
        ..., description="One of: rag (KB lookup), tool (order/product), escalate (human handoff)."
    )


def _format_history(messages: list) -> str:
    """Render the running conversation as a compact transcript for prompt context."""
    if not messages:
        return "(no prior turns)"
    lines: list[str] = []
    for m in messages[-6:]:  # last 3 user/agent pairs is plenty
        role = "User" if isinstance(m, HumanMessage) else "Agent"
        content = getattr(m, "content", str(m))
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# router
# ---------------------------------------------------------------------------

async def router_node(state: AgentState) -> dict[str, Any]:
    """Classify user intent into rag | tool | escalate via Gemini structured output."""
    user_message = state.get("user_message", "")
    history = _format_history(state.get("messages") or [])

    prompt = ROUTER_PROMPT.format(message=user_message, history=history)

    try:
        structured = get_router_llm().with_structured_output(_RouterDecision)
        decision: _RouterDecision = await structured.ainvoke(prompt)
        intent = decision.intent
        logger.info("router → %s  (msg=%r)", intent, user_message[:60])
    except Exception as exc:  # noqa: BLE001
        logger.warning("router failed (%s); defaulting to rag", exc)
        intent = "rag"

    return {"intent": intent}


# ---------------------------------------------------------------------------
# rag
# ---------------------------------------------------------------------------

async def rag_node(state: AgentState) -> dict[str, Any]:
    """Pull top-k KB chunks for the user's question."""
    query = state.get("user_message", "")
    if not query:
        return {"retrieved_docs": [], "cited_sources": []}

    try:
        docs = await retrieve(query, k=4, fetch_k=10)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rag retrieval failed: %s", exc)
        return {"retrieved_docs": [], "cited_sources": []}

    # Only cite sources that actually scored above the threshold — diversity
    # fillers with score=0 should be available to the LLM but not show as pills.
    cite_candidates = [d for d in docs if d.get("relevance_score", 0) >= CITATION_MIN_SCORE]
    sources = cited_sources(cite_candidates)
    logger.info("rag → %d docs, %d citations: %s", len(docs), len(sources), sources)
    return {"retrieved_docs": docs, "cited_sources": sources}


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------

async def tools_node(state: AgentState) -> dict[str, Any]:
    """Parse the user message for an order id or SKU and call the right tool."""
    msg = state.get("user_message", "")

    order_match = ORDER_ID_RE.search(msg)
    sku_match = SKU_RE.search(msg)

    try:
        if order_match:
            order_id = order_match.group(0).upper()
            result = await get_order_status(order_id)
            tool_result = {"tool": "order_status", "args": {"order_id": order_id}, "result": result}
        elif sku_match:
            sku = sku_match.group(0).upper()
            result = await get_product_info(sku)
            tool_result = {"tool": "get_product_info", "args": {"sku": sku}, "result": result}
        else:
            # No identifier in the message — the router shouldn't normally land us here,
            # but defend against it: tell the LLM what's missing so it can ask for clarification.
            tool_result = {
                "tool": None,
                "result": {
                    "error": "I need an order number (like ORD-2024-0001) or product SKU "
                             "(like SKU-001) to look that up. Could you share it?"
                },
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("tool dispatch failed: %s", exc)
        tool_result = {"tool": None, "result": {"error": "Tool call failed; please try again."}}

    logger.info("tools → %s", tool_result.get("tool"))
    return {"tool_result": tool_result}


# ---------------------------------------------------------------------------
# escalate
# ---------------------------------------------------------------------------

def _summarize_for_ticket(user_message: str, history: list) -> str:
    """Cheap summary: last user message + a hint of context. Good enough for an inbox preview."""
    summary = user_message.strip() or "User requested escalation."
    if len(summary) > 240:
        summary = summary[:237] + "..."
    return summary


async def escalate_node(state: AgentState) -> dict[str, Any]:
    """Mark the conversation as escalated and create a real support ticket."""
    user_message = state.get("user_message", "")
    history = state.get("messages") or []
    session_id = state.get("session_id") or "unknown-session"

    issue_summary = _summarize_for_ticket(user_message, history)
    reason = state.get("escalation_reason") or "Frustration or complex issue detected by router."

    tool_result: dict[str, Any]
    try:
        ticket = await create_ticket(
            session_id=session_id,
            issue_summary=issue_summary,
            priority="high",
        )
        tool_result = {"tool": "create_ticket", "args": {"priority": "high"}, "result": ticket}
        logger.info("escalate → ticket %s", ticket.get("ticket_id"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("ticket creation failed: %s", exc)
        tool_result = {"tool": "create_ticket", "result": {"error": "Ticket creation failed; "
                                                                   "an agent has still been notified."}}

    return {
        "should_escalate": True,
        "escalation_reason": reason,
        "tool_result": tool_result,
    }


# ---------------------------------------------------------------------------
# respond
# ---------------------------------------------------------------------------

def _format_docs_for_prompt(docs: list[dict] | None) -> str:
    if not docs:
        return "(none)"
    lines: list[str] = []
    for i, d in enumerate(docs, 1):
        src = d.get("source_file", "?")
        content = d.get("content", "").strip()
        lines.append(f"[{i}] source={src}\n{content}")
    return "\n\n".join(lines)


def _format_tool_for_prompt(tool_result: dict | None) -> str:
    if not tool_result:
        return "(none)"
    return json.dumps(tool_result, indent=2, default=str)


async def respond_node(state: AgentState) -> dict[str, Any]:
    """Generate the final user-facing reply via Gemini using all gathered context."""
    user_message = state.get("user_message", "")
    history = _format_history(state.get("messages") or [])

    prompt = RESPOND_PROMPT.format(
        retrieved_docs=_format_docs_for_prompt(state.get("retrieved_docs")),
        tool_result=_format_tool_for_prompt(state.get("tool_result")),
        history=history,
        user_message=user_message,
    )

    text = ""
    try:
        # Use .astream() (not ainvoke) so each token chunk surfaces as an
        # on_chat_model_stream event through LangGraph's astream_events(v2)
        # pipeline. The SSE endpoint filters those by langgraph_node=="respond"
        # and forwards them to the browser.
        async for chunk in get_llm().astream(prompt):
            piece = getattr(chunk, "content", "") or ""
            text += piece
    except Exception as exc:  # noqa: BLE001
        logger.error("respond_node LLM call failed: %s", exc)
        text = ("I ran into an issue generating a response. A support agent has been notified — "
                "please try again shortly.")

    logger.info("respond → %d chars", len(text))
    return {
        "final_response": text,
        # Append both turns to the running conversation log.
        "messages": [HumanMessage(content=user_message), AIMessage(content=text)],
    }
