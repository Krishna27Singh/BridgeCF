import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db, graph_engine, vector_engine
from .config import get_settings
from .schemas import (
    HealthResponse,
    HintRequest,
    HintResponse,
    ReadyResponse,
    StructuredHint,
)
from .services.llm_service import LLMHintService


logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("bridgecf.api")
hint_service = LLMHintService(get_settings())


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    db.ensure_data_dir()
    connection = db.connect()
    try:
        db.initialize_schema(connection)
    finally:
        connection.close()
    graph_engine._initialize_dynamic_graph()
    vector_engine.load_database()
    LOGGER.info(
        "startup_complete db=%s native_engine=%s",
        settings.db_path,
        settings.native_engine_path,
    )
    yield
    LOGGER.info("shutdown_complete")


app = FastAPI(title="BridgeCF Hint Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "Hint Engine Backend Online"}


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
    return {
        "status": "ready" if graph_ready or vector_ready else "degraded",
        "ready": graph_ready and vector_ready,
        "graph_engine": graph_ready,
        "vector_database": vector_ready,
    }


@app.post("/api/hint", response_model=HintResponse)
async def generate_hint(request: HintRequest):
    target_id = request.problem_id
    handle = request.user_handle

    missing_concepts = graph_engine.find_missing_concepts(handle, target_id)
    solved_set = set(graph_engine.get_user_solved_problems(handle))
    rankings = vector_engine.find_bridge_problems(
        target_id,
        missing_concepts,
        solved_set,
        top_k=3,
    )
    bridge_url = rankings[0]["problem"]["url"] if rankings else None
    bridge_id = rankings[0]["problem"]["problem_id"] if rankings else None

    if not missing_concepts:
        message = "You already know all the mapped concepts required for this problem. Focus on implementation and constraints."
    elif "Graph Not Mapped" in missing_concepts[0] or "C++ Engine Offline" in missing_concepts[0]:
        message = f"We found a semantic bridge problem, but {target_id} is not mapped in the dependency graph yet."
        missing_concepts = []
    else:
        message = f"For {target_id}, focus on these prerequisites: {', '.join(missing_concepts)}"

    provider_name = str(get_settings().llm_provider).lower()
    generated = hint_service.generate(target_id, missing_concepts, bridge_id)
    structured = StructuredHint(
        level=generated.get("level", "guided"),
        message=generated["message"],
        next_step=generated.get("next_step", ""),
        missing_concepts=missing_concepts,
        bridge_problem_id=bridge_id,
    )

    LOGGER.info(
        "hint_request problem_id=%s handle=%s missing=%s bridge=%s provider=%s",
        target_id,
        handle,
        ",".join(missing_concepts) or "-",
        bridge_id or "-",
        provider_name,
    )

    return {
        "status": "success",
        "problem_id": target_id,
        "message": structured.message,
        "missing_concepts": missing_concepts,
        "bridge_problem": bridge_url or "#",
        "bridge_id": bridge_id or "Unknown",
        "bridge_rankings": rankings,
        "hint": structured,
        "provider": provider_name,
    }
