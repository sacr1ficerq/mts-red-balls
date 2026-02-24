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

# Session logging setup
LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class Orchestrator:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load()
        self.state = StateManager()
        self.llm = LLM()
        self.sandbox = Sandbox(Path(self.config.sandbox.root))
        self.tool_registry = ToolRegistry
        self._event_callbacks: List[Callable] = []

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
        event_callback: Optional[Callable] = None
    ) -> BaseAgent:
        # Create agent factory closure for delegation
        def agent_factory_fn(**kwargs):
            agent_name = kwargs.get("name", kwargs.get("agent_name", ""))
            agent_role = kwargs.get("role", kwargs.get("agent_role", ""))
            agent_tools = kwargs.get("tools", kwargs.get("agent_tools", ["tool"]))
            agent_event_callback = kwargs.get("event_callback", kwargs.get("agent_event_callback", None))
            return self.create_agent(agent_name, agent_role, agent_tools, agent_event_callback)
        
        if name in AgentRegistry.list_agents():
            config = AgentConfig(
                name=name,
                role=role,
                tools=tools,
                model=self.config.llm.model,
                max_iterations=10,
                temperature=self.config.llm.temperature
            )
            return AgentRegistry.create(
                name, config, self.llm, self.sandbox, self.tool_registry, event_callback, agent_factory_fn
            )

        class DynamicAgent(BaseAgent):
            def system_prompt(self) -> str:
                return f"You are {name}. {role}"

        config = AgentConfig(
            name=name,
            role=role,
            tools=tools,
            model=self.config.llm.model,
            max_iterations=10,
            temperature=self.config.llm.temperature
        )
        
        return DynamicAgent(config, self.llm, self.sandbox, self.tool_registry, event_callback)

    def run(self, query: str, session_id: Optional[str] = None) -> Session:
        session = self.state.create_session(query, session_id)
        
        # Session log file
        session_log_file = LOG_DIR / f"session_{session.id}.log"
        
        def log_event(event):
            # Write to session log file
            try:
                with open(session_log_file, "a") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
            except Exception:
                pass
            
            # Also emit to websocket
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
        
        def event_callback(event):
            try:
                log_event(event)
            except Exception as e:
                logger.warning(f"Event callback error: {e}")

        coordinator = self.create_agent(
            name="Coordinator",
            role="Plan and delegate tasks to solve the user's request",
            tools=["delegate", "message", "tool"],
            event_callback=event_callback
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
