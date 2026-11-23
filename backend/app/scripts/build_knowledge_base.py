import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Iterable, List, Tuple

import faiss
import numpy as np
import requests
from sentence_transformers import SentenceTransformer

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import db  # noqa: E402

DATA_DIR = BACKEND_DIR / "data"
INDEX_PATH = DATA_DIR / "vector_database.index"
MODEL_NAME = "all-MiniLM-L6-v2"
DIMENSION = 384
CATALOG_URL = "https://codeforces.com/api/problemset.problems"

OFFICIAL_TAGS = [
    "2-sat", "binary search", "bitmasks", "brute force",
    "chinese remainder theorem", "combinatorics", "constructive algorithms",
    "data structures", "dfs and similar", "divide and conquer",
    "dp", "dsu", "expression parsing", "fft", "flows", "games",
    "geometry", "graph matchings", "graphs", "greedy", "hashing",
    "implementation", "interactive", "math", "matrices",
    "meet-in-the-middle", "number theory", "probabilities",
    "schedules", "shortest paths", "sortings", "string suffix structures",
    "strings", "trees", "two pointers", "ternary search",
]


PREREQUISITE_DAG = [
    ("number theory", "math"),
    ("combinatorics", "math"),
    ("probabilities", "math"),
    ("dfs and similar", "graphs"),
    ("shortest paths", "dfs and similar"),
    ("trees", "shortest paths"),
    ("flows", "trees"),
    ("graph matchings", "graphs"),
    ("trees", "graphs"),
    ("shortest paths", "graphs"),
    ("bitmasks", "dp"),
    ("trees", "dp"),
    ("divide and conquer", "dp"),
    ("dsu", "data structures"),
    ("trees", "data structures"),
    ("divide and conquer", "data structures"),
    ("two pointers", "binary search"),
    ("ternary search", "binary search"),
    ("fft", "divide and conquer"),
    ("hashing", "strings"),
    ("string suffix structures", "strings"),
    ("dp", "games"),
    ("geometry", "math"),
    ("matrices", "math"),
    ("chinese remainder theorem", "number theory"),
    ("probabilities", "combinatorics"),
    ("brute force", "meet-in-the-middle"),
    ("greedy", "math"),
    ("greedy", "sortings"),
    ("divide and conquer", "sortings"),
    ("implementation", "data structures"),
    ("2-sat", "graphs"),
    ("constructive algorithms", "implementation"),
    ("fft", "number theory"),
    ("graph matchings", "flows"),
    ("hashing", "data structures"),
    ("interactive", "implementation"),
    ("matrices", "dp"),
    ("schedules", "greedy"),
    ("implementation", "brute force"),
]


