import sqlite3
from pathlib import Path
from typing import Optional


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "bridgecf.db"


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
        """
    )
    connection.commit()
