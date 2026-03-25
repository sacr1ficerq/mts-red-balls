"""
Settings management for API keys and model configuration.
Settings are stored in a local JSON file and persist across restarts.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any
from threading import Lock

logger = logging.getLogger(__name__)

# Default model for all agents
DEFAULT_MODEL = "openai/gpt-4o-mini"

# Default models for each agent type (can be customized per agent)
DEFAULT_AGENT_MODELS = {
    "coordinator": DEFAULT_MODEL,
    "code": DEFAULT_MODEL,
    "search": DEFAULT_MODEL,
    "critic": DEFAULT_MODEL,
    "hypothesis": DEFAULT_MODEL,
    "data_preprocessor": DEFAULT_MODEL,
    "feature_engineer": DEFAULT_MODEL,
    "model_trainer": DEFAULT_MODEL,
    "data_parser": DEFAULT_MODEL,
    "kaggle_submitter": DEFAULT_MODEL,
}

# Available free models on OpenRouter (updated 2025)
AVAILABLE_FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemma-3-1b-it:free",
    "google/gemma-3-4b-it:free",
    "qwen/qwen3-1.7b:free",
    "qwen/qwen3-4b:free",
    "deepseek/deepseek-r1-0528:free",
    "rekaai/reka-flash-3:free",
]

# All available models (including paid)
AVAILABLE_MODELS = [
    *AVAILABLE_FREE_MODELS,
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "openai/gpt-4-turbo",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-opus",
    "anthropic/claude-3-haiku",
    "google/gemini-pro-1.5",
    "google/gemini-2.0-flash-exp",
    "meta-llama/llama-3.1-70b-instruct",
    "meta-llama/llama-3.1-405b-instruct",
    "deepseek/deepseek-chat",
    "deepseek/deepseek-coder",
]


@dataclass
class AgentModelConfig:
    """Model configuration for a specific agent."""

    model: str = DEFAULT_MODEL
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class Settings:
    """Application settings stored persistently."""

    api_key: str = ""
    kaggle_key: str = ""
    agent_models: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        # Initialize default models for all agents
        for agent_name, default_model in DEFAULT_AGENT_MODELS.items():
            if agent_name not in self.agent_models:
                self.agent_models[agent_name] = {
                    "model": default_model,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                }

    def get_agent_model(self, agent_name: str) -> AgentModelConfig:
        """Get model configuration for a specific agent."""
        config = self.agent_models.get(agent_name, {})
        return AgentModelConfig(
            model=config.get(
                "model", DEFAULT_AGENT_MODELS.get(agent_name, DEFAULT_MODEL)
            ),
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 4096),
        )

    def set_agent_model(
        self,
        agent_name: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """Set model configuration for a specific agent."""
        if agent_name not in self.agent_models:
            self.agent_models[agent_name] = {}

        if model is not None:
            self.agent_models[agent_name]["model"] = model
        elif "model" not in self.agent_models[agent_name]:
            self.agent_models[agent_name]["model"] = DEFAULT_AGENT_MODELS.get(
                agent_name, DEFAULT_MODEL
            )
        if temperature is not None:
            self.agent_models[agent_name]["temperature"] = temperature
        if max_tokens is not None:
            self.agent_models[agent_name]["max_tokens"] = max_tokens


class SettingsManager:
    """Thread-safe settings manager with persistent storage."""

    _instance: Optional["SettingsManager"] = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._settings_lock = Lock()
        self._settings: Optional[Settings] = None
        self._storage_path = self._get_storage_path()

    def _get_storage_path(self) -> Path:
        """Get the path to the settings storage file."""
        from kaggle_solver import get_project_root

        root = get_project_root()
        data_dir = root / "backend" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "settings.json"

    def _load(self) -> Settings:
        """Load settings from storage."""
        try:
            if self._storage_path.exists():
                with open(self._storage_path, "r") as f:
                    data = json.load(f)
                return Settings(
                    api_key=data.get("api_key", ""),
                    kaggle_key=data.get("kaggle_key", ""),
                    agent_models=data.get("agent_models", {}),
                )
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}")
        return Settings()

    def _save(self, settings: Settings):
        """Save settings to storage."""
        try:
            with open(self._storage_path, "w") as f:
                json.dump(asdict(settings), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def get_settings(self) -> Settings:
        """Get current settings (thread-safe)."""
        with self._settings_lock:
            if self._settings is None:
                self._settings = self._load()
            return self._settings

    def update_settings(
        self,
        api_key: Optional[str] = None,
        kaggle_key: Optional[str] = None,
        agent_models: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Settings:
        """Update settings (thread-safe)."""
        with self._settings_lock:
            if self._settings is None:
                self._settings = self._load()

            if api_key is not None:
                self._settings.api_key = api_key

            if kaggle_key is not None:
                self._settings.kaggle_key = kaggle_key

            if agent_models is not None:
                for agent_name, config in agent_models.items():
                    if isinstance(config, dict):
                        self._settings.set_agent_model(
                            agent_name,
                            model=config.get("model"),
                            temperature=config.get("temperature"),
                            max_tokens=config.get("max_tokens"),
                        )

            self._save(self._settings)
            return self._settings

    def get_api_key(self) -> str:
        """Get the API key."""
        return self.get_settings().api_key

    def set_api_key(self, api_key: str):
        """Set the API key."""
        self.update_settings(api_key=api_key)

    def get_kaggle_key(self) -> str:
        """Get the Kaggle API token/key."""
        return self.get_settings().kaggle_key

    def set_kaggle_key(self, kaggle_key: str):
        """Set the Kaggle API token/key."""
        self.update_settings(kaggle_key=kaggle_key)

    def get_agent_model_config(self, agent_name: str) -> AgentModelConfig:
        """Get model configuration for a specific agent."""
        return self.get_settings().get_agent_model(agent_name)

    def update_agent_model(
        self,
        agent_name: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Settings:
        """Update model configuration for a specific agent (thread-safe)."""
        with self._settings_lock:
            if self._settings is None:
                self._settings = self._load()

            self._settings.set_agent_model(
                agent_name, model=model, temperature=temperature, max_tokens=max_tokens
            )

            self._save(self._settings)
            return self._settings

    def has_api_key(self) -> bool:
        """Check if an API key is configured."""
        return bool(self.get_api_key())

    def has_kaggle_key(self) -> bool:
        """Check if a Kaggle key/token is configured."""
        return bool(self.get_kaggle_key())


# Global instance
def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance."""
    return SettingsManager()
