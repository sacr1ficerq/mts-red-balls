from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import logging
import json
import threading
import time
from pathlib import Path
from contextlib import asynccontextmanager

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


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 10, max_concurrent: int = 5):
        self.requests_per_minute = requests_per_minute
        self.max_concurrent = max_concurrent
        self.requests: Dict[str, List[datetime]] = defaultdict(list)
        self.active_requests: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
    
    def try_acquire(self, client_id: str) -> bool:
        """Atomically check if request is allowed and record it."""
        with self._lock:
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)
            
            if self.active_requests[client_id] >= self.max_concurrent:
                return False
            
            self.requests[client_id] = [
                t for t in self.requests[client_id] if t > minute_ago
            ]
            
            if len(self.requests[client_id]) >= self.requests_per_minute:
                return False
            
            # Atomically record the request
            self.requests[client_id].append(now)
            self.active_requests[client_id] += 1
            return True
    
    def check(self, client_id: str) -> bool:
        """Check if request is allowed (without recording)."""
        return self.try_acquire(client_id)
    
    def record(self, client_id: str):
        """Record a request (for backward compatibility)."""
        self.try_acquire(client_id)
    
    def release(self, client_id: str):
        with self._lock:
            self.active_requests[client_id] = max(0, self.active_requests[client_id] - 1)


rate_limiter = RateLimiter(requests_per_minute=10, max_concurrent=5)

# Thread pool for background agent tasks
from concurrent.futures import ThreadPoolExecutor

task_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="agent_task")


app = FastAPI(
    title="Kaggle Solver API",
    description="Multi-agent system for solving Kaggle competitions and data analysis tasks",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Kaggle Solver API")
    yield
    logger.info("Shutting down Kaggle Solver API")


app.router.lifespan_context = lifespan

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
_orchestrator: Optional[Orchestrator] = None
_orchestrator_lock = threading.Lock()


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        with _orchestrator_lock:
            if _orchestrator is None:
                _orchestrator = Orchestrator()
    return _orchestrator


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = Field(None, max_length=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Analyze this dataset and create a model"
            }
        }


@app.get("/api/health")
def health_check():
    """Comprehensive health check endpoint."""
    health = {
        "status": "healthy",
        "checks": {}
    }
    
    # Check workspace directory
    try:
        from pathlib import Path
        workspace = Path("workspace")
        if workspace.exists() and workspace.is_dir():
            health["checks"]["workspace"] = "ok"
        else:
            health["checks"]["workspace"] = "missing"
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["workspace"] = f"error: {e}"
        health["status"] = "degraded"
    
    # Check logs directory
    try:
        logs_dir = Path("logs")
        if logs_dir.exists() or logs_dir.parent.exists():
            health["checks"]["logs"] = "ok"
        else:
            health["checks"]["logs"] = "missing"
    except Exception as e:
        health["checks"]["logs"] = f"error: {e}"
    
    # Check data directory
    try:
        data_dir = Path("data")
        if data_dir.exists():
            health["checks"]["data"] = "ok"
        else:
            health["checks"]["data"] = "not_initialized"
    except Exception as e:
        health["checks"]["data"] = f"error: {e}"
    
    # Check active sessions
    try:
        orch = get_orchestrator()
        active_count = len([s for s in orch.state.sessions.values() if s.status == "running"])
        health["checks"]["sessions"] = f"{active_count} active"
    except Exception as e:
        health["checks"]["sessions"] = f"error: {e}"
        health["status"] = "degraded"
    
    if health["status"] == "degraded":
        health["status"] = "degraded"
    
    return health


@app.get("/api/sse/{session_id}")
async def sse_session_events(session_id: str):
    """Server-Sent Events stream for session events."""
    from fastapi.responses import StreamingResponse, JSONResponse
    import asyncio
    
    # Validate session_id
    if not session_id or not session_id.replace("-", "").replace("_", "").isalnum():
        return JSONResponse({"error": "Invalid session ID"}, status_code=400)
    
    orch = get_orchestrator()
    session = orch.get_session(session_id)
    if not session:
        return {"error": "Session not found"}, 404
    
    initial_events = list(session.events)
    max_duration = 3600  # 1 hour max
    start_time = time.time()
    
    async def event_generator():
        nonlocal start_time
        try:
            # Send initial events
            for event in initial_events:
                yield f"data: {json.dumps(event)}\n\n"
            
            # Then stream new events
            last_idx = len(initial_events)
            while True:
                # Check for timeout
                if time.time() - start_time > max_duration:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Connection timeout'})}\n\n"
                    break
                
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
        except asyncio.CancelledError:
            # Client disconnected - cleanup
            logger.info(f"SSE connection closed for session {session_id}")
            raise
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


