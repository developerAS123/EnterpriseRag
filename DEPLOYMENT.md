# Free-Tier Deployment Guide (₹0 Budget)

This guide covers deploying the **Enterprise IT Support Agentic RAG Copilot** to public cloud infrastructure with strictly **₹0 expenditure** using **Render Free Web Services**, **Pinecone Starter**, **Groq Free Tier**, and **Tavily Free Tier**.

---

## 1. Free-Tier Service Matrix

| Service | Component | Free Allowance | Constraints & Limitations |
|---|---|---|---|
| **Render** | Web App (FastAPI + UI) | Free Web Service | 512 MB RAM, 0.1 CPU, spins down after 15 minutes of inactivity |
| **Pinecone** | Vector Store | Starter Tier | 1 free serverless index, 2 GB vector storage, us-east-1 AWS |
| **Groq** | LLM Inference | Free Tier | High tokens/sec, subject to RPM and TPM quotas |
| **Tavily** | External Web Search | Free Tier | 1,000 search API calls / month |
| **HuggingFace** | Embeddings | Local Execution | Runs locally inside backend container (~90MB model) |

---

## 2. Step-by-Step Setup Instructions

### Step 1: Obtain Free API Keys

1. **Groq API Key**:
   - Visit [console.groq.com](https://console.groq.com/)
   - Sign up with GitHub / Google
   - Navigate to **API Keys** &rarr; **Create API Key**
   - Save your `gsk_...` key.

2. **Pinecone API Key**:
   - Visit [app.pinecone.io](https://app.pinecone.io/)
   - Sign up on the **Starter Plan**
   - In **API Keys**, copy your `pcsk_...` key.
   - Note: The app automatically detects or creates an index with 384 dimensions and cosine metric.

3. **Tavily API Key**:
   - Visit [app.tavily.com](https://app.tavily.com/)
   - Sign up to receive your free `tvly-...` API key (1,000 monthly queries).

---

### Step 2: Deploy to Render via Blueprint

1. Push this repository to your GitHub account:
   ```bash
   git add .
   git commit -m "feat: complete enterprise agentic rag upgrade"
   git push origin main
   ```

2. Log in to [render.com](https://render.com/).
3. Click **New +** &rarr; **Blueprint**.
4. Connect your GitHub repository.
5. Render will automatically read [`render.yaml`](file:///home/ankitsingh/Desktop/projects/EnterpriseLevelRAG/render.yaml) and configure:
   - **Environment**: Python 3.11
   - **Build Command**: `pip install --no-cache-dir -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/api/health`

6. Under Environment Variables, input your secret keys:
   - `GROQ_API_KEY`: `gsk_...`
   - `PINECONE_API_KEY`: `pcsk_...`
   - `TAVILY_API_KEY`: `tvly-...`
   - `ADMIN_API_KEY`: Choose a secure secret key for document ingestion.

7. Click **Apply**. Render will build and deploy your container.

---

## 3. Pre-Ingest Sample Documents into Pinecone

Because Render Free filesystem storage is ephemeral (resets on deploy), the private enterprise knowledge base vectors reside permanently in **Pinecone**.

To populate your Pinecone index once before going public:
```bash
# Run locally from your machine:
uv run python ingest_sample_kb.py
```
This chunks and vectorizes:
- `data/sample_kb/company_it_handbook.md`
- `data/sample_kb/service_desk_runbook.md`

All vectors are saved permanently in Pinecone namespace `company-kb` and will persist indefinitely without ongoing costs.

---

## 4. Free-Tier Operational Realities & Transparency

When presenting this project to recruiters or engineering teams, transparency about cloud constraints demonstrates senior engineering maturity:

1. **Cold Starts**:
   - Render's free instances spin down after 15 minutes of inactivity.
   - The first request after sleep takes 30-50 seconds to wake the service and load the HuggingFace embedding weights into memory.
   - Subsequent queries execute in under 1.5 seconds.
2. **RAM Constraints (512 MB)**:
   - The embedding model `all-MiniLM-L6-v2` was specifically chosen because its footprint is only ~90 MB, safely leaving ~420 MB for Python, FastAPI, and LangGraph execution.
3. **Ephemeral Local Storage**:
   - The SQLite database (`audit.db`) stores real local logs and ticket history. On Render's free tier, restarting the container resets local disk files.
   - For an enterprise deployment requiring persistent relational tickets across rebuilds, migrate SQLite to a free **Supabase PostgreSQL** instance with zero code changes (SQLAlchemy compatible).
4. **External Rate Limits**:
   - Groq free tier enforces rate limits. The evaluation runner includes `--sample` and `--mock` flags to avoid burning API quotas during automated continuous integration testing.
