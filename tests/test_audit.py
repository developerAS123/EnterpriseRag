import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.services.audit import (
    init_db,
    write_audit,
    record_document,
    get_document_by_hash,
    list_documents,
)


def test_audit_lifecycle():
    with tempfile.NamedTemporaryFile("w", suffix=".db", delete=False) as tmp_db:
        db_path = tmp_db.name

    with patch("app.services.audit.settings.audit_db_path", db_path):
        init_db()

        # Test writing audit entry
        write_audit("How to reset password?", "private_kb", ["Route -> KB"], latency_ms=85)

        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT question, source_used, latency_ms FROM query_audit")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "How to reset password?"
        assert row[1] == "private_kb"
        assert row[2] == 85
        con.close()

        # Test document registry
        record_document(
            document_id="doc_test123",
            filename="policy.pdf",
            content_hash="abc123hash",
            file_type="pdf",
            chunk_count=5,
        )

        doc = get_document_by_hash("abc123hash")
        assert doc is not None
        assert doc["document_id"] == "doc_test123"
        assert doc["chunk_count"] == 5

        docs = list_documents()
        assert len(docs) == 1
        assert docs[0]["document_id"] == "doc_test123"

    Path(db_path).unlink(missing_ok=True)
