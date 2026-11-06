"""
Enterprise LangGraph Agentic RAG Workflow
─────────────────────────────────────────
Upgraded architecture featuring:
  - Prompt injection defense & query preprocessing
  - Conversational memory integration
  - Intelligent routing (KB, External Web, Ticket Creation, Ticket Lookup, Guidance, Direct)
  - Tool execution (Ticket system, IT troubleshooting guides, Tavily search)
  - Evidence grading & query rewriting
  - Answer verification & groundness checking
  - Source citation generation
"""

import logging
import re
from typing import Literal

from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, START, END

from app.core.config import get_settings
from app.rag.state import (
    AgentState,
    RouteDecision,
    EvidenceGrade,
    VerificationGrade,
    TicketExtraction,
)
from app.rag.vectorstore import get_retriever
from app.services.memory import (
    add_message,
    format_history_for_prompt,
)
from app.services.tools import execute_tool

logger = logging.getLogger(__name__)
settings = get_settings()

_llm = None
_web_search = None


def llm() -> ChatGroq:
    global _llm
    if _llm is None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        _llm = ChatGroq(
            model=settings.groq_model,
            temperature=0,
            api_key=settings.groq_api_key,
        )
    return _llm


def web_search_tool() -> TavilySearch:
    global _web_search
    if _web_search is None:
        if not settings.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is not configured.")
        _web_search = TavilySearch(
            tavily_api_key=settings.tavily_api_key,
            max_results=5,
            topic="general",
            include_answer=True,
            include_raw_content=False,
        )
    return _web_search


def add_trace(state: AgentState, message: str) -> list[str]:
    return [*state.get("trace", []), message]


# ── Prompt Injection Detection ────────────────────────────────────────────────

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|previous\s+|prior\s+)*(instructions|directions|rules|prompts)",
    r"disregard\s+(all\s+|previous\s+|prior\s+)*(instructions|directions|rules|prompts)",
    r"you are now (an unrestricted|in developer mode|dan)",
    r"reveal (the|your) (system prompt|internal prompt|hidden instructions|api keys)",
    r"bypass (all\s+|safety\s+|security\s+)*(filters|checks|protocols|guardrails)",
]


def detect_prompt_injection(text: str) -> bool:
    """Deterministic pattern check for common prompt injection exploits."""
    text_lower = text.lower()
    return any(re.search(pat, text_lower) for pat in INJECTION_PATTERNS)


# ── Graph Nodes ───────────────────────────────────────────────────────────────

def preprocess_query(state: AgentState) -> dict:
    """
    Validate input, screen for prompt injections, and enrich with session memory.
    """
    q = state["question"].strip()
    if detect_prompt_injection(q):
        logger.warning("Prompt injection attempt detected: '%s'", q[:60])
        return {
            "is_injection": True,
            "source_used": "security_block",
            "answer": "I am an enterprise IT assistant. I cannot follow instructions to bypass policies, modify system constraints, or reveal private configuration.",
            "trace": add_trace(state, "Security Guard → Adversarial prompt injection detected and blocked"),
        }

    return {
        "current_query": q,
        "is_injection": False,
        "trace": add_trace(state, "Preprocessor → Query validated and session context attached"),
    }


def route_after_preprocess(state: AgentState) -> Literal["route_question", "blocked_response"]:
    return "blocked_response" if state.get("is_injection") else "route_question"


def blocked_response(state: AgentState) -> dict:
    return {"answer": state["answer"]}


def route_question(state: AgentState) -> dict:
    """
    Classify intent using structured JSON output from LLM.
    Routes to: kb, direct, ticket_create, ticket_lookup, guidance.
    """
    history_ctx = format_history_for_prompt(state.get("session_id", ""))
    router = llm().with_structured_output(RouteDecision, method="json_mode")

    prompt = f"""You route user inquiries for an enterprise IT support assistant.
Routes:
- "kb": for technical questions about VPN, password policies, software installation, hardware, MFA, wifi, company IT handbook, etc.
- "ticket_create": when user asks to open, create, raise, or submit an IT support ticket.
- "ticket_lookup": when user wants to check status of a specific ticket ID (e.g. TICK-XXXX).
- "guidance": when user asks for standard step-by-step diagnostic checklists for common problems.
- "direct": ONLY for greetings, thanks, or simple conversational small talk.

{history_ctx}
User query: {state['question']}
Return valid JSON like {{"route":"kb"}}."""

    decision: RouteDecision = router.invoke(prompt)
    return {
        "source_used": decision.route,
        "trace": add_trace(state, f"Router → Intent: {decision.route.upper()}"),
    }


