from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import logging
import time
import json
from datetime import datetime

from kaggle_solver.constants import (
    AgentType,
    AgentConstants,
    StateConstants,
    LoggingConstants,
)
from kaggle_solver.core.state import StateManager, Session
from kaggle_solver.core.config import Config
from kaggle_solver.llm import LLM
from kaggle_solver.sandbox import Sandbox
from kaggle_solver.tools.registry import ToolRegistry
from kaggle_solver.agents.base import BaseAgent, AgentConfig, AgentResult
from kaggle_solver.agents.registry import AgentRegistry

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).parent.parent.parent.parent / LoggingConstants.LOG_DIR
LOG_DIR.mkdir(exist_ok=True)


def _create_agent_factory(orchestrator, event_callback, session=None):
    def agent_factory_fn(**kwargs):
        agent_name = kwargs.get("name", "")
        agent_role = kwargs.get("role", "")
        agent_tools = kwargs.get("tools", ["tool"])
        return orchestrator.create_agent(
            agent_name, agent_role, agent_tools, event_callback, session=session
        )

    return agent_factory_fn


class Orchestrator:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load()
        storage_path = Path(__file__).parent.parent.parent / "data" / "sessions.json"
        self.state = StateManager(str(storage_path))
        self.llm = LLM(requests_per_minute=self.config.llm.requests_per_minute)
        # Sandbox root is the base directory. Sessions will use subdirectories.
        sandbox_root = self.config.sandbox.root
        if not Path(sandbox_root).is_absolute():
            sandbox_root = Path(__file__).parent.parent.parent / sandbox_root
        self.base_sandbox_path = Path(sandbox_root).resolve()
        self.base_sandbox_path.mkdir(parents=True, exist_ok=True)
        # Default sandbox for general tasks (or backward compatibility)
        # preinstall is controlled by Sandbox.ENABLE_PREINSTALL class constant
        self.sandbox = Sandbox(
            self.base_sandbox_path, timeout=self.config.sandbox.timeout
        )
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
        sandbox: Optional[Sandbox] = None,
        session: Optional[Any] = None,
    ) -> BaseAgent:
        if agent_factory is None:

            def agent_factory_fn(**kwargs):
                agent_name = kwargs.get("name", "")
                agent_role = kwargs.get("role", "")
                agent_tools = kwargs.get("tools", ["tool"])
                return self.create_agent(
                    agent_name,
                    agent_role,
                    agent_tools,
                    event_callback,
                    agent_factory_fn,
                    sandbox,
                    session,
                )

            agent_factory = agent_factory_fn

        current_sandbox = sandbox or self.sandbox

        max_iterations = 10
        if name in self.config.agents:
            max_iterations = self.config.agents[name].max_iterations

        # Get per-agent model settings from SettingsManager
        agent_model = None
        agent_temperature = None
        agent_max_tokens = None
        try:
            from kaggle_solver.core.settings import SettingsManager

            settings = SettingsManager().get_settings()
            agent_config_from_settings = settings.get_agent_model(name)
            if agent_config_from_settings:
                agent_model = agent_config_from_settings.model
                agent_temperature = agent_config_from_settings.temperature
                agent_max_tokens = agent_config_from_settings.max_tokens
        except Exception as e:
            logger.debug(f"Could not get agent model from settings: {e}")

        # Use settings model if available, otherwise fall back to config
        model = agent_model or self.config.llm.model
        temperature = (
            agent_temperature
            if agent_temperature is not None
            else self.config.llm.temperature
        )

        if name in AgentRegistry.list_agents():
            agent_config = AgentConfig(
                name=name,
                role=role,
                tools=tools,
                model=model,
                max_iterations=max_iterations,
                temperature=temperature,
            )
            return AgentRegistry.create(
                name,
                agent_config,
                self.llm,
                current_sandbox,
                self.tool_registry,
                event_callback,
                agent_factory,
                session,
            )

        class DynamicAgent(BaseAgent):
            def system_prompt(self) -> str:
                return f"You are {name}. {role}"

        agent_config = AgentConfig(
            name=name,
            role=role,
            tools=tools,
            model=model,
            max_iterations=max_iterations,
            temperature=temperature,
        )

        return DynamicAgent(
            agent_config,
            self.llm,
            current_sandbox,
            self.tool_registry,
            event_callback,
            agent_factory,
            session,
        )

    def _create_session_callback(self, session: Session) -> Callable:
        session_log_file = LOG_DIR / f"session_{session.id}.log"

        def log_event(event: Dict[str, Any]):
            # Log to file
            try:
                with open(session_log_file, "a") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
            except Exception as e:
                logger.warning(f"Failed to write event to log file: {e}")

            # Log to stdout for docker logs
            event_type = event.get("type", "unknown")
            agent_name = event.get("agent", "System")
            data = event.get("data", {})

            if event_type == "thought":
                logger.info(
                    f"[{agent_name}] THOUGHT: {str(data.get('content', ''))[:200]}..."
                )
            elif event_type == "tool":
                tool_name = data.get("tool_name", "unknown")
                logger.info(f"[{agent_name}] TOOL: {tool_name}")
                logger.info(f"  Input: {str(data.get('input', {}))[:100]}")
                logger.info(f"  Output: {str(data.get('output', ''))[:100]}")
            elif event_type == "delegate":
                target = data.get("target_agent", data.get("agent", "unknown"))
                logger.info(f"[{agent_name}] DELEGATE -> {target}")
            elif event_type == "result":
                logger.info(
                    f"[{agent_name}] RESULT: {str(data.get('content', ''))[:200]}..."
                )
            else:
                logger.info(f"[{agent_name}] {event_type.upper()}: {str(data)[:100]}")

            # Emit to SSE
            try:
                self._emit_event(session.id, event)
            except Exception as e:
                logger.warning(f"Failed to emit event to SSE: {e}")

            session.add_event(event)
            session.add_step(
                agent=event.get("agent", "System"),
                action=event.get("type", "event"),
                input=str(event.get("data", {}).get("input", "")),
                output=str(event.get("data", {})),
            )

        return log_event

    def _setup_session_environment(self, session: Session, role: str) -> BaseAgent:
        event_callback = self._create_session_callback(session)

        if session.id in self._session_sandboxes:
            session_sandbox = self._session_sandboxes[session.id]
        else:
            session_sandbox_path = self.base_sandbox_path / session.id
            # preinstall is controlled by Sandbox.ENABLE_PREINSTALL class constant
            session_sandbox = Sandbox(
                session_sandbox_path, timeout=self.config.sandbox.timeout
            )
            self._session_sandboxes[session.id] = session_sandbox
            logger.info(f"Created sandbox at: {session_sandbox_path}")

        coordinator = self.create_agent(
            name=AgentType.COORDINATOR.value,
            role=role,
            tools=["delegate", "message", "tool"],
            event_callback=event_callback,
            sandbox=session_sandbox,
            session=session,
        )
        return coordinator

    def _record_error_event(
        self, session: Session, message: str, code: str = "error"
    ) -> None:
        content = str(message or "Unknown error")
        event = {
            "type": "error",
            "agent": AgentType.COORDINATOR.value,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "code": code,
                "content": content,
            },
        }
        session.add_event(event)
        self._emit_event(session.id, event)

    async def run(self, query: str, session_id: Optional[str] = None) -> Session:
        logger.info("=" * 60)
        logger.info(f"ORCHESTRATOR.RUN() STARTED")
        logger.info(f"  Query: {query[:100]}...")
        logger.info(f"  Session ID: {session_id or 'new'}")
        logger.info("=" * 60)

        session = self.state.create_session(query, session_id)
        logger.info(f"Session created: {session.id}")

        coordinator = self._setup_session_environment(
            session, role="Plan and delegate tasks"
        )
        logger.info(f"Coordinator agent created, starting execution...")

        start_time = time.time()

        try:
            logger.info("-" * 40)
            logger.info("Calling coordinator.run()...")
            result = await coordinator.run(query, {"session": session})
            logger.info("-" * 40)
            logger.info(f"Coordinator.run() COMPLETED")
            logger.info(f"  Success: {result.success}")
            logger.info(f"  Duration: {result.duration:.2f}s")
            logger.info(f"  Steps: {result.steps}")
            logger.info(
                f"  Output preview: {result.output[:200] if result.output else 'None'}..."
            )

            session.status = "completed" if result.success else "error"
            session.artifacts["result"] = result.output
            session.artifacts["duration"] = result.duration
            session.artifacts["steps"] = result.steps
            if not result.success:
                error_msg = result.error or "Task failed"
                session.artifacts["error"] = error_msg
                self._record_error_event(session, error_msg)
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"EXCEPTION in coordinator.run(): {e}", exc_info=True)
            logger.error("=" * 60)
            session.status = "error"
            session.artifacts["error"] = str(e)
            self._record_error_event(session, str(e))

        session.artifacts["total_time"] = time.time() - start_time
        logger.info(f"Session {session.id} finished with status: {session.status}")
        logger.info(f"Total time: {session.artifacts['total_time']:.2f}s")

        self.state.sessions[session.id] = session
        self.state.save()

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self.state.get_session(session_id)

    async def continue_session(self, session_id: str, message: str) -> Session:
        session = self.state.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.add_message("user", message)

        coordinator = self._setup_session_environment(
            session, role="Continue conversation with context"
        )

        for msg in session.messages[:-1]:
            coordinator.add_message(msg["role"], msg["content"])

        start_time = time.time()
        session.status = "running"

        try:
            context = session.get_context()
            result = await coordinator.run(message, context)
            session.status = "completed" if result.success else "error"
            session.artifacts["result"] = result.output
            session.artifacts["duration"] = result.duration
            session.artifacts["steps"] = result.steps
            if not result.success:
                error_msg = result.error or "Task failed"
                session.artifacts["error"] = error_msg
                self._record_error_event(session, error_msg)
            session.add_message("assistant", result.output)
        except Exception as e:
            logger.error(f"Continue session error: {e}")
            session.status = "error"
            session.artifacts["error"] = str(e)
            self._record_error_event(session, str(e))

        session.artifacts["total_time"] = time.time() - start_time
        self.state.update_session(session.id)
        return session

    def list_sessions(self) -> Dict[str, Any]:
        active = {
            k: v.to_dict()
            for k, v in self.state.sessions.items()
            if v.status == "running"
        }
        historical = [
            v.to_dict() for v in self.state.sessions.values() if v.status != "running"
        ]
        return {"active": active, "historical": historical}

    def clear_sessions(self):
        historical = [
            sid for sid, s in self.state.sessions.items() if s.status != "running"
        ]
        for sid in historical:
            del self.state.sessions[sid]
        self.state.save()

    def stop_session(self, session_id: str) -> bool:
        session = self.state.get_session(session_id)
        if session:
            session.status = "cancelled"
            self.state.update_session(session.id)
            return True
        return False
