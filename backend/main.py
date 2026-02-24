from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os

from kaggle_solver.core.orchestrator import Orchestrator

app = FastAPI(title="Kaggle Solver API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global orchestrator
    if orchestrator is None:
        orchestrator = Orchestrator()
    return orchestrator


class QueryRequest(BaseModel):
    query: str


@app.get("/")
def read_root():
    return {"message": "Kaggle Solver API", "status": "running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from backend!"}


@app.post("/api/query")
def query(request: QueryRequest):
    try:
        orch = get_orchestrator()
        session = orch.run(request.query)
        return {
            "session_id": session.id,
            "status": session.status,
            "result": session.steps[-1].output if session.steps else "No result"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    orch = get_orchestrator()
    session = orch.state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


@app.get("/api/tools")
def list_tools():
    from kaggle_solver.tools.registry import ToolRegistry
    return {"tools": ToolRegistry.list_tools()}
