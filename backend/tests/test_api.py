from fastapi.testclient import TestClient

from app import db, graph_engine, vector_engine
from app.main import app
from app.schemas import StructuredHint


def test_health_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(graph_engine, "engine", object())
    monkeypatch.setattr(vector_engine, "INDEX", type("Index", (), {"ntotal": 3})())
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "bridgecf.db")

    connection = db.connect(db.DB_PATH)
    db.initialize_schema(connection)
    for faiss_id, problem_id in enumerate(("1890_A", "1890_B", "1890_C")):
        connection.execute(
            """
            INSERT INTO problems
            (problem_id, contest_id, problem_index, name, rating, tags_json, faiss_id)
            VALUES (?, 1890, 'A', 'Test', 1000, '[]', ?)
            """,
            (problem_id, faiss_id),
        )
    connection.commit()
    connection.close()

    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code in (200, 503)


def test_hint_normalization_and_log(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "bridgecf.db")
    monkeypatch.setattr(graph_engine, "engine", object())
    monkeypatch.setattr(vector_engine, "INDEX", type("Index", (), {"ntotal": 1})())
    monkeypatch.setattr(
        graph_engine,
        "get_user_solved_problems",
        lambda handle: [],
    )
    monkeypatch.setattr(
        graph_engine,
        "find_missing_concepts",
        lambda handle, problem_id: ["math"],
    )
    monkeypatch.setattr(
        vector_engine,
        "find_bridge_problems",
        lambda target, missing, solved, top_k=3: [
            {
                "problem": {
                    "problem_id": "1890_B",
                    "url": "https://codeforces.com/problemset/problem/1890/B",
                    "rating": 900,
                    "tags": ["math"],
                },
                "semantic_score": 0.9,
                "concept_score": 1.0,
                "difficulty_score": 1.0,
                "final_score": 0.94,
            }
        ],
    )
    monkeypatch.setattr(
        "app.main.hint_service.generate",
        lambda *args, **kwargs: (
            StructuredHint(
                concept_tag="math",
                conceptual_nudge="What observation is invariant?",
                strategy_hint="Separate cases.",
                complexity_nudge="O(n).",
                bridge_rationale="The bridge practices the same mathematical observation.",
            ),
            "fallback",
            True,
        ),
    )

    connection = db.connect(db.DB_PATH)
    db.initialize_schema(connection)
    connection.execute(
        """
        INSERT INTO problems
        (problem_id, contest_id, problem_index, name, rating, tags_json, statement, faiss_id)
        VALUES ('1890_A', 1890, 'A', 'Test', 1000, '["math"]', '', 0)
        """,
    )
    connection.commit()
    connection.close()

    with TestClient(app) as client:
        response = client.post(
            "/api/hint",
            json={"problem_id": "1890A", "user_handle": " tourist ", "max_bridges": 3},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["problem_id"] == "1890_A"
    assert data["fallback_used"] is True

    connection = db.connect(db.DB_PATH)
    count = connection.execute("SELECT COUNT(*) FROM hint_logs").fetchone()[0]
    connection.close()
    assert count == 1


def test_hint_invalid_input_returns_422():
    with TestClient(app) as client:
        response = client.post("/api/hint", json={"problem_id": ""})
    assert response.status_code == 422


def test_demo_and_root_routes():
    with TestClient(app) as client:
        root_response = client.get("/")
        demo_response = client.get("/demo")

    assert root_response.status_code == 200
    assert root_response.json() == {"status": "Hint Engine Backend Online"}
    assert demo_response.status_code == 200
    assert "text/html" in demo_response.headers["content-type"]
    assert "BridgeCF" in demo_response.text


def test_extension_manifest_and_files():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    manifest_path = root / "extension" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())

    assert manifest["manifest_version"] == 3
    assert manifest["background"]["service_worker"] == "background.js"
    assert manifest["action"]["default_popup"] == "popup.html"
    for relative in (
        "background.js",
        "content.js",
        "popup.js",
        "popup.html",
        "styles.css",
    ):
        assert (root / "extension" / relative).exists()
