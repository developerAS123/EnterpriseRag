"""
Agent state and structured decision schemas for LangGraph.
"""

from typing import Any, List, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.documents import Document

# ── Structured output schemas for LLM nodes ───────────────────────────────────

class RouteDecision(BaseModel):
    route: Literal["kb", "direct", "ticket_create", "ticket_lookup", "guidance"] = Field(
        description=(
            "'kb' for IT questions about company policies, VPN, MFA, hardware, password, etc.; "
            "'ticket_create' if the user explicitly asks to create, open, submit, or raise a support ticket; "
            "'ticket_lookup' if the user provides a ticket ID and asks for its status; "
            "'guidance' for standardized step-by-step diagnostic checklists; "
            "'direct' ONLY for simple greetings, thanks, or casual conversation."
        )
    )


class EvidenceGrade(BaseModel):
    grade: Literal["good", "weak"] = Field(
        description="Whether the provided evidence is sufficient, relevant, and confident to answer the question."
    )


class VerificationGrade(BaseModel):
    grade: Literal["grounded", "hallucinated"] = Field(
        description="Whether the generated answer is strictly grounded in the provided context and evidence."
    )


class TicketExtraction(BaseModel):
    category: str = Field(..., description="IT Category e.g. VPN, Hardware, Email, Access")
    priority: Literal["P1", "P2", "P3", "P4"] = Field(default="P3", description="P1 for outage, P2 team blocked, P3 individual, P4 general")
    description: str = Field(..., description="Summary of the user issue to record in the ticket")


# ── LangGraph shared Agent State ──────────────────────────────────────────────

class AgentState(TypedDict):
    question: str
    current_query: str
    session_id: str
    kb_docs: List[Document]
    web_results: str
    kb_grade: str
    web_grade: str
    verification_grade: str
    answer: str
    source_used: str
    retry_count: int
    trace: List[str]
    citations: List[dict]
    ticket_info: dict[str, Any]
    is_injection: bool
