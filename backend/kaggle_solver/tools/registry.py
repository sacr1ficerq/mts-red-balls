from dataclasses import dataclass
from typing import Dict, Callable, Any, Optional, List
import logging

from kaggle_solver.constants import ToolConstants

logger = logging.getLogger(__name__)

TOOL_CONSOLE = ToolConstants.TOOL_CONSOLE
TOOL_FILES = ToolConstants.TOOL_FILES
TOOL_SEARCH = ToolConstants.TOOL_SEARCH
TOOL_RAG = ToolConstants.TOOL_RAG

TOOLS_REQUIRING_LLM = ToolConstants.TOOLS_REQUIRING_LLM
TOOLS_REQUIRING_SANDBOX = ToolConstants.TOOLS_REQUIRING_SANDBOX


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
        parameters: Optional[Dict[str, Any]] = None,
    ):
        cls._tools[name] = func
        cls._tool_metadata[name] = {
            "name": name,
            "description": description,
            "parameters": parameters or {},
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
            if name in TOOLS_REQUIRING_LLM:
                if "llm" in kwargs:
                    tool_kwargs["llm"] = kwargs["llm"]
            if name in TOOLS_REQUIRING_SANDBOX:
                if "sandbox" in kwargs:
                    tool_kwargs["sandbox"] = kwargs["sandbox"]

            passthrough_kwargs = {
                k: v for k, v in kwargs.items() if k not in {"sandbox", "llm"}
            }

            if name == TOOL_FILES:
                tool_kwargs["op"] = kwargs.get("op", "read")
                tool_kwargs["path"] = kwargs.get("path", "")
                tool_kwargs["content"] = kwargs.get("content", "")
                tool_kwargs["search"] = kwargs.get("search", "")
                tool_kwargs["replace"] = kwargs.get("replace", "")
                result = func(**tool_kwargs)
            elif name == TOOL_SEARCH:
                search_query = kwargs.get("query", query)
                tool_kwargs["query"] = search_query
                result = func(**tool_kwargs)
            else:
                if query and "query" not in passthrough_kwargs:
                    passthrough_kwargs["query"] = query
                result = func(**passthrough_kwargs, **tool_kwargs)
            return ToolResult(
                True,
                output=str(result) if result is not None else "",
                metadata={"tool": name},
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


def create_tool(
    name: str, description: str = "", parameters: Optional[Dict[str, Any]] = None
):
    def decorator(func: Callable):
        ToolRegistry.register(name, func, description, parameters)
        return func

    return decorator
