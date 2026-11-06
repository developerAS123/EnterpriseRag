import tempfile
from pathlib import Path
import pytest
from app.services.ingestion import (
    load_file,
    chunk_documents,
    compute_content_hash,
    SUPPORTED,
)


def test_supported_extensions():
    assert ".pdf" in SUPPORTED
    assert ".docx" in SUPPORTED
    assert ".txt" in SUPPORTED
    assert ".md" in SUPPORTED
    assert ".csv" in SUPPORTED


def test_compute_content_hash():
    data1 = b"Hello Enterprise RAG"
    data2 = b"Hello Enterprise RAG"
    data3 = b"Different content"
    assert compute_content_hash(data1) == compute_content_hash(data2)
    assert compute_content_hash(data1) != compute_content_hash(data3)


def test_load_and_chunk_markdown():
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write("# Company Policy\n\nAll employees must use VPN when accessing internal services.\n")
        f_path = Path(f.name)

    try:
        docs = load_file(f_path)
        assert len(docs) > 0
        assert "Company Policy" in docs[0].page_content

        chunks = chunk_documents(docs, chunk_size=50, chunk_overlap=10, document_id="doc_test1")
        assert len(chunks) > 0
        assert chunks[0].metadata["chunk_id"].startswith("doc_test1_chunk_")
        assert chunks[0].metadata["chunk_index"] == 0
    finally:
        f_path.unlink(missing_ok=True)


def test_load_and_chunk_csv():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write("Service,Port,Status\nVPN,443,Active\nSSH,22,Restricted\n")
        f_path = Path(f.name)

    try:
        docs = load_file(f_path)
        assert len(docs) == 1
        assert "Service: VPN" in docs[0].page_content
        assert "Port: 443" in docs[0].page_content
    finally:
        f_path.unlink(missing_ok=True)


def test_unsupported_file_type():
    with tempfile.NamedTemporaryFile("w", suffix=".exe", delete=False) as f:
        f.write("binary stuff")
        f_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="Unsupported file type"):
            load_file(f_path)
    finally:
        f_path.unlink(missing_ok=True)


def test_empty_file_rejected():
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("   \n   \n")
        f_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="No extractable text"):
            load_file(f_path)
    finally:
        f_path.unlink(missing_ok=True)
