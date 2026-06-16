from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import vector_engine
import graph_engine

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HintRequest(BaseModel):
    problem_id: str
    user_handle: str

@app.get("/")
def root():
    return {"status": "Hint Engine Backend Online"}

@app.post("/api/hint")
async def generate_hint(request: HintRequest):
    target_id = request.problem_id
    handle = request.user_handle
    
    # 1. Ask C++ Engine for the exact conceptual bottleneck
    missing_concepts = graph_engine.find_missing_concepts(handle, target_id)
    
    # 2. Ask Vector Engine for the nearest semantic bridge problem
    bridge_url, bridge_id = vector_engine.get_bridge_problem(target_id)
    
    # Handle the "Missing == 0" Advanced User Case
    if len(missing_concepts) == 0:
        message = "You already know all the mathematical concepts required for this problem! Focus on implementation and constraints."
    elif "Graph Not Mapped" in missing_concepts[0] or "C++ Engine Offline" in missing_concepts[0]:
        message = f"We successfully found a semantic bridge problem, but {target_id} is not manually mapped in the dependency graph yet."
        missing_concepts = []
    else:
        message = f"Based on your Codeforces history, to solve {target_id}, you are missing these prerequisites: {', '.join(missing_concepts)}"

    return {
        "status": "success",
        "problem_id": target_id,
        "message": message,
        "missing_concepts": missing_concepts,
        "bridge_problem": bridge_url or "#",
        "bridge_id": bridge_id or "Unknown"
    }