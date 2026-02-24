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
            "status": self.status
        }


class StateManager:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}

    def create_session(self, query: str, session_id: Optional[str] = None) -> Session:
        session = Session(
            id=session_id if session_id else str(uuid.uuid4()),
            query=query,
            created_at=datetime.now().isoformat()
        )
        self.sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(
                {sid: s.to_dict() for sid, s in self.sessions.items()},
                f, indent=2
            )
