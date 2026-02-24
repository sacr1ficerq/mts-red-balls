from kaggle_solver.agents.base import BaseAgent, AgentConfig, AgentResult
from kaggle_solver.agents.registry import AgentRegistry
from kaggle_solver.agents.coordinator import CoordinatorAgent
from kaggle_solver.agents.code import CodeAgent
from kaggle_solver.agents.search import SearchAgent
from kaggle_solver.agents.critic import CriticAgent

AgentRegistry.register("Coordinator", CoordinatorAgent)
AgentRegistry.register("Code", CodeAgent)
AgentRegistry.register("Search", SearchAgent)
AgentRegistry.register("Critic", CriticAgent)

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
