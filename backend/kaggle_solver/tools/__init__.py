from kaggle_solver.tools.registry import ToolRegistry, ToolResult
from kaggle_solver.tools.console import console_tool
from kaggle_solver.tools.files import files_tool
from kaggle_solver.tools.search import search_tool


# Register all core tools at startup
ToolRegistry.register(
    "console",
    lambda query, sandbox=None, **kwargs: console_tool(query, sandbox),
    "Execute shell commands in sandbox",
    {"query": {"type": "string", "description": "Command to execute"}}
)

ToolRegistry.register(
    "files",
    lambda op="read", path="", content="", sandbox=None, **kwargs: files_tool(op, path, content, sandbox),
    "File operations in sandbox",
    {
        "op": {"type": "string", "enum": ["read", "write", "list", "delete", "exists"]},
        "path": {"type": "string"},
        "content": {"type": "string"}
    }
)

ToolRegistry.register(
    "search",
    lambda query, llm=None, **kwargs: search_tool(query, llm),
    "Search the web for information",
    {"query": {"type": "string", "description": "Search query"}}
)


def get_rag_tool():
    from kaggle_solver.rag import rag_instance
    
    def rag_tool(query: str, **kwargs) -> str:
        context = rag_instance.get_context(query)
        return context if context else "No relevant context found."
    
    return rag_tool


def register_rag_tool():
    ToolRegistry.register("rag", get_rag_tool(), "Query local knowledge base")


register_rag_tool()

__all__ = [
    "ToolRegistry",
    "ToolResult",
    "console_tool",
    "files_tool", 
    "search_tool",
]
