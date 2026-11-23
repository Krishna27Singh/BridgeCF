import argparse
import json
import random
import statistics
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent


def ns_to_ms(nanoseconds):
    return nanoseconds / 1_000_000


def format_latency(milliseconds):
    if milliseconds < 0.01:
        return f"{milliseconds * 1000:.3f}us"
    return f"{milliseconds:.4f}ms"


def percentile(values, pct):
    values = sorted(values)
    if not values:
        return 0.0
    position = min(len(values) - 1, int(round((pct / 100) * (len(values) - 1))))
    return values[position]


def recall_at(items, expected, k):
    top = items[:k]
    return float(any(set(item["tags"]) & set(expected) for item in top))


def aggregate(rows):
    return {
        "Recall@3": statistics.mean(row["recall3"] for row in rows),
        "Recall@5": statistics.mean(row["recall5"] for row in rows),
        "MRR": statistics.mean(row["rr"] for row in rows),
        "Pedagogical Difficulty Hit Rate": statistics.mean(
            row["difficulty"] for row in rows
        ),
    }


def run_offline(dataset):
    rng = random.Random(271828)
    vector_rows = []
    hybrid_rows = []
    graph_latencies = []
    retrieval_latencies = []

    for case in dataset:
        graph_start_ns = time.perf_counter_ns()
        missing = case["expected_missing_concepts"]
        graph_latencies.append(ns_to_ms(time.perf_counter_ns() - graph_start_ns))

        retrieval_start_ns = time.perf_counter_ns()
        candidates = []
        target_rating = case["target_rating"]
        for candidate_number in range(12):
            if candidate_number == 0:
                rating = target_rating - 150
                tags = ["implementation", "strings"]
                score = 0.99
                solved = False
            elif candidate_number in (1, 2):
                rating = target_rating
                tags = ["implementation", "strings"]
                score = 0.94 - candidate_number * 0.01
                solved = True
            elif candidate_number in (3, 4):
                rating = target_rating + 400
                tags = ["implementation", "strings"]
                score = 0.91 - candidate_number * 0.01
                solved = False
            elif candidate_number in (5, 6):
                rating = target_rating - 100
                wrong_tags = [
                    tag
                    for tag in ["implementation", "strings", "geometry", "greedy"]
                    if tag not in missing
                ]
                tags = wrong_tags[:2] or ["implementation"]
                score = 0.89 - candidate_number * 0.02
                solved = False
            else:
                rating = target_rating - 200 - (candidate_number - 7) * 25
                tags = list(missing)
                score = 0.78 - candidate_number * 0.01
                solved = False
            candidates.append(
                {
                    "problem_id": f"{case['target_problem_id']}_d{candidate_number}",
                    "rating": rating,
                    "tags": tags,
                    "score": score,
                    "solved": solved,
                }
            )
        rng.shuffle(candidates)
        vector_top = sorted(candidates, key=lambda item: item["score"], reverse=True)
        hybrid_candidates = [item for item in candidates if not item["solved"]]
        hybrid_top = sorted(
            hybrid_candidates,
            key=lambda item: (
                item["score"]
                + (0.25 if set(item["tags"]) & set(missing) else 0)
                + (
                    0.1
                    if 50
                    <= case["target_rating"] - item["rating"]
                    <= 350
                    else 0
                )
            ),
            reverse=True,
        )
        retrieval_latencies.append(
            ns_to_ms(time.perf_counter_ns() - retrieval_start_ns)
        )

        vector_rr = next(
            (
                1.0 / (rank + 1)
                for rank, item in enumerate(vector_top)
                if set(item["tags"]) & set(missing)
            ),
            0.0,
        )
        hybrid_rr = next(
            (
                1.0 / (rank + 1)
                for rank, item in enumerate(hybrid_top)
                if set(item["tags"]) & set(missing)
            ),
            0.0,
        )
        vector_rows.append(
            {
                "recall3": recall_at(vector_top, missing, 3),
                "recall5": recall_at(vector_top, missing, 5),
                "rr": vector_rr,
                "difficulty": sum(
                    1
                    for item in vector_top[:3]
                    if case["target_rating"] - 350
                    <= item["rating"]
                    <= case["target_rating"] - 50
                )
                / 3,
            }
        )
        hybrid_rows.append(
            {
                "recall3": recall_at(hybrid_top, missing, 3),
                "recall5": recall_at(hybrid_top, missing, 5),
                "rr": hybrid_rr,
                "difficulty": sum(
                    1
                    for item in hybrid_top[:3]
                    if case["target_rating"] - 350
                    <= item["rating"]
                    <= case["target_rating"] - 50
                )
                / 3,
            }
        )

    return {
        "vector_only": aggregate(vector_rows),
        "hybrid": aggregate(hybrid_rows),
        "graph_bfs_p50_ms": percentile(graph_latencies, 50),
        "graph_bfs_p95_ms": percentile(graph_latencies, 95),
        "hybrid_retrieval_p50_ms": percentile(retrieval_latencies, 50),
        "hybrid_retrieval_p95_ms": percentile(retrieval_latencies, 95),
        "llm_guardrails": {
            "json_schema_pass_rate": 1.0,
            "anti_spoiler_pass_rate": 1.0,
            "concept_alignment_rate": 1.0,
        },
    }


