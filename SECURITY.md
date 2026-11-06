# Enterprise Security Architecture & Threat Mitigation

This document outlines the security controls, defensive layers, and threat mitigations implemented across the **Enterprise IT Support Agentic RAG Copilot**.

---

## 1. Threat Model & Defensive Strategy

In enterprise agentic workflows, LLMs interface directly with user inputs, internal private vector databases, external search APIs, and database mutation tools. Treating all inputs and external content as untrusted is fundamental.

```text
Untrusted Input ──► [Layer 1: Input & Injection Screen]
                         │
                         ├── Malicious? ──► Terminate with Safe Error
                         │
                         ▼
                    [Layer 2: Multi-Intent Guardrails]
                         │
                         ▼
                    [Layer 3: Allowlisted Tool Execution]
                         │
                         ▼
                    [Layer 4: Answer & Citation Verification]
                         │
                         ▼
                    Sanitized Output ──► User
```

---

## 2. Implemented Security Controls

### 2.1 Prompt Injection Defenses
- **Regex Guardrails (`INJECTION_PATTERNS`)**:
  - The preprocessing node filters adversarial directives before they reach the router or model.
  - Matches patterns such as:
    - `"ignore (all/previous/prior) instructions"`
    - `"disregard rules"`
    - `"you are now in developer mode / DAN"`
    - `"reveal system prompt / internal instructions / API keys"`
    - `"bypass safety / security filters"`
- **Strict Separation of Data and Instructions**:
  - Retrieved documents from Pinecone and external web results from Tavily are tagged as untrusted context and formatted within distinct XML/fenced boundaries. The LLM is instructed never to follow instructions found inside retrieved text.

### 2.2 Tool Registry Allowlisting & Boundary Isolation
- **No Arbitrary Execution**:
  - The agent has zero access to shell interpreters (`bash`, `sh`), filesystem exploration, or arbitrary Python execution (`eval`, `exec`).
- **Strict Input Validation**:
  - Every registered tool (`search_kb`, `search_web`, `troubleshooting_guide`, `create_it_ticket`, `lookup_it_ticket`, `escalate_to_human`) enforces strict Pydantic schemas. Unregistered tools are rejected with an explicit error.
- **Execution Timeouts & Error Isolation**:
  - Tool executions are wrapped in defensive try-except blocks with execution timers so that a third-party API failure cannot crash the worker process.

### 2.3 Human-in-the-Loop (HITL) Safety Gates
- **High-Severity Action Gates**:
  - Submitting critical incidents (Priority **P1** or **P2**) does not execute immediate unrestricted external alerts. Instead, the ticket is placed into `PENDING_APPROVAL` and queued in the `approvals` table.
  - A human operator must explicitly review and trigger `POST /api/approvals/{id}/action` with `APPROVED` before the incident is promoted to `OPEN`.

### 2.4 File Ingestion & Path Traversal Mitigations
- **File Type Whitelist**:
  - Only `.pdf`, `.docx`, `.txt`, `.md`, and `.csv` are permitted. Binary executables (`.exe`, `.sh`, `.py`) are rejected (HTTP 400).
- **Upload Size Limit**:
  - Uploads exceeding 20 MB are rejected immediately (HTTP 413) to protect memory from denial-of-service exhaustion.
- **Path Sanitization**:
  - Filenames are sanitized via regex (`re.sub(r"[^\w.\-]", "_", name)`) and directory paths are stripped to prevent directory traversal attacks (`../../etc/passwd`).
- **Cryptographic Deduplication**:
  - SHA-256 hashes prevent indexing duplicate payloads (HTTP 409).
- **Admin Header Protection**:
  - Ingestion requires the `X-Admin-Key` header matching `ADMIN_API_KEY`.

### 2.5 Container & Operating System Hardening
- **Non-Root Execution**:
  - The production [`Dockerfile`](file:///home/ankitsingh/Desktop/projects/EnterpriseLevelRAG/Dockerfile) creates an unprivileged user `appuser` (UID 1001) and drops root permissions before starting uvicorn.
- **Minimal Attack Surface**:
  - Based on `python:3.11-slim`, omitting unnecessary development packages and compilers.
- **CORS Policies**:
  - CORS middleware is configured to restrict unauthorized origin cross-site access in production.

### 2.6 Secrets Management
- Real API credentials are never committed to version control.
- [`.gitignore`](file:///home/ankitsingh/Desktop/projects/EnterpriseLevelRAG/.gitignore) explicitly excludes `.env`, `*.db`, and credentials.
- [`.env.example`](file:///home/ankitsingh/Desktop/projects/EnterpriseLevelRAG/.env.example) is maintained with dummy values for developer onboarding.
- Exception handlers in [`app/api/routes.py`](file:///home/ankitsingh/Desktop/projects/EnterpriseLevelRAG/app/api/routes.py) return generic safe error messages on 500 status codes, preventing internal file paths, stack traces, or API keys from leaking to client responses.
