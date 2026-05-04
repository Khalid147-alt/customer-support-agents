"""LangGraph StateGraph — the agent brain.

Topology:

    START → router → (conditional on state["intent"]) ─┬─ rag_lookup ─┐
                                                       ├─ mcp_tools ──┤
                                                       └─ escalate ───┘
                                                                       └→ respond → END

The router decides which retrieval/action node to dispatch to. Each branch flows
into respond, which assembles and streams the final answer.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    escalate_node,
    rag_node,
    respond_node,
    router_node,
    tools_node,
)
from agent.state import AgentState


def _route_after_router(state: AgentState) -> str:
    """Branch selector — must return one of the keys in the conditional edge map."""
    intent = state.get("intent") or "rag"
    if intent not in {"rag", "tool", "escalate"}:
        # Defensive default — never strand the graph if the router emits something weird.
        return "rag"
    return intent


def build_graph() -> StateGraph:
    """Construct (but do not compile) the StateGraph. Useful for tests/inspection."""
    builder = StateGraph(AgentState)

    builder.add_node("router",     router_node)
    builder.add_node("rag_lookup", rag_node)
    builder.add_node("mcp_tools",  tools_node)
    builder.add_node("escalate",   escalate_node)
    builder.add_node("respond",    respond_node)

    builder.add_edge(START, "router")

    builder.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "rag":      "rag_lookup",
            "tool":     "mcp_tools",
            "escalate": "escalate",
        },
    )

    # All branches funnel into respond, then end.
    builder.add_edge("rag_lookup", "respond")
    builder.add_edge("mcp_tools",  "respond")
    builder.add_edge("escalate",   "respond")
    builder.add_edge("respond",    END)

    return builder


# Compiled graph — import this from the FastAPI layer.
graph = build_graph().compile()


if __name__ == "__main__":
    print("Graph OK")
    print("Nodes:", sorted(graph.get_graph().nodes.keys()))
