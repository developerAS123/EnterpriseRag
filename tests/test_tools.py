from unittest.mock import MagicMock, patch
import pytest

from app.services.tools import execute_tool, TOOLS


def test_registered_tools_exist():
    assert "search_kb" in TOOLS
    assert "search_web" in TOOLS
    assert "troubleshooting_guide" in TOOLS
    assert "create_it_ticket" in TOOLS
    assert "lookup_it_ticket" in TOOLS
    assert "escalate_to_human" in TOOLS


def test_execute_unauthorized_tool():
    res = execute_tool("format_hard_drive", {"path": "/"})
    assert res["status"] == "error"
    assert "not in the authorized tool registry" in res["message"]


def test_troubleshooting_guide_tool():
    res = execute_tool("troubleshooting_guide", {"topic": "vpn"})
    assert res["result"]["status"] == "success"
    assert "VPN" in res["result"]["guide"]["title"]
    assert len(res["result"]["guide"]["steps"]) > 0


def test_tool_input_validation_failure():
    # Priority 'P99' is invalid
    res = execute_tool("create_it_ticket", {
        "category": "Email",
        "priority": "P99",
        "description": "Short",
    })
    assert res["status"] == "error"
    assert "Execution failed" in res["message"]
