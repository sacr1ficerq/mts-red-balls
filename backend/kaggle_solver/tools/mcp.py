from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MCPToolWrapper:
    """Wrapper for MCP tools to use with ToolRegistry."""
    
    def __init__(self, mcp_client, server_name: str):
        self.mcp = mcp_client
        self.server = server_name
    
    def execute(self, tool_name: str, query: str = "", **kwargs) -> str:
        """Execute MCP tool (sync wrapper)."""
        import asyncio
        
        try:
            result = asyncio.run(
                self.mcp.call_tool(self.server, tool_name, {"query": query, **kwargs})
            )
            return result
        except Exception as e:
            logger.error(f"MCP tool error: {e}")
            return f"Error: {e}"


def create_mcp_tool_wrapper(mcp_client, server_name: str):
    """Factory function to create MCP tool wrappers."""
    
    def mcp_tool(query: str, tool_name: str = "", **kwargs) -> str:
        if not tool_name:
            return "Error: tool_name required"
        
        wrapper = MCPToolWrapper(mcp_client, server_name)
        return wrapper.execute(tool_name, query, **kwargs)
    
    return mcp_tool
