"""AgentState — the single source of truth for everything flowing through the graph.

Each node receives the full state and returns a partial dict that LangGraph merges in.
The `messages` channel uses the built-in `add_messages` reducer so chat history
accumulates rather than overwriting on each node update.
"""
from __future__ import annotations

from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages

# Allowed values for state["intent"] — keep in sync with router_node + conditional edges.
Intent = str  # Literal["rag", "tool", "escalate"] — kept str to avoid import gymnastics in stubs


class AgentState(TypedDict, total=False):
    """State carried through every node in the support-agent graph.

    `total=False` lets nodes return partial updates without TypedDict yelling.
    """

    # Conversation channel — accumulates BaseMessage objects across turns.
    messages: Annotated[list, add_messages]

    # Per-request identity and input
    session_id: str
    user_message: str

    # Router decision
    intent: Optional[Intent]               # "rag" | "tool" | "escalate"

    # RAG output
    retrieved_docs: Optional[list[dict]]   # [{content, source_file, relevance_score}, ...]
    cited_sources: Optional[list[str]]     # source filenames for the UI citation pills

    # MCP tool output
    tool_result: Optional[dict]

    # Escalation
    should_escalate: bool
    escalation_reason: Optional[str]

    # Final assembled response (for non-streaming consumers / tests)
    final_response: Optional[str]
