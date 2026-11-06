import pytest
from fastapi.testclient import TestClient

from app.evaluation.retrieval_metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    ndcg_at_k,
    compute_retrieval_metrics,
)
from app.evaluation.generation_metrics import (
    compute_citation_correctness,
    compute_correct_refusal,
    compute_deterministic_faithfulness,
    compute_fact_coverage,
)
from app.main import app

client = TestClient(app)


def test_retrieval_metrics_calculation():
    retrieved = ["doc_a.md", "doc_b.md", "doc_c.md", "doc_d.md"]
    relevant = ["doc_b.md", "doc_e.md"]

    # Precision@2: doc_a is not relevant, doc_b is -> 1/2 = 0.5
    assert precision_at_k(retrieved, relevant, k=2) == 0.5

    # Recall@4: doc_b is in top 4 -> 1/2 = 0.5
    assert recall_at_k(retrieved, relevant, k=4) == 0.5

    # Reciprocal Rank: doc_b is at position 2 -> 1/2 = 0.5
    assert reciprocal_rank(retrieved, relevant) == 0.5

    # NDCG@4 is between 0 and 1
    ndcg = ndcg_at_k(retrieved, relevant, k=4)
    assert 0.0 < ndcg <= 1.0

    all_metrics = compute_retrieval_metrics(retrieved, relevant, k=4)
    assert "precision@4" in all_metrics
    assert "recall@4" in all_metrics
    assert "mrr" in all_metrics
    assert "ndcg@4" in all_metrics


def test_fact_coverage():
    answer = "To connect to the corporate VPN, open NovaSecure client and complete MFA challenge."
    expected = ["novasecure", "mfa", "vpn"]
    assert compute_fact_coverage(answer, expected) == 1.0

    partial = ["novasecure", "hardware key", "sms recovery"]
    assert compute_fact_coverage(answer, partial) == pytest.approx(1 / 3, 0.01)


def test_citation_correctness():
    citations = [
        {"title": "company_it_handbook.md", "url": "", "type": "private_kb"},
        {"title": "Vendor Health", "url": "https://status.vendor.com", "type": "web"},
    ]
    valid_sources = ["company_it_handbook.md", "service_desk_runbook.md"]
    assert compute_citation_correctness(citations, valid_sources) == 1.0


def test_correct_refusal():
    refusal_answer = "I couldn't find enough reliable evidence in the company knowledge base to answer."
    assert compute_correct_refusal(refusal_answer, is_out_of_scope=True)
    assert not compute_correct_refusal(refusal_answer, is_out_of_scope=False)

    direct_answer = "To reset your password, visit https://identity.company.internal."
    assert compute_correct_refusal(direct_answer, is_out_of_scope=False)
    assert not compute_correct_refusal(direct_answer, is_out_of_scope=True)


def test_deterministic_faithfulness():
    context = ["NovaSecure VPN client must be installed from internal Software Portal."]
    grounded_ans = "Employees must install the NovaSecure VPN client from the internal Software Portal."
    hallucinated_ans = "You should install Cisco AnyConnect and configure port forwarding on router."

    assert compute_deterministic_faithfulness(grounded_ans, context) == 1.0
    assert compute_deterministic_faithfulness(hallucinated_ans, context) < 0.5


def test_metrics_api_endpoint():
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "telemetry" in data
    assert "total_requests" in data["telemetry"]
    assert "latency_summary_ms" in data["telemetry"]
    assert "p50" in data["telemetry"]["latency_summary_ms"]
    assert "p95" in data["telemetry"]["latency_summary_ms"]
    assert "p99" in data["telemetry"]["latency_summary_ms"]
    assert "benchmark_evaluation" in data
