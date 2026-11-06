"""
SQLite audit log and metadata registry.

Schemas
-------
  1. query_audit(id, created_at, question, source_used, trace_json, latency_ms)
  2. documents(document_id, filename, content_hash, file_type, chunk_count, uploaded_at, status)
"""

import json
import logging
import math
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def init_db() -> None:
    """Create or migrate the audit database and tables."""
    con = sqlite3.connect(settings.audit_db_path)
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS query_audit (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT    NOT NULL,
                question    TEXT    NOT NULL,
                source_used TEXT    NOT NULL,
                trace_json  TEXT    NOT NULL,
                latency_ms  INTEGER NOT NULL DEFAULT 0
            )"""
        )

        cur = con.cursor()
        cur.execute("PRAGMA table_info(query_audit)")
        columns = [row[1] for row in cur.fetchall()]
        if "latency_ms" not in columns:
            con.execute("ALTER TABLE query_audit ADD COLUMN latency_ms INTEGER NOT NULL DEFAULT 0")
            logger.info("Migrated query_audit: added latency_ms column.")

        con.execute(
            """CREATE TABLE IF NOT EXISTS documents (
                document_id  TEXT PRIMARY KEY,
                filename     TEXT NOT NULL,
                content_hash TEXT UNIQUE NOT NULL,
                file_type    TEXT NOT NULL,
                chunk_count  INTEGER NOT NULL,
                uploaded_at  TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'indexed'
            )"""
        )
        con.commit()
        logger.info("Audit & Document Registry DB initialised at '%s'.", settings.audit_db_path)
    finally:
        con.close()


def write_audit(
    question: str,
    source_used: str,
    trace: list[str],
    latency_ms: int = 0,
) -> None:
    """Append a query record to the audit log."""
    con = sqlite3.connect(settings.audit_db_path)
    try:
        con.execute(
            """INSERT INTO query_audit
               (created_at, question, source_used, trace_json, latency_ms)
               VALUES (?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                question,
                source_used,
                json.dumps(trace),
                latency_ms,
            ),
        )
        con.commit()
    except Exception:
        logger.exception("Failed to write audit record.")
    finally:
        con.close()


def get_document_by_hash(content_hash: str) -> dict[str, Any] | None:
    """Check if a document with this content hash has already been ingested."""
    con = sqlite3.connect(settings.audit_db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM documents WHERE content_hash = ?", (content_hash,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def record_document(
    document_id: str,
    filename: str,
    content_hash: str,
    file_type: str,
    chunk_count: int,
) -> None:
    """Record an indexed document in the registry."""
    con = sqlite3.connect(settings.audit_db_path)
    try:
        con.execute(
            """INSERT OR REPLACE INTO documents
               (document_id, filename, content_hash, file_type, chunk_count, uploaded_at, status)
               VALUES (?, ?, ?, ?, ?, ?, 'indexed')""",
            (
                document_id,
                filename,
                content_hash,
                file_type,
                chunk_count,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        con.commit()
    finally:
        con.close()


def list_documents() -> list[dict[str, Any]]:
    """List all registered documents."""
    con = sqlite3.connect(settings.audit_db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM documents ORDER BY uploaded_at DESC")
        return [dict(row) for row in cur.fetchall()]
    finally:
        con.close()


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(s[int(k)], 1)
    return round(s[int(f)] * (c - k) + s[int(c)] * (k - f), 1)


def get_observability_metrics() -> dict[str, Any]:
    """
    Calculate live observability metrics directly from real audit database entries
    and merge latest evaluation benchmark scores if available.
    """
    con = sqlite3.connect(settings.audit_db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute("SELECT source_used, latency_ms FROM query_audit")
        rows = cur.fetchall()

        total_requests = len(rows)
        routing_distribution: dict[str, int] = {}
        latencies: list[float] = []

        for r in rows:
            src = r["source_used"]
            routing_distribution[src] = routing_distribution.get(src, 0) + 1
            lat = r["latency_ms"]
            if lat > 0:
                latencies.append(float(lat))

        avg_latency = round(statistics.mean(latencies), 1) if latencies else 0.0
        p50 = _percentile(latencies, 50)
        p95 = _percentile(latencies, 95)
        p99 = _percentile(latencies, 99)

        # Count total documents and chunks
        cur.execute("SELECT COUNT(*), COALESCE(SUM(chunk_count), 0) FROM documents")
        doc_count, chunk_count = cur.fetchone()

        # Load latest offline evaluation run if exists
        reports_path = Path(settings.audit_db_path).resolve().parents[1] / "data" / "reports" / "eval_report_latest.json"
        evaluation_data: dict[str, Any] = {"status": "Not yet evaluated"}
        if reports_path.exists():
            try:
                eval_payload = json.loads(reports_path.read_text(encoding="utf-8"))
                evaluation_data = eval_payload.get("summary", {})
                evaluation_data["status"] = "Evaluated"
            except Exception:
                pass

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "telemetry": {
                "total_requests": total_requests,
                "routing_distribution": routing_distribution,
                "latency_summary_ms": {
                    "avg": avg_latency,
                    "p50": p50,
                    "p95": p95,
                    "p99": p99,
                    "min": min(latencies) if latencies else 0,
                    "max": max(latencies) if latencies else 0,
                },
                "knowledge_base": {
                    "indexed_documents": doc_count,
                    "indexed_chunks": chunk_count,
                },
            },
            "benchmark_evaluation": evaluation_data,
        }
    finally:
        con.close()
