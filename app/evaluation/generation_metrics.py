"""
Answer Quality & Grounding Evaluation Metrics
─────────────────────────────────────────────
Implements both deterministic and optional LLM-assisted evaluation metrics:
  1. Faithfulness (context overlap ratio & hallucination indicators)
  2. Answer Relevance / Fact Coverage
  3. Citation Correctness
  4. Correct Refusal Evaluation (for questions outside KB evidence)
"""

import re
from typing import Sequence


def compute_citation_correctness(citations: list[dict], valid_sources: Sequence[str]) -> float:
    """
    Evaluate citation correctness.
    Returns 1.0 if all citations match known valid sources or valid URLs, 0.0 if empty when required,
    or ratio of valid to total citations.
    """
    if not citations:
        return 0.0

    valid_set = {s.lower() for s in valid_sources}
    correct = 0
    for cite in citations:
        title = cite.get("title", "").lower()
        url = cite.get("url", "")
        # Private KB matches source name
        if any(valid in title for valid in valid_set) or (url and url.startswith("http")):
            correct += 1

    return round(correct / len(citations), 4)


def compute_fact_coverage(answer: str, expected_facts: Sequence[str]) -> float:
    """
    Deterministic check: measures what fraction of expected ground-truth facts
    or technical terms are captured in the generated answer.
    """
    if not expected_facts:
        return 1.0

    ans_lower = answer.lower()
    matches = sum(1 for fact in expected_facts if fact.lower() in ans_lower)
    return round(matches / len(expected_facts), 4)


def compute_correct_refusal(answer: str, is_out_of_scope: bool) -> bool:
    """
    Verify whether the agent appropriately refused to answer when evidence was absent.
    Refusal triggers: phrases indicating insufficient knowledge base evidence.
    """
    refusal_markers = [
        "couldn't find enough reliable evidence",
        "insufficient evidence",
        "does not contain sufficient information",
        "please contact the it help desk",
        "cannot answer confidently",
        "not found in the company knowledge base",
    ]
    ans_lower = answer.lower()
    has_refusal = any(marker in ans_lower for marker in refusal_markers)

    if is_out_of_scope:
        return has_refusal
    return not has_refusal


def compute_deterministic_faithfulness(answer: str, context_chunks: Sequence[str]) -> float:
    """
    Compute sentence-level token overlap between generated answer and context.
    Penalizes hallucinated assertions that have zero lexical support in retrieved chunks.
    """
    if not context_chunks:
        return 0.0

    # Tokenize context
    context_tokens = set(re.findall(r"\w+", " ".join(context_chunks).lower()))
    if not context_tokens:
        return 0.0

    # Split answer into sentences
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", answer) if len(s.strip()) > 15]
    if not sentences:
        return 1.0

    supported_sentences = 0
    for sentence in sentences:
        words = set(re.findall(r"\w+", sentence.lower()))
        # Filter common stopwords
        informative = {w for w in words if len(w) > 3}
        if not informative:
            supported_sentences += 1
            continue

        overlap = len(informative.intersection(context_tokens)) / len(informative)
        # Sentence is considered supported if >= 40% of informative tokens appear in context
        if overlap >= 0.40:
            supported_sentences += 1

    return round(supported_sentences / len(sentences), 4)
