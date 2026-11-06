# Evaluation & Benchmark Methodology

This document details the evaluation framework, metrics formulas, and reproducible benchmark runner built into the **Enterprise IT Support Agentic RAG Copilot**.

All metrics displayed in the application dashboard and reports come from **real deterministic calculations and recorded request runs** — never fabricated or randomized values.

---

## 1. The 100-Question Enterprise Benchmark Dataset

Located at [`data/evaluation_dataset.json`](file:///home/ankitsingh/Desktop/projects/EnterpriseLevelRAG/data/evaluation_dataset.json), the benchmark contains 100 curated enterprise IT support test cases spanning 10 distinct operational categories:

1. **VPN Access & Gateway Troubleshooting** (10 questions)
2. **Password Policy & Self-Service Resets** (10 questions)
3. **Multi-Factor Authentication (MFA) & Tokens** (10 questions)
4. **Corporate Email & Outlook Synchronization** (10 questions)
5. **Network Connectivity & Office Wi-Fi** (10 questions)
6. **Laptop Performance & Kernel Crash Diagnostics** (10 questions)
7. **Approved Software & Admin Privilege Requests** (10 questions)
8. **Security Incident Policies & Stolen Devices** (10 questions)
9. **Support Ticket Creation & Incident Escalation** (10 questions)
10. **Vendor Outages & Web Search Fallbacks** (10 questions)

Each test case contains:
```json
{
  "id": 1,
  "category": "VPN Access & Troubleshooting",
  "question": "How do I connect to the company VPN from home?",
  "expected_route": "kb",
  "expected_sources": ["company_it_handbook.md"],
  "expected_facts": ["novasecure", "software portal", "gateway", "mfa"],
  "is_out_of_scope": false
}
```

---

## 2. Retrieval Metrics & Formulas

Retrieval quality is measured against ground-truth document labels:

### Precision@K
Measures what proportion of the top-$K$ retrieved documents are relevant:
$$\text{Precision@}K = \frac{|\text{Retrieved}_K \cap \text{Relevant}|}{K}$$

### Recall@K
Measures what fraction of the total relevant documents were successfully retrieved in the top-$K$:
$$\text{Recall@}K = \frac{|\text{Retrieved}_K \cap \text{Relevant}|}{|\text{Relevant}|}$$

### Mean Reciprocal Rank (MRR)
Evaluates where the first relevant document appears in the ranked results:
$$\text{RR} = \frac{1}{\text{rank}_1}, \quad \text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \text{RR}_i$$
An MRR of $1.0$ indicates that the most relevant document was retrieved at rank 1 on every query.

### Normalized Discounted Cumulative Gain (NDCG@K)
Evaluates ranking quality, heavily penalizing relevant documents that appear low in the list:
$$\text{DCG@}K = \sum_{i=1}^K \frac{2^{\text{rel}_i} - 1}{\log_2(i + 1)}, \quad \text{NDCG@}K = \frac{\text{DCG@}K}{\text{IDCG@}K}$$
Where $\text{IDCG@}K$ is the Ideal DCG score obtained if all relevant documents were ordered perfectly at the top.

---

## 3. Answer Generation & Grounding Metrics

### Technical Fact Coverage
Measures what percentage of expected factual terms, commands, or policy names appear in the final response:
$$\text{FactCoverage} = \frac{|\{f \in \text{ExpectedFacts} \mid f \in \text{Answer}\}|}{|\text{ExpectedFacts}|}$$

### Sentence-Level Lexical Faithfulness
Evaluates whether generated sentences have informative lexical support in the retrieved context:
$$\text{Faithfulness} = \frac{\text{Number of Grounded Sentences}}{\text{Total Answer Sentences}}$$
A sentence is classified as supported if $\ge 40\%$ of its non-stopword tokens appear directly within the retrieved context chunks.

### Correct Refusal Rate
Verifies that when evidence is absent (out-of-scope or unanswerable queries), the agent returns an explicit refusal rather than inventing false answers.

---

## 4. How to Run the Benchmark

The evaluation runner supports both **live model inference** and **offline mock mode** (for continuous integration without consuming API quotas).

### Live Evaluation (using Pinecone & Groq):
```bash
# Evaluate entire 100-question benchmark
uv run python scripts/run_evaluation.py

# Evaluate a quick sample (e.g., 5 questions)
uv run python scripts/run_evaluation.py --sample 5
```

### Mock Evaluation (0 API keys required, ideal for GitHub Actions):
```bash
uv run python scripts/run_evaluation.py --mock --sample 15
```

---

## 5. Generated Artifacts

Every evaluation run automatically generates:
1. `data/reports/eval_report_latest.json`: Raw metrics and individual test results.
2. `data/reports/eval_report_latest.html`: Visual HTML report with metric scorecards and execution breakdown table.
3. Baseline comparison: Automatically detects previous reports and logs $\Delta$ improvements or regressions.