def fetch_catalog(timeout: float = 30.0, retries: int = 5) -> List[dict]:
    last_error = None
    for attempt in range(retries):
        try:
            response = requests.get(CATALOG_URL, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "OK":
                raise RuntimeError(f"Codeforces API status: {payload.get('status')}")
            problems = payload["result"].get("problems", [])
            if not isinstance(problems, list):
                raise RuntimeError("Codeforces catalog problems field is not a list")
            return problems
        except (requests.RequestException, ValueError, KeyError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Could not fetch Codeforces catalog after {retries} attempts: {last_error}")


def normalize_problem(problem: dict) -> dict:
    contest_id = problem.get("contestId")
    problem_index = problem.get("index")
    if contest_id is None or not problem_index:
        return None
    problem_id = f"{contest_id}_{problem_index}"
    tags = [str(tag) for tag in problem.get("tags", []) if isinstance(tag, str)]
    return {
        "problem_id": problem_id,
        "contest_id": int(contest_id),
        "problem_index": str(problem_index),
        "name": str(problem.get("name", "")),
        "rating": int(problem["rating"]) if problem.get("rating") is not None else None,
        "tags": tags,
    }


def batch(values: Iterable, size: int):
    current = []
    for value in values:
        current.append(value)
        if len(current) == size:
            yield current
            current = []
    if current:
        yield current


def build(limit=None) -> Tuple[int, int]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    catalog = fetch_catalog()
    normalized = []
    seen = set()
    for raw in catalog:
        problem = normalize_problem(raw)
        if problem is None or problem["problem_id"] in seen:
            continue
        seen.add(problem["problem_id"])
        normalized.append(problem)
        if limit is not None and len(normalized) >= limit:
            break

    print(f"Loading Transformer Model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    index = faiss.IndexFlatIP(DIMENSION)
    vectors = []

    for batch_index, problem_batch in enumerate(batch(normalized, 64), start=1):
        texts = [
            f"{problem['name']} | tags: {', '.join(problem['tags'])} "
            f"| rating: {problem['rating'] or 'unrated'}"
            for problem in problem_batch
        ]
        encoded = model.encode(texts, batch_size=64, convert_to_numpy=True, show_progress_bar=False)
        encoded = np.asarray(encoded, dtype=np.float32)
        faiss.normalize_L2(encoded)
        vectors.append(encoded)
        print(f"Embedded batch {batch_index} ({len(problem_batch)} problems)")

    if vectors:
        matrix = np.vstack(vectors)
        if matrix.shape[1] != DIMENSION:
            raise RuntimeError(
                f"Embedding dimension mismatch: expected {DIMENSION}, got {matrix.shape[1]}"
            )
        faiss.normalize_L2(matrix)
        index.add(matrix)

    temp_db = DATA_DIR / "bridgecf.db.tmp"
    temp_index = DATA_DIR / "vector_database.index.tmp"
    for temp_path in (temp_db, temp_index):
        if temp_path.exists():
            temp_path.unlink()

    connection = db.connect(temp_db)
    db.initialize_schema(connection)
    connection.execute("DELETE FROM problems")
    connection.execute("DELETE FROM concept_prerequisites")
    connection.execute("DELETE FROM user_cache")

    for faiss_id, problem in enumerate(normalized):
        connection.execute(
            """
            INSERT INTO problems
            (problem_id, contest_id, problem_index, name, rating, tags_json, statement, faiss_id)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                problem["problem_id"],
                problem["contest_id"],
                problem["problem_index"],
                problem["name"],
                problem["rating"],
                json.dumps(problem["tags"], separators=(",", ":")),
                faiss_id,
            ),
        )

    official_set = set(OFFICIAL_TAGS)
    edge_set = set(PREREQUISITE_DAG)
    for problem in normalized:
        for tag in problem["tags"]:
            if tag in official_set:
                edge_set.add((tag, tag))
    for concept, prerequisite in sorted(edge_set):
        if concept == prerequisite:
            continue
        connection.execute(
            "INSERT OR IGNORE INTO concept_prerequisites(concept, prerequisite) VALUES (?, ?)",
            (concept, prerequisite),
        )
    connection.commit()

    faiss_count = index.ntotal
    sqlite_count = connection.execute(
        "SELECT COUNT(*) AS count FROM problems WHERE faiss_id IS NOT NULL"
    ).fetchone()["count"]
    sqlite_unique = connection.execute(
        "SELECT COUNT(DISTINCT faiss_id) AS count FROM problems"
    ).fetchone()["count"]
    if faiss_count != sqlite_count or faiss_count != sqlite_unique:
        connection.close()
        temp_db.unlink(missing_ok=True)
        temp_index.unlink(missing_ok=True)
        raise RuntimeError(
            f"Cardinality mismatch before persistence: FAISS={faiss_count}, "
            f"SQLite={sqlite_count}, unique_ids={sqlite_unique}"
        )
    connection.close()

    faiss.write_index(index, str(temp_index))
    os.replace(temp_db, db.DB_PATH)
    os.replace(temp_index, INDEX_PATH)
    print(f"Successfully indexed {index.ntotal} problems.")
    return index.ntotal, sqlite_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be a positive integer")
    build(args.limit)


if __name__ == "__main__":
    main()
