from typing import Dict, Any
from kaggle_solver.tools.registry import ToolRegistry, ToolResult
from kaggle_solver.mcp.client import mcp_manager


def mcp_tool(query: str, tool_name: str = "", **kwargs) -> str:
    import asyncio
    
    if not tool_name:
        return "Error: tool_name required"
    
    try:
        result = asyncio.run(
            mcp_manager.client.call_tool("default", tool_name, {"query": query, **kwargs})
        )
        return result
    except Exception as e:
        return f"Error: {e}"


ToolRegistry.register("mcp", mcp_tool, "Call MCP tool", {"tool_name": {"type": "string"}})
