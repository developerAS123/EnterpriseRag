from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Enterprise IT Support" in data["service"]
    assert "model" in data


def test_home_page_renders():
    response = client.get("/")
    assert response.status_code == 200
    assert "Enterprise IT" in response.text
    assert "tab-overview" in response.text


def test_documents_endpoint():
    response = client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data


def test_ingest_unauthorized():
    response = client.post(
        "/api/ingest",
        files={"file": ("test.txt", b"Sample text", "text/plain")},
        headers={"x-admin-key": "wrong-key"},
    )
    assert response.status_code == 401
    assert "Invalid admin key" in response.json()["detail"]


def test_ingest_unsupported_file_type():
    from app.core.config import get_settings
    settings = get_settings()

    response = client.post(
        "/api/ingest",
        files={"file": ("test.exe", b"Binary data", "application/octet-stream")},
        headers={"x-admin-key": settings.admin_api_key},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_chat_endpoint_mocked():
    mock_result = {
        "answer": "You can connect to VPN using NovaSecure client.",
        "source_used": "private_kb",
        "trace": ["Router -> KB", "Answer generation -> PRIVATE KB"],
        "citations": [{"title": "handbook.md", "url": "", "type": "private_kb"}],
        "current_query": "How to connect to VPN?",
        "session_id": "test_session_1",
        "verification_grade": "grounded",
        "ticket_info": None,
    }

    with patch("app.api.routes.ask", return_value=mock_result):
        response = client.post(
            "/api/chat",
            json={"question": "How to connect to VPN?", "session_id": "test_session_1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == mock_result["answer"]
        assert data["source_used"] == "private_kb"
        assert data["session_id"] == "test_session_1"
        assert len(data["trace"]) == 2
        assert len(data["citations"]) == 1


def test_tickets_api_crud():
    # 1. Create a ticket
    create_res = client.post(
        "/api/tickets",
        json={
            "user_id": "tester@company.internal",
            "category": "Software",
            "priority": "P3",
            "description": "Cannot install Docker desktop",
        },
    )
    assert create_res.status_code == 200
    ticket = create_res.json()["ticket"]
    ticket_id = ticket["ticket_id"]
    assert ticket["status"] == "OPEN"

    # 2. Get ticket by ID
    get_res = client.get(f"/api/tickets/{ticket_id}")
    assert get_res.status_code == 200
    assert get_res.json()["ticket"]["category"] == "Software"

    # 3. Update status
    patch_res = client.patch(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "IN_PROGRESS"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["ticket"]["status"] == "IN_PROGRESS"

    # 4. Escalate ticket
    esc_res = client.post(f"/api/tickets/{ticket_id}/escalate")
    assert esc_res.status_code == 200
    assert esc_res.json()["ticket"]["status"] == "ESCALATED"


def test_approvals_api():
    # Create P1 ticket -> requires approval
    create_res = client.post(
        "/api/tickets",
        json={
            "user_id": "manager@company.internal",
            "category": "Critical Outage",
            "priority": "P1",
            "description": "Production database unreachable",
        },
    )
    ticket = create_res.json()["ticket"]
    approval_id = ticket["approval_id"]
    assert approval_id is not None

    # Get approvals list
    list_res = client.get("/api/approvals")
    assert list_res.status_code == 200
    appr_ids = [a["approval_id"] for a in list_res.json()["approvals"]]
    assert approval_id in appr_ids

    # Reject approval
    action_res = client.post(
        f"/api/approvals/{approval_id}/action",
        json={"decision": "REJECTED", "decided_by": "Security Officer"},
    )
    assert action_res.status_code == 200
    assert action_res.json()["decision"] == "REJECTED"
    assert action_res.json()["ticket_status"] == "REJECTED"


def test_conversations_api():
    session = "test_conv_session"
    from app.services.memory import add_message

    add_message(session, "user", "What is MFA?")
    add_message(session, "assistant", "MFA is multi-factor authentication.")

    # Get history
    hist_res = client.get(f"/api/conversations/{session}")
    assert hist_res.status_code == 200
    assert hist_res.json()["count"] == 2

    # Delete history
    del_res = client.delete(f"/api/conversations/{session}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted_count"] == 2

    # Check empty
    hist_after = client.get(f"/api/conversations/{session}")
    assert hist_after.json()["count"] == 0
