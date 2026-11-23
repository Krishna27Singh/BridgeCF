import ctypes
import sys
import time
from pathlib import Path

import faiss
import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import db, graph_engine, vector_engine  # noqa: E402


def test_cpp_engine_bounds_safety_and_multi_source_bfs():
    graph_engine._load_native_engine()
    graph_engine._initialize_dynamic_graph()
    assert graph_engine.engine is not None
    engine = graph_engine.engine

    assert engine.init_graph(0) == -1
    assert engine.init_graph(-1) == -1
    assert engine.init_graph(10) == 0

    assert engine.add_edge(-1, 2) == -1
    assert engine.add_edge(1, -1) == -1
    assert engine.add_edge(0, 99) == -1
    assert engine.add_edge(0, 2) == 0
    assert engine.add_edge(1, 3) == 0
    assert engine.add_edge(2, 4) == 0
    assert engine.add_edge(3, 4) == 0

    solved = (ctypes.c_int * 2)(0, 1)
    output = (ctypes.c_int * 1)(-999)
    start = time.perf_counter()
    count = engine.find_bottlenecks(solved, 2, 4, output, 1)
    elapsed = time.perf_counter() - start
    assert count == 1
    assert output[0] in (2, 3)
    assert elapsed < 0.002

    invalid_output = engine.find_bottlenecks(solved, 2, 4, None, 5)
    assert invalid_output == -1
    assert engine.find_bottlenecks(solved, -1, 4, (ctypes.c_int * 5)(), 5) == -1
    assert engine.find_bottlenecks(solved, 2, 99, (ctypes.c_int * 5)(), 5) == -1

    output_all = (ctypes.c_int * 5)()
    count_all = engine.find_bottlenecks(solved, 2, 4, output_all, 5)
    found = {output_all[i] for i in range(count_all)}
    assert found == {2, 3}


def test_sqlite_faiss_cardinality_consistency(tmp_path):
    database_path = tmp_path / "bridgecf.db"
    connection = db.connect(database_path)
    db.initialize_schema(connection)
    index = faiss.IndexFlatIP(384)
    vectors = np.eye(384, dtype=np.float32)[:3]
    faiss.normalize_L2(vectors)
    index.add(vectors)

    for faiss_id in range(index.ntotal):
        connection.execute(
            """
            INSERT INTO problems
            (problem_id, contest_id, problem_index, name, rating, tags_json, statement, faiss_id)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (f"test_{faiss_id}", faiss_id + 1000, "A", "Test", 1000, "[]", faiss_id),
        )
    connection.commit()
    sqlite_count = connection.execute(
        "SELECT COUNT(*) FROM problems WHERE faiss_id IS NOT NULL"
    ).fetchone()[0]
    sqlite_unique = connection.execute(
        "SELECT COUNT(DISTINCT faiss_id) FROM problems"
    ).fetchone()[0]
    connection.close()

    assert index.ntotal == sqlite_count == sqlite_unique == 3


class FakeIndex:
    ntotal = 4
    dimension = 384

    def search(self, vector, k):
        scores = np.array([[0.95, 0.80, 0.75, 0.50]], dtype=np.float32)
        indices = np.array([[0, 1, 2, 3]], dtype=np.int64)
        return scores[:, :k], indices[:, :k]


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, params=None):
        return self

    def fetchall(self):
        return self.rows

    def close(self):
        pass


def test_hybrid_ranker_prefers_unsolved_matching_easier_problem(monkeypatch):
    target = {
        "problem_id": "1000_A",
        "rating": 1500,
        "tags_json": '["math"]',
        "contest_id": 1000,
        "problem_index": "A",
    }
    rows = [
        {
            "problem_id": "1000_A",
            "faiss_id": 0,
            "rating": 1500,
            "tags_json": '["math"]',
            "contest_id": 1000,
            "problem_index": "A",
        },
        {
            "problem_id": "1001_B",
            "faiss_id": 1,
            "rating": 1300,
            "tags_json": '["math","greedy"]',
            "contest_id": 1001,
            "problem_index": "B",
        },
        {
            "problem_id": "1002_C",
            "faiss_id": 2,
            "rating": 2100,
            "tags_json": '["implementation"]',
            "contest_id": 1002,
            "problem_index": "C",
        },
        {
            "problem_id": "1003_D",
            "faiss_id": 3,
            "rating": 1200,
            "tags_json": '["math"]',
            "contest_id": 1003,
            "problem_index": "D",
        },
    ]

    monkeypatch.setattr(vector_engine, "INDEX", FakeIndex())
    monkeypatch.setattr(vector_engine, "_problem_row", lambda problem_id: target)
    monkeypatch.setattr(
        vector_engine,
        "_get_target_vector",
        lambda problem_id: np.array([[1.0] * 384], dtype=np.float32),
    )
    monkeypatch.setattr(db, "connect", lambda: FakeConnection(rows))

    rankings = vector_engine.find_bridge_problems(
        "1000_A",
        ["math"],
        {"1003_D"},
        top_k=3,
    )
    assert rankings
    assert rankings[0]["problem"]["problem_id"] == "1001_B"
    assert rankings[0]["concept_score"] == 1.0
    assert rankings[0]["difficulty_score"] == 1.0
