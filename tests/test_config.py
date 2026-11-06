import pytest
from app.core.config import Settings, get_settings


def test_settings_load():
    settings = get_settings()
    assert settings.app_name == "Enterprise IT Support Agentic RAG Copilot"
    assert settings.groq_model == "openai/gpt-oss-20b"
    assert settings.embedding_model.lower() == "all-minilm-l6-v2"
    assert settings.embedding_dimension == 384
    assert settings.top_k == 4
    assert settings.max_retries == 1
    assert settings.max_upload_mb == 20


def test_strip_whitespace_validator():
    # Trailing spaces should be automatically stripped by the validator
    test_settings = Settings(
        pinecone_index_name="  industry-agentic-rag-kb  ",
        pinecone_namespace="  company-kb  ",
    )
    assert test_settings.pinecone_index_name == "industry-agentic-rag-kb"
    assert test_settings.pinecone_namespace == "company-kb"
