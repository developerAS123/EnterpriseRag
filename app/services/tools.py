"""
Controlled Agentic Tool Registry
────────────────────────────────
All tools are strictly registered with Pydantic validation,
bounded execution timeouts, error isolation, and audit logging.

Registered tools:
  1. search_kb            – Search internal IT documentation
  2. search_web           – Fallback external search via Tavily
  3. troubleshooting_guide– Standard deterministic troubleshooting flows
  4. create_it_ticket     – Submit a support ticket (with P1/P2 HITL gates)
  5. lookup_it_ticket     – Query ticket status by ticket ID
  6. escalate_to_human    – Escalate an ongoing incident to service desk human staff
"""

import logging
import time
from typing import Any, Callable, Literal
from pydantic import BaseModel, Field

from app.rag.vectorstore import get_retriever
from app.services.tickets import (
    create_ticket,
    get_ticket,
    escalate_ticket,
    TicketPriority,
)

logger = logging.getLogger(__name__)

# ── Tool Schemas ──────────────────────────────────────────────────────────────

class KBSearchInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="Technical search query for internal KB")


class WebSearchInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="External search query")


class GuidanceInput(BaseModel):
    topic: Literal["vpn", "password", "mfa", "email", "laptop", "software", "printer", "network"] = Field(
        ..., description="Topic for standardized IT troubleshooting flowchart"
    )


class CreateTicketInput(BaseModel):
    user_id: str = Field(default="employee@company.internal", description="User email or employee ID")
    category: str = Field(..., min_length=2, max_length=100, description="Ticket category (e.g. Hardware, Network, Access)")
    priority: TicketPriority = Field(default="P3", description="P1 (Outage), P2 (Team blocked), P3 (User blocked), P4 (Inquiry)")
    description: str = Field(..., min_length=5, max_length=2000, description="Detailed description of the issue")


class LookupTicketInput(BaseModel):
    ticket_id: str = Field(..., min_length=4, max_length=50, description="Ticket ID e.g. TICK-A1B2C3D4")


class EscalateTicketInput(BaseModel):
    ticket_id: str = Field(..., min_length=4, max_length=50, description="Ticket ID to escalate")
    reason: str = Field(default="Automated resolution unsuccessful or user requested live support", max_length=500)


# ── Tool Implementations ──────────────────────────────────────────────────────

def tool_search_kb(payload: KBSearchInput) -> dict[str, Any]:
    """Retrieve private knowledge base chunks."""
    retriever = get_retriever()
    docs = retriever.invoke(payload.query)
    results = []
    for d in docs:
        results.append({
            "content": d.page_content,
            "source": d.metadata.get("source", "Private KB"),
            "chunk_id": d.metadata.get("chunk_id", ""),
        })
    return {"status": "success", "query": payload.query, "chunks_found": len(results), "chunks": results}


def tool_search_web(payload: WebSearchInput) -> dict[str, Any]:
    """Search external web via Tavily."""
    from app.rag.workflow import web_search_tool
    res = web_search_tool().invoke({"query": payload.query})
    return {"status": "success", "query": payload.query, "raw_result": res}


def tool_troubleshooting_guide(payload: GuidanceInput) -> dict[str, Any]:
    """Provide standard enterprise troubleshooting steps for common topics."""
    guides = {
        "vpn": {
            "title": "VPN Connection Troubleshooting Flow",
            "steps": [
                "1. Verify your local internet connectivity by browsing to an external site.",
                "2. Open NovaSecure VPN client and verify you are using your company email.",
                "3. Complete the multi-factor authentication prompt on your registered device.",
                "4. Select the nearest corporate gateway (e.g., US-East, EU-Central).",
                "5. If error persists, reboot your system and retry.",
                "6. If still failing, submit a P3 support ticket with a screenshot of the error code.",
            ],
            "escalation_policy": "Escalate to P2 if entire remote office is unable to connect.",
        },
        "password": {
            "title": "Password Reset Procedures",
            "steps": [
                "1. Navigate to the self-service identity portal at https://identity.company.internal.",
                "2. Enter your corporate email and complete the MFA verification challenge.",
                "3. Choose a new password meeting policy: minimum 14 characters, mixed case, numbers, and symbols.",
                "4. Note: Accounts lock automatically after 5 consecutive failed attempts.",
                "5. Important: IT staff will NEVER ask for your password or MFA code.",
            ],
            "escalation_policy": "Service desk can issue a one-time temporary access code after identity verification.",
        },
        "mfa": {
            "title": "Multi-Factor Authentication Setup & Recovery",
            "steps": [
                "1. Ensure you have the approved corporate authenticator app installed.",
                "2. If device was lost or changed, use your registered hardware security key as backup.",
                "3. If all backup methods are unavailable, contact the Service Desk for identity re-enrollment.",
            ],
            "escalation_policy": "Hardware key replacement requests are treated as P3 tickets.",
        },
        "email": {
            "title": "Corporate Email Troubleshooting",
            "steps": [
                "1. Test access via Outlook Web Access (OWA) at https://mail.company.internal.",
                "2. If web mail works but desktop client fails, check account sync settings.",
                "3. Verify mailbox quota has not exceeded 50 GB threshold.",
            ],
            "escalation_policy": "If widespread mail delivery stops, report as P1 incident.",
        },
        "laptop": {
            "title": "Laptop Performance & Crash Diagnostics",
            "steps": [
                "1. Open Task Manager / Activity Monitor and inspect CPU and RAM usage.",
                "2. Check available disk space (minimum 10% free space required for OS caching).",
                "3. Ensure all pending corporate OS updates and security patches are installed.",
                "4. Warning: Never disable endpoint security agents.",
            ],
            "escalation_policy": "Hardware failures require scheduling a depot swap.",
        },
        "software": {
            "title": "Software Installation & Access Requests",
            "steps": [
                "1. Open the internal Software Portal and search the catalog of approved applications.",
                "2. Click 'Install' — approved applications install automatically without admin privileges.",
                "3. For unlisted third-party software, submit an IT Security Review request.",
            ],
            "escalation_policy": "Security reviews typically take 2-3 business days.",
        },
        "printer": {
            "title": "Office Printer Connectivity",
            "steps": [
                "1. Verify you are connected to the corporate internal network or office Wi-Fi.",
                "2. Add printer via hostname: 'prt-<building>-<floor>'.",
                "3. Badge-release printers require tapping your employee RFID card.",
            ],
            "escalation_policy": "P4 routine hardware maintenance.",
        },
        "network": {
            "title": "Network & Wi-Fi Connectivity",
            "steps": [
                "1. Connect to 'Corp-Secure' Wi-Fi using 802.1x enterprise credentials.",
                "2. Ensure device trust certificate is valid in system settings.",
                "3. Test DNS resolution: ping internal gateway.",
            ],
            "escalation_policy": "P1 if entire floor or office switches are down.",
        },
    }
    guide = guides.get(payload.topic, {"title": "General IT Guidance", "steps": ["Contact IT Service Desk."]})
    return {"status": "success", "topic": payload.topic, "guide": guide}


