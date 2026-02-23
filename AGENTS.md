# Multi-Agent Kaggle Solver - Architecture Reference

---

## Project Structure

```
sandbox_workspace/
├── kaggle_solver/
│   ├── __init__.py
│   ├── main.py              # CLI: python -m kaggle_solver.main
│   ├── server.py            # FastAPI + WebSocket
│   │
│   ├── core/
│   │   ├── orchestrator.py  # Agent coordination (<300 lines)
│   │   ├── state.py        # Session state management
│   │   └── config.py       # YAML config loader
│   │
│   ├── agents/
│   │   ├── base.py         # BaseAgent abstract class
│   │   ├── registry.py     # Agent factory/registry
│   │   ├── coordinator.py  # Main planning agent
│   │   ├── code.py         # Code execution agent
│   │   ├── critic.py       # Review/critique agent
│   │   └── search.py       # Web search agent
│   │
│   ├── tools/
│   │   ├── registry.py     # Tool registry + execution
│   │   ├── console.py     # Shell: python, pip, ls, cat, head
│   │   ├── files.py       # File read/write in sandbox
│   │   ├── search.py      # Web search via OpenRouter
│   │   └── mcp.py        # MCP tools wrapper
│   │
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── client.py      # MCP client
│   │
│   ├── prompts/
│   │   ├── coordinator.yaml
│   │   ├── code.yaml
│   │   └── critic.yaml
│   │
│   ├── llm.py              # OpenRouter LLM client
│   ├── sandbox.py          # Secure workspace execution
│   └── kaggle.py           # Pipeline: load → train → submit
│
├── knowledge/              # RAG: chunked docs for retrieval
├── workspace/              # Agent working files
├── tests/                 # Unit tests (TDD)
│   ├── test_agents/
│   ├── test_tools/
│   └── test_sandbox/
│
├── frontend/              # Svelte web UI
│   ├── src/lib/components/
│   └── package.json
│
└── config.yaml            # All configuration
```

---

## Core Classes

### Agent (agents/base.py)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
import json

class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    TOOL = "tool"
    DELEGATING = "delegating"
    DONE = "done"
    ERROR = "error"

@dataclass
class AgentConfig:
    name: str
    role: str
    tools: List[str]
    model: str = "anthropic/claude-3.5-sonnet"
    max_iterations: int = 10
    temperature: float = 0.7

class BaseAgent(ABC):
    def __init__(self, config: AgentConfig, llm, sandbox, tool_registry):
        self.config = config
        self.llm = llm
        self.sandbox = sandbox
        self.tools = tool_registry
        self.state = AgentState.IDLE
        self.messages: List[Dict[str, str]] = []
        self.context: List[str] = []
    
    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
    
    @abstractmethod
    def system_prompt(self) -> str:
        """Return agent-specific system prompt"""
        pass
    
    def run(self, user_input: str) -> str:
        """Main agent loop"""
        self.add_message("user", user_input)
        
        for _ in range(self.config.max_iterations):
            self.state = AgentState.THINKING
            response = self.llm.chat(
                model=self.config.model,
                messages=self.messages,
                temperature=self.config.temperature
            )
            self.add_message("assistant", response)
            
            action = self._parse_action(response)
            
            if action["type"] == "done":
                self.state = AgentState.DONE
                return action["result"]
            
            elif action["type"] == "tool":
                self.state = AgentState.TOOL
                result = self.tools.execute(action["tool"], action["query"], sandbox=self.sandbox)
                self.add_message("tool", f"{action['tool']}: {result.output}")
            
            elif action["type"] == "delegate":
                self.state = AgentState.DELEGATING
                # Handle delegation to another agent
                pass
        
        self.state = AgentState.ERROR
        return "Max iterations reached"
    
    def _parse_action(self, response: str) -> Dict[str, Any]:
        """Parse JSON action from LLM response"""
        # Look for JSON in response
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass
        return {"type": "done", "result": response}
