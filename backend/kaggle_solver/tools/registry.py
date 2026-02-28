from dataclasses import dataclass
from typing import Dict, Callable, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ToolRegistry:
    _tools: Dict[str, Callable] = {}
    _tool_metadata: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        func: Callable,
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None
    ):
        cls._tools[name] = func
        cls._tool_metadata[name] = {
            "name": name,
            "description": description,
            "parameters": parameters or {}
        }
        logger.info(f"Registered tool: {name}")

    @classmethod
    def get(cls, name: str) -> Optional[Callable]:
        return cls._tools.get(name)

    @classmethod
    def get_metadata(cls, name: str) -> Optional[Dict[str, Any]]:
        return cls._tool_metadata.get(name)

    @classmethod
    def execute(cls, name: str, query: str = "", **kwargs) -> ToolResult:
        if name not in cls._tools:
            return ToolResult(False, error=f"Unknown tool: {name}")

        try:
            func = cls._tools[name]
            
            tool_kwargs = {}
            if name in ("search", "rag"):
                if "llm" in kwargs:
                    tool_kwargs["llm"] = kwargs["llm"]
            if name in ("console", "files"):
                if "sandbox" in kwargs:
                    tool_kwargs["sandbox"] = kwargs["sandbox"]
            
            if name == "files":
                tool_kwargs["op"] = kwargs.get("op", "read")
                tool_kwargs["path"] = kwargs.get("path", "")
                tool_kwargs["content"] = kwargs.get("content", "")
                result = func(**tool_kwargs)
            else:
                result = func(query=query, **tool_kwargs)
            return ToolResult(
                True,
                output=str(result) if result is not None else "",
                metadata={"tool": name}
            )
        except Exception as e:
            logger.error(f"Tool execution error: {name} - {e}")
            return ToolResult(False, error=str(e))

    @classmethod
    def list_tools(cls) -> List[str]:
        return list(cls._tools.keys())

    @classmethod
    def list_with_metadata(cls) -> List[Dict[str, Any]]:
        return list(cls._tool_metadata.values())

    @classmethod
    def unregister(cls, name: str):
        if name in cls._tools:
            del cls._tools[name]
            del cls._tool_metadata[name]
            logger.info(f"Unregistered tool: {name}")


def create_tool(name: str, description: str = "", parameters: Optional[Dict[str, Any]] = None):
    def decorator(func: Callable):
        ToolRegistry.register(name, func, description, parameters)
        return func
    return decorator
