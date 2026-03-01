from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import json


@dataclass
class Step:
    id: int
    agent: str
    action: str
    input: str
    output: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = True


@dataclass
class Session:
    id: str
    query: str
    created_at: str
    steps: List[Step] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    status: str = "running"
    events: List[Dict[str, Any]] = field(default_factory=list)
    messages: List[Dict[str, str]] = field(default_factory=list)
    total_tokens: int = 0
    total_cost: float = 0.0

    def add_step(self, agent: str, action: str, input: str, output: str, success: bool = True):
        step = Step(
            id=len(self.steps) + 1,
            agent=agent,
            action=action,
            input=input,
            output=output,
            success=success
        )
        self.steps.append(step)

    def add_event(self, event: Dict[str, Any]):
        self.events.append(event)

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def add_tokens(self, tokens: int, cost: float = 0.0):
        self.total_tokens += tokens
        self.total_cost += cost

    def get_context(self) -> Dict[str, Any]:
        """Get context for continuing conversation."""
        return {
            "session_id": self.id,
            "history": self.messages[-10:] if self.messages else [],
            "artifacts": self.artifacts
        }

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "query": self.query,
            "created_at": self.created_at,
            "start_time": self.created_at,
            "task": self.query,
            "events": self.events,
            "messages": self.messages,
            "steps": [
                {"id": s.id, "agent": s.agent, "action": s.action,
                 "input": s.input, "output": s.output, "success": s.success}
                for s in self.steps
            ],
            "artifacts": self.artifacts,
            "status": self.status,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost
        }


class StateManager:
    def __init__(self, storage_path: str = "data/sessions.json"):
        self.storage_path = storage_path
        self.sessions: Dict[str, Session] = {}
        self.load()

    def load(self):
        """Load sessions from disk."""
        import os
        from pathlib import Path
        path = Path(self.storage_path)
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                for sid, sess_data in data.items():
                    events = sess_data.get("events", [])
                    session = Session(
                        id=sess_data["id"],
                        query=sess_data.get("query", ""),
                        created_at=sess_data.get("created_at", sess_data.get("start_time", "")),
                        status=sess_data.get("status", "completed")
                    )
                    session.events = events
                    session.messages = sess_data.get("messages", [])
                    session.artifacts = sess_data.get("artifacts", {})
                    
                    # Fix: if session was "running" but old, mark as completed/error
                    if session.status == "running":
                        try:
                            created = datetime.fromisoformat(session.created_at)
                            age = (datetime.now() - created).total_seconds()
                            # If session is older than 5 minutes and still running, mark as completed
                            if age > 300:
                                session.status = "completed"
                        except:
                            session.status = "completed"
                    
                    self.sessions[sid] = session
            except Exception as e:
                print(f"Error loading sessions: {e}")

    def _ensure_storage_dir(self):
        import os
        from pathlib import Path
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)

    def create_session(self, query: str, session_id: Optional[str] = None) -> Session:
        session = Session(
            id=session_id if session_id else str(uuid.uuid4()),
            query=query,
            created_at=datetime.now().isoformat()
        )
        self.sessions[session.id] = session
        self._ensure_storage_dir()
        self.save()
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)

    def update_session(self, session_id: str):
        """Call after session changes to persist."""
        self._ensure_storage_dir()
        self.save()

    def save(self, path: str = None):
        path = path or self.storage_path
        with open(path, "w") as f:
            json.dump(
                {sid: s.to_dict() for sid, s in self.sessions.items()},
                f, indent=2
            )