```

### Tool Registry (tools/registry.py)

```python
from dataclasses import dataclass
from typing import Dict, Callable, Any, Optional
import json

@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""

class ToolRegistry:
    _tools: Dict[str, Callable] = {}
    
    @classmethod
    def register(cls, name: str, func: Callable):
        """Register a tool function"""
        cls._tools[name] = func
    
    @classmethod
    def get(cls, name: str) -> Optional[Callable]:
        return cls._tools.get(name)
    
    @classmethod
    def execute(cls, name: str, query: str = "", **kwargs) -> ToolResult:
        """Execute a tool by name"""
        if name not in cls._tools:
            return ToolResult(False, error=f"Unknown tool: {name}")
        
        try:
            func = cls._tools[name]
            # Pass query and additional kwargs
            result = func(query=query, **kwargs)
            return ToolResult(True, output=str(result))
        except Exception as e:
            return ToolResult(False, error=str(e))
    
    @classmethod
    def list_tools(cls) -> List[str]:
        return list(cls._tools.keys())
```

### Sandbox (sandbox.py)

```python
from pathlib import Path
from subprocess import run, PIPE, TimeoutExpired
from dataclasses import dataclass
import shutil

@dataclass
class Result:
    success: bool
    output: str = ""
    error: str = ""

class Sandbox:
    """Secure workspace execution"""
    
    ALLOWED_COMMANDS = {"python", "pip", "ls", "cat", "head", "mkdir", "rm", "cp"}
    
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
    
    def _secure_path(self, path: str) -> Path:
        """Ensure path is within sandbox"""
        # Prevent path traversal
        clean = path.replace("..", "").lstrip("/")
        full = (self.root / clean).resolve()
        
        if not str(full).startswith(str(self.root)):
            raise ValueError(f"Security: path outside sandbox: {path}")
        return full
    
    def read(self, path: str) -> str:
        """Read file contents"""
        return self._secure_path(path).read_text()
    
    def write(self, path: str, content: str):
        """Write file contents"""
        p = self._secure_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    
    def list(self, path: str = ".") -> list:
        """List files in directory"""
        p = self._secure_path(path)
        if p.is_dir():
            return [str(x.relative_to(self.root)) for x in p.rglob("*")]
        return []
    
    def execute(self, command: str, timeout: int = 60) -> Result:
        """Execute shell command"""
        cmd = command.strip().split()
        
        if not cmd:
            return Result(False, error="Empty command")
        
        # Security: only allow specific commands
        if cmd[0] not in self.ALLOWED_COMMANDS:
            return Result(False, error=f"Command not allowed: {cmd[0]}")
        
        try:
            r = run(
                command,
                shell=True,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            output = r.stdout + r.stderr
            return Result(r.returncode == 0, output)
        except TimeoutExpired:
            return Result(False, error="Command timed out")
        except Exception as e:
            return Result(False, error=str(e))
    
    def cleanup(self):
        """Remove all files in sandbox"""
        if self.root.exists():
            shutil.rmtree(self.root)
            self.root.mkdir(parents=True)
```

### LLM Client (llm.py)

```python
from openai import OpenAI
from typing import List, Dict, Any
import os

class LLM:
    """OpenRouter LLM client"""
    
    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key or os.getenv("OPENROUTER_API_KEY")
        )
    
    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """Send chat request to OpenRouter"""
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """Simple generate (system + user messages)"""
        return self.chat(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
```

### State Manager (core/state.py)

```python
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import json

@dataclass
class Step:
    id: int
    agent: str
    action: str
    input: str
    output: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = True

@dataclass
class Session:
    id: str
    query: str
    created_at: str
    steps: List[Step] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    status: str = "running"  # running, completed, error
    
    def add_step(self, agent: str, action: str, input: str, output: str, success: bool = True):
        step = Step(
            id=len(self.steps) + 1,
            agent=agent,
            action=action,
            input=input,
            output=output,
            success=success
        )
        self.steps.append(step)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "query": self.query,
            "created_at": self.created_at,
            "steps": [
                {"id": s.id, "agent": s.agent, "action": s.action, 
                 "input": s.input, "output": s.output, "success": s.success}
                for s in self.steps
            ],
            "artifacts": self.artifacts,
            "status": self.status
        }

