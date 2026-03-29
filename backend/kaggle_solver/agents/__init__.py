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


class HypothesisGeneratorAgent(BaseAgent):
    def system_prompt(self) -> str:
        return get_agent_prompts("HypothesisGenerator")


class DataPreprocessorAgent(BaseAgent):
    def system_prompt(self) -> str:
        return get_agent_prompts("DataPreprocessor")


class FeatureEngineerAgent(BaseAgent):
    def system_prompt(self) -> str:
        return get_agent_prompts("FeatureEngineer")


class ModelTrainerAgent(BaseAgent):
    def system_prompt(self) -> str:
        return get_agent_prompts("ModelTrainer")


class DataParserAgent(BaseAgent):
    def system_prompt(self) -> str:
        return get_agent_prompts("DataParser")


class KaggleSubmitterAgent(BaseAgent):
    def system_prompt(self) -> str:
        return get_agent_prompts("KaggleSubmitter")


AgentRegistry.register("Coordinator", CoordinatorAgent)
AgentRegistry.register("CodeAgent", CodeAgent)
AgentRegistry.register("SearchAgent", SearchAgent)
AgentRegistry.register("CriticAgent", CriticAgent)
AgentRegistry.register("HypothesisGenerator", HypothesisGeneratorAgent)
AgentRegistry.register("DataPreprocessor", DataPreprocessorAgent)
AgentRegistry.register("FeatureEngineer", FeatureEngineerAgent)
AgentRegistry.register("ModelTrainer", ModelTrainerAgent)
AgentRegistry.register("DataParser", DataParserAgent)
AgentRegistry.register("KaggleSubmitter", KaggleSubmitterAgent)

__all__ = [
    "BaseAgent",
    "AgentConfig",
    "AgentResult",
    "AgentRegistry",
    "CoordinatorAgent",
    "CodeAgent",
    "SearchAgent",
    "CriticAgent",
    "HypothesisGeneratorAgent",
    "DataPreprocessorAgent",
    "FeatureEngineerAgent",
    "ModelTrainerAgent",
    "DataParserAgent",
    "KaggleSubmitterAgent",
]