def get_client_id(request: Request) -> str:
    """Get client identifier from request."""
    return request.client.host if request.client else "unknown"


def validate_session_id(session_id: str) -> bool:
    """Validate session_id format to prevent injection attacks."""
    if not session_id:
        return False
    # Allow only alphanumeric, hyphens, underscores
    return all(c.isalnum() or c in '-_' for c in session_id)


@app.post("/api/query")
async def query(request: QueryRequest, req: Request):
    client_id = get_client_id(req)
    
    if not rate_limiter.try_acquire(client_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    
    try:
        orch = get_orchestrator()
    except Exception as e:
        rate_limiter.release(client_id)
        raise
    
    try:
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
        
        # Create sandbox for this session with preinstalled packages
        from kaggle_solver.sandbox import Sandbox
        session_sandbox_path = orch.base_sandbox_path / session_id
        session_sandbox = Sandbox(session_sandbox_path, timeout=orch.config.sandbox.timeout, preinstall=True)
        orch._session_sandboxes[session_id] = session_sandbox
        
        # Run in BACKGROUND THREAD - return immediately
        import threading
        def run_task_background():
            try:
                coordinator = orch.create_agent(
                    name="Coordinator",
                    role="Plan and delegate tasks",
                    tools=["delegate", "message", "tool"],
                    event_callback=event_callback,
                    sandbox=session_sandbox
                )
                result = coordinator.run(request.query, {"session": session})
                session.status = "completed" if result.success else "error"
                session.artifacts["result"] = result.output
                session.artifacts["duration"] = result.duration
                session.artifacts["steps"] = result.steps
                orch.state.save()
                logger.info(f"Session {session_id} completed with status: {session.status}")
            except Exception as e:
                logger.error(f"Background task error: {e}")
                session.status = "error"
                session.artifacts["error"] = str(e)
                orch.state.save()
        
        thread = threading.Thread(target=run_task_background)
        thread.start()
        
        # Return immediately with session_id
        return {
            "session_id": session_id,
            "status": "running",
            "events": session.events,
            "result": None
        }
    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        if 'session' in locals() and session:
            session.status = "error"
            session.artifacts["error"] = str(e)
            orch.state.save()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        rate_limiter.release(client_id)


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    if not validate_session_id(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")
    orch = get_orchestrator()
    session = orch.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


class ContinueRequest(BaseModel):
    message: str


@app.post("/api/session/{session_id}/continue")
async def continue_session(session_id: str, request: ContinueRequest):
    if not validate_session_id(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")
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
                logger.error(f"Background continue error: {e}", exc_info=True)
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
        logger.error(f"Continue error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class OptionSelectionRequest(BaseModel):
    selected: str


@app.post("/api/session/{session_id}/select")
async def select_option(session_id: str, request: OptionSelectionRequest):
    if not validate_session_id(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")
    try:
        orch = get_orchestrator()
        session = orch.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Add user selection as a message to the session
        user_message = f"User selected: {request.selected}"
        
        # Emit event for the selection
        event = {
            "type": "user_selection",
            "data": {"selected": request.selected},
            "agent": "User"
        }
        session.add_event(event)
        
        # Continue session with the selection
        def run_in_background():
            try:
                orch.continue_session(session_id, user_message)
            except Exception as e:
                logger.error(f"Background select error: {e}", exc_info=True)
                session.status = "error"
                session.artifacts["error"] = str(e)

        import threading
        thread = threading.Thread(target=run_in_background, daemon=True)
        thread.start()

        return {
            "session_id": session.id,
            "status": "running",
            "result": f"Selected: {request.selected}"
        }
    except Exception as e:
        logger.error(f"Select error: {e}", exc_info=True)
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
    if not validate_session_id(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")
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