class StateManager:
    """Manages session state"""
    
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
    
    def create_session(self, query: str) -> Session:
        session = Session(
            id=str(uuid.uuid4()),
            query=query,
            created_at=datetime.now().isoformat()
        )
        self.sessions[session.id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)
    
    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(
                {sid: s.to_dict() for sid, s in self.sessions.items()},
                f, indent=2
            )
```

### Config (core/config.py)

```python
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class LLMConfig:
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096

@dataclass
class SandboxConfig:
    root: str
    timeout: int = 60
    allowed_commands: list = None
    
    def __post_init__(self):
        if self.allowed_commands is None:
            self.allowed_commands = ["python", "pip", "ls", "cat", "head"]

@dataclass
class AgentConfig:
    name: str
    role: str
    tools: list

@dataclass
class Config:
    llm: LLMConfig
    sandbox: SandboxConfig
    agents: list
    
    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        with open(path) as f:
            data = yaml.safe_load(f)
        
        return cls(
            llm=LLMConfig(**data.get("llm", {})),
            sandbox=SandboxConfig(**data.get("sandbox", {})),
            agents=data.get("agents", [])
        )
```

---

## Agent Loop (Flow Diagram)

```
┌────────────────────────────────────────────────────────────────────────┐
│                         AGENT EXECUTION LOOP                           │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────┐
                    │     1. START with input     │
                    │   (user query or task)      │
                    └─────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │  2. LLM.chat(messages)       │
                    │  ┌─────────────────────────┐ │
                    │  │ system_prompt           │ │
                    │  │ + history               │ │
                    │  │ + user input            │ │
                    │  └─────────────────────────┘ │
                    └──────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │  3. Parse LLM response        │
                    │  to extract JSON action       │
                    └───────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌───────────┐   ┌───────────┐   ┌───────────┐
            │  "done"   │   │  "tool"   │   │ "delegate"│
            │  action   │   │  action   │   │  action   │
            └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
                 │                │                │
                 ▼                ▼                ▼
      ┌──────────────────┐  ┌─────────────┐  ┌──────────────┐
      │ Return result    │  │ Execute     │  │ Call target  │
      │ to caller        │  │ tool(...)   │  │ agent.run()  │
      │                  │  │             │  │              │
      │ STATE: DONE      │  │ STATE: TOOL │  │STATE:DELEGATE│
      └──────────────────┘  └──────┬──────┘  └──────┬───────┘
                                   │                │
                                   ▼                │
                        ┌─────────────────┐         │
                        │ Add tool result │         │
                        │ to messages     │         │
                        │ as "tool" role  │         │
                        └────────┬────────┘         │
                                 │                  │
                                 └────────┬─────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │   Check iterations     │
                              │   < max_iterations?    │
                              └───────────┬────────────┘
                                          │
                         ┌────────────────┴───────────┐
                         │ NO                         │ YES
                         ▼                            ▼
              ┌──────────────────┐        ┌───────────────────────┐
              │ STATE: ERROR     │        │ Back to step 2        │
              │ "Max iterations  │        │ LLM.chat(messages)    │
              │  reached"        │        │ (loop continues)      │
              └──────────────────┘        └───────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                        STATE TRANSITIONS                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   IDLE ──▶ THINKING ──▶ TOOL ──▶ THINKING ──▶ ... ──▶ DONE              │
│                         │                                               │
│                         └──▶ DELEGATING ──▶ THINKING ──▶ DONE           │
│                                                                         │
│   Any state ──▶ ERROR (on failure)                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## MCP Integration

