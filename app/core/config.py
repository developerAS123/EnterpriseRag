from functools import lru_cache
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Enterprise IT Support Agentic RAG Copilot"
    app_env: str = "development"

    # ── LLM — Groq ───────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"

    # ── Web search ───────────────────────────────────────────────────────────
    tavily_api_key: str = ""

    # ── Vector database — Pinecone ───────────────────────────────────────────
    pinecone_api_key: str = ""
    pinecone_index_name: str = "industry-agentic-rag-kb"
    pinecone_namespace: str = "company-kb"

    # ── Embeddings ───────────────────────────────────────────────────────────
    # all-minilm-l6-v2 → 384 dimensions (local HuggingFace model, no API key)
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # ── Retrieval ────────────────────────────────────────────────────────────
    top_k: int = 4
    max_retries: int = 1
    retrieval_score_threshold: float = 0.0  # 0.0 = no threshold (all results)

    # ── Ingestion ────────────────────────────────────────────────────────────
    chunk_size: int = 900
    chunk_overlap: int = 120
    max_upload_mb: int = 20

    # ── Security ─────────────────────────────────────────────────────────────
    admin_api_key: str = "change-me"

    # ── Storage ──────────────────────────────────────────────────────────────
    audit_db_path: str = str(BASE_DIR / "data" / "audit.db")
    upload_dir: str = str(BASE_DIR / "uploads")
    sample_kb_dir: str = str(BASE_DIR / "data" / "sample_kb")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        extra="ignore",
    )

    # ── Validators ───────────────────────────────────────────────────────────
    @field_validator("pinecone_index_name", "pinecone_namespace", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Remove accidental leading/trailing spaces from index name and namespace."""
        return v.strip() if isinstance(v, str) else v


@lru_cache
def get_settings() -> Settings:
    return Settings()
