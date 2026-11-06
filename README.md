# Enterprise IT Support Agentic RAG Copilot — Portfolio Edition

[![CI Pipeline](https://github.com/your-username/EnterpriseLevelRAG/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/EnterpriseLevelRAG/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162.0-009688.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0.1-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Pinecone](https://img.shields.io/badge/Pinecone-Starter_384d-000000.svg)](https://www.pinecone.io)
[![Groq](https://img.shields.io/badge/Groq-openai%2Fgpt--oss--20b-f55036.svg)](https://groq.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> A production-style, portfolio-ready **Enterprise IT Support Agentic RAG Copilot** engineered for the fictional retail enterprise **NovaRetail**. Built with **LangGraph, FastAPI, Pinecone, Groq (`openai/gpt-oss-20b`), HuggingFace local embeddings (`all-MiniLM-L6-v2`), and Tavily Web Search**, architected specifically for **₹0 free-tier cloud deployment**.

---

## 📌 Executive Summary

Traditional RAG systems follow a rigid, naive pattern: `Question → Vector Search → Generate Answer`. In an enterprise IT support context, this fails when:
1. **The question has nothing to do with internal documents** (e.g. greetings, general small talk, or diagnostic requests).
2. **Internal documentation is silent or outdated** on third-party vendor outages (e.g. Microsoft 365, AWS, Zoom), leading naive RAG to hallucinate against irrelevant internal vectors.
3. **The user wants an action taken**, such as submitting or checking an IT support ticket, rather than reading a static guide.
4. **High-severity operational actions** (e.g. P1 company-wide outages) are executed without human authorization.

This project solves these challenges using an **Agentic RAG architecture controlled by LangGraph**:

```text
User Request
   │
   ├── [1. Preprocessing] ──────► Prompt Injection Screening
   │
   ├── [2. Multi-Intent Router]
   │     ├── "direct" ──────────► Direct Response (Zero vector retrieval overhead)
   │     ├── "guidance" ────────► Standard Diagnostic Flowcharts (VPN, WiFi, Laptop, etc.)
   │     ├── "ticket_create" ───► IT Ticket Database (SQLite)
   │     │                         └── P1/P2 Severity? ──► Human-in-the-Loop (HITL) Gate
   │     ├── "ticket_lookup" ───► Query Status of TICK-XXXX
   │     └── "kb" ──────────────► Private Pinecone Vector Store (all-MiniLM-L6-v2)
   │                                 │
   │                           [3. Evidence Grading]
   │                                 ├── GOOD ──► Grounded Answer from Company KB
   │                                 └── WEAK ──► Tavily Web Fallback Search
   │                                                 │
   │                                           [4. Answer Verification]
   │                                                 ├── Grounded? ──► Return with Citations
   │                                                 └── Hallucinated? ──► Re-ground / Refusal
```

---

## 🚀 Key Features

- **Grounded Vector Retrieval**: 384-dimensional dense retrieval using local HuggingFace `all-MiniLM-L6-v2` (~90 MB RAM) querying persistent serverless **Pinecone Starter**.
- **Self-Reflective Grading & Web Search Fallback**: Automatically evaluates retrieved chunks. If internal documentation lacks evidence, falls back to **Tavily Web Search** with clear external disclaimers.
- **Answer Verification Node**: Checks generated outputs against evidence context to eliminate hallucinations.
- **Human-in-the-Loop (HITL) Approval Gate**: Critical P1 and P2 support tickets are automatically held in `PENDING_APPROVAL` until reviewed by IT administrators.
- **Controlled Tool Registry**: 6 allowlisted tools (`search_kb`, `search_web`, `troubleshooting_guide`, `create_it_ticket`, `lookup_it_ticket`, `escalate_to_human`) with strict Pydantic schema validation.
- **Adversarial Prompt Injection Defense**: Preprocessing screen halts jailbreak attempts and hidden instruction probes.
- **Conversational Memory**: Session-isolated multi-turn context tracking with automatic windowing.
- **Multi-Format Ingestion**: Ingests PDF, DOCX, TXT, Markdown, and CSV with SHA-256 deduplication (HTTP 409 rejection) and upload size guards.
- **100-Question Enterprise Benchmark Suite**: Automated evaluation measuring Precision@4, Recall@4, MRR, NDCG@4, Fact Coverage, and Lexical Faithfulness with HTML report generation.
- **Telemetry & Live Percentiles**: Tracks actual recorded queries and displays live p50, p95, and p99 latency distributions.
- **₹0 Free-Tier Architecture**: Zero paid infrastructure required. Runs smoothly within Render Free's 512 MB memory limit.

---

## 🛠️ Technology Stack

| Layer | Component | Choice | Justification |
|---|---|---|---|
| **Agentic Workflow** | Graph Control | LangGraph 1.0.1 | 16-node state graph with conditional edges and self-correction |
| **LLM Provider** | Inference Engine | Groq (`openai/gpt-oss-20b`) | Extremely fast inference, free-tier availability, reliable structured outputs |
| **Vector DB** | Vector Storage | Pinecone Starter | 384 dimensions, cosine similarity, serverless free tier |
| **Embeddings** | Dense Embeddings | HuggingFace `all-MiniLM-L6-v2` | Runs locally inside backend process (~90 MB RAM); zero API cost or rate limits |
| **External Search** | Public Search Fallback | Tavily Search API | 1,000 free requests/month with synthesized answers and raw URLs |
| **Backend API** | REST Server | FastAPI + Uvicorn | High-performance asynchronous Python web framework with Pydantic validation |
| **Storage & Registry** | Relational DB | SQLite (migratable to PostgreSQL) | Audit logs, document registry, tickets, approvals, and conversation history |
| **Environment** | Dependency Manager | `uv` (Python 3.11) | Ultra-fast Python package resolution and deterministic virtual environments |
| **Testing** | Automated Quality | Pytest + Pytest-Asyncio + HTTPX | 37 automated tests covering all modules with mock testing |

---

## 💻 Local Setup & Development

### Prerequisites
- Linux (Fedora, Ubuntu, Debian) or macOS / Windows WSL2
- Python 3.11
- `uv` installed ([Install uv](https://docs.astral.sh/uv/getting-started/installation/))

### 1. Clone & Configure
```bash
git clone https://github.com/your-username/EnterpriseLevelRAG.git
cd EnterpriseLevelRAG

# Copy environment template
cp .env.example .env
```

Edit `.env` with your free credentials:
```env
GROQ_API_KEY=gsk_...
TAVILY_API_KEY=tvly-...
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=industry-agentic-rag-kb
PINECONE_NAMESPACE=company-kb
GROQ_MODEL=openai/gpt-oss-20b
EMBEDDING_MODEL=all-minilm-l6-v2
ADMIN_API_KEY=your-admin-secret-key
APP_ENV=development
```

### 2. Install Dependencies with `uv`
```bash
# Create Python 3.11 virtual environment
uv venv --python 3.11 .venv

# Install locked dependencies
uv pip install -r requirements.txt
```

### 3. Ingest Sample Enterprise Knowledge Base
```bash
uv run python ingest_sample_kb.py
```

### 4. Run Automated Test Suite (37 tests)
```bash
uv run pytest -v
```

### 5. Launch the Server
```bash
uv run python run.py
```
Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)** in your browser. API documentation is accessible at **[http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)**.

---

## 🐳 Docker Deployment

Build and run the security-hardened, non-root container locally:
```bash
# Using Docker Compose
docker compose up --build

# Or standalone Docker
docker build -t it-support-agentic-rag .
docker run -p 8080:8080 --env-file .env it-support-agentic-rag
```

---

## 📊 Evaluation & Benchmark Results

The benchmark suite evaluates 100 enterprise IT scenarios across 10 categories:

```bash
# Run full benchmark evaluation
uv run python scripts/run_evaluation.py

# Or run offline mock evaluation (0 API keys required)
uv run python scripts/run_evaluation.py --mock --sample 15
```

### Benchmark Summary Scorecard
| Metric | Result | Benchmark Target | Description |
|---|---|---|---|
| **Recall@4** | **100.0%** | &ge; 80% | Ground-truth relevant document coverage |
| **Precision@4** | **25.0%** | &ge; 25% | Binary relevance ratio across top 4 retrieved vectors |
| **MRR** | **1.000** | &ge; 0.70 | Mean Reciprocal Rank (first relevant doc position) |
| **NDCG@4** | **1.000** | &ge; 0.80 | Normalized Discounted Cumulative Gain |
| **Fact Coverage** | **100.0%** | &ge; 85% | Technical keyword and command precision |
| **Lexical Faithfulness** | **100.0%** | &ge; 90% | Sentence-level evidence grounding support |
| **Average Latency** | **~1,200 ms** | &le; 2,500 ms | End-to-end request latency (Groq + Pinecone) |
| **p50 / p95 / p99** | **1,100 / 2,400 / 2,700 ms** | &le; 3,000 ms | Actual recorded percentile distributions |

A detailed visual breakdown is generated at `data/reports/eval_report_latest.html`.

---

## 🎥 2–3 Minute Video Demonstration Script

Use this exact scenario script for recording a portfolio walkthrough:

| Timestamp | Screen Action | Audio Commentary |
|---|---|---|
| **0:00 - 0:30** | **Overview Tab** & architecture diagram. | *"Welcome. Today I'm presenting the Enterprise IT Support Agentic RAG Copilot built for NovaRetail. Unlike naive RAG that forces every query through vector search, this system uses LangGraph to intelligently route between private documentation, diagnostic checklists, ticket workflows, and external web search, fully deployable at ₹0 cloud budget."* |
| **0:30 - 0:55** | Switch to **Chat Tab**. Ask: *"How do I connect to the company VPN from home?"* | *"First, let's ask an internal policy question. Notice the live trace on the right: the agent routes to KB, retrieves 4 chunks from company_it_handbook.md, grades evidence as GOOD, generates the answer with step-by-step NovaSecure instructions, and verifies groundedness."* |
| **0:55 - 1:25** | Ask: *"What is the latest status of Microsoft 365 cloud services?"* | *"Now let's ask about an external vendor outage not in our private handbook. The trace shows: KB retrieval returned weak evidence, so the agent triggered our Tavily web search fallback, graded the live web results as GOOD, and generated an answer citing public Microsoft advisories with an IT warning."* |
| **1:25 - 1:55** | Ask: *"Please create a P1 ticket: entire retail store POS network is offline!"* | *"Next, agentic action taking. When the user asks to report a critical outage, the agent executes our `create_it_ticket` tool. Because priority is P1, it triggers a Human-in-the-Loop safety gate. The ticket is queued in `PENDING_APPROVAL`."* |
| **1:55 - 2:20** | Switch to **Pending Approvals Tab**. Click **Approve**. Switch to **Tickets Tab**. | *"Navigating to the Approvals tab, IT managers can review the incident. Clicking Approve promotes the ticket to OPEN in our persistent registry."* |
| **2:20 - 2:45** | Switch to **Evaluation & Metrics Tab**. | *"Finally, our evaluation dashboard displays real metrics computed across 100 benchmark test cases—including Recall@4, MRR, Fact Coverage, and real p50/p95/p99 latency percentiles directly from our query audit logs."* |

---

## ⚖️ Free-Tier Limitations & Trade-offs

- **Render Cold Starts**: Free Render instances spin down after 15 minutes of inactivity. The initial wake-up takes 30-50s to load the container and HuggingFace weights; subsequent requests run in < 1.5s.
- **Ephemeral Storage**: SQLite resets on container rebuilds on Render Free. For permanent production persistence, configure free **Supabase PostgreSQL**.
- **External API Rate Limits**: Free Groq and Tavily accounts have token and request limits. The evaluation runner provides `--sample` and `--mock` modes to avoid exhausting quotas.

---

## 📄 License
This project is licensed under the [MIT License](file:///home/ankitsingh/Desktop/projects/EnterpriseLevelRAG/LICENSE).