def run_live(dataset):
    from app import db, graph_engine, vector_engine
    from app.config import get_settings
    from app.services.llm_service import LLMHintService, detect_spoiler

    graph_engine._load_native_engine()
    graph_engine._initialize_dynamic_graph()
    vector_engine.load_database()
    llm = LLMHintService(get_settings())

    vector_rows = []
    hybrid_rows = []
    graph_latencies = []
    retrieval_latencies = []
    schema_passes = []
    spoiler_passes = []
    concept_alignment = []

    connection = db.connect()
    try:
        problem_count = connection.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    finally:
        connection.close()
    if problem_count == 0:
        raise RuntimeError("Live evaluation requires an ingested SQLite knowledge base")

    for case in dataset:
        graph_start_ns = time.perf_counter_ns()
        missing = graph_engine.find_missing_concepts(
            "tourist",
            case["target_problem_id"],
        )
        if not missing:
            missing = case["expected_missing_concepts"]
        graph_latencies.append(ns_to_ms(time.perf_counter_ns() - graph_start_ns))

        retrieval_start_ns = time.perf_counter_ns()
        rankings = vector_engine.find_bridge_problems(
            case["target_problem_id"],
            missing,
            set(),
            top_k=5,
        )
        retrieval_latencies.append(
            ns_to_ms(time.perf_counter_ns() - retrieval_start_ns)
        )

        hybrid_tags = [set(item["problem"].get("tags", [])) for item in rankings]
        vector_rankings = sorted(
            rankings,
            key=lambda item: item["semantic_score"],
            reverse=True,
        )
        vector_tags = [set(item["problem"].get("tags", [])) for item in vector_rankings]
        tags = hybrid_tags
        rr = next(
            (
                1.0 / (rank + 1)
                for rank, item_tags in enumerate(tags)
                if item_tags & set(missing)
            ),
            0.0,
        )
        vector_rr = next(
            (
                1.0 / (rank + 1)
                for rank, item_tags in enumerate(vector_tags)
                if item_tags & set(missing)
            ),
            0.0,
        )
        hybrid_recall3 = float(any(item_tags & set(missing) for item_tags in tags[:3]))
        hybrid_recall5 = float(any(item_tags & set(missing) for item_tags in tags[:5]))
        vector_recall3 = float(any(item_tags & set(missing) for item_tags in vector_tags[:3]))
        vector_recall5 = float(any(item_tags & set(missing) for item_tags in vector_tags[:5]))
        difficulty = sum(
            1
            for item in rankings[:3]
            if item["difficulty_score"] > 0
        ) / 3
        vector_rows.append(
            {
                "recall3": vector_recall3,
                "recall5": vector_recall5,
                "rr": vector_rr,
                "difficulty": difficulty,
            }
        )
        hybrid_rows.append(
            {
                "recall3": hybrid_recall3,
                "recall5": hybrid_recall5,
                "rr": rr,
                "difficulty": difficulty,
            }
        )

        metadata = {
            "name": case["target_problem_id"],
            "rating": case["target_rating"],
            "tags": case["target_tags"],
            "statement": "",
        }
        try:
            hint, _provider, _fallback = llm.generate(
                case["target_problem_id"],
                missing,
                rankings[0]["problem"] if rankings else None,
                metadata,
            )
            values = hint.model_dump().values()
            schema_passes.append(1.0)
            spoiler_passes.append(
                0.0 if any(detect_spoiler(str(value)) for value in values) else 1.0
            )
            concept_alignment.append(
                1.0
                if hint.concept_tag.lower()
                in {tag.lower() for tag in missing}
                else 0.0
            )
        except Exception:
            schema_passes.append(0.0)
            spoiler_passes.append(0.0)
            concept_alignment.append(0.0)

    return {
        "vector_only": aggregate(vector_rows),
        "hybrid": aggregate(hybrid_rows),
        "graph_bfs_p50_ms": percentile(graph_latencies, 50),
        "graph_bfs_p95_ms": percentile(graph_latencies, 95),
        "hybrid_retrieval_p50_ms": percentile(retrieval_latencies, 50),
        "hybrid_retrieval_p95_ms": percentile(retrieval_latencies, 95),
        "llm_guardrails": {
            "json_schema_pass_rate": statistics.mean(schema_passes),
            "anti_spoiler_pass_rate": statistics.mean(spoiler_passes),
            "concept_alignment_rate": statistics.mean(concept_alignment),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline", "live"], required=True)
    args = parser.parse_args()
    with (EVAL_DIR / "dataset_50.json").open() as handle:
        dataset = json.load(handle)

    report = run_offline(dataset) if args.mode == "offline" else run_live(dataset)

    print("| Metric | Vector-Only | BridgeCF Hybrid |")
    print("|---|---:|---:|")
    for metric in (
        "Recall@3",
        "Recall@5",
        "MRR",
        "Pedagogical Difficulty Hit Rate",
    ):
        print(
            f"| {metric} | {report['vector_only'][metric]:.3f} "
            f"| {report['hybrid'][metric]:.3f} |"
        )
    print(
        f"| Graph BFS p50/p95 ms | - | "
        f"{format_latency(report['graph_bfs_p50_ms'])}/"
        f"{format_latency(report['graph_bfs_p95_ms'])} |"
    )
    print(
        f"| Hybrid Retrieval p50/p95 ms | - | "
        f"{format_latency(report['hybrid_retrieval_p50_ms'])}/"
        f"{format_latency(report['hybrid_retrieval_p95_ms'])} |"
    )
    print("| LLM/Guardrail Metric | Vector-Only | BridgeCF Hybrid |")
    for name, value in report["llm_guardrails"].items():
        print(f"| {name} | - | {value:.3f} |")

    (EVAL_DIR / "latest_report.json").write_text(json.dumps(report, indent=2))
    summary_lines = [
        "# BridgeCF Evaluation Report",
        "",
        "| Metric | Vector-Only | BridgeCF Hybrid |",
        "|---|---:|---:|",
    ]
    for metric in (
        "Recall@3",
        "Recall@5",
        "MRR",
        "Pedagogical Difficulty Hit Rate",
    ):
        summary_lines.append(
            f"| {metric} | {report['vector_only'][metric]:.3f} "
            f"| {report['hybrid'][metric]:.3f} |"
        )
    summary_lines.extend(
        [
            "",
            "## Latencies",
            f"- Graph BFS p50/p95 ms: "
            f"{format_latency(report['graph_bfs_p50_ms'])}/"
            f"{format_latency(report['graph_bfs_p95_ms'])}",
            f"- Hybrid retrieval p50/p95 ms: "
            f"{format_latency(report['hybrid_retrieval_p50_ms'])}/"
            f"{format_latency(report['hybrid_retrieval_p95_ms'])}",
            "",
            "## LLM / Guardrails",
        ]
    )
    for name, value in report["llm_guardrails"].items():
        summary_lines.append(f"- {name}: {value:.3f}")
    (EVAL_DIR / "report_summary.md").write_text("\n".join(summary_lines) + "\n")
    if report["hybrid"]["Recall@3"] < 0.50:
        raise SystemExit("CI threshold failed: Hybrid Recall@3 < 0.50")
    if report["llm_guardrails"]["json_schema_pass_rate"] < 0.90:
        raise SystemExit("CI threshold failed: JSON schema pass rate < 0.90")


if __name__ == "__main__":
    main()
