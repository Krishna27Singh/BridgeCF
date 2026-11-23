# BridgeCF Evaluation Report

| Metric | Vector-Only | BridgeCF Hybrid |
|---|---:|---:|
| Recall@3 | 0.380 | 1.000 |
| Recall@5 | 0.380 | 1.000 |
| MRR | 0.458 | 0.690 |
| Pedagogical Difficulty Hit Rate | 0.333 | 0.747 |

## Latencies
- Graph BFS p50/p95 ms: 0.000/0.000
- Hybrid retrieval p50/p95 ms: 0.013/0.051

## LLM / Guardrails
- json_schema_pass_rate: 1.000
- anti_spoiler_pass_rate: 1.000
- concept_alignment_rate: 1.000
