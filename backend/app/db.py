import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "bridgecf.db"
LOGGER = logging.getLogger("bridgecf.db")


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    ensure_data_dir()
    db_path = path if path is not None else DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS problems (
            problem_id TEXT PRIMARY KEY,
            contest_id INTEGER,
            problem_index TEXT,
            name TEXT,
            rating INTEGER,
            tags_json TEXT,
            statement TEXT,
            faiss_id INTEGER UNIQUE
        );
        CREATE INDEX IF NOT EXISTS idx_problems_rating ON problems(rating);
        CREATE INDEX IF NOT EXISTS idx_problems_faiss_id ON problems(faiss_id);

        CREATE TABLE IF NOT EXISTS concept_prerequisites (
            concept TEXT,
            prerequisite TEXT,
            PRIMARY KEY (concept, prerequisite)
        );

        CREATE TABLE IF NOT EXISTS user_cache (
            handle TEXT PRIMARY KEY,
            solved_json TEXT,
            updated_at REAL
        );
        CREATE TABLE IF NOT EXISTS hint_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_handle TEXT,
            problem_id TEXT,
            missing_concepts_json TEXT,
            bridge_problem_id TEXT,
            provider TEXT,
            latency_ms REAL,
            created_at REAL
        );
        CREATE INDEX IF NOT EXISTS idx_hint_logs_user_created
            ON hint_logs(user_handle, created_at);
        """
    )
    connection.commit()


def reconciliation_status(connection: sqlite3.Connection, index_ntotal: Optional[int] = None):
    problem_count = connection.execute(
        "SELECT COUNT(*) FROM problems"
    ).fetchone()[0]
    faiss_id_count = connection.execute(
        "SELECT COUNT(DISTINCT faiss_id) FROM problems WHERE faiss_id IS NOT NULL"
    ).fetchone()[0]
    consistent = problem_count == faiss_id_count
    if index_ntotal is not None:
        consistent = consistent and problem_count == index_ntotal
    if not consistent:
        LOGGER.warning(
            "Asset mismatch: sqlite_problems=%s sqlite_faiss_ids=%s faiss_ntotal=%s",
            problem_count,
            faiss_id_count,
            index_ntotal,
        )
    return {"problem_count": problem_count, "consistent": consistent}


def log_hint(connection, user_handle, problem_id, missing, bridge_id, provider, latency_ms):
    connection.execute(
        """
        INSERT INTO hint_logs
        (user_handle, problem_id, missing_concepts_json, bridge_problem_id,
         provider, latency_ms, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_handle,
            problem_id,
            json.dumps(missing),
            bridge_id,
            provider,
            float(latency_ms),
            time.time(),
        ),
    )
    connection.commit()
