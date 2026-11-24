# BridgeCF Evaluation Report

| Metric | Vector-Only | BridgeCF Hybrid |
|---|---:|---:|
| Recall@3 | 0.380 | 1.000 |
| Recall@5 | 0.380 | 1.000 |
| MRR | 0.458 | 0.690 |
| Pedagogical Difficulty Hit Rate | 0.333 | 0.747 |

## Live LLM Configuration
- Provider: `offline`
- LLM sample: `all 50`

## Latencies
- Graph BFS p50/p95 ms: 0.083us/0.291us
- Hybrid retrieval p50/p95 ms: 0.0131ms/0.0223ms

## LLM / Guardrails
- json_schema_pass_rate: 1.000
- anti_spoiler_pass_rate: 1.000
- concept_alignment_rate: 1.000
