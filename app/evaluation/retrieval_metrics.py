"""
Retrieval Evaluation Metrics
────────────────────────────
Implements industry-standard Information Retrieval (IR) metrics:
  - Precision@K
  - Recall@K
  - Mean Reciprocal Rank (MRR)
  - Normalized Discounted Cumulative Gain (NDCG@K)

Formulas
────────
Precision@K:
    Number of relevant documents in top-K retrieved / K

Recall@K:
    Number of relevant documents in top-K retrieved / Total ground-truth relevant documents

Mean Reciprocal Rank (MRR):
    1 / rank of the first relevant document in the retrieved list (0 if none found)

Discounted Cumulative Gain (DCG@K):
    DCG@K = sum_{i=1}^K (2^{rel_i} - 1) / log_2(i + 1)
    NDCG@K = DCG@K / IDCG@K  (where IDCG@K is ideal DCG with perfect sorting)
"""

import math
from typing import Sequence


def precision_at_k(retrieved_docs: Sequence[str], relevant_docs: Sequence[str], k: int = 4) -> float:
    """
    Compute Precision@K.
    retrieved_docs: List of retrieved document filenames or identifiers.
    relevant_docs: List of ground-truth relevant document filenames.
    k: Number of top documents to consider.
    """
    if k <= 0:
        return 0.0
    top_k = list(retrieved_docs)[:k]
    if not top_k:
        return 0.0

    relevant_set = {d.lower() for d in relevant_docs}
    hits = sum(1 for doc in top_k if doc.lower() in relevant_set)
    return hits / k


def recall_at_k(retrieved_docs: Sequence[str], relevant_docs: Sequence[str], k: int = 4) -> float:
    """
    Compute Recall@K.
    """
    if not relevant_docs or k <= 0:
        return 0.0

    top_k = list(retrieved_docs)[:k]
    relevant_set = {d.lower() for d in relevant_docs}
    hits = sum(1 for doc in top_k if doc.lower() in relevant_set)
    return hits / len(relevant_set)


def reciprocal_rank(retrieved_docs: Sequence[str], relevant_docs: Sequence[str]) -> float:
    """
    Compute Reciprocal Rank (RR) for a single query.
    Returns 1 / rank (1-indexed) of the first relevant document, or 0.0 if not found.
    """
    relevant_set = {d.lower() for d in relevant_docs}
    for rank, doc in enumerate(retrieved_docs, start=1):
        if doc.lower() in relevant_set:
            return 1.0 / rank
    return 0.0


def dcg_at_k(retrieved_docs: Sequence[str], relevant_docs: Sequence[str], k: int = 4) -> float:
    """
    Compute Discounted Cumulative Gain at rank K using binary relevance.
    """
    relevant_set = {d.lower() for d in relevant_docs}
    top_k = list(retrieved_docs)[:k]
    dcg = 0.0
    for idx, doc in enumerate(top_k, start=1):
        rel = 1.0 if doc.lower() in relevant_set else 0.0
        dcg += (2.0**rel - 1.0) / math.log2(idx + 1.0)
    return dcg


def ndcg_at_k(retrieved_docs: Sequence[str], relevant_docs: Sequence[str], k: int = 4) -> float:
    """
    Compute Normalized Discounted Cumulative Gain at rank K.
    """
    if not relevant_docs or k <= 0:
        return 0.0

    actual_dcg = dcg_at_k(retrieved_docs, relevant_docs, k=k)

    # Ideal DCG: all relevant documents appear first
    num_relevant = min(len(relevant_docs), k)
    ideal_dcg = 0.0
    for idx in range(1, num_relevant + 1):
        ideal_dcg += (2.0**1.0 - 1.0) / math.log2(idx + 1.0)

    if ideal_dcg == 0.0:
        return 0.0

    return actual_dcg / ideal_dcg


def compute_retrieval_metrics(
    retrieved_docs: Sequence[str],
    relevant_docs: Sequence[str],
    k: int = 4,
) -> dict[str, float]:
    """Compute all standard retrieval metrics for a single query."""
    return {
        f"precision@{k}": round(precision_at_k(retrieved_docs, relevant_docs, k=k), 4),
        f"recall@{k}": round(recall_at_k(retrieved_docs, relevant_docs, k=k), 4),
        "mrr": round(reciprocal_rank(retrieved_docs, relevant_docs), 4),
        f"ndcg@{k}": round(ndcg_at_k(retrieved_docs, relevant_docs, k=k), 4),
    }
