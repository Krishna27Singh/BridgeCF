import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import db, graph_engine, vector_engine
from .config import get_settings
from .schemas import (
    HealthResponse,
    HintRequest,
    HintResponse,
    ReadyResponse,
)
from .services.llm_service import LLMHintService

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("bridgecf.api")
hint_service = LLMHintService(get_settings())
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    if "DATA_DIR" in os.environ:
        db.configure_data_dir(settings.data_dir)
        vector_engine.DATA_DIR = settings.data_dir
        vector_engine.INDEX_FILE = settings.index_path
    db.ensure_data_dir()
    graph_engine._load_native_engine()
    connection = db.connect()
    try:
        db.initialize_schema(connection)
        db.reconciliation_status(connection)
    finally:
        connection.close()
    vector_engine.load_database()
    connection = db.connect()
    try:
        db.reconciliation_status(
            connection,
            getattr(vector_engine.INDEX, "ntotal", None),
        )
    finally:
        connection.close()
    graph_engine._initialize_dynamic_graph()
    LOGGER.info(
        "startup_complete db=%s native_engine=%s",
        settings.db_path,
        settings.native_engine_path,
    )
    yield
    LOGGER.info("shutdown_complete")


app = FastAPI(title="BridgeCF Hint Engine", lifespan=lifespan)

settings = get_settings()
allow_credentials = "*" not in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    del request
    return JSONResponse(
        status_code=422,
        content={"status": "error", "error": "invalid_request", "detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    del request
    LOGGER.exception("Unhandled API exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "error": "internal_error"},
    )


@app.get("/")
def root():
    return {"status": "Hint Engine Backend Online"}


@app.get("/demo", include_in_schema=False)
def demo():
    return FileResponse(STATIC_DIR / "demo.html", media_type="text/html")


@app.get("/health", response_model=HealthResponse)
def health():
    return {
        "status": "ok",
        "graph_engine": graph_engine.engine is not None,
        "vector_database": vector_engine.INDEX is not None,
    }


@app.get("/ready", response_model=ReadyResponse)
def ready():
    settings = get_settings()
    graph_ready = graph_engine.engine is not None
    vector_ready = vector_engine.INDEX is not None and settings.db_path.exists()
    if vector_ready:
        connection = db.connect()
        try:
            reconciliation = db.reconciliation_status(
                connection,
                getattr(vector_engine.INDEX, "ntotal", None),
            )
            vector_ready = reconciliation["consistent"]
        finally:
            connection.close()
    return {
        "status": "ready" if graph_ready or vector_ready else "degraded",
        "ready": graph_ready and vector_ready,
        "graph_engine": graph_ready,
        "vector_database": vector_ready,
    }


@app.post("/api/hint", response_model=HintResponse)
async def generate_hint(request: HintRequest):
    started = time.perf_counter()
    target_id = request.problem_id
    handle = request.user_handle

    graph_started = time.perf_counter()
    missing_concepts = graph_engine.find_missing_concepts(handle, target_id)
    solved_set = set(graph_engine.get_user_solved_problems(handle))
    graph_ms = (time.perf_counter() - graph_started) * 1000

    retrieval_started = time.perf_counter()
    rankings = vector_engine.find_bridge_problems(
        target_id,
        missing_concepts,
        solved_set,
        top_k=request.max_bridges,
    )
    retrieval_ms = (time.perf_counter() - retrieval_started) * 1000

    bridge = rankings[0] if rankings else None
    top_problem = bridge["problem"] if bridge else None
    bridge_id = top_problem["problem_id"] if top_problem else None

    connection = db.connect()
    try:
        row = connection.execute(
            "SELECT name, rating, tags_json, statement FROM problems WHERE problem_id = ?",
            (target_id,),
        ).fetchone()
    finally:
        connection.close()
    import json
    target_metadata = {}
    if row:
        target_metadata = {
            "name": row["name"],
            "rating": row["rating"],
            "tags": json.loads(row["tags_json"] or "[]"),
            "statement": row["statement"],
        }

    llm_started = time.perf_counter()
    structured, provider_name, fallback_used = hint_service.generate(
        target_id,
        missing_concepts,
        top_problem,
        target_metadata,
    )
    llm_ms = (time.perf_counter() - llm_started) * 1000
    total_ms = (time.perf_counter() - started) * 1000

    connection = db.connect()
    try:
        db.log_hint(
            connection,
            handle,
            target_id,
            missing_concepts,
            bridge_id,
            provider_name,
            total_ms,
        )
    finally:
        connection.close()

    return {
        "status": "success",
        "problem_id": target_id,
        "user_handle": handle,
        "missing_concepts": missing_concepts,
        "bridge_problems": rankings,
        "hint": structured,
        "provider": provider_name,
        "fallback_used": fallback_used,
        "timings_ms": {
            "graph_ms": round(graph_ms, 3),
            "retrieval_ms": round(retrieval_ms, 3),
            "llm_ms": round(llm_ms, 3),
            "total_ms": round(total_ms, 3),
        },
    }