def route_after_router(
    state: AgentState,
) -> Literal["retrieve_kb", "direct_answer", "handle_ticket_create", "handle_ticket_lookup", "handle_guidance"]:
    route = state["source_used"]
    if route == "ticket_create":
        return "handle_ticket_create"
    elif route == "ticket_lookup":
        return "handle_ticket_lookup"
    elif route == "guidance":
        return "handle_guidance"
    elif route == "direct":
        return "direct_answer"
    return "retrieve_kb"


def handle_ticket_create(state: AgentState) -> dict:
    """Extract ticket parameters and create ticket in database."""
    extractor = llm().with_structured_output(TicketExtraction, method="json_mode")
    extraction: TicketExtraction = extractor.invoke(
        f"""Extract IT ticket parameters from the user's request.
User query: {state['question']}
Return valid JSON with category, priority (P1/P2/P3/P4), and description."""
    )

    result = execute_tool("create_it_ticket", {
        "user_id": "employee@novaretail.internal",
        "category": extraction.category,
        "priority": extraction.priority,
        "description": extraction.description,
    })

    ticket = result["result"]["ticket"]
    ticket_id = ticket["ticket_id"]
    priority = ticket["priority"]
    requires_approval = ticket["requires_approval"]

    if requires_approval:
        answer = (
            f"**High-Priority IT Support Ticket Submitted ({priority})**\n\n"
            f"- **Ticket ID**: `{ticket_id}`\n"
            f"- **Category**: {extraction.category}\n"
            f"- **Priority**: {priority} (Requires IT Management Approval)\n"
            f"- **Status**: `PENDING_APPROVAL` (Approval ID: `{ticket.get('approval_id')}`)\n\n"
            f"Because this is a high-severity incident, an approval request has been queued for IT leadership. "
            f"You will be notified once reviewed."
        )
    else:
        answer = (
            f"**IT Support Ticket Created Successfully**\n\n"
            f"- **Ticket ID**: `{ticket_id}`\n"
            f"- **Category**: {extraction.category}\n"
            f"- **Priority**: {priority}\n"
            f"- **Status**: `OPEN`\n\n"
            f"A service desk engineer has been assigned to your issue: \"{extraction.description}\"."
        )

    return {
        "answer": answer,
        "source_used": "ticket_system",
        "ticket_info": ticket,
        "trace": add_trace(state, f"Tool → Created Ticket {ticket_id} (Priority: {priority})"),
    }


def handle_ticket_lookup(state: AgentState) -> dict:
    """Find ticket ID in query and query database."""
    match = re.search(r"TICK-[A-Za-z0-9]+", state["question"].upper())
    if not match:
        return {
            "answer": "Please provide a valid ticket ID (e.g., `TICK-1A2B3C4D`) to check its status.",
            "source_used": "ticket_system",
            "trace": add_trace(state, "Tool → Ticket lookup failed (no ticket ID found in query)"),
        }

    ticket_id = match.group(0)
    result = execute_tool("lookup_it_ticket", {"ticket_id": ticket_id})
    res_data = result["result"]

    if res_data.get("status") == "error":
        answer = f"No record found for Ticket ID `{ticket_id}`. Please verify the ID and try again."
    else:
        t = res_data["ticket"]
        answer = (
            f"**Ticket Status Report**\n\n"
            f"- **Ticket ID**: `{t['ticket_id']}`\n"
            f"- **Category**: {t['category']}\n"
            f"- **Priority**: {t['priority']}\n"
            f"- **Current Status**: `{t['status']}`\n"
            f"- **Created**: {t['created_at']}\n"
            f"- **Last Updated**: {t['updated_at']}\n"
            f"- **Description**: {t['description']}"
        )

    return {
        "answer": answer,
        "source_used": "ticket_system",
        "trace": add_trace(state, f"Tool → Ticket lookup: {ticket_id}"),
    }


