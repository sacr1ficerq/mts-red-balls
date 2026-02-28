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
            # Check if there is a running event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We are in an async context (e.g. FastAPI), but this method is sync.
                # We need to schedule the coroutine in the loop and wait for it.
                # However, since we can't await here, this is tricky without blocking the loop.
                # Ideally, tools should be async. For now, we use a separate thread or nest_asyncio.
                # A safer fallback for now if we can't change the architecture to async:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.mcp.call_tool(self.server, tool_name, {"query": query, **kwargs})
                    )
                    result = future.result()
            else:
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
