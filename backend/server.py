from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime

from kaggle_solver.core.orchestrator import Orchestrator

BASE_DIR = Path(__file__).parent.parent.resolve()
FRONTEND_DIR = BASE_DIR / "frontend"

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
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

orchestrator: Optional[Orchestrator] = None
websocket_connections: List[WebSocket] = []


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


@app.get("/")
def read_root():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "message": "Kaggle Solver API",
        "version": "1.0.0",
        "status": "running"
    }


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
        return {"error": "Session not found"}
    
    initial_events = session.events
    
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
        
        def event_callback(event):
            for ws in websocket_connections:
                try:
                    asyncio.create_task(ws.send_json(event))
                except Exception as e:
                    logger.error(f"WebSocket send error: {e}")
        
        orch.add_event_callback(event_callback)
        
        session = orch.run(request.query, request.session_id)
        
        return {
            "session_id": session.id,
            "status": session.status,
            "result": session.artifacts.get("result", "No result"),
            "duration": session.artifacts.get("total_time", 0)
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


@app.get("/api/sessions")
def list_sessions():
    orch = get_orchestrator()
    return orch.list_sessions()


@app.post("/api/session/{session_id}/stop")
def stop_session(session_id: str):
    orch = get_orchestrator()
    success = orch.stop_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "stopped"}


@app.get("/api/tools")
def list_tools():
    orch = get_orchestrator()
    return {"tools": orch.tool_registry.list_with_metadata()}


@app.get("/api/agents")
def list_agents():
    from kaggle_solver.agents.registry import AgentRegistry
    return {"agents": AgentRegistry.list_agents()}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_connections.append(websocket)
    logger.info(f"WebSocket connected: {websocket.client}")
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                
                if message.get("type") == "query":
                    orch = get_orchestrator()
                    
                    def event_callback(event):
                        asyncio.create_task(websocket.send_json(event))
                    
                    orch.add_event_callback(event_callback)
                    
                    query = message.get("query", "")
                    session = orch.run(query)
                    
                    await websocket.send_json({
                        "type": "session_created",
                        "session_id": session.id
                    })
                
                elif message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {websocket.client}")
    finally:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
