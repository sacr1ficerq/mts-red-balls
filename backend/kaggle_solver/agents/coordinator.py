import yaml
import logging
from pathlib import Path
from typing import Optional
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

# Canonical tool file names (without .yaml) for each agent.
# These map to files in prompts/tools/ whose top-level YAML keys become
# {key} placeholders substituted into the agent's system_prompt.
_KAGGLE_TOOLS = [
    "kaggle_get_competition_info",
    "kaggle_download_data",
    "kaggle_submit",
    "kaggle_get_submission_status",
    "kaggle_get_leaderboard",
    "kaggle_list_competitions",
    "kaggle_validate_submission",
    "kaggle_prepare_submission",
]

AGENT_TOOL_FILES = {
    AgentType.COORDINATOR.value: ["plan", "delegate", "result", "pip_install"],
    AgentType.CODE.value: [
        "console",
        "files",
        "pip_install",
        "result",
    ] + _KAGGLE_TOOLS,
    AgentType.SEARCH.value: ["rag", "search", "result"],
    AgentType.CRITIC.value: ["console", "files", "result"],
    "HypothesisGenerator": ["console", "files", "pip_install", "rag", "search", "result"],
    "DataPreprocessor": ["console", "files", "pip_install", "result"],
    "FeatureEngineer": ["console", "files", "pip_install", "rag", "result"],
    "ModelTrainer": ["console", "files", "pip_install", "rag", "result"],
    "DataParser": ["console", "files", "pip_install", "result"],
    "KaggleSubmitter": [
        "console",
        "files",
        "pip_install",
        "result",
        "kaggle_validate_submission",
        "kaggle_prepare_submission",
        "kaggle_submit",
        "kaggle_get_submission_status",
        "kaggle_get_leaderboard",
    ],
}


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


def load_prompt(filename: str, default: str, tools: Optional[list] = None) -> str:
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
                        # Remove any unresolved placeholders to avoid LLM confusion
                        import re
                        prompt = re.sub(r"\{[a-z_]+_tool\}", "", prompt)
                    return prompt
    except Exception as e:
        logger.warning(f"Failed to load prompt {filename}: {e}")
    return default


def _load(filename: str, agent_name: str) -> str:
    tools = AGENT_TOOL_FILES.get(agent_name, ["result"])
    return load_prompt(filename, f"You are {agent_name}.", tools=tools)


class CoordinatorAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        return _load("coordinator.yaml", AgentType.COORDINATOR.value)


class CodeAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        return _load("code.yaml", AgentType.CODE.value)


class SearchAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        return _load("search.yaml", AgentType.SEARCH.value)


class CriticAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        return _load("critic.yaml", AgentType.CRITIC.value)


class HypothesisGeneratorPrompts:
    @staticmethod
    def system_prompt() -> str:
        return _load("hypothesis.yaml", "HypothesisGenerator")


class DataPreprocessorPrompts:
    @staticmethod
    def system_prompt() -> str:
        return _load("data_preprocessor.yaml", "DataPreprocessor")


class FeatureEngineerPrompts:
    @staticmethod
    def system_prompt() -> str:
        return _load("feature_engineer.yaml", "FeatureEngineer")


class ModelTrainerPrompts:
    @staticmethod
    def system_prompt() -> str:
        return _load("model_trainer.yaml", "ModelTrainer")


class DataParserPrompts:
    @staticmethod
    def system_prompt() -> str:
        return _load("data_parser.yaml", "DataParser")


class KaggleSubmitterPrompts:
    @staticmethod
    def system_prompt() -> str:
        return _load("kaggle_submitter.yaml", "KaggleSubmitter")


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
