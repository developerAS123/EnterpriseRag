"""
IT Support Ticket & Approval Management System
──────────────────────────────────────────────
Manages IT support tickets with severity levels (P1-P4),
status workflows, and Human-in-the-Loop (HITL) approval gates.

Severity levels:
  P1: Critical / Company-wide outage (requires approval)
  P2: Major team blocked (requires approval)
  P3: Single user blocked (auto-approved)
  P4: General inquiry / minor request (auto-approved)

Status workflow:
  PENDING_APPROVAL → OPEN → IN_PROGRESS → RESOLVED
  PENDING_APPROVAL → REJECTED
  OPEN / IN_PROGRESS → ESCALATED
"""

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TicketPriority = Literal["P1", "P2", "P3", "P4"]
TicketStatus = Literal[
    "PENDING_APPROVAL", "OPEN", "IN_PROGRESS", "RESOLVED", "ESCALATED", "REJECTED"
]


class TicketCreateRequest(BaseModel):
    user_id: str = Field(default="employee@company.internal", min_length=3)
    category: str = Field(..., min_length=2, max_length=100)
    priority: TicketPriority = Field(default="P3")
    description: str = Field(..., min_length=5, max_length=2000)


class TicketUpdateRequest(BaseModel):
    status: TicketStatus
    comment: str | None = None


def init_ticket_tables() -> None:
    """Initialize ticket and approval tables in SQLite."""
    con = sqlite3.connect(settings.audit_db_path)
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS tickets (
                ticket_id   TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                category    TEXT NOT NULL,
                priority    TEXT NOT NULL,
                description TEXT NOT NULL,
                status      TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS approvals (
                approval_id  TEXT PRIMARY KEY,
                ticket_id    TEXT NOT NULL,
                action_type  TEXT NOT NULL,
                details      TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'PENDING',
                requested_at TEXT NOT NULL,
                decided_at   TEXT,
                decided_by   TEXT,
                FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
            )"""
        )
        con.commit()
    finally:
        con.close()


def create_ticket(
    user_id: str,
    category: str,
    priority: TicketPriority,
    description: str,
) -> dict[str, Any]:
    """
    Create a new support ticket.
    P1 and P2 priority tickets automatically generate a pending approval gate.
    """
    init_ticket_tables()
    ticket_id = f"TICK-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    # Determine initial status: high-severity tickets require approval
    requires_approval = priority in ("P1", "P2")
    initial_status: TicketStatus = "PENDING_APPROVAL" if requires_approval else "OPEN"

    con = sqlite3.connect(settings.audit_db_path)
    try:
        con.execute(
            """INSERT INTO tickets
               (ticket_id, user_id, category, priority, description, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticket_id, user_id, category, priority, description, initial_status, now, now),
        )

        approval_id = None
        if requires_approval:
            approval_id = f"APPR-{uuid.uuid4().hex[:8].upper()}"
            con.execute(
                """INSERT INTO approvals
                   (approval_id, ticket_id, action_type, details, status, requested_at)
                   VALUES (?, ?, 'HIGH_PRIORITY_TICKET_CREATION', ?, 'PENDING', ?)""",
                (
                    approval_id,
                    ticket_id,
                    f"Create {priority} ticket for '{category}': {description[:100]}",
                    now,
                ),
            )

        con.commit()
        logger.info(
            "Created ticket %s (%s, priority %s, status %s)",
            ticket_id,
            category,
            priority,
            initial_status,
        )

        return {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "category": category,
            "priority": priority,
            "description": description,
            "status": initial_status,
            "requires_approval": requires_approval,
            "approval_id": approval_id,
            "created_at": now,
        }
    finally:
        con.close()


def get_ticket(ticket_id: str) -> dict[str, Any] | None:
    """Retrieve ticket details by ID."""
    con = sqlite3.connect(settings.audit_db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def list_tickets(limit: int = 50) -> list[dict[str, Any]]:
    """List recent support tickets."""
    init_ticket_tables()
    con = sqlite3.connect(settings.audit_db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM tickets ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in cur.fetchall()]
    finally:
        con.close()


def update_ticket_status(ticket_id: str, status: TicketStatus) -> dict[str, Any]:
    """Update ticket status."""
    now = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(settings.audit_db_path)
    try:
        cur = con.cursor()
        cur.execute(
            "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
            (status, now, ticket_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Ticket {ticket_id} not found.")
        con.commit()
        return get_ticket(ticket_id)  # type: ignore
    finally:
        con.close()


def escalate_ticket(ticket_id: str, reason: str = "") -> dict[str, Any]:
    """Escalate a ticket to human service desk staff."""
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise ValueError(f"Ticket {ticket_id} not found.")
    return update_ticket_status(ticket_id, "ESCALATED")


def list_pending_approvals() -> list[dict[str, Any]]:
    """List all approval requests awaiting decision."""
    init_ticket_tables()
    con = sqlite3.connect(settings.audit_db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(
            """SELECT a.*, t.category, t.priority, t.user_id, t.description
               FROM approvals a
               JOIN tickets t ON a.ticket_id = t.ticket_id
               WHERE a.status = 'PENDING'
               ORDER BY a.requested_at ASC"""
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        con.close()


def decide_approval(approval_id: str, decision: Literal["APPROVED", "REJECTED"], decided_by: str = "IT Admin") -> dict[str, Any]:
    """Approve or reject a pending approval request."""
    now = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(settings.audit_db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,))
        appr = cur.fetchone()
        if not appr:
            raise ValueError(f"Approval request {approval_id} not found.")
        if appr["status"] != "PENDING":
            raise ValueError(f"Approval request {approval_id} has already been decided ({appr['status']}).")

        ticket_id = appr["ticket_id"]
        # Update approval
        con.execute(
            "UPDATE approvals SET status = ?, decided_at = ?, decided_by = ? WHERE approval_id = ?",
            (decision, now, decided_by, approval_id),
        )

        # Update associated ticket status
        new_ticket_status: TicketStatus = "OPEN" if decision == "APPROVED" else "REJECTED"
        con.execute(
            "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
            (new_ticket_status, now, ticket_id),
        )
        con.commit()

        logger.info("Approval %s %s by %s. Ticket %s -> %s", approval_id, decision, decided_by, ticket_id, new_ticket_status)
        return {
            "approval_id": approval_id,
            "decision": decision,
            "ticket_id": ticket_id,
            "ticket_status": new_ticket_status,
            "decided_at": now,
        }
    finally:
        con.close()
