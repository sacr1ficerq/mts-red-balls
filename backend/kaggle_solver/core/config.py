import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List


@dataclass
class LLMConfig:
    model: str = "openrouter/free"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class SandboxConfig:
    root: str = "./workspace"
    timeout: int = 60
    allowed_commands: List[str] = field(default_factory=lambda: ["python", "pip", "ls", "cat", "head"])


@dataclass
class AgentSettings:
    role: str = ""
    tools: List[str] = field(default_factory=list)
    max_iterations: int = 10
    model: Optional[str] = None
    temperature: Optional[float] = None


@dataclass
class SearchConfig:
    model: str = "openrouter/free"
    max_results: int = 8
    relevance_filter: bool = True


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = field(default_factory=lambda: ["*"])


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "logs/server.log"


@dataclass
class Config:
    llm: LLMConfig
    sandbox: SandboxConfig
    agents: Dict[str, AgentSettings]
    search: SearchConfig = field(default_factory=SearchConfig)
    rag: Dict[str, Any] = field(default_factory=dict)
    server: ServerConfig = field(default_factory=ServerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    complex_tasks: List[str] = field(default_factory=lambda: ["analyze", "train", "model", "ml", "ai", "chart", "visual", "graph", "report"])
    simple_tasks: List[str] = field(default_factory=lambda: ["hi", "hello", "hey", "what is", "how to", "find", "search", "info", "code", "file"])

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        config_path = Path(path)
        if not config_path.exists():
            return cls(
                llm=LLMConfig(),
                sandbox=SandboxConfig(),
                agents={}
            )

        with open(path) as f:
            data = yaml.safe_load(f)

        agents = {}
        for name, cfg in data.get("agents", {}).items():
            agents[name] = AgentSettings(
                role=cfg.get("role", ""),
                tools=cfg.get("tools", []),
                max_iterations=cfg.get("max_iterations", 10),
                model=cfg.get("model"),
                temperature=cfg.get("temperature")
            )

        return cls(
            llm=LLMConfig(**data.get("llm", {})),
            sandbox=SandboxConfig(**data.get("sandbox", {})),
            agents=agents,
            search=SearchConfig(**data.get("search", {})),
            rag=data.get("rag", {}),
            server=ServerConfig(**data.get("server", {})),
            logging=LoggingConfig(**data.get("logging", {})),
            complex_tasks=data.get("complex_tasks", ["analyze", "train", "model", "ml", "ai", "chart", "visual", "graph", "report"]),
            simple_tasks=data.get("simple_tasks", ["hi", "hello", "hey", "what is", "how to", "find", "search", "info", "code", "file"])
        )


class ConfigHolder:
    _instance: Optional["ConfigHolder"] = None
    _config: Optional[Config] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def set_config(self, config: Config):
        self._config = config

    def get_config(self) -> Config:
        if self._config is None:
            self._config = Config.load()
        return self._config

    @property
    def llm_config(self) -> dict:
        cfg = self.get_config().llm
        return {"model": cfg.model, "temperature": cfg.temperature, "max_tokens": cfg.max_tokens}

    @property
    def search_config(self) -> dict:
        cfg = self.get_config().search
        return {"model": cfg.model, "max_results": cfg.max_results, "relevance_filter": cfg.relevance_filter}
