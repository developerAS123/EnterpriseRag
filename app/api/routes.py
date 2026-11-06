"""
FastAPI route definitions
─────────────────────────
  GET    /api/health                     – liveness probe
  POST   /api/chat                       – agentic RAG query with session memory
  GET    /api/documents                  – list ingested documents
  POST   /api/ingest                     – admin-protected document ingestion
  GET    /api/tickets                    – list support tickets
  POST   /api/tickets                    – create support ticket
  GET    /api/tickets/{id}               – get ticket details
  PATCH  /api/tickets/{id}/status        – update ticket status
  POST   /api/tickets/{id}/escalate      – escalate ticket
  GET    /api/approvals                  – list pending HITL approvals
  POST   /api/approvals/{id}/action      – approve / reject pending request
  GET    /api/conversations/{session_id} – get session conversation history
  DELETE /api/conversations/{session_id} – clear session memory
"""

import hashlib
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.rag.vectorstore import add_documents
from app.rag.workflow import ask
from app.services.audit import (
    write_audit,
    get_document_by_hash,
    record_document,
    list_documents,
)
from app.services.ingestion import (
    SUPPORTED,
    chunk_documents,
    compute_content_hash,
    load_file,
)
from app.services.memory import (
    get_conversation_history,
    clear_conversation,
)
from app.services.tickets import (
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket_status,
    escalate_ticket,
    list_pending_approvals,
    decide_approval,
    TicketCreateRequest,
    TicketUpdateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
settings = get_settings()

_MAX_UPLOAD_BYTES = settings.max_upload_mb * 1024 * 1024

# ── Request / response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=3000)
    session_id: str | None = Field(default=None, description="Optional session UUID for conversation memory")


class ChatResponse(BaseModel):
    answer: str
    source_used: str
    trace: list[str]
    citations: list[dict]
    rewritten_query: str
    session_id: str
    verification_grade: str | None = None
    ticket_info: dict[str, Any] | None = None


class ApprovalActionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    decided_by: str = Field(default="IT Service Desk Manager")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^\w.\-]", "_", name)
    return name or "upload"


# ── Health & Chat ─────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
        "model": settings.groq_model,
        "embedding": settings.embedding_model,
    }


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    """
    Run LangGraph agentic RAG workflow with conversational session memory.
    """
    session_id = payload.session_id or str(uuid.uuid4())
    start = time.perf_counter()
    try:
        result = ask(payload.question, session_id=session_id)
        latency_ms = int((time.perf_counter() - start) * 1000)

        write_audit(
            payload.question,
            result["source_used"],
            result.get("trace", []),
            latency_ms=latency_ms,
        )

        return ChatResponse(
            answer=result["answer"],
            source_used=result["source_used"],
            trace=result.get("trace", []),
            citations=result.get("citations", []),
            rewritten_query=result.get("current_query", payload.question),
            session_id=session_id,
            verification_grade=result.get("verification_grade"),
            ticket_info=result.get("ticket_info"),
        )

    except RuntimeError as exc:
        logger.error("Configuration error during chat: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    except Exception as exc:
        logger.exception("Unexpected error during chat request")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again or contact IT support.",
        ) from exc


# ── Document Management ───────────────────────────────────────────────────────

@router.get("/documents")
def get_documents():
    docs = list_documents()
    return {"documents": docs, "total": len(docs)}


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    x_admin_key: str = Header(default=""),
):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key.")

    original_name = file.filename or "upload"
    suffix = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {', '.join(sorted(SUPPORTED))}",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_mb} MB upload limit.",
        )

    content_hash = compute_content_hash(raw_bytes)
    existing_doc = get_document_by_hash(content_hash)
    if existing_doc:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Document with identical content already exists "
                f"('{existing_doc['filename']}', ID: {existing_doc['document_id']}). "
                "Duplicate ingestion prevented."
            ),
        )

    safe_name = _safe_filename(original_name)
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / safe_name
    dest.write_bytes(raw_bytes)

    doc_id = f"doc_{content_hash[:12]}"
    try:
        docs = load_file(dest)
        for doc in docs:
            doc.metadata.update({
                "document_id": doc_id,
                "filename": safe_name,
                "content_hash": content_hash,
                "file_type": suffix.lstrip("."),
                "source": safe_name,
            })

        chunks = chunk_documents(docs, document_id=doc_id)
        ids = add_documents(chunks)

        record_document(
            document_id=doc_id,
            filename=safe_name,
            content_hash=content_hash,
            file_type=suffix.lstrip("."),
            chunk_count=len(chunks),
        )

        return {
            "message": "Document indexed successfully.",
            "document_id": doc_id,
            "file": safe_name,
            "chunks": len(chunks),
            "ids_created": len(ids),
            "content_hash": content_hash[:16],
        }

    except Exception as exc:
        logger.exception("Error ingesting document '%s'", safe_name)
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {str(exc)}",
        ) from exc


# ── Support Tickets & HITL Approvals ──────────────────────────────────────────

@router.get("/tickets")
def get_tickets(limit: int = 50):
    tickets = list_tickets(limit=limit)
    return {"tickets": tickets, "total": len(tickets)}


@router.post("/tickets")
def post_ticket(payload: TicketCreateRequest):
    ticket = create_ticket(
        user_id=payload.user_id,
        category=payload.category,
        priority=payload.priority,
        description=payload.description,
    )
    return {"ticket": ticket}


@router.get("/tickets/{ticket_id}")
def get_ticket_by_id(ticket_id: str):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")
    return {"ticket": ticket}


@router.patch("/tickets/{ticket_id}/status")
def patch_ticket_status(ticket_id: str, payload: TicketUpdateRequest):
    try:
        updated = update_ticket_status(ticket_id, payload.status)
        return {"ticket": updated}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tickets/{ticket_id}/escalate")
def post_ticket_escalate(ticket_id: str):
    try:
        updated = escalate_ticket(ticket_id)
        return {"message": "Ticket escalated to human service desk staff.", "ticket": updated}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/approvals")
def get_pending_approvals():
    approvals = list_pending_approvals()
    return {"approvals": approvals, "total": len(approvals)}


@router.post("/approvals/{approval_id}/action")
def post_approval_action(approval_id: str, payload: ApprovalActionRequest):
    try:
        res = decide_approval(
            approval_id=approval_id,
            decision=payload.decision,
            decided_by=payload.decided_by,
        )
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Conversation Session Memory ───────────────────────────────────────────────

@router.get("/conversations/{session_id}")
def get_session_history(session_id: str):
    history = get_conversation_history(session_id)
    return {"session_id": session_id, "messages": history, "count": len(history)}


@router.delete("/conversations/{session_id}")
def delete_session_history(session_id: str):
    deleted = clear_conversation(session_id)
    return {"session_id": session_id, "deleted_count": deleted, "message": "Conversation history cleared."}


# ── Observability & Evaluation Dashboard ──────────────────────────────────────

@router.get("/metrics")
def get_metrics():
    """
    Observability endpoint: returns live system metrics (request counts,
    real p50/p95/p99 latency percentiles, routing distribution) and benchmark evaluation results.
    """
    from app.services.audit import get_observability_metrics
    return get_observability_metrics()
