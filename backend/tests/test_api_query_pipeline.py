import threading
from unittest.mock import Mock

from fastapi.testclient import TestClient

import server


class DummySession:
    def __init__(self, session_id: str, query: str):
        self.id = session_id
        self.query = query
        self.status = "running"
        self.events = []
        self.artifacts = {}


class DummyState:
    def __init__(self):
        self.sessions = {}
        self.save = Mock()

    def create_session(self, query, session_id=None):
        sid = session_id or "test-session-id"
        session = DummySession(sid, query)
        self.sessions[sid] = session
        return session


class InlineExecutor:
    def submit(self, fn, *args, **kwargs):
        worker = threading.Thread(target=fn, args=args, kwargs=kwargs)
        worker.start()
        worker.join()
        fut = Mock()
        fut.result = Mock(return_value=None)
        return fut


def test_query_endpoint_runs_full_orchestrator_pipeline(monkeypatch):
    orch = Mock()
    orch.state = DummyState()
    orch.get_session = Mock(side_effect=lambda sid: orch.state.sessions.get(sid))
    run_calls = []

    async def fake_run(query, session_id=None):
        run_calls.append((query, session_id))
        session = orch.state.sessions[session_id]
        session.events.extend(
            [
                {"type": "system", "data": {"message": f"Starting: {query}"}},
                {"type": "result", "data": {"content": "ok"}},
            ]
        )
        session.status = "completed"
        return session

    orch.run = fake_run

    monkeypatch.setattr(server, "get_orchestrator", lambda: orch)
    monkeypatch.setattr(server, "task_executor", InlineExecutor())

    client = TestClient(server.app)
    response = client.post("/api/query", json={"query": "write hello world in rust"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "test-session-id"
    assert payload["status"] == "running"

    assert run_calls == [("write hello world in rust", "test-session-id")]

    session = orch.state.sessions["test-session-id"]
    assert session.status == "completed"
    assert any(event.get("type") == "result" for event in session.events)
