from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import json
import logging

from kaggle_solver.constants import StateConstants

logger = logging.getLogger(__name__)


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
    MAX_EVENTS_IN_MEMORY = StateConstants.MAX_EVENTS_IN_MEMORY
    MAX_MESSAGES = StateConstants.MAX_EVENTS_PER_SESSION
    
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
    _event_counter: int = 0

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

    def add_event(self, event: Dict[str, Any]) -> int:
        self._event_counter += 1
        event["event_id"] = self._event_counter
        
        # Keep only recent events in memory
        if len(self.events) >= self.MAX_EVENTS_IN_MEMORY:
            self.events = self.events[-self.MAX_EVENTS_IN_MEMORY//2:]
        
        self.events.append(event)
        return self._event_counter
    
    def add_message(self, role: str, content: str):
        # Keep only recent messages
        if len(self.messages) >= self.MAX_MESSAGES:
            self.messages = self.messages[-self.MAX_MESSAGES//2:]
        self.messages.append({"role": role, "content": content})

    def get_events_by_ids(self, event_ids: List[int]) -> List[Dict[str, Any]]:
        return [e for e in self.events if e.get("event_id") in event_ids]

    def get_latest_events(self, count: int = 3) -> List[Dict[str, Any]]:
        return self.events[-count:] if self.events else []

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
        import logging
        log = logging.getLogger(__name__)
        path = path or self.storage_path
        try:
            data = {sid: s.to_dict() for sid, s in self.sessions.items()}
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            
            log.debug(f"Saved {len(data)} sessions to {path}")
            
            # Also save a request/response log for debugging
            log_path = path.replace(".json", "_requests.log")
            with open(log_path, "a") as log_file:
                for sid, s in data.items():
                    if s.get("status") == "running" and s.get("steps"):
                        for step in s.get("steps", []):
                            log_file.write(f"{s.get('created_at')} | {sid[:8]} | {step.get('agent')} | {step.get('action')} | {step.get('input', '')[:50]} -> {str(step.get('output', ''))[:100]}\n")
        except Exception as e:
            log.warning(f"Failed to save sessions: {e}")