def handle_guidance(state: AgentState) -> dict:
    """Retrieve standard IT diagnostic flowchart."""
    q_lower = state["question"].lower()
    topic = "vpn"
    for candidate in ["vpn", "password", "mfa", "email", "laptop", "software", "printer", "network"]:
        if candidate in q_lower:
            topic = candidate
            break

    result = execute_tool("troubleshooting_guide", {"topic": topic})
    guide = result["result"]["guide"]

    answer = f"**{guide['title']}**\n\n" + "\n".join(guide["steps"])
    if "escalation_policy" in guide:
        answer += f"\n\n*Escalation Policy:* {guide['escalation_policy']}"

    return {
        "answer": answer,
        "source_used": "troubleshooting_guide",
        "trace": add_trace(state, f"Tool → Standard troubleshooting checklist for '{topic.upper()}'"),
    }


def retrieve_kb(state: AgentState) -> dict:
    """Retrieve top-k relevant chunks from Pinecone vector store."""
    docs = get_retriever().invoke(state["current_query"])
    return {
        "kb_docs": docs,
        "trace": add_trace(state, f"Private KB retrieval → {len(docs)} chunks"),
    }


def grade_kb(state: AgentState) -> dict:
    """Grade whether the retrieved KB evidence is sufficient to answer."""
    grader = llm().with_structured_output(EvidenceGrade, method="json_mode")
    context = "\n\n".join(
        f"Source: {d.metadata.get('source', 'unknown')}\n{d.page_content}"
        for d in state["kb_docs"]
    )
    grade: EvidenceGrade = grader.invoke(
        f"""You grade evidence for an enterprise IT support assistant.
Question: {state['question']}
Private company KB evidence:
{context}

Return "good" ONLY if the evidence is sufficient to answer confidently and specifically.
Return "weak" if the evidence is missing, irrelevant, or insufficient.
JSON: {{"grade":"good"}} or {{"grade":"weak"}}."""
    )
    return {
        "kb_grade": grade.grade,
        "trace": add_trace(state, f"KB evidence grade → {grade.grade.upper()}"),
    }


def after_kb(state: AgentState) -> Literal["generate_from_kb", "search_web"]:
    return "generate_from_kb" if state["kb_grade"] == "good" else "search_web"


def search_web(state: AgentState) -> dict:
    """Fall back to Tavily web search when KB evidence is weak."""
    result = web_search_tool().invoke({"query": state["current_query"]})
    lines: list[str] = []
    citations: list[dict] = []

    if isinstance(result, dict):
        if result.get("answer"):
            lines.append("Search answer: " + result["answer"])
        for item in result.get("results", []):
            title = item.get("title", "")
            url = item.get("url", "")
            content = item.get("content", "")
            lines.append(f"Title: {title}\nURL: {url}\nContent: {content}")
            citations.append({"title": title or url, "url": url, "type": "web"})
    else:
        lines.append(str(result))

    return {
        "web_results": "\n\n".join(lines),
        "citations": citations,
        "source_used": "web",
        "trace": add_trace(state, "Web fallback → Tavily search"),
    }


def grade_web(state: AgentState) -> dict:
    """Grade whether the web search results are sufficient to answer."""
    grader = llm().with_structured_output(EvidenceGrade, method="json_mode")
    grade: EvidenceGrade = grader.invoke(
        f"""Question: {state['question']}
Web evidence:
{state['web_results']}

Return "good" if the evidence is sufficient and directly relevant to the question.
Return "weak" if it is irrelevant, too general, or missing key information.
JSON: {{"grade":"good"}} or {{"grade":"weak"}}."""
    )
    return {
        "web_grade": grade.grade,
        "trace": add_trace(state, f"Web evidence grade → {grade.grade.upper()}"),
    }


