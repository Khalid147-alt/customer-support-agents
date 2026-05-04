"""Tool layer.

Plain async functions live in their own modules (order_lookup, product_info,
ticket_creator). `mcp_server.py` exposes the same set as a real MCP server
over stdio for clients that want the protocol.
"""
from tools.order_lookup import get_order_status
from tools.product_info import get_product_info
from tools.ticket_creator import create_ticket

__all__ = ["get_order_status", "get_product_info", "create_ticket"]
