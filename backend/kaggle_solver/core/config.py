import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List


@dataclass
class LLMConfig:
    model: str = "meta-llama/llama-3.1-8b-instruct"
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class SandboxConfig:
    root: str = "./workspace"
    timeout: int = 60
    allowed_commands: List[str] = field(default_factory=lambda: ["python", "pip", "ls", "cat", "head"])


@dataclass
class AgentConfig:
    name: str
    role: str
    tools: List[str]
    model: str = "meta-llama/llama-3.1-8b-instruct"
    max_iterations: int = 10
    temperature: float = 0.7


@dataclass
class Config:
    llm: LLMConfig
    sandbox: SandboxConfig
    agents: List[AgentConfig]

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        config_path = Path(path)
        if not config_path.exists():
            return cls(
                llm=LLMConfig(),
                sandbox=SandboxConfig(),
                agents=[]
            )

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls(
            llm=LLMConfig(**data.get("llm", {})),
            sandbox=SandboxConfig(**data.get("sandbox", {})),
            agents=[AgentConfig(**a) for a in data.get("agents", [])]
        )