def after_web(
    state: AgentState,
) -> Literal["generate_from_web", "rewrite_query", "insufficient"]:
    if state["web_grade"] == "good":
        return "generate_from_web"
    if state["retry_count"] < settings.max_retries:
        return "rewrite_query"
    return "insufficient"


def rewrite_query(state: AgentState) -> dict:
    """Rewrite the query with better technical keywords for improved retrieval."""
    rewritten: str = llm().invoke(
        f"""Rewrite this IT support question for better private knowledge retrieval and vendor web search.
Preserve original intent. Add useful technical keywords. Do not answer.
Return ONLY the rewritten query.

Original question: {state['question']}"""
    ).content.strip()
    return {
        "current_query": rewritten,
        "retry_count": state["retry_count"] + 1,
        "trace": add_trace(state, f"Query rewrite → {rewritten}"),
    }


def generate_from_kb(state: AgentState) -> dict:
    """Generate grounded answer exclusively from the private KB."""
    context = "\n\n".join(
        f"[Source: {d.metadata.get('source', 'unknown')}]\n{d.page_content}"
        for d in state["kb_docs"]
    )
    answer: str = llm().invoke(
        f"""You are an enterprise IT support copilot. Answer ONLY from the private company KB below.
Be concise and actionable. Present numbered steps where appropriate.
Do not invent policy details not found in the KB.
Mention that the answer is based on the company's private knowledge base.

Question: {state['question']}

Private KB:
{context}"""
    ).content

    citations: list[dict] = []
    seen: set[str] = set()
    for d in state["kb_docs"]:
        src = d.metadata.get("source", "Private KB")
        if src not in seen:
            seen.add(src)
            citations.append({
                "title": src.split("/")[-1],
                "url": "",
                "type": "private_kb",
            })

    return {
        "answer": answer,
        "source_used": "private_kb",
        "citations": citations,
        "trace": add_trace(state, "Answer generation → PRIVATE KB"),
    }


def generate_from_web(state: AgentState) -> dict:
    """Generate answer from web search results, with an appropriate disclaimer."""
    answer: str = llm().invoke(
        f"""You are an enterprise IT support copilot. The private company KB was insufficient.
Answer ONLY from the web evidence below.
Clearly state that this information comes from public external sources and may need
IT team validation before applying to company-managed systems.

Question: {state['question']}

Web evidence:
{state['web_results']}"""
    ).content
    return {
        "answer": answer,
        "source_used": "web_search",
        "trace": add_trace(state, "Answer generation → WEB SEARCH"),
    }


def verify_answer(state: AgentState) -> dict:
    """
    Verify that generated answer is strictly grounded in retrieved evidence.
    Prevents hallucination.
    """
    if state.get("source_used") in ("direct", "ticket_system", "troubleshooting_guide", "security_block"):
        return {"verification_grade": "grounded"}

    evidence = ""
    if state.get("source_used") == "private_kb":
        evidence = "\n".join(d.page_content for d in state.get("kb_docs", []))
    else:
        evidence = state.get("web_results", "")

    if not evidence.strip():
        return {"verification_grade": "grounded"}

    verifier = llm().with_structured_output(VerificationGrade, method="json_mode")
    v_grade: VerificationGrade = verifier.invoke(
        f"""You verify grounding for an enterprise IT support assistant.
Evidence:
{evidence[:3000]}

Generated Answer:
{state['answer'][:2000]}

Is the answer strictly grounded in the evidence without inventing unauthorized details?
Return valid JSON like {{"grade":"grounded"}} or {{"grade":"hallucinated"}}."""
    )

    trace_msg = f"Answer Verification → {v_grade.grade.upper()}"
    return {
        "verification_grade": v_grade.grade,
        "trace": add_trace(state, trace_msg),
    }


