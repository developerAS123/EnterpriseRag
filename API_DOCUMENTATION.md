# REST API Documentation

Base URL: `http://localhost:8080/api` (Local) / `https://<render-service-url>/api` (Production)

---

## 1. System & Health

### `GET /health`
Liveness and diagnostic probe.

**Response `200 OK`**:
```json
{
  "status": "ok",
  "service": "Enterprise IT Support Agentic RAG Copilot",
  "env": "production",
  "model": "openai/gpt-oss-20b",
  "embedding": "all-MiniLM-L6-v2"
}
```

---

## 2. Agentic Chat & Retrieval

### `POST /chat`
Runs the complete LangGraph workflow for an IT question. Supports conversational session tracking.

**Request Body**:
```json
{
  "question": "How do I connect to the company VPN from home?",
  "session_id": "optional-uuid-string"
}
```

**Response `200 OK`**:
```json
{
  "answer": "**Answer (based on company's private knowledge base)**:\n\n1. Install the NovaSecure VPN client...",
  "source_used": "private_kb",
  "trace": [
    "Preprocessor → Query validated and session context attached",
    "Router → Intent: KB",
    "Private KB retrieval → 4 chunks",
    "KB evidence grade → GOOD",
    "Answer generation → PRIVATE KB",
    "Answer Verification → GROUNDED"
  ],
  "citations": [
    {
      "title": "company_it_handbook.md",
      "url": "",
      "type": "private_kb"
    }
  ],
  "rewritten_query": "How do I connect to the company VPN from home?",
  "session_id": "session-1234",
  "verification_grade": "grounded",
  "ticket_info": null
}
```

---

## 3. Knowledge Base & Document Ingestion

### `GET /documents`
Lists all documents registered in the persistent knowledge base registry.

**Response `200 OK`**:
```json
{
  "total": 2,
  "documents": [
    {
      "document_id": "doc_64496f767770",
      "filename": "company_it_handbook.md",
      "content_hash": "64496f7677700d0085ed455a18bf1ed2e27e4cb5223967c44a1e1fcad4ae3a5a",
      "file_type": "md",
      "chunk_count": 3,
      "uploaded_at": "2026-11-06T11:00:00Z",
      "status": "indexed"
    }
  ]
}
```

### `POST /ingest`
Admin-only endpoint to upload, chunk, embed, and index new company documents.

**Headers**:
- `X-Admin-Key`: Required. Must match `ADMIN_API_KEY`.

**Form-Data**:
- `file`: Uploaded file (`.pdf`, `.docx`, `.txt`, `.md`, `.csv`). Max 20 MB.

**Response `200 OK`**:
```json
{
  "message": "Document indexed successfully.",
  "document_id": "doc_a1b2c3d4e5f6",
  "file": "wifi_runbook.pdf",
  "chunks": 4,
  "ids_created": 4,
  "content_hash": "a1b2c3d4e5f67890"
}
```

**Errors**:
- `401 Unauthorized`: Invalid admin key
- `400 Bad Request`: Unsupported file extension
- `409 Conflict`: Identical document already exists in registry
- `413 Payload Too Large`: Exceeds 20 MB

---

## 4. IT Support Tickets & Approvals

### `GET /tickets`
Lists recent support tickets.

**Query Parameters**:
- `limit` (int, default: 50)

**Response `200 OK`**:
```json
{
  "total": 1,
  "tickets": [
    {
      "ticket_id": "TICK-FF810161",
      "user_id": "employee@novaretail.internal",
      "category": "Payment Gateway",
      "priority": "P1",
      "description": "Store POS network offline",
      "status": "PENDING_APPROVAL",
      "created_at": "2026-11-06T11:23:12Z",
      "updated_at": "2026-11-06T11:23:12Z"
    }
  ]
}
```

### `POST /tickets`
Create a new support ticket directly.

**Request Body**:
```json
{
  "user_id": "employee@company.com",
  "category": "Hardware",
  "priority": "P3",
  "description": "Laptop screen flickering after update"
}
```

**Response `200 OK`**:
```json
{
  "ticket": {
    "ticket_id": "TICK-1A2B3C4D",
    "user_id": "employee@company.com",
    "category": "Hardware",
    "priority": "P3",
    "status": "OPEN",
    "requires_approval": false,
    "approval_id": null,
    "created_at": "2026-11-06T11:30:00Z"
  }
}
```

### `GET /approvals`
Lists pending Human-in-the-Loop approvals for high-severity P1/P2 tickets.

**Response `200 OK`**:
```json
{
  "total": 1,
  "approvals": [
    {
      "approval_id": "APPR-95485EA3",
      "ticket_id": "TICK-FF810161",
      "priority": "P1",
      "category": "Payment Gateway",
      "details": "Create P1 ticket for 'Payment Gateway': Store POS network offline",
      "status": "PENDING",
      "requested_at": "2026-11-06T11:23:12Z"
    }
  ]
}
```

### `POST /approvals/{approval_id}/action`
Decide an approval request (promotes ticket to `OPEN` or `REJECTED`).

**Request Body**:
```json
{
  "decision": "APPROVED",
  "decided_by": "IT Service Desk Director"
}
```

---

## 5. Conversational Session Memory

### `GET /conversations/{session_id}`
Returns recent conversation history for a given session.

### `DELETE /conversations/{session_id}`
Clears stored conversation history for a session.

---

## 6. Observability & Telemetry

### `GET /metrics`
Returns live system metrics computed from actual audit database entries, real latency percentiles, and offline benchmark results.

**Response `200 OK`**:
```json
{
  "timestamp": "2026-11-06T11:40:00Z",
  "telemetry": {
    "total_requests": 14,
    "routing_distribution": {
      "private_kb": 6,
      "web_search": 2,
      "ticket_system": 3,
      "direct": 2,
      "security_block": 1
    },
    "latency_summary_ms": {
      "avg": 1240.5,
      "p50": 1100.0,
      "p95": 2400.0,
      "p99": 2700.0,
      "min": 142.0,
      "max": 2850.0
    },
    "knowledge_base": {
      "indexed_documents": 2,
      "indexed_chunks": 6
    }
  },
  "benchmark_evaluation": {
    "status": "Evaluated",
    "retrieval": {
      "precision@4": 0.25,
      "recall@4": 1.0,
      "mrr": 1.0,
      "ndcg@4": 1.0
    },
    "generation": {
      "fact_coverage": 1.0,
      "faithfulness": 1.0
    }
  }
}
```
