#!/usr/bin/env python3
"""
Debug script to trace agent system execution.
Run from backend directory: cd backend && python3 debug_run.py
"""
import sys
import os
import json
import logging
from pathlib import Path
from unittest.mock import Mock

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging to see everything
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import after path setup
from kaggle_solver import get_project_root
from kaggle_solver.core.config import Config, ConfigHolder
# Skip importing from orchestrator due to import bug
# from kaggle_solver.core.orchestrator import Orchestrator
from kaggle_solver.core.state import StateManager
from kaggle_solver.llm import LLM
from kaggle_solver.sandbox import Sandbox
from kaggle_solver.tools.registry import ToolRegistry
from kaggle_solver.agents.base import AgentConfig, AgentResult, BaseAgent
from kaggle_solver.agents.registry import AgentRegistry
from kaggle_solver.agents.coordinator import get_agent_prompts, load_prompt, load_tool_definitions
import kaggle_solver.tools

print("=" * 80)
print("DEBUGGING AGENT SYSTEM")
print("=" * 80)

# 1. Check config loading
print("\n[1] CHECKING CONFIG LOADING")
print("-" * 40)
config = Config.load("config.yaml")
print(f"LLM Model: {config.llm.model}")
print(f"Sandbox timeout: {config.sandbox.timeout}")
print(f"Agents: {list(config.agents.keys())}")

# 2. Check agent prompts
print("\n[2] CHECKING AGENT PROMPTS")
print("-" * 40)
prompts = {
    "Coordinator": get_agent_prompts("Coordinator"),
    "CodeAgent": get_agent_prompts("CodeAgent"),
    "SearchAgent": get_agent_prompts("SearchAgent"),
    "CriticAgent": get_agent_prompts("CriticAgent"),
}
for name, prompt in prompts.items():
    print(f"\n--- {name} Prompt ---")
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)

# 3. Check tool definitions loading
print("\n[3] CHECKING TOOL DEFINITIONS")
print("-" * 40)
tools = ["plan", "update_plan", "delegate", "result", "console", "files", "search"]
for tool in tools:
    tool_path = get_project_root() / "backend" / "kaggle_solver" / "prompts" / "tools" / f"{tool}.yaml"
    exists = tool_path.exists()
    print(f"Tool '{tool}': {'EXISTS' if exists else 'MISSING'} ({tool_path})")

# 4. Check delegate tool specifically
print("\n[4] CHECKING DELEGATE TOOL IN COORDINATOR")
print("-" * 40)
coord_prompt = get_agent_prompts("Coordinator")
if "{delegate_tool}" in coord_prompt:
    print("BUG FOUND: {delegate_tool} placeholder NOT REPLACED!")
    print("This is because prompts/tools/delegate.yaml doesn't exist!")
else:
    print("Delegate tool placeholder replaced successfully")
    if "delegate" in coord_prompt.lower():
        print("Delegate info found in prompt")

# 5. Check tool registry
print("\n[5] CHECKING TOOL REGISTRY")
print("-" * 40)
print(f"Registered tools: {ToolRegistry.list_tools()}")

# 6. Check agent registry
print("\n[6] CHECKING AGENT REGISTRY")
print("-" * 40)
print(f"Registered agents: {AgentRegistry.list_agents()}")

# 7. Check what happens in load_tool_definitions
print("\n[7] TESTING load_tool_definitions FUNCTION")
print("-" * 40)
loaded_tools = load_tool_definitions(["plan", "delegate", "result"])
print(f"Loaded tools: {list(loaded_tools.keys())}")
for name, content in loaded_tools.items():
    print(f"  - {name}: {content[:100] if content else 'EMPTY'}...")

# 8. Check sandbox creation
print("\n[8] CHECKING SANDBOX")
print("-" * 40)
sandbox = Sandbox(Path("./workspace"), timeout=60)
print(f"Sandbox root: {sandbox.root}")
print(f"Sandbox allowed commands: {sandbox.ALLOWED_COMMANDS}")

# 9. Run a test query with mock LLM
print("\n[9] RUNNING TEST QUERY WITH MOCK LLM")
print("-" * 40)

# Create mock LLM
mock_llm = Mock()
mock_llm.chat = Mock(return_value='{"action": "done", "result": "Mock test completed!"}')
mock_llm.generate = Mock(return_value="Mock generation result")

# Create minimal orchestrator with mock
class DebugOrchestrator:
    def __init__(self, config, llm):
        self.config = config
        self.state = StateManager(str(Path("./data/sessions.json")))
        self.llm = llm
        sandbox_root = self.config.sandbox.root
        if not Path(sandbox_root).is_absolute():
            sandbox_root = Path(__file__).parent.parent / sandbox_root
        self.base_sandbox_path = Path(sandbox_root).resolve()
        self.base_sandbox_path.mkdir(parents=True, exist_ok=True)
        self.sandbox = Sandbox(self.base_sandbox_path, timeout=self.config.sandbox.timeout)
        self.tool_registry = ToolRegistry
        self._event_callbacks = []
        self._session_sandboxes = {}
        
    def create_agent(self, name, role, tools, event_callback=None, sandbox=None, session=None):
        from kaggle_solver.agents.registry import AgentRegistry
        from kaggle_solver.agents.base import AgentConfig
        
        max_iterations = 10
        if name in self.config.agents:
            max_iterations = self.config.agents[name].max_iterations
        
        if name in AgentRegistry.list_agents():
            agent_config = AgentConfig(
                name=name,
                role=role,
                tools=tools,
                model=self.config.llm.model,
                max_iterations=max_iterations,
                temperature=self.config.llm.temperature
            )
            return AgentRegistry.create(
                name, agent_config, self.llm, sandbox or self.sandbox, 
                self.tool_registry, event_callback, None, session
            )
        
        class DynamicAgent(BaseAgent):
            def system_prompt(self) -> str:
                return f"You are {name}. {role}"

        agent_config = AgentConfig(
            name=name,
            role=role,
            tools=tools,
            model=self.config.llm.model,
            max_iterations=max_iterations,
            temperature=self.config.llm.temperature
        )
        
        return DynamicAgent(agent_config, self.llm, sandbox or self.sandbox, self.tool_registry, event_callback, None, session)
        
orch = DebugOrchestrator(config, mock_llm)

# Create event callback that logs everything
def debug_event_callback(event):
    print(f"EVENT: {event.get('type')} - {json.dumps(event.get('data', {}), ensure_ascii=False)[:200]}")

# Run test query
print("\nRunning query: 'Hello, what is 2+2?'")
session = orch.state.create_session("Hello, what is 2+2?")

coordinator = orch.create_agent(
    name="Coordinator",
    role="Plan and delegate tasks",
    tools=["delegate", "message", "tool"],
    event_callback=debug_event_callback,
    sandbox=orch.sandbox,
    session=session
)

result = coordinator.run("Hello, what is 2+2?", {"session_id": session.id})

print(f"\nResult: success={result.success}, output={result.output[:200] if result.output else 'NONE'}")

# 10. Check the conversation history
print("\n[10] CHECKING MESSAGES IN COORDINATOR")
print("-" * 40)
for i, msg in enumerate(coordinator.messages):
    role = msg.get('role', 'unknown')
    content = msg.get('content', '')[:100]
    print(f"  {i}: [{role}] {content}...")

print("\n" + "=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)
