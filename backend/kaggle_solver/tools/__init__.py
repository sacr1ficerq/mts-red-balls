# Import modules to trigger decorator registration
# Tools are registered via @create_tool decorator in each module
from kaggle_solver.tools.registry import ToolRegistry, ToolResult

# Import modules to trigger tool registration via decorators
import kaggle_solver.tools.console
import kaggle_solver.tools.files
import kaggle_solver.tools.search
import kaggle_solver.tools.kaggle


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