Model Context Protocol (MCP) - connect to external tools/services.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         MCP INTEGRATION                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐     ┌──────────────────┐     ┌────────────────┐ │
│  │   Agent     │────▶│  ToolRegistry    │────▶│   MCP Client   │ │
│  │             │     │                  │     │                │ │
│  └─────────────┘     └──────────────────┘     └───────┬────────┘ │
│                                                       │          │
│                  ┌────────────────────────────────────┼────────┐ │
│                  │              MCP Servers           │        │ │
│                  ├────────────────────────────────────┼────────┤ │
│                  │                                    │        │ │
│                  │  ┌─────────┐  ┌─────────┐  ┌──────┴─┐       │ │
│                  │  │  Files  │  │ GitHub  │  │Slack   │       │ │
│                  │  │ Server  │  │ Server  │  │Server  │       │ │
│                  │  └─────────┘  └─────────┘  └────────┘       │ │
│                  │                                             │ │
│                  │  ┌─────────┐  ┌─────────┐  ┌────────┐       │ │
│                  │  │  Jira   │  │ Notion  │  │Custom  │       │ │
│                  │  │ Server  │  │ Server  │  │Server  │       │ │
│                  │  └─────────┘  └─────────┘  └────────┘       │ │
│                  │                                             │ │
│                  └─────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### MCP Client (mcp/client.py)

```python
from mcp import ClientSession, StdioServerParameters
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: Dict

class MCPClient:
    """MCP client for connecting to external tools"""
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: Dict[str, MCPTool] = {}
    
    async def connect(self, name: str, command: List[str], env: Dict = None):
        """Connect to an MCP server"""
        params = StdioServerParameters(
            command=command[0],
            args=command[1:],
            env=env
        )
        session = ClientSession(params)
        await session.initialize()
        
        # Get available tools
        tools = await session.list_tools()
        for tool in tools:
            self.tools[f"{name}:{tool.name}"] = MCPTool(
                name=tool.name,
                description=tool.description,
                input_schema=tool.inputSchema
            )
        
        self.sessions[name] = session
    
    async def call_tool(self, server_name: str, tool_name: str, args: Dict) -> str:
        """Call a tool on an MCP server"""
        if server_name not in self.sessions:
            raise ValueError(f"Not connected to MCP server: {server_name}")
        
        session = self.sessions[server_name]
        result = await session.call_tool(tool_name, args)
        return result.content[0].text if result.content else ""
    
    async def disconnect(self, name: str):
        """Disconnect from an MCP server"""
        if name in self.sessions:
            await self.sessions[name].close()
            del self.sessions[name]
```

### MCP Tool Wrapper (tools/mcp.py)

```python
from tools.registry import ToolRegistry, ToolResult

class MCPToolWrapper:
    """Wrap MCP tools for use in ToolRegistry"""
    
    def __init__(self, mcp_client, server_name: str):
        self.mcp = mcp_client
        self.server = server_name
    
    def execute(self, tool_name: str, query: str = "", **kwargs) -> ToolResult:
        """Execute MCP tool (sync wrapper)"""
        import asyncio
        
        try:
            # Run async MCP call in sync context
            result = asyncio.run(
                self.mcp.call_tool(self.server, tool_name, {"query": query, **kwargs})
            )
            return ToolResult(True, result)
        except Exception as e:
            return ToolResult(False, error=str(e))


# Config-driven MCP servers (config.yaml)
mcp:
  servers:
    - name: "filesystem"
      command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
    
    - name: "github"
      command: ["npx", "-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_TOKEN: "${GITHUB_TOKEN}"
    
    - name: "slack"
      command: ["python", "-m", "mcp_server_slack"]
      env:
        SLACK_BOT_TOKEN: "${SLACK_BOT_TOKEN}"
```