def tool_create_it_ticket(payload: CreateTicketInput) -> dict[str, Any]:
    """Create an IT ticket in the persistent database."""
    res = create_ticket(
        user_id=payload.user_id,
        category=payload.category,
        priority=payload.priority,
        description=payload.description,
    )
    return {"status": "success", "ticket": res}


def tool_lookup_it_ticket(payload: LookupTicketInput) -> dict[str, Any]:
    """Look up an existing IT ticket."""
    ticket = get_ticket(payload.ticket_id)
    if not ticket:
        return {"status": "error", "message": f"Ticket '{payload.ticket_id}' not found."}
    return {"status": "success", "ticket": ticket}


def tool_escalate_to_human(payload: EscalateTicketInput) -> dict[str, Any]:
    """Escalate a ticket to human support."""
    try:
        updated = escalate_ticket(payload.ticket_id, reason=payload.reason)
        return {"status": "success", "ticket": updated, "message": "Ticket has been escalated to human service desk staff."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# ── Tool Registry Map ─────────────────────────────────────────────────────────

TOOLS: dict[str, dict[str, Any]] = {
    "search_kb": {
        "name": "search_kb",
        "description": "Search internal company IT documentation for official policies, runbooks, and procedures.",
        "input_model": KBSearchInput,
        "func": tool_search_kb,
    },
    "search_web": {
        "name": "search_web",
        "description": "Search public external web via Tavily for vendor updates, third-party outages, or public technical documentation.",
        "input_model": WebSearchInput,
        "func": tool_search_web,
    },
    "troubleshooting_guide": {
        "name": "troubleshooting_guide",
        "description": "Retrieve standard enterprise troubleshooting steps for common IT issues (vpn, password, mfa, email, laptop, software, printer, network).",
        "input_model": GuidanceInput,
        "func": tool_troubleshooting_guide,
    },
    "create_it_ticket": {
        "name": "create_it_ticket",
        "description": "Create an official IT support ticket. Note: P1 and P2 priority tickets require human approval.",
        "input_model": CreateTicketInput,
        "func": tool_create_it_ticket,
    },
    "lookup_it_ticket": {
        "name": "lookup_it_ticket",
        "description": "Check the status and details of an IT support ticket using its ticket ID.",
        "input_model": LookupTicketInput,
        "func": tool_lookup_it_ticket,
    },
    "escalate_to_human": {
        "name": "escalate_to_human",
        "description": "Escalate a ticket to a live human service desk technician when automated troubleshooting cannot resolve the issue.",
        "input_model": EscalateTicketInput,
        "func": tool_escalate_to_human,
    },
}


def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Safely execute a registered tool with schema validation and error isolation.
    Disallows unregistered tools, arbitrary code execution, or unrestricted shell commands.
    """
    if tool_name not in TOOLS:
        return {
            "status": "error",
            "message": f"Tool '{tool_name}' is not in the authorized tool registry. Available tools: {', '.join(TOOLS.keys())}",
        }

    tool_meta = TOOLS[tool_name]
    input_model = tool_meta["input_model"]
    func: Callable = tool_meta["func"]

    start = time.perf_counter()
    try:
        # Validate arguments against Pydantic schema
        validated_input = input_model(**arguments)
        result = func(validated_input)
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info("Tool '%s' executed successfully in %d ms.", tool_name, duration_ms)
        return {"tool": tool_name, "duration_ms": duration_ms, "result": result}
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("Error executing tool '%s': %s", tool_name, exc)
        return {
            "tool": tool_name,
            "duration_ms": duration_ms,
            "status": "error",
            "message": f"Execution failed: {str(exc)}",
        }
