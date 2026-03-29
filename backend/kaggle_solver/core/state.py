from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import json
import logging
import threading

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
    """Thread-safe session data container.
    
    All modifications to session state are protected by a lock
    to prevent race conditions in concurrent access scenarios.
    """
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
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_step(self, agent: str, action: str, input: str, output: str, success: bool = True):
        """Add a step to the session (thread-safe)."""
        with self._lock:
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
        """Add an event to the session (thread-safe).
        
        Returns:
            The event ID assigned to this event.
        """
        with self._lock:
            self._event_counter += 1
            event["event_id"] = self._event_counter
            
            # Keep only recent events in memory
            if len(self.events) >= self.MAX_EVENTS_IN_MEMORY:
                self.events = self.events[-self.MAX_EVENTS_IN_MEMORY//2:]
            
            self.events.append(event)
            return self._event_counter
    
    def add_message(self, role: str, content: str):
        """Add a message to the session (thread-safe)."""
        with self._lock:
            # Keep only recent messages
            if len(self.messages) >= self.MAX_MESSAGES:
                self.messages = self.messages[-self.MAX_MESSAGES//2:]
            self.messages.append({"role": role, "content": content})

    def get_events_by_ids(self, event_ids: List[int]) -> List[Dict[str, Any]]:
        """Get events by their IDs (thread-safe)."""
        with self._lock:
            return [e for e in self.events if e.get("event_id") in event_ids]

    def get_latest_events(self, count: int = 3) -> List[Dict[str, Any]]:
        """Get the latest N events (thread-safe)."""
        with self._lock:
            return self.events[-count:] if self.events else []

    def add_tokens(self, tokens: int, cost: float = 0.0):
        """Add token usage to the session (thread-safe)."""
        with self._lock:
            self.total_tokens += tokens
            self.total_cost += cost

    def get_context(self) -> Dict[str, Any]:
        """Get context for continuing conversation (thread-safe)."""
        with self._lock:
            return {
                "session_id": self.id,
                "history": self.messages[-10:] if self.messages else [],
                "artifacts": self.artifacts.copy()
            }
    
    def set_artifact(self, key: str, value: Any):
        """Set a shared artifact (thread-safe)."""
        with self._lock:
            self.artifacts[key] = value
        logger.debug(f"Session {self.id}: Set artifact '{key}'")
    
    def get_artifact(self, key: str, default: Any = None) -> Any:
        """Get a shared artifact (thread-safe)."""
        with self._lock:
            return self.artifacts.get(key, default)
    
    def has_artifact(self, key: str) -> bool:
        """Check if an artifact exists (thread-safe)."""
        with self._lock:
            return key in self.artifacts
    
    def update_artifact(self, key: str, value: Any):
        """Update an existing artifact (thread-safe)."""
        with self._lock:
            if key in self.artifacts:
                self.artifacts[key] = value
                logger.debug(f"Session {self.id}: Updated artifact '{key}'")
            else:
                self.artifacts[key] = value
                logger.debug(f"Session {self.id}: Set artifact '{key}'")
    
    def delete_artifact(self, key: str):
        """Delete an artifact (thread-safe)."""
        with self._lock:
            if key in self.artifacts:
                del self.artifacts[key]
                logger.debug(f"Session {self.id}: Deleted artifact '{key}'")
    
    def get_all_artifacts(self) -> Dict[str, Any]:
        """Get all artifacts (thread-safe)."""
        with self._lock:
            return self.artifacts.copy()
    
    def clear_artifacts(self):
        """Clear all artifacts (thread-safe)."""
        with self._lock:
            self.artifacts.clear()
        logger.debug(f"Session {self.id}: Cleared all artifacts")

    def to_dict(self) -> Dict:
        """Convert session to dictionary (thread-safe)."""
        with self._lock:
            return {
                "id": self.id,
                "query": self.query,
                "created_at": self.created_at,
                "start_time": self.created_at,
                "task": self.query,
                "events": list(self.events),
                "messages": list(self.messages),
                "steps": [
                    {"id": s.id, "agent": s.agent, "action": s.action,
                     "input": s.input, "output": s.output, "success": s.success}
                    for s in self.steps
                ],
                "artifacts": dict(self.artifacts),
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
                    
                    # Restore steps
                    steps_data = sess_data.get("steps", [])
                    session.steps = [
                        Step(
                            id=s.get("id", i+1),
                            agent=s.get("agent", ""),
                            action=s.get("action", ""),
                            input=s.get("input", ""),
                            output=s.get("output", ""),
                            success=s.get("success", True)
                        )
                        for i, s in enumerate(steps_data)
                    ]
                    
                    # Restore event counter to avoid duplicate IDs
                    if events:
                        max_event_id = max((e.get("event_id", 0) for e in events), default=0)
                        session._event_counter = max_event_id
                    
                    # Restore token usage
                    session.total_tokens = sess_data.get("total_tokens", 0)
                    session.total_cost = sess_data.get("total_cost", 0.0)
                    
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
                logger.error(f"Error loading sessions: {e}")

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
