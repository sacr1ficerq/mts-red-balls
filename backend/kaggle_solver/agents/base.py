from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
import json
import logging
import time

logger = logging.getLogger(__name__)


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    TOOL = "tool"
    DELEGATING = "delegating"
    WAITING = "waiting"
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
    max_tokens: int = 4096


@dataclass
class AgentResult:
    success: bool
    output: str = ""
    error: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    duration: float = 0.0


class BaseAgent(ABC):
    def __init__(
        self,
        config: AgentConfig,
        llm,
        sandbox,
        tool_registry,
        event_callback: Optional[Callable] = None,
        agent_factory: Optional[Any] = None
    ):
        self.config = config
        self.llm = llm
        self.sandbox = sandbox
        self.tools = tool_registry
        self.event_callback = event_callback
        self.agent_factory = agent_factory
        self.state = AgentState.IDLE
        self.messages: List[Dict[str, str]] = []
        self.context: List[str] = []
        self._iteration = 0

    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        if self.event_callback:
            self.event_callback({
                "agent": self.config.name,
                "type": event_type,
                "data": data,
                "timestamp": time.time()
            })

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def add_context(self, text: str):
        self.context.append(text)
        if len(self.context) > 10:
            self.context = self.context[-10:]

    @abstractmethod
    def system_prompt(self) -> str:
        pass

    def reset(self):
        self.messages = []
        self.context = []
        self.state = AgentState.IDLE
        self._iteration = 0

    def run(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        start_time = time.time()
        self.reset()
        self.add_message("user", user_input)
        
        system_msg = self.system_prompt()
        if context:
            system_msg += f"\n\nContext: {json.dumps(context)}"
        
        full_messages = [{"role": "system", "content": system_msg}] + self.messages

        self._emit_event("start", {"input": user_input})

        for self._iteration in range(1, self.config.max_iterations + 1):
            self.state = AgentState.THINKING
            self._emit_event("thinking", {"iteration": self._iteration})

            try:
                response = self.llm.chat(
                    model=self.config.model,
                    messages=full_messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
                )
            except Exception as e:
                self.state = AgentState.ERROR
                logger.error(f"LLM error: {e}")
                return AgentResult(
                    success=False,
                    error=str(e),
                    duration=time.time() - start_time
                )

            self.add_message("assistant", response)
            self._emit_event("thought", {"content": response, "iteration": self._iteration})

            action = self._parse_action(response)
            action_type = action.get("action", "done")

            if action_type == "done":
                self.state = AgentState.DONE
                self._emit_event("done", {"result": action.get("result", response)})
                return AgentResult(
                    success=True,
                    output=action.get("result", response),
                    steps=self._collect_steps(),
                    duration=time.time() - start_time
                )

            elif action_type == "tool":
                self.state = AgentState.TOOL
                tool_name = action.get("tool", "")
                tool_input = action.get("query", action.get("input", ""))
                
                self._emit_event("tool_start", {"tool": tool_name, "input": tool_input})

                result = self.tools.execute(
                    tool_name,
                    query=tool_input,
                    sandbox=self.sandbox
                )

                tool_result = result.output if result.success else f"Error: {result.error}"
                full_messages.append({"role": "tool", "content": f"{tool_name}: {tool_result}"})
                
                self._emit_event("tool_end", {
                    "tool": tool_name,
                    "success": result.success,
                    "output": tool_result[:500]
                })

            elif action_type == "delegate":
                self.state = AgentState.DELEGATING
                delegate_to = action.get("agent", "")
                task = action.get("task", "")
                
                self._emit_event("delegate_start", {"to": delegate_to, "task": task})
                
                # Actually delegate to another agent
                if self.agent_factory and delegate_to:
                    try:
                        sub_agent = self.agent_factory(
                            name=delegate_to,
                            role=f"Execute {delegate_to} tasks",
                            tools=["tool"],
                            event_callback=self.event_callback
                        )
                        
                        # Run the sub-agent
                        sub_result = sub_agent.run(task)
                        
                        # Add sub-agent result to messages
                        full_messages.append({
                            "role": "system", 
                            "content": f"[{delegate_to} completed]: {sub_result.output}"
                        })
                        
                        self._emit_event("delegate_end", {
                            "to": delegate_to,
                            "result": sub_result.output,
                            "success": sub_result.success
                        })
                    except Exception as e:
                        self._emit_event("delegate_error", {"to": delegate_to, "error": str(e)})
                else:
                    self._emit_event("delegate", {"to": delegate_to, "task": task})

            elif action_type == "clarify":
                self.state = AgentState.WAITING
                question = action.get("question", "")
                self._emit_event("clarify", {"question": question})
                return AgentResult(
                    success=False,
                    output="",
                    error=f"Clarification needed: {question}",
                    duration=time.time() - start_time
                )

        self.state = AgentState.ERROR
        self._emit_event("max_iterations", {"iterations": self._iteration})
        return AgentResult(
            success=False,
            output="",
            error=f"Max iterations ({self.config.max_iterations}) reached",
            steps=self._collect_steps(),
            duration=time.time() - start_time
        )

    def _collect_steps(self) -> List[Dict[str, Any]]:
        steps = []
        for msg in self.messages:
            if msg["role"] == "assistant":
                action = self._parse_action(msg["content"])
                if action.get("action", "done") != "done":
                    steps.append(action)
        return steps

    def _parse_action(self, response: str) -> Dict[str, Any]:
        try:
            start = response.find('{')
            if start == -1:
                return {"type": "done", "result": response}
            
            end = response.rfind('}')
            if end == -1:
                return {"type": "done", "result": response}
            
            json_str = response[start:end+1]
            action = json.loads(json_str)
            
            if "content" in action:
                content = action["content"]
                if isinstance(content, str):
                    content = content.strip()
                    if content.startswith('{') and content.endswith('}'):
                        try:
                            nested = json.loads(content)
                            if isinstance(nested, dict):
                                action.update(nested)
                                del action["content"]
                        except:
                            pass
            
            return action
        except (json.JSONDecodeError, ValueError) as e:
            pass
        
        if "done" in response.lower()[:50]:
            return {"type": "done", "result": response}
        
        return {"type": "done", "result": response}


class AgentFactory:
    """Deprecated: Use AgentRegistry from agents.registry instead."""
    
    @classmethod
    def register(cls, name: str, agent_class: type):
        from kaggle_solver.agents.registry import AgentRegistry
        return AgentRegistry.register(name, agent_class)
    
    @classmethod
    def create(cls, name: str, config, llm, sandbox, tool_registry, event_callback=None):
        from kaggle_solver.agents.registry import AgentRegistry
        return AgentRegistry.create(name, config, llm, sandbox, tool_registry, event_callback)
    
    @classmethod
    def list_agents(cls) -> List[str]:
        from kaggle_solver.agents.registry import AgentRegistry
        return AgentRegistry.list_agents()

