from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import logging
import time
import json

from kaggle_solver.core.state import StateManager, Session
from kaggle_solver.core.config import Config
from kaggle_solver.llm import LLM
from kaggle_solver.sandbox import Sandbox
from kaggle_solver.tools.registry import ToolRegistry
from kaggle_solver.tools import console_tool, files_tool, search_tool
from kaggle_solver.agents.base import BaseAgent, AgentConfig, AgentResult
from kaggle_solver.agents.registry import AgentRegistry

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _create_agent_factory(orchestrator, event_callback):
    def agent_factory_fn(**kwargs):
        agent_name = kwargs.get("name", "")
        agent_role = kwargs.get("role", "")
        agent_tools = kwargs.get("tools", ["tool"])
        return orchestrator.create_agent(agent_name, agent_role, agent_tools, event_callback)
    return agent_factory_fn


class Orchestrator:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load()
        self.state = StateManager()
        self.llm = LLM()
        # Sandbox root is the base directory. Sessions will use subdirectories.
        self.base_sandbox_path = Path(self.config.sandbox.root)
        self.base_sandbox_path.mkdir(parents=True, exist_ok=True)
        # Default sandbox for general tasks (or backward compatibility)
        self.sandbox = Sandbox(self.base_sandbox_path, timeout=self.config.sandbox.timeout)
        self.tool_registry = ToolRegistry
        self._event_callbacks: List[Callable] = []
        self._session_sandboxes: Dict[str, Sandbox] = {}

    def add_event_callback(self, callback: Callable):
        self._event_callbacks.append(callback)

    def _emit_event(self, session_id: str, event: Dict[str, Any]):
        event["session_id"] = session_id
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

    def create_agent(
        self,
        name: str,
        role: str,
        tools: List[str],
        event_callback: Optional[Callable] = None,
        agent_factory: Optional[Callable] = None,
        sandbox: Optional[Sandbox] = None
    ) -> BaseAgent:
        if agent_factory is None:
            # We need to pass the sandbox to the factory so sub-agents use the same sandbox
            def agent_factory_fn(**kwargs):
                agent_name = kwargs.get("name", "")
                agent_role = kwargs.get("role", "")
                agent_tools = kwargs.get("tools", ["tool"])
                return self.create_agent(agent_name, agent_role, agent_tools, event_callback, None, sandbox)
            agent_factory = agent_factory_fn
        
        current_sandbox = sandbox or self.sandbox
        
        max_iterations = 10
        if name in self.config.agents:
            max_iterations = self.config.agents[name].max_iterations
        
        if name in AgentRegistry.list_agents():
            agent_config = AgentConfig(
                name=name,
                role=role,
                tools=tools,
                model=self.config.llm.model,
                max_iterations=max_iterations,
                temperature=self.config.llm.temperature
            )
            return AgentRegistry.create(
                name, agent_config, self.llm, current_sandbox, self.tool_registry, event_callback, agent_factory
            )

        class DynamicAgent(BaseAgent):
            def system_prompt(self) -> str:
                return f"You are {name}. {role}"

        agent_config = AgentConfig(
            name=name,
            role=role,
            tools=tools,
            model=self.config.llm.model,
            max_iterations=max_iterations,
            temperature=self.config.llm.temperature
        )
        
        return DynamicAgent(agent_config, self.llm, current_sandbox, self.tool_registry, event_callback, agent_factory)

    def _create_session_callback(self, session: Session) -> Callable:
        session_log_file = LOG_DIR / f"session_{session.id}.log"
        
        def log_event(event: Dict[str, Any]):
            try:
                with open(session_log_file, "a") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
            except Exception:
                pass
            try:
                self._emit_event(session.id, event)
            except Exception:
                pass
            session.add_event(event)
            session.add_step(
                agent=event.get("agent", "System"),
                action=event.get("type", "event"),
                input=str(event.get("data", {}).get("input", "")),
                output=str(event.get("data", {}))
            )
        
        return log_event

    def run(self, query: str, session_id: Optional[str] = None) -> Session:
        session = self.state.create_session(query, session_id)
        event_callback = self._create_session_callback(session)

        # Create session-specific sandbox
        session_sandbox_path = self.base_sandbox_path / session.id
        session_sandbox = Sandbox(session_sandbox_path, timeout=self.config.sandbox.timeout)
        self._session_sandboxes[session.id] = session_sandbox

        coordinator = self.create_agent(
            name="Coordinator",
            role="Plan and delegate tasks",
            tools=["delegate", "message", "tool"],
            event_callback=event_callback,
            sandbox=session_sandbox
        )

        start_time = time.time()
        
        try:
            result = coordinator.run(query, {"session_id": session.id})
            session.status = "completed" if result.success else "error"
            session.artifacts["result"] = result.output
            session.artifacts["duration"] = result.duration
            session.artifacts["steps"] = result.steps
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            session.status = "error"
            session.artifacts["error"] = str(e)
        
        session.artifacts["total_time"] = time.time() - start_time

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self.state.get_session(session_id)

    def continue_session(self, session_id: str, message: str) -> Session:
        session = self.state.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.add_message("user", message)
        event_callback = self._create_session_callback(session)

        # Retrieve or recreate session sandbox
        if session_id in self._session_sandboxes:
            session_sandbox = self._session_sandboxes[session_id]
        else:
            session_sandbox_path = self.base_sandbox_path / session.id
            session_sandbox = Sandbox(session_sandbox_path, timeout=self.config.sandbox.timeout)
            self._session_sandboxes[session.id] = session_sandbox

        coordinator = self.create_agent(
            name="Coordinator",
            role="Continue conversation with context",
            tools=["delegate", "message", "tool"],
            event_callback=event_callback,
            sandbox=session_sandbox
        )
        
        for msg in session.messages[:-1]:
            coordinator.add_message(msg["role"], msg["content"])
        
        start_time = time.time()
        session.status = "running"
        
        try:
            context = session.get_context()
            result = coordinator.run(message, context)
            session.status = "completed" if result.success else "error"
            session.artifacts["result"] = result.output
            session.artifacts["duration"] = result.duration
            session.artifacts["steps"] = result.steps
            session.add_message("assistant", result.output)
        except Exception as e:
            logger.error(f"Continue session error: {e}")
            session.status = "error"
            session.artifacts["error"] = str(e)
        
        session.artifacts["total_time"] = time.time() - start_time
        return session

    def list_sessions(self) -> Dict[str, Any]:
        active = {k: v.to_dict() for k, v in self.state.sessions.items() if v.status == "running"}
        historical = [v.to_dict() for v in self.state.sessions.values() if v.status != "running"]
        return {"active": active, "historical": historical}

    def stop_session(self, session_id: str) -> bool:
        session = self.state.get_session(session_id)
        if session:
            session.status = "cancelled"
            return True
        return False