### Register MCP Tools

```python
# In main.py or tools/__init__.py
import asyncio

async def setup_mcp_tools(config):
    mcp_client = MCPClient()
    
    for server in config.mcp.servers:
        await mcp_client.connect(
            name=server.name,
            command=server.command,
            env=server.env
        )
        
        # Wrap and register each tool
        wrapper = MCPToolWrapper(mcp_client, server.name)
        
        # Register all tools from this server
        for tool_name in mcp_client.tools:
            if tool_name.startswith(f"{server.name}:"):
                actual_name = tool_name.replace(f"{server.name}:", "")
                ToolRegistry.register(
                    f"mcp_{server.name}_{actual_name}",
                    lambda q, t=actual_name, w=wrapper: w.execute(t, q)
                )

# Or simple sync version
def mcp_tool(query: str, mcp_client, tool_name: str) -> str:
    """Sync wrapper for MCP tool"""
    import asyncio
    return asyncio.run(mcp_client.call_tool("default", tool_name, {"query": query}))

ToolRegistry.register("mcp", mcp_tool)
```

### MCP in Agent Protocol

```python
# Agent can now use MCP tools
{
    "action": "tool",
    "tool": "mcp_github_get_issues",
    "query": "repo=owner/repo&state=open"
}

{
    "action": "tool",
    "tool": "mcp_filesystem_read",
    "query": "path=/workspace/data.csv"
}
```

---

## Agent Protocol

Agents communicate via JSON actions:

```python
# Tool execution
{"action": "tool", "tool": "console", "query": "python train.py"}

# Delegate to another agent
{"action": "delegate", "agent": "CodeAgent", "task": "Write training script"}

# Complete with result
{"action": "done", "result": "Training complete. Score: 0.85"}

# Ask for more info
{"action": "clarify", "question": "What metric should I optimize?"}
```

---

## Tool Examples

```python
# Console tool
def console_tool(query: str, sandbox: Sandbox) -> str:
    result = sandbox.execute(query)
    return result.output if result.success else f"Error: {result.error}"

# Files tool
def files_tool(op: str, path: str, content: str = "", sandbox: Sandbox = None) -> str:
    if op == "read":
        return sandbox.read(path)
    elif op == "write":
        sandbox.write(path, content)
        return f"Written to {path}"
    elif op == "list":
        return "\n".join(sandbox.list(path))
    return f"Unknown operation: {op}"

# Search tool (via OpenRouter)
def search_tool(query: str, llm: LLM) -> str:
    response = llm.generate(
        model="openai/gpt-4o-mini",
        prompt=f"Search for: {query}\n\nProvide a concise answer.",
        max_tokens=500
    )
    return response

# Register tools
ToolRegistry.register("console", console_tool)
ToolRegistry.register("files", files_tool)
ToolRegistry.register("search", search_tool)
```

---

## Kaggle Pipeline (kaggle.py)

```python
class KagglePipeline:
    def __init__(self, sandbox: Sandbox, llm: LLM):
        self.sandbox = sandbox
        self.llm = llm
    
    def run(self, competition: str) -> str:
        # Phase 1: Load and analyze data
        self.sandbox.write("analyze.py", self._get_analysis_code())
        result = self.sandbox.execute(f"python analyze.py")
        if not result.success:
            return f"Analysis failed: {result.error}"
        
        # Phase 2: Preprocess
        self.sandbox.write("preprocess.py", self._get_preprocess_code())
        result = self.sandbox.execute(f"python preprocess.py")
        
        # Phase 3: Feature engineering
        self.sandbox.write("features.py", self._get_features_code())
        result = self.sandbox.execute(f"python features.py")
        
        # Phase 4: Train model
        self.sandbox.write("train.py", self._get_train_code())
        result = self.sandbox.execute(f"python train.py")
        
        # Phase 5: Generate submission
        self.sandbox.write("submit.py", self._get_submit_code())
        result = self.sandbox.execute(f"python submit.py")
        
        return "Pipeline complete"
    
    def _get_analysis_code(self) -> str:
        # Return LLM-generated analysis code
        prompt = """Write Python code to:
1. Load train.csv and test.csv
2. Display basic statistics
3. Show missing values
4. Display first few rows"""
        return self.llm.generate("anthropic/claude-3.5-sonnet", prompt)
```

