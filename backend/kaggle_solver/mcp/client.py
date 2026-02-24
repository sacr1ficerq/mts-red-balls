from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class MCPTool:
    def __init__(self, name: str, description: str, input_schema: Dict):
        self.name = name
        self.description = description
        self.input_schema = input_schema


class MCPClient:
    def __init__(self):
        self.sessions: Dict[str, Any] = {}
        self.tools: Dict[str, MCPTool] = {}

    async def connect(self, name: str, command: List[str], env: Dict = None):
        logger.info(f"Connecting to MCP server: {name}")
        self.sessions[name] = {"command": command, "env": env, "connected": True}
        logger.info(f"MCP server {name} connected (stub)")

    async def disconnect(self, name: str):
        if name in self.sessions:
            del self.sessions[name]
            logger.info(f"Disconnected from MCP server: {name}")

    async def list_tools(self, server_name: str) -> List[MCPTool]:
        return []

    async def call_tool(self, server_name: str, tool_name: str, args: Dict) -> str:
        logger.info(f"MCP call: {server_name}.{tool_name} with args: {args}")
        return f"Result from {server_name}.{tool_name}"

    def is_connected(self, name: str) -> bool:
        return name in self.sessions and self.sessions[name].get("connected", False)


class MCPManager:
    def __init__(self):
        self.client = MCPClient()
        self.servers: Dict[str, Dict] = {}

    def add_server(self, name: str, command: List[str], env: Dict = None):
        self.servers[name] = {"command": command, "env": env}

    async def connect_all(self):
        for name, config in self.servers.items():
            await self.client.connect(name, config["command"], config.get("env"))

    async def disconnect_all(self):
        for name in list(self.servers.keys()):
            await self.client.disconnect(name)

    def get_tools(self) -> List[Dict[str, Any]]:
        tools = []
        for name, tool in self.client.tools.items():
            tools.append({
                "name": f"mcp_{name}",
                "description": tool.description,
                "server": name
            })
        return tools


mcp_manager = MCPManager()
