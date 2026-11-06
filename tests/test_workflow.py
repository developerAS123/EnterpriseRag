from unittest.mock import MagicMock, patch
import pytest
from app.rag.state import AgentState, RouteDecision, EvidenceGrade
from app.rag.workflow import (
    route_question,
    route_after_router,
    after_kb,
    after_web,
    direct_answer,
    insufficient,
)


def test_route_after_router():
    state_kb: AgentState = {"source_used": "kb"}
    assert route_after_router(state_kb) == "retrieve_kb"

    state_direct: AgentState = {"source_used": "direct"}
    assert route_after_router(state_direct) == "direct_answer"


def test_after_kb_routing():
    state_good: AgentState = {"kb_grade": "good"}
    assert after_kb(state_good) == "generate_from_kb"

    state_weak: AgentState = {"kb_grade": "weak"}
    assert after_kb(state_weak) == "search_web"


def test_after_web_routing():
    state_good: AgentState = {"web_grade": "good", "retry_count": 0}
    assert after_web(state_good) == "generate_from_web"

    state_retry: AgentState = {"web_grade": "weak", "retry_count": 0}
    assert after_web(state_retry) == "rewrite_query"

    state_insufficient: AgentState = {"web_grade": "weak", "retry_count": 1}
    assert after_web(state_insufficient) == "insufficient"


def test_insufficient_evidence_response():
    state: AgentState = {"trace": []}
    res = insufficient(state)
    assert res["source_used"] == "insufficient_evidence"
    assert "couldn't find enough reliable evidence" in res["answer"]
    assert any("Stopped" in t for t in res["trace"])


def test_direct_answer_mocked():
    state: AgentState = {"question": "Hello there!", "trace": []}
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Hello! How can I help you today?")

    with patch("app.rag.workflow.llm", return_value=mock_llm):
        res = direct_answer(state)
        assert res["source_used"] == "direct"
        assert res["answer"] == "Hello! How can I help you today?"
