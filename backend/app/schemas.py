from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class HintRequest(BaseModel):
    problem_id: str = Field(min_length=1)
    user_handle: str = Field(min_length=1)


class BridgeProblem(BaseModel):
    problem_id: str
    url: str
    rating: Optional[int] = None
    tags: List[str] = []


class BridgeScore(BaseModel):
    problem: BridgeProblem
    semantic_score: float
    concept_score: float
    difficulty_score: float
    final_score: float


class StructuredHint(BaseModel):
    level: Literal["guided", "nudge", "review"] = "guided"
    message: str
    next_step: str = ""
    missing_concepts: List[str] = []
    bridge_problem_id: Optional[str] = None


class HintResponse(BaseModel):
    status: str
    problem_id: str
    message: str
    missing_concepts: List[str]
    bridge_problem: str
    bridge_id: str
    bridge_rankings: List[BridgeScore] = []
    hint: Optional[StructuredHint] = None
    provider: str = "fallback"


class HealthResponse(BaseModel):
    status: str
    graph_engine: bool
    vector_database: bool


class ReadyResponse(BaseModel):
    status: str
    ready: bool
    graph_engine: bool
    vector_database: bool
