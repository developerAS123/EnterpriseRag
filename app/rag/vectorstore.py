"""
Pinecone vector store + HuggingFace embedding adapter
──────────────────────────────────────────────────────
Embedding model : all-MiniLM-L6-v2  (local, 384-dim, ~90 MB RAM)
Vector DB       : Pinecone Starter
Index name      : from PINECONE_INDEX_NAME (stripped of whitespace)
Namespace       : from PINECONE_NAMESPACE

SAFETY RULE: This module NEVER deletes an existing Pinecone index.
If a dimension mismatch is detected, a RuntimeError is raised with
instructions for the operator. Data is never destroyed automatically.
"""

import logging
import time
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Module-level singletons (lazy initialised) ────────────────────────────────
_embeddings: HuggingFaceEmbeddings | None = None
_vectorstore: PineconeVectorStore | None = None


# ── Embedding model ───────────────────────────────────────────────────────────

def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Return the shared HuggingFaceEmbeddings instance.

    Uses all-MiniLM-L6-v2 (384-dim) loaded locally — no API key required.
    The model is downloaded to ~/.cache/huggingface on first use (~90 MB).
    Subsequent calls return the cached singleton.
    """
    global _embeddings
    if _embeddings is None:
        logger.info(
            "Loading HuggingFace embedding model '%s' (first load may take ~10s)",
            settings.embedding_model,
        )
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("Embedding model loaded successfully.")
    return _embeddings


# ── Pinecone index management ─────────────────────────────────────────────────

def ensure_index():
    """
    Verify that the configured Pinecone index exists and has the correct dimension.

    NEVER deletes the index. If a mismatch is detected, raises RuntimeError
    with explicit operator instructions.

    Returns the Pinecone Index object on success.
    """
    if not settings.pinecone_api_key:
        raise RuntimeError(
            "PINECONE_API_KEY is not configured. "
            "Add PINECONE_API_KEY to your .env file."
        )

    desired_dimension = settings.embedding_dimension
    pc = Pinecone(api_key=settings.pinecone_api_key)
    existing_names = [idx["name"] for idx in pc.list_indexes()]

    if settings.pinecone_index_name in existing_names:
        # Index exists — verify dimension matches before using it
        index_info = pc.describe_index(settings.pinecone_index_name)
        current_dimension = getattr(index_info, "dimension", None)
        if current_dimension is None and isinstance(index_info, dict):
            current_dimension = index_info.get("dimension")

        if current_dimension is not None and current_dimension != desired_dimension:
            raise RuntimeError(
                f"Pinecone index '{settings.pinecone_index_name}' has dimension "
                f"{current_dimension} but the configured embedding model "
                f"'{settings.embedding_model}' produces {desired_dimension}-dim vectors.\n\n"
                "Resolution options:\n"
                "  1. Set PINECONE_INDEX_NAME to a different index name and let the app\n"
                "     create a new one with the correct dimension.\n"
                "  2. Change EMBEDDING_MODEL to one that matches the existing index dimension\n"
                "     and update EMBEDDING_DIMENSION accordingly.\n\n"
                "The existing index has NOT been modified. No data was lost."
            )

        logger.info(
            "Pinecone index '%s' found (dim=%s). Ready.",
            settings.pinecone_index_name,
            current_dimension,
        )
        return pc.Index(settings.pinecone_index_name)

    # Index does not exist — create it
    logger.info(
        "Pinecone index '%s' not found. Creating with dim=%d, metric=cosine.",
        settings.pinecone_index_name,
        desired_dimension,
    )
    pc.create_index(
        name=settings.pinecone_index_name,
        dimension=desired_dimension,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

    # Wait for index to become ready
    max_wait = 60  # seconds
    waited = 0
    while waited < max_wait:
        status = pc.describe_index(settings.pinecone_index_name).status
        if status.get("ready"):
            break
        time.sleep(2)
        waited += 2

    logger.info("Pinecone index '%s' is ready.", settings.pinecone_index_name)
    return pc.Index(settings.pinecone_index_name)


# ── Vector store ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_vectorstore_cached() -> PineconeVectorStore:
    """
    Build and cache the PineconeVectorStore singleton.
    Uses lru_cache so it is constructed exactly once per process.
    """
    index = ensure_index()
    return PineconeVectorStore(
        index=index,
        embedding=get_embeddings(),
        namespace=settings.pinecone_namespace,
    )


def get_vectorstore() -> PineconeVectorStore:
    return _get_vectorstore_cached()


def get_retriever():
    """Return a LangChain retriever backed by the Pinecone vector store."""
    return get_vectorstore().as_retriever(
        search_kwargs={"k": settings.top_k}
    )


def add_documents(chunks: list) -> list[str]:
    """
    Embed and upsert document chunks into Pinecone.
    Returns a list of vector IDs created.
    """
    store = get_vectorstore()
    ids = store.add_documents(chunks)
    logger.info("Upserted %d chunks into Pinecone namespace '%s'.", len(ids), settings.pinecone_namespace)
    return ids
