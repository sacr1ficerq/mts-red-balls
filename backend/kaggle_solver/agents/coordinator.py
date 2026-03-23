import yaml
import logging
from pathlib import Path
from kaggle_solver import get_project_root
from kaggle_solver.constants import AgentType, AgentConstants

logger = logging.getLogger(__name__)


def _resolve_prompts_dir() -> Path:
    root = get_project_root()
    candidates = [
        root / "backend" / "kaggle_solver" / "prompts",
        root / "kaggle_solver" / "prompts",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


PROMPTS_DIR = _resolve_prompts_dir()
TOOLS_DIR = PROMPTS_DIR / "tools"


def load_tool_definitions(tools: list) -> dict:
    definitions = {}
    for tool in tools:
        tool_path = TOOLS_DIR / f"{tool}.yaml"
        if tool_path.exists():
            try:
                with open(tool_path, "r") as f:
                    data = yaml.safe_load(f)
                    if data:
                        for key, value in data.items():
                            definitions[key] = value
            except Exception as e:
                logger.warning(f"Failed to load tool definitions for {tool}: {e}")
    return definitions


def load_prompt(filename: str, default: str, tools: list | None = None) -> str:
    try:
        path = PROMPTS_DIR / filename
        if path.exists():
            with open(path, "r") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    prompt = data.get("system", data.get("system_prompt", default))
                    if tools:
                        tool_defs = load_tool_definitions(tools)
                        for placeholder, definition in tool_defs.items():
                            prompt = prompt.replace(f"{{{placeholder}}}", definition)
                    return prompt
    except Exception as e:
        logger.warning(f"Failed to load prompt {filename}: {e}")
    return default


class CoordinatorAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        return load_prompt(
            "coordinator.yaml", "", tools=["plan", "update_plan", "delegate", "result"]
        )


class CodeAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        return load_prompt("code.yaml", "", tools=["console", "files", "result"])


class SearchAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        return load_prompt("search.yaml", "", tools=["search", "result"])


class CriticAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        return load_prompt("critic.yaml", "", tools=["console", "search", "result"])


class HypothesisGeneratorPrompts:
    @staticmethod
    def system_prompt() -> str:
        return load_prompt(
            "hypothesis.yaml", "", tools=["console", "files", "search", "result"]
        )


class DataPreprocessorPrompts:
    @staticmethod
    def system_prompt() -> str:
        return load_prompt(
            "data_preprocessor.yaml", "", tools=["console", "files", "result"]
        )


class FeatureEngineerPrompts:
    @staticmethod
    def system_prompt() -> str:
        return load_prompt(
            "feature_engineer.yaml", "", tools=["console", "files", "result"]
        )


class ModelTrainerPrompts:
    @staticmethod
    def system_prompt() -> str:
        return load_prompt(
            "model_trainer.yaml", "", tools=["console", "files", "result"]
        )


class DataParserPrompts:
    @staticmethod
    def system_prompt() -> str:
        return load_prompt("data_parser.yaml", "", tools=["console", "files", "result"])


class KaggleSubmitterPrompts:
    @staticmethod
    def system_prompt() -> str:
        return load_prompt(
            "kaggle_submitter.yaml", "", tools=["console", "files", "result"]
        )


def get_agent_prompts(agent_name: str) -> str:
    prompts = {
        AgentType.COORDINATOR.value: CoordinatorAgentPrompts.system_prompt(),
        AgentType.CODE.value: CodeAgentPrompts.system_prompt(),
        AgentType.SEARCH.value: SearchAgentPrompts.system_prompt(),
        AgentType.CRITIC.value: CriticAgentPrompts.system_prompt(),
        "HypothesisGenerator": HypothesisGeneratorPrompts.system_prompt(),
        "DataPreprocessor": DataPreprocessorPrompts.system_prompt(),
        "FeatureEngineer": FeatureEngineerPrompts.system_prompt(),
        "ModelTrainer": ModelTrainerPrompts.system_prompt(),
        "DataParser": DataParserPrompts.system_prompt(),
        "KaggleSubmitter": KaggleSubmitterPrompts.system_prompt(),
    }
    return prompts.get(agent_name, f"You are {agent_name}.")


def should_use_powerful_model(query: str) -> bool:
    from kaggle_solver.core.config import ConfigHolder

    config = ConfigHolder().get_config()
    complex_tasks = config.complex_tasks
    simple_tasks = config.simple_tasks

    query_lower = query.lower()
    for simple in simple_tasks:
        if simple in query_lower:
            return False
    for complex in complex_tasks:
        if complex in query_lower:
            return True
    return False
