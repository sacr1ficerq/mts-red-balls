from kaggle_solver.tools.registry import ToolRegistry, ToolResult
from kaggle_solver.tools.console import console_tool
from kaggle_solver.tools.files import files_tool
from kaggle_solver.tools.search import search_tool


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
