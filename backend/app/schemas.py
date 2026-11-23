import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class HintRequest(BaseModel):
    problem_id: str = Field(min_length=1)
    user_handle: str = Field(min_length=1)
    max_bridges: int = Field(default=3, ge=1, le=10)

    @field_validator("problem_id")
    @classmethod
    def normalize_problem_id(cls, value: str) -> str:
        value = value.strip().upper()
        if "_" not in value:
            match = re.fullmatch(r"(\d+)([A-Z]\d*)", value)
            if match:
                value = f"{match.group(1)}_{match.group(2)}"
        return value

    @field_validator("user_handle")
    @classmethod
    def normalize_handle(cls, value: str) -> str:
        return value.strip()


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
    concept_tag: str
    conceptual_nudge: str
    strategy_hint: str
    complexity_nudge: str
    bridge_rationale: str


class HintResponse(BaseModel):
    status: str
    problem_id: str
    user_handle: str
    missing_concepts: List[str]
    bridge_problems: List[BridgeScore] = []
    hint: StructuredHint
    provider: str
    fallback_used: bool
    timings_ms: Dict[str, float]


class HealthResponse(BaseModel):
    status: str
    graph_engine: bool
    vector_database: bool


class ReadyResponse(BaseModel):
    status: str
    ready: bool
    graph_engine: bool
    vector_database: bool
