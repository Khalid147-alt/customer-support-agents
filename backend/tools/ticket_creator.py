"""create_ticket tool — insert a support ticket and return its public id."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

from db.connection import get_pool

logger = logging.getLogger(__name__)

Priority = Literal["low", "medium", "high", "urgent"]
_VALID_PRIORITIES = {"low", "medium", "high", "urgent"}

# SLA mapping shown to the user in the agent's escalation message.
_RESPONSE_SLA = {
    "low":    "within 48 hours",
    "medium": "within 24 hours",
    "high":   "within 4 hours",
    "urgent": "within 1 hour",
}


async def create_ticket(
    session_id: str,
    issue_summary: str,
    priority: str = "medium",
) -> dict[str, Any]:
    """Create a support ticket with a human-readable id like TKT-2026-0001.

    The ticket id is generated inside a transaction (SELECT MAX → INSERT) so
    concurrent calls each get a unique sequential number per year.
    """
    if priority not in _VALID_PRIORITIES:
        priority = "medium"

    year = datetime.utcnow().year
    prefix = f"TKT-{year}-"

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Find the highest existing suffix for this year. SUBSTRING returns the trailing digits.
            max_suffix = await conn.fetchval(
                """
                SELECT COALESCE(
                    MAX(CAST(SUBSTRING(ticket_id FROM '[0-9]+$') AS INT)),
                    0
                )
                FROM tickets
                WHERE ticket_id LIKE $1
                """,
                f"{prefix}%",
            )
            next_n = int(max_suffix) + 1
            ticket_id = f"{prefix}{next_n:04d}"

            row = await conn.fetchrow(
                """
                INSERT INTO tickets (ticket_id, session_id, issue_summary, priority, status)
                VALUES ($1, $2, $3, $4, 'open')
                RETURNING ticket_id, created_at, priority
                """,
                ticket_id, session_id, issue_summary, priority,
            )

    logger.info("create_ticket — created %s (priority=%s)", ticket_id, priority)
    return {
        "ticket_id":              row["ticket_id"],
        "created_at":             row["created_at"].isoformat(),
        "priority":               row["priority"],
        "expected_response_time": _RESPONSE_SLA[row["priority"]],
    }
