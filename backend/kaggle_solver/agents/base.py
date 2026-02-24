import json
import re
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


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


@dataclass
class AgentResult:
    success: bool
    output: str = ""
    error: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
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
        self._iteration = 0

    def _emit(self, event_type: str, data: Dict[str, Any]):
        if self.event_callback:
            self.event_callback({"type": event_type, "data": data, "agent": self.config.name})

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    @abstractmethod
    def system_prompt(self) -> str:
        pass

    def run(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        import time
        start = time.time()
        
        self.messages = []
        self.add_message("user", user_input)
        
        system = self.system_prompt()
        if context:
            system += f"\n\nContext: {json.dumps(context)}"
        
        full = [{"role": "system", "content": system}] + self.messages
        self._emit("start", {"input": user_input})

        for self._iteration in range(1, self.config.max_iterations + 1):
            try:
                resp = self.llm.chat(
                    model=self.config.model,
                    messages=full,
                    temperature=self.config.temperature,
                    max_tokens=1024
                )
            except Exception as e:
                logger.error(f"LLM error: {e}")
                return AgentResult(success=False, error=str(e), duration=time.time() - start)

            self.add_message("assistant", resp)
            self._emit("thought", {"content": resp})

            action = self._parse(resp)
            
            if action.get("action") == "tool":
                self._emit("tool_start", {"tool": action.get("tool"), "input": action.get("query", "")})
                
                result = self.tools.execute(
                    action.get("tool", ""),
                    query=action.get("query", ""),
                    sandbox=self.sandbox,
                    llm=self.llm
                )
                
                output = result.output if result.success else f"Error: {result.error}"
                self._emit("tool_end", {"tool": action.get("tool"), "output": output[:200]})
                
                self.add_message("tool", f"{action.get('tool')}: {output}")
                full.append({"role": "tool", "content": f"{action.get('tool')}: {output}"})
                
                self._emit("done", {"result": output})
                return AgentResult(success=result.success, output=output, duration=time.time() - start)

            elif action.get("action") == "delegate" and self.agent_factory:
                target = action.get("agent", "")
                task = action.get("task", "")
                self._emit("delegate_start", {"to": target, "task": task})
                
                sub = self.agent_factory(name=target, role=f"Execute {target}", tools=["tool"])
                sub_result = sub.run(task)
                
                self._emit("delegate_end", {"to": target, "result": sub_result.output, "success": sub_result.success})
                self._emit("done", {"result": sub_result.output})
                return AgentResult(success=sub_result.success, output=sub_result.output, duration=time.time() - start)

            elif action.get("action") == "done":
                self._emit("done", {"result": action.get("result", "")})
                return AgentResult(success=True, output=action.get("result", ""), duration=time.time() - start)

        return AgentResult(success=False, error="Max iterations", duration=time.time() - start)

    def _parse(self, response: str) -> Dict[str, Any]:
        matches = re.findall(r'\{[^{}]*\}', response)
        
        for m in reversed(matches):
            try:
                obj = json.loads(m)
                if isinstance(obj, dict) and "action" in obj:
                    return obj
            except:
                continue
        
        return {"action": "done", "result": response}