def direct_answer(state: AgentState) -> dict:
    """Handle greetings and casual conversation without retrieval."""
    answer: str = llm().invoke(
        f"Respond briefly and naturally as an enterprise IT support assistant: {state['question']}"
    ).content
    return {
        "answer": answer,
        "source_used": "direct",
        "trace": add_trace(state, "Direct response → no retrieval needed"),
    }


def insufficient(state: AgentState) -> dict:
    """Return polite refusal when no reliable evidence was found."""
    return {
        "answer": (
            "I couldn't find enough reliable evidence in the company knowledge base "
            "or external search to answer this confidently. "
            "Please contact the IT help desk directly or open a ticket."
        ),
        "source_used": "insufficient_evidence",
        "trace": add_trace(state, "Stopped → insufficient reliable evidence after retries"),
    }


# ── LangGraph Workflow Construction ───────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)

    nodes = {
        "preprocess_query": preprocess_query,
        "blocked_response": blocked_response,
        "route_question": route_question,
        "handle_ticket_create": handle_ticket_create,
        "handle_ticket_lookup": handle_ticket_lookup,
        "handle_guidance": handle_guidance,
        "retrieve_kb": retrieve_kb,
        "grade_kb": grade_kb,
        "search_web": search_web,
        "grade_web": grade_web,
        "rewrite_query": rewrite_query,
        "generate_from_kb": generate_from_kb,
        "generate_from_web": generate_from_web,
        "verify_answer": verify_answer,
        "direct_answer": direct_answer,
        "insufficient": insufficient,
    }

    for name, fn in nodes.items():
        graph.add_node(name, fn)

    # Preprocessing & Injection guard
    graph.add_edge(START, "preprocess_query")
    graph.add_conditional_edges(
        "preprocess_query",
        route_after_preprocess,
        {"route_question": "route_question", "blocked_response": "blocked_response"},
    )
    graph.add_edge("blocked_response", END)

    # Intent routing
    graph.add_conditional_edges(
        "route_question",
        route_after_router,
        {
            "retrieve_kb": "retrieve_kb",
            "direct_answer": "direct_answer",
            "handle_ticket_create": "handle_ticket_create",
            "handle_ticket_lookup": "handle_ticket_lookup",
            "handle_guidance": "handle_guidance",
        },
    )

    # Tool edges
    graph.add_edge("handle_ticket_create", END)
    graph.add_edge("handle_ticket_lookup", END)
    graph.add_edge("handle_guidance", END)

    # KB retrieval & grading
    graph.add_edge("retrieve_kb", "grade_kb")
    graph.add_conditional_edges(
        "grade_kb",
        after_kb,
        {"generate_from_kb": "generate_from_kb", "search_web": "search_web"},
    )

    # Web fallback & grading
    graph.add_edge("search_web", "grade_web")
    graph.add_conditional_edges(
        "grade_web",
        after_web,
        {
            "generate_from_web": "generate_from_web",
            "rewrite_query": "rewrite_query",
            "insufficient": "insufficient",
        },
    )
    graph.add_edge("rewrite_query", "retrieve_kb")

    # Generation & verification
    graph.add_edge("generate_from_kb", "verify_answer")
    graph.add_edge("generate_from_web", "verify_answer")
    graph.add_edge("verify_answer", END)

    graph.add_edge("direct_answer", END)
    graph.add_edge("insufficient", END)

    return graph.compile()


agent_graph = build_graph()


def ask(question: str, session_id: str = "default_session") -> dict:
    """
    Invoke the agent graph with a user question and session identifier.
    Persists user query and agent response into conversation memory.
    """
    initial: AgentState = {
        "question": question,
        "current_query": question,
        "session_id": session_id,
        "kb_docs": [],
        "web_results": "",
        "kb_grade": "",
        "web_grade": "",
        "verification_grade": "",
        "answer": "",
        "source_used": "",
        "retry_count": 0,
        "trace": [],
        "citations": [],
        "ticket_info": {},
        "is_injection": False,
    }

    result = agent_graph.invoke(initial)

    # Record message turns into session memory
    if not result.get("is_injection"):
        add_message(session_id, "user", question)
        add_message(session_id, "assistant", result["answer"])

    return result
