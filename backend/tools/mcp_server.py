"""MCP server exposing the three support-agent tools.

Two run modes:

    python -m tools.mcp_server                # serve over stdio (real MCP transport)
    python -m tools.mcp_server --test         # in-process smoke test against live Postgres

The agent (Phase 5) calls the underlying async functions directly for performance,
but this server proves the protocol path works and is the file you point at when
demoing "MCP-protocol tool servers" in the portfolio walkthrough.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from db.adapter import close_db_pool, init_db_pool
from tools.order_lookup import get_order_status as _get_order_status
from tools.product_info import get_product_info as _get_product_info
from tools.ticket_creator import create_ticket as _create_ticket

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("mcp_server")

mcp = FastMCP("customer-support-tools")


@mcp.tool()
async def order_status(order_id: str) -> dict[str, Any]:
    """Look up the current status of a customer order.

    Args:
        order_id: Human-readable order id, e.g. 'ORD-2024-0001'.

    Returns:
        Order detail (status, items, tracking, ETA, customer name) or {error: ...} on miss.
    """
    return await _get_order_status(order_id)


@mcp.tool()
async def get_product_info(sku: str) -> dict[str, Any]:
    """Fetch product details by SKU.

    Args:
        sku: Product SKU, e.g. 'SKU-001'.

    Returns:
        Product detail (name, description, price, in_stock, return_policy) or {error: ...}.
    """
    return await _get_product_info(sku)


@mcp.tool()
async def create_ticket(
    session_id: str,
    issue_summary: str,
    priority: str = "medium",
) -> dict[str, Any]:
    """Create a support ticket and return its public id.

    Args:
        session_id: Conversation session id from the agent.
        issue_summary: Short description of the issue (one or two sentences).
        priority: One of 'low' | 'medium' | 'high' | 'urgent'. Defaults to 'medium'.

    Returns:
        {ticket_id, created_at, priority, expected_response_time}.
    """
    return await _create_ticket(session_id, issue_summary, priority)


# ---------------------------------------------------------------------------
# Smoke test (run with: python -m tools.mcp_server --test)
# ---------------------------------------------------------------------------

async def _smoke_test() -> None:
    """Exercise every tool against a live Postgres. Fails loudly on miss."""
    await init_db_pool(min_size=1, max_size=2)
    try:
        print("\n=== order_status('ORD-2024-0001') ===")
        result = await _get_order_status("ORD-2024-0001")
        print(json.dumps(result, indent=2, default=str))
        assert "error" not in result, "ORD-2024-0001 should exist after Phase 1 seed"
        assert result["status"] == "delivered"

        print("\n=== order_status('ORD-DOES-NOT-EXIST') ===")
        miss = await _get_order_status("ORD-DOES-NOT-EXIST")
        print(json.dumps(miss, indent=2))
        assert miss.get("error") == "Order not found"

        print("\n=== get_product_info('SKU-001') ===")
        product = await _get_product_info("SKU-001")
        print(json.dumps(product, indent=2, default=str))
        assert product["name"].startswith("Wireless")

        print("\n=== get_product_info('SKU-NOPE') ===")
        miss = await _get_product_info("SKU-NOPE")
        print(json.dumps(miss, indent=2))
        assert miss.get("error") == "Product not found"

        print("\n=== create_ticket(...) ===")
        ticket = await _create_ticket(
            session_id="smoke-test-session",
            issue_summary="Smoke test: ignore — verifying tool wiring.",
            priority="low",
        )
        print(json.dumps(ticket, indent=2))
        assert ticket["ticket_id"].startswith("TKT-")
        assert ticket["expected_response_time"] == "within 48 hours"

        print("\nAll tool smoke checks passed.")
    finally:
        await close_db_pool()


if __name__ == "__main__":
    if "--test" in sys.argv:
        asyncio.run(_smoke_test())
    else:
        # Default mode: serve over stdio for real MCP clients.
        logger.info("Starting MCP server on stdio transport...")
        mcp.run()
