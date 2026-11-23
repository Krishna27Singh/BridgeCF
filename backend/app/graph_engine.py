import ctypes
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Set

import requests

from . import db

LOGGER = logging.getLogger(__name__)
engine = None

CONCEPT_IDS: Dict[str, int] = {}
PROBLEM_IDS: Dict[str, int] = {}
CONCEPT_NAMES: Dict[int, str] = {}

engine_path = Path(__file__).resolve().parents[1] / "engine.so"


def _load_native_engine() -> bool:
    global engine
    try:
        library = ctypes.CDLL(str(engine_path))
        library.init_graph.argtypes = [ctypes.c_int]
        library.init_graph.restype = ctypes.c_int
        library.add_edge.argtypes = [ctypes.c_int, ctypes.c_int]
        library.add_edge.restype = ctypes.c_int
        library.find_bottlenecks.argtypes = [
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
        ]
        library.find_bottlenecks.restype = ctypes.c_int
        engine = library
        return True
    except (OSError, AttributeError) as exc:
        LOGGER.warning(
            "C++ graph engine unavailable at %s: %s. Using Python BFS fallback.",
            engine_path,
            exc,
        )
        engine = None
        return False


def _initialize_dynamic_graph() -> None:
    global CONCEPT_IDS, PROBLEM_IDS, CONCEPT_NAMES
    CONCEPT_IDS = {}
    PROBLEM_IDS = {}
    CONCEPT_NAMES = {}

    if not db.DB_PATH.exists():
        LOGGER.warning(
            "SQLite knowledge base missing at %s. Graph engine will have no mappings.",
            db.DB_PATH,
        )
        return

    connection = db.connect()
    try:
        prerequisite_rows = connection.execute(
            "SELECT concept, prerequisite FROM concept_prerequisites"
        ).fetchall()
        problem_rows = connection.execute(
            "SELECT problem_id, tags_json FROM problems"
        ).fetchall()
    finally:
        connection.close()

    concepts = set()
    for row in prerequisite_rows:
        concepts.add(str(row["concept"]))
        concepts.add(str(row["prerequisite"]))

    import json
    problem_tags: Dict[str, List[str]] = {}
    for row in problem_rows:
        problem_id = str(row["problem_id"])
        try:
            tags = json.loads(row["tags_json"] or "[]")
        except json.JSONDecodeError:
            tags = []
        problem_tags[problem_id] = [str(tag) for tag in tags]
        concepts.update(str(tag) for tag in tags)

    for concept in sorted(concepts):
        node_id = len(CONCEPT_IDS)
        CONCEPT_IDS[concept] = node_id
        CONCEPT_NAMES[node_id] = concept

    for index, problem_id in enumerate(sorted(problem_tags)):
        PROBLEM_IDS[problem_id] = 100000 + index

    if engine is not None:
        max_node = max(
            list(CONCEPT_IDS.values()) + list(PROBLEM_IDS.values()),
            default=1,
        ) + 1
        if engine.init_graph(max_node) != 0:
            LOGGER.warning("C++ engine rejected graph initialization for %d nodes", max_node)
            return
        for row in prerequisite_rows:
            concept = str(row["concept"])
            prerequisite = str(row["prerequisite"])
            engine.add_edge(CONCEPT_IDS[prerequisite], CONCEPT_IDS[concept])
        for problem_id, tags in problem_tags.items():
            target = PROBLEM_IDS[problem_id]
            for tag in tags:
                if tag in CONCEPT_IDS:
                    engine.add_edge(CONCEPT_IDS[tag], target)


def get_user_solved_problems(handle: str) -> List[str]:
    url = "https://codeforces.com/api/user.status"
    try:
        response = requests.get(url, params={"handle": handle}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "OK":
            return []
        solved: Set[str] = set()
        for submission in data.get("result", []):
            if submission.get("verdict") != "OK":
                continue
            problem = submission.get("problem", {})
            contest_id = problem.get("contestId")
            problem_index = problem.get("index")
            if contest_id is not None and problem_index:
                solved.add(f"{contest_id}_{problem_index}")
        return sorted(solved)
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("Codeforces user history unavailable for %s: %s", handle, exc)
        return []


def _python_bfs(solved_problem_ids: Iterable[str], target_problem_id: str) -> List[str]:
    if not db.DB_PATH.exists():
        return []
    connection = db.connect()
    try:
        prereq_rows = connection.execute(
            "SELECT concept, prerequisite FROM concept_prerequisites"
        ).fetchall()
        target_row = connection.execute(
            "SELECT tags_json FROM problems WHERE problem_id = ?", (target_problem_id,)
        ).fetchone()
        solved_placeholders = ",".join("?" for _ in solved_problem_ids)
        solved_values = list(solved_problem_ids)
        if solved_values:
            solved_rows = connection.execute(
                "SELECT problem_id, tags_json FROM problems "
                f"WHERE problem_id IN ({solved_placeholders})",
                solved_values,
            ).fetchall()
        else:
            solved_rows = []
    finally:
        connection.close()

    import json
    prereqs: Dict[str, Set[str]] = {}
    for row in prereq_rows:
        prereqs.setdefault(str(row["concept"]), set()).add(str(row["prerequisite"]))

    mastered: Set[str] = set()
    stack = []
    for row in solved_rows:
        for tag in json.loads(row["tags_json"] or "[]"):
            if tag not in mastered:
                mastered.add(str(tag))
                stack.append(str(tag))
    while stack:
        concept = stack.pop()
        for prerequisite in prereqs.get(concept, set()):
            if prerequisite not in mastered:
                mastered.add(prerequisite)
                stack.append(prerequisite)

    if target_row is None:
        return []
    required: Set[str] = set()
    stack = json.loads(target_row["tags_json"] or "[]")
    while stack:
        concept = stack.pop()
        concept = str(concept)
        if concept in required:
            continue
        required.add(concept)
        stack.extend(prereqs.get(concept, set()))

    missing_frontier = []
    for concept in sorted(required - mastered):
        if prereqs.get(concept, set()).issubset(mastered):
            missing_frontier.append(concept)
    return missing_frontier


def find_missing_concepts(handle: str, target_str: str) -> List[str]:
    solved_strings = get_user_solved_problems(handle)
    if engine is None:
        return _python_bfs(solved_strings, target_str)
    if target_str not in PROBLEM_IDS:
        return ["Graph Not Mapped For This Problem Yet"]

    solved_ids = [PROBLEM_IDS[problem] for problem in solved_strings if problem in PROBLEM_IDS]
    if len(solved_ids) == 0:
        solved_array = (ctypes.c_int * 1)(-1)
        solved_count = 0
    else:
        solved_array = (ctypes.c_int * len(solved_ids))(*solved_ids)
        solved_count = len(solved_ids)

    out = (ctypes.c_int * 5)()
    count = engine.find_bottlenecks(
        solved_array,
        solved_count,
        PROBLEM_IDS[target_str],
        out,
        5,
    )
    if count < 0:
        LOGGER.warning("C++ graph engine rejected the bottleneck query")
        return _python_bfs(solved_strings, target_str)

    result: List[str] = []
    for i in range(count):
        concept = CONCEPT_NAMES.get(out[i])
        if concept is not None:
            result.append(concept)
    return result
