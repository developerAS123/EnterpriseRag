"""
Conversation Memory & Session Management
────────────────────────────────────────
Provides session-isolated conversational memory stored in SQLite.

Features:
  - Isolated history per session_id
  - Automatic history windowing (last N turns)
  - Clear conversation endpoint
  - Clean formatted prompt context for the LLM
"""

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_HISTORY_TURNS = 6  # Last 3 user + 3 assistant messages


def init_memory_table() -> None:
    """Create conversations table if not exists."""
    con = sqlite3.connect(settings.audit_db_path)
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )"""
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id)"
        )
        con.commit()
    finally:
        con.close()


def add_message(session_id: str, role: str, content: str) -> None:
    """Append a message to the session's conversation history."""
    init_memory_table()
    now = datetime.now(timezone.utc).isoformat()
    con = sqlite3.connect(settings.audit_db_path)
    try:
        con.execute(
            """INSERT INTO conversations (session_id, role, content, created_at)
               VALUES (?, ?, ?, ?)""",
            (session_id, role, content, now),
        )
        con.commit()
    finally:
        con.close()


def get_conversation_history(session_id: str, limit: int = DEFAULT_HISTORY_TURNS) -> list[dict[str, str]]:
    """Retrieve the recent message history for a session."""
    init_memory_table()
    con = sqlite3.connect(settings.audit_db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(
            """SELECT role, content, created_at FROM conversations
               WHERE session_id = ?
               ORDER BY id DESC LIMIT ?""",
            (session_id, limit),
        )
        rows = cur.fetchall()
        # Return in chronological order
        return [{"role": r["role"], "content": r["content"], "created_at": r["created_at"]} for r in reversed(rows)]
    finally:
        con.close()


def format_history_for_prompt(session_id: str, limit: int = DEFAULT_HISTORY_TURNS) -> str:
    """Format past conversation turns into a string context block for the prompt."""
    history = get_conversation_history(session_id, limit=limit)
    if not history:
        return ""
    lines = ["Previous conversation context:"]
    for msg in history:
        prefix = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{prefix}: {msg['content']}")
    return "\n".join(lines)


def clear_conversation(session_id: str) -> int:
    """Clear all stored messages for a specific session."""
    init_memory_table()
    con = sqlite3.connect(settings.audit_db_path)
    try:
        cur = con.cursor()
        cur.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        deleted = cur.rowcount
        con.commit()
        logger.info("Cleared %d messages for session %s.", deleted, session_id)
        return deleted
    finally:
        con.close()
