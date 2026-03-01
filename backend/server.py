from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime

from kaggle_solver.core.config import ConfigHolder, Config
from kaggle_solver.core.orchestrator import Orchestrator
import kaggle_solver.tools  # noqa: F401 - triggers tool registration

BASE_DIR = Path(__file__).parent.parent.resolve()
FRONTEND_DIR = BASE_DIR / "frontend"
CONFIG_PATH = Path(__file__).parent / "config.yaml"

ConfigHolder().set_config(Config.load(str(CONFIG_PATH)))

Path("logs").mkdir(exist_ok=True)
log_file = f"logs/server_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kaggle Solver API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount("/src", StaticFiles(directory=str(FRONTEND_DIR / "src")), name="src")


@app.get("/")
def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Kaggle Solver API", "version": "1.0.0", "status": "running"}


@app.get("/index.html")
def serve_index_html():
    return FileResponse(FRONTEND_DIR / "index.html")


# Global orchestrator instance
orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global orchestrator
    if orchestrator is None:
        orchestrator = Orchestrator()
    return orchestrator


class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Kaggle Solver API")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Kaggle Solver API")


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}


@app.get("/api/sse/{session_id}")
async def sse_session_events(session_id: str):
    """Server-Sent Events stream for session events."""
    from fastapi.responses import StreamingResponse
    import asyncio
    
    orch = get_orchestrator()
    session = orch.get_session(session_id)
    if not session:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Session not found"}, status_code=404)
    
    initial_events = list(session.events)
    
    async def event_generator():
        # Send initial events
        for event in initial_events:
            yield f"data: {json.dumps(event)}\n\n"
        
        # Then stream new events
        last_idx = len(initial_events)
        while True:
            await asyncio.sleep(0.5)
            session = orch.get_session(session_id)
            if not session:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Session not found'})}\n\n"
                break
            if len(session.events) > last_idx:
                for event in session.events[last_idx:]:
                    yield f"data: {json.dumps(event)}\n\n"
                last_idx = len(session.events)
            
            # Stop when session is done
            if session.status != "running":
                yield f"data: {json.dumps({'type': 'session_done', 'status': session.status})}\n\n"
                break
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/api/query")
async def query(request: QueryRequest):
    try:
        orch = get_orchestrator()
        
        # Create session FIRST
        session = orch.state.create_session(request.query, request.session_id)
        session_id = session.id
        
        # Set up event callback for this session
        def event_callback(event):
            event["session_id"] = session_id
            session.add_event(event)
            session.add_step(
                agent=event.get("agent", "System"),
                action=event.get("type", "event"),
                input=str(event.get("data", {}).get("input", "")),
                output=str(event.get("data", {}))
            )
        
        # Create sandbox for this session
        from kaggle_solver.sandbox import Sandbox
        session_sandbox_path = orch.base_sandbox_path / session_id
        session_sandbox = Sandbox(session_sandbox_path, timeout=orch.config.sandbox.timeout)
        orch._session_sandboxes[session_id] = session_sandbox
        
        # Run in background
        def run_in_background():
            try:
                coordinator = orch.create_agent(
                    name="Coordinator",
                    role="Plan and delegate tasks",
                    tools=["delegate", "message", "tool"],
                    event_callback=event_callback,
                    sandbox=session_sandbox
                )
                result = coordinator.run(request.query, {"session_id": session_id})
                session.status = "completed" if result.success else "error"
                session.artifacts["result"] = result.output
                session.artifacts["duration"] = result.duration
                session.artifacts["steps"] = result.steps
            except Exception as e:
                logger.error(f"Background task error: {e}")
                session.status = "error"
                session.artifacts["error"] = str(e)
        
        import threading
        thread = threading.Thread(target=run_in_background, daemon=True)
        thread.start()
        
        return {
            "session_id": session_id,
            "status": "running",
            "result": "Task started"
        }
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    orch = get_orchestrator()
    session = orch.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


class ContinueRequest(BaseModel):
    message: str


@app.post("/api/session/{session_id}/continue")
async def continue_session(session_id: str, request: ContinueRequest):
    try:
        orch = get_orchestrator()
        session = orch.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Run in background thread
        def run_in_background():
            try:
                orch.continue_session(session_id, request.message)
            except Exception as e:
                logger.error(f"Background continue error: {e}")
                session.status = "error"
                session.artifacts["error"] = str(e)

        import threading
        thread = threading.Thread(target=run_in_background, daemon=True)
        thread.start()

        return {
            "session_id": session.id,
            "status": "running",
            "result": "Task continued"
        }
    except Exception as e:
        logger.error(f"Continue error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
def list_sessions():
    orch = get_orchestrator()
    return orch.list_sessions()


@app.post("/api/sessions/clear")
def clear_sessions():
    orch = get_orchestrator()
    orch.clear_sessions()
    return {"status": "cleared"}


@app.post("/api/session/{session_id}/stop")
def stop_session(session_id: str):
    orch = get_orchestrator()
    success = orch.stop_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "stopped"}


@app.get("/api/workspace/files")
def list_workspace_files():
    """List files in the workspace directory as a tree."""
    orch = get_orchestrator()
    try:
        files = orch.sandbox.list(".")
        
        def build_tree(paths):
            tree = {}
            for p in paths:
                parts = p.strip('/').split('/')
                current = tree
                for part in parts:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
            return tree
        
        def flatten_tree(tree, prefix=""):
            result = []
            for name, children in sorted(tree.items()):
                path = prefix + "/" + name if prefix else name
                if children:
                    result.append({"name": name, "path": path, "type": "folder"})
                    result.extend(flatten_tree(children, path))
                else:
                    result.append({"name": name, "path": path, "type": "file"})
            return result
        
        tree = build_tree(files)
        flat = flatten_tree(tree)
        
        return {"files": flat, "root": str(orch.sandbox.root), "tree": tree}
    except Exception as e:
        return {"files": [], "tree": {}, "error": str(e)}


@app.get("/api/workspace/read")
def read_workspace_file(path: str = ""):
    """Read a file from workspace."""
    orch = get_orchestrator()
    try:
        if not path:
            return {"error": "No path provided", "content": ""}
        
        # Security: only allow reading files, not directories
        # Check if path is a directory using sandbox.exists and sandbox.list_dir
        # Note: sandbox.read will fail if it's a directory anyway, but explicit check is better
        try:
            # If list_dir succeeds and returns items, it's a directory
            # If it returns empty list, it could be an empty directory or a file (depending on implementation)
            # Better to rely on sandbox.read raising IsADirectoryError or similar
            content = orch.sandbox.read(path)
            return {"path": path, "content": content}
        except IsADirectoryError:
             return {"error": "Path is a directory", "content": ""}
        except Exception as e:
             # Fallback check
             if "Is a directory" in str(e):
                 return {"error": "Path is a directory", "content": ""}
             raise e

    except Exception as e:
        return {"error": str(e), "content": ""}


@app.get("/api/tools")
def list_tools():
    orch = get_orchestrator()
    return {"tools": orch.tool_registry.list_with_metadata()}


@app.get("/api/agents")
def list_agents():
    from kaggle_solver.agents.registry import AgentRegistry
    return {"agents": AgentRegistry.list_agents()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
