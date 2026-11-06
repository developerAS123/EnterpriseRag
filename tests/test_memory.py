import tempfile
from pathlib import Path
from unittest.mock import patch

from app.services.memory import (
    add_message,
    get_conversation_history,
    format_history_for_prompt,
    clear_conversation,
)


def test_session_isolation_and_memory():
    with tempfile.NamedTemporaryFile("w", suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    with patch("app.services.memory.settings.audit_db_path", db_path):
        session_a = "user_session_alpha"
        session_b = "user_session_beta"

        # Add messages to session A
        add_message(session_a, "user", "How do I reset password?")
        add_message(session_a, "assistant", "Use the self-service portal.")

        # Add messages to session B
        add_message(session_b, "user", "VPN is not working.")

        # Verify session A has 2 messages
        hist_a = get_conversation_history(session_a)
        assert len(hist_a) == 2
        assert hist_a[0]["content"] == "How do I reset password?"
        assert hist_a[1]["content"] == "Use the self-service portal."

        # Verify session B has only 1 message (strict session isolation)
        hist_b = get_conversation_history(session_b)
        assert len(hist_b) == 1
        assert hist_b[0]["content"] == "VPN is not working."

        # Verify prompt formatted context
        formatted = format_history_for_prompt(session_a)
        assert "Previous conversation context:" in formatted
        assert "User: How do I reset password?" in formatted
        assert "Assistant: Use the self-service portal." in formatted

        # Clear session A
        deleted = clear_conversation(session_a)
        assert deleted == 2
        assert len(get_conversation_history(session_a)) == 0

        # Session B is unaffected
        assert len(get_conversation_history(session_b)) == 1

    Path(db_path).unlink(missing_ok=True)
