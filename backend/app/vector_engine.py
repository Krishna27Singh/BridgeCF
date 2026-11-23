import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import faiss
import numpy as np
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
import cloudscraper

from . import db


LOGGER = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
INDEX_FILE = DATA_DIR / "vector_database.index"
MODEL_NAME = "all-MiniLM-L6-v2"

MODEL = None
INDEX = None
FAISS_LOCK = threading.RLock()


def load_database() -> None:
    global INDEX
    with FAISS_LOCK:
        if INDEX_FILE.exists():
            try:
                INDEX = faiss.read_index(str(INDEX_FILE))
            except Exception as exc:
                LOGGER.error("Could not load FAISS index %s: %s", INDEX_FILE, exc)
                INDEX = faiss.IndexFlatIP(384)
        else:
            LOGGER.warning("Vector database missing at %s", INDEX_FILE)
            INDEX = faiss.IndexFlatIP(384)


load_database()


def _load_model():
    global MODEL
    if MODEL is None:
        MODEL = SentenceTransformer(MODEL_NAME)
    return MODEL


def scrape_codeforces_problem(contest_id: str, index_letter: str) -> Optional[str]:
    url = f"https://codeforces.com/problemset/problem/{contest_id}/{index_letter}"
    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        statement_div = soup.find("div", class_="problem-statement")
        if statement_div is None:
            return None
        header = statement_div.find("div", class_="header")
        if header:
            header.decompose()
        sample_tests = statement_div.find("div", class_="sample-tests")
        if sample_tests:
            sample_tests.decompose()
        return statement_div.get_text(separator=" ", strip=True)
    except Exception as exc:
        LOGGER.warning("Cloudflare or network blocked scraping %s: %s", url, exc)
        return None


def _problem_row(problem_id: str) -> Optional[sqlite3.Row]:
    connection = db.connect()
    try:
        return connection.execute(
            "SELECT * FROM problems WHERE problem_id = ?", (problem_id,)
        ).fetchone()
    finally:
        connection.close()


def _get_target_vector(problem_id: str) -> Optional[np.ndarray]:
    row = _problem_row(problem_id)
    if row is None or row["faiss_id"] is None:
        return None
    faiss_id = int(row["faiss_id"])
    with FAISS_LOCK:
        if INDEX is None or faiss_id < 0 or faiss_id >= INDEX.ntotal:
            return None
        return np.asarray([INDEX.reconstruct(faiss_id)], dtype=np.float32)


def jit_ingest_problem(problem_id: str) -> Optional[int]:
    parts = problem_id.split("_", 1)
    if len(parts) != 2:
        return None
    contest_id, index_letter = parts
    text = scrape_codeforces_problem(contest_id, index_letter)
    if not text:
        return None

    with FAISS_LOCK:
        existing = _problem_row(problem_id)
        if existing is not None and existing["faiss_id"] is not None:
            return int(existing["faiss_id"])

        vector = _load_model().encode([text], convert_to_numpy=True)[0].astype(np.float32)
        vector = np.asarray([vector], dtype=np.float32)
        faiss.normalize_L2(vector)
        faiss_id = INDEX.ntotal

        INDEX.add(vector)
        temp_index = DATA_DIR / "vector_database.index.tmp"
        faiss.write_index(INDEX, str(temp_index))

        connection = db.connect()
        try:
            connection.execute(
                """
                INSERT OR REPLACE INTO problems
                (problem_id, contest_id, problem_index, name, rating, tags_json, statement, faiss_id)
                VALUES (?, ?, ?, ?, NULL, '[]', ?, ?)
                """,
                (problem_id, int(contest_id), index_letter, problem_id, text, faiss_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            connection.close()
            if temp_index.exists():
                temp_index.unlink()
            raise
        connection.close()
        os.replace(temp_index, INDEX_FILE)
        return faiss_id


def get_bridge_problem(target_id: str) -> Tuple[Optional[str], Optional[str]]:
    ranked = find_bridge_problems(target_id, [], set(), top_k=1)
    if not ranked:
        return None, None
    row = ranked[0]["problem"]
    return row["url"], row["problem_id"]


def _cosine_from_faiss(score: float) -> float:
    return max(0.0, min(1.0, float(score)))


def find_bridge_problems(
    target_problem_id: str,
    missing_concepts: Iterable[str],
    solved_set: Set[str],
    top_k: int = 3,
) -> List[dict]:
    target_row = _problem_row(target_problem_id)
    if target_row is None:
        with FAISS_LOCK:
            jit_ingest_problem(target_problem_id)
        target_row = _problem_row(target_problem_id)
    if target_row is None:
        return []

    target_vector = _get_target_vector(target_problem_id)
    if target_vector is None:
        return []

    missing = {str(concept).lower() for concept in missing_concepts}
    target_rating = target_row["rating"]

    with FAISS_LOCK:
        k = min(50, INDEX.ntotal)
        scores, indices = INDEX.search(target_vector, k)

    candidate_ids = []
    for rank, faiss_id in enumerate(indices[0]):
        faiss_id = int(faiss_id)
        if faiss_id < 0:
            continue
        candidate_ids.append((faiss_id, float(scores[0][rank])))

    connection = db.connect()
    try:
        rows = connection.execute(
            "SELECT * FROM problems WHERE faiss_id IS NOT NULL"
        ).fetchall()
    finally:
        connection.close()

    by_faiss_id = {int(row["faiss_id"]): row for row in rows}
    ranked = []
    for faiss_id, raw_score in candidate_ids:
        candidate = by_faiss_id.get(faiss_id)
        if candidate is None:
            continue
        candidate_id = candidate["problem_id"]
        if candidate_id == target_problem_id or candidate_id in solved_set:
            continue

        try:
            tags = set(
                str(tag).lower()
                for tag in json.loads(candidate["tags_json"] or "[]")
            )
        except json.JSONDecodeError:
            tags = set()

        semantic = _cosine_from_faiss(raw_score)
        overlap = missing.intersection(tags)
        concept_score = len(overlap) / max(1, len(missing)) if missing else 0.0
        concept_score = min(1.0, concept_score)

        candidate_rating = candidate["rating"]
        difficulty_score = 0.0
        if target_rating is not None and candidate_rating is not None:
            delta = int(target_rating) - int(candidate_rating)
            if 100 <= delta <= 300:
                difficulty_score = 1.0
            elif 0 < delta < 100:
                difficulty_score = 0.5
            elif 300 < delta <= 500:
                difficulty_score = 0.5

        final_score = (
            0.65 * semantic +
            0.25 * concept_score +
            0.10 * difficulty_score
        )
        url = (
            f"https://codeforces.com/problemset/problem/"
            f"{candidate['contest_id']}/{candidate['problem_index']}"
        )
        ranked.append({
            "problem": {
                "problem_id": candidate_id,
                "url": url,
                "rating": candidate_rating,
                "tags": sorted(tags),
            },
            "semantic_score": round(semantic, 6),
            "concept_score": round(concept_score, 6),
            "difficulty_score": round(difficulty_score, 6),
            "final_score": round(final_score, 6),
        })

    ranked.sort(
        key=lambda item: (
            item["final_score"],
            item["semantic_score"],
            item["concept_score"],
        ),
        reverse=True,
    )
    return ranked[:max(0, top_k)]
