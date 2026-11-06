# System & Agentic Architecture Specification

This document details the complete production architecture of the **Enterprise IT Support Agentic RAG Copilot**, including the LangGraph directed acyclic graph (DAG), tool registry, human-in-the-loop approval workflow, and free-tier deployment architecture.

---

## 1. End-to-End System Architecture

```mermaid
graph TD
    User["👤 Employee / Recruiter Browser"]
    
    subgraph Frontend["Frontend Layer (FastAPI Static & Jinja2)"]
        UI["Multi-Tab Dashboard\nOverview | Chat | KB | Tickets | Approvals | Eval | Health"]
    end

    subgraph Backend["Backend Application (FastAPI + Python 3.11)"]
        Router["FastAPI Router\n/api/chat, /api/tickets, /api/approvals, /api/metrics"]
        Security["Security Guard & Preprocessor\nPrompt Injection Defense (Regex Engine)"]
        Memory["Session Memory Manager\nSQLite conversations (isolated turns)"]
        
        subgraph Agent["LangGraph Control Layer"]
            Graph["16-Node StateGraph\nRouter ──► KB ──► Grade ──► Web ──► Verify"]
        end

        subgraph Tools["Controlled Tool Registry"]
            ToolKB["search_kb"]
            ToolWeb["search_web"]
            ToolGuide["troubleshooting_guide"]
            ToolCreate["create_it_ticket"]
            ToolLookup["lookup_it_ticket"]
            ToolEscalate["escalate_to_human"]
        end

        subgraph Storage["Persistence & Registry"]
            AuditDB["SQLite Database (audit.db)\nquery_audit | documents | tickets | approvals | conversations"]
        end
    end

    subgraph FreeTierCloud["Free-Tier Cloud Services (₹0 Budget)"]
        Groq["Groq API Engine\nModel: openai/gpt-oss-20b\nFree Fast Inference"]
        Pinecone["Pinecone Starter\nIndex: industry-agentic-rag-kb\nNamespace: company-kb (384d)"]
        Tavily["Tavily Search API\n1,000 monthly free searches"]
        HF["Local HuggingFace Model\nall-MiniLM-L6-v2 (~90 MB RAM)"]
    end

    User <--> UI
    UI <--> Router
    Router --> Security
    Security --> Memory
    Memory --> Graph
    Graph --> Tools
    Tools --> Storage
    
    Graph --> Groq
    ToolKB --> HF
    HF --> Pinecone
    ToolWeb --> Tavily
```

---

## 2. LangGraph 16-Node Workflow DAG

```mermaid
flowchart TD
    START([User Query]) --> Preprocess[preprocess_query<br/>Screen injection & attach memory]

    Preprocess -- "Malicious Injection" --> Blocked[blocked_response<br/>Safe polite refusal]
    Blocked --> END([Response])

    Preprocess -- "Valid Query" --> Route[route_question<br/>Classify intent via Groq]

    Route -- "ticket_create" --> TicketCreate[handle_ticket_create<br/>Extract fields & execute tool]
    Route -- "ticket_lookup" --> TicketLookup[handle_ticket_lookup<br/>Lookup TICK-ID in SQLite]
    Route -- "guidance" --> Guidance[handle_guidance<br/>Standard diagnostic checklists]
    Route -- "direct" --> Direct[direct_answer<br/>Casual greeting reply]
    Route -- "kb" --> RetrieveKB[retrieve_kb<br/>Pinecone 384d vector search]

    TicketCreate --> CheckPriority{Priority P1/P2?}
    CheckPriority -- "Yes" --> QueueApproval[Queue HITL Approval<br/>Status: PENDING_APPROVAL]
    CheckPriority -- "No" --> AutoOpen[Auto Assign<br/>Status: OPEN]
    QueueApproval --> END
    AutoOpen --> END
    TicketLookup --> END
    Guidance --> END
    Direct --> END

    RetrieveKB --> GradeKB[grade_kb<br/>Evaluate retrieved evidence]

    GradeKB -- "Evidence Sufficient (GOOD)" --> GenKB[generate_from_kb<br/>Grounded answer from private docs]
    GradeKB -- "Evidence Weak (WEAK)" --> SearchWeb[search_web<br/>Tavily external search fallback]

    SearchWeb --> GradeWeb[grade_web<br/>Evaluate web search quality]

    GradeWeb -- "Web Evidence Sufficient (GOOD)" --> GenWeb[generate_from_web<br/>External answer with disclaimer]
    GradeWeb -- "Weak & retries < max" --> Rewrite[rewrite_query<br/>Inject technical keywords]
    GradeWeb -- "Weak & retries >= max" --> Insufficient[insufficient<br/>Polite service desk referral]

    Rewrite --> RetrieveKB

    GenKB --> Verify[verify_answer<br/>Audit groundness vs context]
    GenWeb --> Verify
    Verify --> END
    Insufficient --> END
```

---

## 3. Human-in-the-Loop (HITL) Safety Gate Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Employee / Requester
    participant Agent as LangGraph Agent
    participant DB as SQLite Ticket Store
    actor Admin as IT Service Desk Manager

    User->>Agent: "Create P1 ticket: building network switch is down!"
    Agent->>Agent: Extract Category=Network, Priority=P1
    Agent->>DB: INSERT INTO tickets (status: PENDING_APPROVAL)
    Agent->>DB: INSERT INTO approvals (status: PENDING)
    Agent-->>User: Returns Ticket ID & Approval ID (Requires Manager Review)

    Admin->>Agent: GET /api/approvals (Lists pending reviews)
    Admin->>Agent: POST /api/approvals/{id}/action (decision: APPROVED)
    Agent->>DB: UPDATE tickets SET status = 'OPEN'
    Agent->>DB: UPDATE approvals SET status = 'APPROVED'
    Agent-->>Admin: Ticket promoted to active OPEN queue
```

---

## 4. Document Ingestion & Deduplication Pipeline

```mermaid
flowchart LR
    File[Upload File<br/>PDF, DOCX, TXT, MD, CSV] --> SizeCheck{File Size ≤ 20MB?}
    SizeCheck -- "No" --> Err413[HTTP 413 Payload Too Large]
    SizeCheck -- "Yes" --> Hash[Compute SHA-256 Content Hash]
    
    Hash --> DupCheck{Hash in documents table?}
    DupCheck -- "Yes" --> Err409[HTTP 409 Conflict<br/>Duplicate Prevented]
    DupCheck -- "No" --> Chunk[Recursive Character Chunking<br/>size=900, overlap=120]
    
    Chunk --> Embed[Local HuggingFace Model<br/>all-MiniLM-L6-v2 384-dim]
    Embed --> Upsert[Pinecone Serverless Upsert<br/>Namespace: company-kb]
    Upsert --> Registry[Record in SQLite documents table]
    Registry --> Success[HTTP 200 OK<br/>Document Indexed]
```
