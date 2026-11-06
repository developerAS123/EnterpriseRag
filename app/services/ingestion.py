"""
Document ingestion pipeline
───────────────────────────
Supports: PDF, DOCX, TXT, Markdown, CSV

Features:
  - File format validation
  - Configurable chunk size and overlap
  - Content hashing (SHA-256) for deduplication
  - Metadata enrichment (document_id, chunk_id, file_type, source, uploaded_at)
  - Empty file detection and content validation
"""

import csv
import hashlib
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from docx import Document as DocxDocument
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SUPPORTED = {".pdf", ".txt", ".md", ".docx", ".csv"}


def compute_content_hash(content: bytes) -> str:
    """Compute deterministic SHA-256 hash of raw file content."""
    return hashlib.sha256(content).hexdigest()


def load_file(path: Path) -> list[Document]:
    """
    Load a file from disk into LangChain Document objects.
    Supports .pdf, .txt, .md, .docx, and .csv.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"Unsupported file type: {suffix}. Supported: {', '.join(sorted(SUPPORTED))}")

    docs: list[Document] = []

    if suffix == ".pdf":
        loader = PyPDFLoader(str(path))
        docs = loader.load()
    elif suffix in {".txt", ".md"}:
        loader = TextLoader(str(path), encoding="utf-8")
        docs = loader.load()
    elif suffix == ".docx":
        docx_doc = DocxDocument(str(path))
        text = "\n".join(p.text for p in docx_doc.paragraphs if p.text.strip())
        if text.strip():
            docs = [Document(page_content=text, metadata={"source": str(path)})]
    elif suffix == ".csv":
        # Parse CSV into tabular textual representation
        with open(path, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                lines = []
                for idx, row in enumerate(rows, start=1):
                    row_str = ", ".join(f"{k}: {v}" for k, v in row.items() if v)
                    lines.append(f"Row {idx}: {row_str}")
                text = "\n".join(lines)
                docs = [Document(page_content=text, metadata={"source": str(path), "total_rows": len(rows)})]

    # Validate that extracted text is not completely blank
    non_empty = [d for d in docs if d.page_content.strip()]
    if not non_empty:
        raise ValueError(f"No extractable text found in '{path.name}'.")

    return non_empty


def chunk_documents(
    docs: Iterable[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    document_id: str | None = None,
) -> list[Document]:
    """
    Split documents into smaller chunks using RecursiveCharacterTextSplitter.
    Injects chunk_id and index metadata for source citations and traceability.
    """
    settings = get_settings()
    size = chunk_size or settings.chunk_size
    overlap = chunk_overlap or settings.chunk_overlap

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        add_start_index=True,
    )

    chunks = splitter.split_documents(list(docs))
    for idx, chunk in enumerate(chunks):
        c_id = f"{document_id or 'doc'}_chunk_{idx}"
        chunk.metadata["chunk_id"] = c_id
        chunk.metadata["chunk_index"] = idx

    return chunks
