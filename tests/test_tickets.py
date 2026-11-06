import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from app.services.tickets import (
    create_ticket,
    get_ticket,
    update_ticket_status,
    escalate_ticket,
    list_pending_approvals,
    decide_approval,
)


def test_ticket_lifecycle():
    with tempfile.NamedTemporaryFile("w", suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    with patch("app.services.tickets.settings.audit_db_path", db_path):
        # 1. Create standard P3 ticket (auto-approved / OPEN)
        t3 = create_ticket(
            user_id="alice@company.com",
            category="Hardware",
            priority="P3",
            description="Laptop screen flickering",
        )
        assert t3["ticket_id"].startswith("TICK-")
        assert t3["status"] == "OPEN"
        assert not t3["requires_approval"]

        # 2. Create critical P1 ticket (requires approval / PENDING_APPROVAL)
        t1 = create_ticket(
            user_id="bob@company.com",
            category="Network Outage",
            priority="P1",
            description="Entire office floor disconnected from internet",
        )
        assert t1["status"] == "PENDING_APPROVAL"
        assert t1["requires_approval"]
        approval_id = t1["approval_id"]
        assert approval_id is not None

        # 3. Check pending approvals
        pending = list_pending_approvals()
        assert len(pending) == 1
        assert pending[0]["approval_id"] == approval_id

        # 4. Approve P1 ticket
        dec = decide_approval(approval_id, decision="APPROVED", decided_by="IT Director")
        assert dec["decision"] == "APPROVED"
        assert dec["ticket_status"] == "OPEN"

        # Verify ticket status is now OPEN
        updated_t1 = get_ticket(t1["ticket_id"])
        assert updated_t1["status"] == "OPEN"

        # 5. Escalate ticket
        esc = escalate_ticket(t3["ticket_id"], reason="Second tier required")
        assert esc["status"] == "ESCALATED"

    Path(db_path).unlink(missing_ok=True)
