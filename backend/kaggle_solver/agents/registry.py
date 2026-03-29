from typing import Dict, Type, List, Callable, Optional, Any
import logging

logger = logging.getLogger(__name__)


class AgentRegistry:
    _agents: Dict[str, Type] = {}

    @classmethod
    def register(cls, name: str, agent_class: Type):
        cls._agents[name] = agent_class
        logger.info(f"Registered agent: {name}")

    @classmethod
    def get(cls, name: str) -> Optional[Type]:
        return cls._agents.get(name)

    @classmethod
    def list_agents(cls) -> List[str]:
        return list(cls._agents.keys())

    @classmethod
    def create(
        cls,
        name: str,
        config,
        llm,
        sandbox,
        tool_registry,
        event_callback: Optional[Callable] = None,
        agent_factory: Optional[Callable] = None,
        session: Optional[Any] = None
    ):
        if name not in cls._agents:
            raise ValueError(f"Unknown agent: {name}")
        return cls._agents[name](config, llm, sandbox, tool_registry, event_callback, agent_factory, session)
