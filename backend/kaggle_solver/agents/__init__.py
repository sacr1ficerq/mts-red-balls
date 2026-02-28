from kaggle_solver.agents.base import BaseAgent, AgentConfig, AgentResult
from kaggle_solver.agents.registry import AgentRegistry
from kaggle_solver.agents.coordinator import get_agent_prompts


class CoordinatorAgent(BaseAgent):
    def system_prompt(self) -> str:
        return get_agent_prompts("Coordinator")


class CodeAgent(BaseAgent):
    def system_prompt(self) -> str:
        return get_agent_prompts("CodeAgent")


class SearchAgent(BaseAgent):
    def system_prompt(self) -> str:
        return get_agent_prompts("SearchAgent")


class CriticAgent(BaseAgent):
    def system_prompt(self) -> str:
        return get_agent_prompts("CriticAgent")


AgentRegistry.register("Coordinator", CoordinatorAgent)
AgentRegistry.register("CodeAgent", CodeAgent)
AgentRegistry.register("SearchAgent", SearchAgent)
AgentRegistry.register("CriticAgent", CriticAgent)

__all__ = [
    "BaseAgent",
    "AgentConfig", 
    "AgentResult",
    "AgentRegistry",
    "CoordinatorAgent",
    "CodeAgent",
    "SearchAgent",
    "CriticAgent",
]
