# BridgeCF Evaluation Report

| Metric | Vector-Only | BridgeCF Hybrid |
|---|---:|---:|
| Recall@3 | 0.880 | 0.980 |
| Recall@5 | 0.960 | 0.980 |
| MRR | 0.826 | 0.980 |
| Pedagogical Difficulty Hit Rate | 1.000 | 1.000 |

## Live LLM Configuration
- Provider: `openai_compat`
- LLM sample: `15`

## Latencies
- Graph BFS p50/p95 ms: 1.0331ms/6.2973ms
- Hybrid retrieval p50/p95 ms: 35.5187ms/70.3442ms
- Codeforces network fetch ms: 1901.9210ms

## LLM / Guardrails
- json_schema_pass_rate: 1.000
- anti_spoiler_pass_rate: 1.000
- concept_alignment_rate: 1.000