---

## Config (config.yaml)

```yaml
llm:
  model: "anthropic/claude-3.5-sonnet"
  temperature: 0.7
  max_tokens: 4096

sandbox:
  root: "./workspace"
  timeout: 120
  allowed_commands:
    - python
    - pip
    - ls
    - cat
    - head
    - mkdir

agents:
  - name: "Coordinator"
    role: "Plan and delegate tasks"
    tools: ["delegate", "message"]
  
  - name: "Code"
    role: "Execute code in sandbox"
    tools: ["console", "files"]
  
  - name: "Critic"
    role: "Review and critique solutions"
    tools: ["message", "search"]

prompts:
  coordinator: "prompts/coordinator.yaml"
  code: "prompts/code.yaml"
  critic: "prompts/critic.yaml"
```

---

## Frontend (Svelte)

```svelte
<!-- src/lib/Chat.svelte -->
<script>
  import { onMount } from 'svelte';
  import { ws } from '$lib/stores';
  
  export let sessionId;
  let messages = [];
  let input = "";
  
  async function send() {
    const res = await fetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, message: input })
    });
    const data = await res.json();
    messages = [...messages, { role: 'user', content: input }, data.response];
    input = "";
  }
</script>

<div class="chat">
  {#each messages as msg}
    <div class="message {msg.role}">{msg.content}</div>
  {/each}
  <input bind:value={input} on:keydown={(e) => e.key === 'Enter' && send()} />
</div>
```

---

## Entry Point (main.py)

```python
import sys
from pathlib import Path
from core.config import Config
from core.state import StateManager
from core.llm import LLM
from core.sandbox import Sandbox
from tools.registry import ToolRegistry
from agents.base import BaseAgent, AgentConfig

def main():
    config = Config.load("config.yaml")
    
    # Initialize components
    llm = LLM()
    sandbox = Sandbox(Path(config.sandbox.root))
    state = StateManager()
    
    # Register tools
    from tools.console import console_tool
    from tools.files import files_tool
    ToolRegistry.register("console", console_tool)
    ToolRegistry.register("files", files_tool)
    
    # Create session
    query = " ".join(sys.argv[1:]) or "Hello"
    session = state.create_session(query)
    
    # Run coordinator agent
    agent_config = AgentConfig(
        name="Coordinator",
        role="Plan tasks",
        tools=["delegate", "message"]
    )
    agent = BaseAgent(agent_config, llm, sandbox, ToolRegistry)
    
    result = agent.run(query)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
```

### Old scripts exsemple paths

Agent (base.py)	my_old/multi_agent_system/agents/base/base_agent.py
ToolRegistry	my_old/multi_agent_system/tools/tools.py (класс Tool)
Sandbox	my_old/multi_agent_system/utils/sandbox.py
LLM	my_old/multi_agent_system/core/llm_engine.py
Config	my_old/multi_agent_system/core/config.py + core/settings.py
State	my_old/multi_agent_system/core/context_manager.py
Orchestrator	my_old/multi_agent_system/core/orchestrator.py
Coordinator	my_old/multi_agent_system/agents/base/coordinator.py
CodeAgent	my_old/multi_agent_system/agents/base/base_agent.py
SearchAgent	my_old/multi_agent_system/agents/base/search.py
RAG	my_old/multi_agent_system/rag/rag_system.py
Prompts	my_old/multi_agent_system/core/protocol_2026.py (patterns)
Dashboard	my_old/multi_agent_system/dashboard.py