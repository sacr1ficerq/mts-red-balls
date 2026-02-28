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
            data["expanded"] = True
            self.event_callback({"type": event_type, "data": data, "agent": self.config.name, "timestamp": __import__("datetime").datetime.now().isoformat()})

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
        self._emit("system", {"message": f"Starting: {user_input}"})

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
            self._emit("thought", {"content": resp, "raw_response": resp, "expanded": True})
            
            action = self._parse(resp)
            
            # Check for infinite loops or repeated failures
            if self._iteration > 1 and self.messages[-2].get("role") == "assistant" and self.messages[-2].get("content") == resp:
                 logger.warning("Agent is repeating itself. Forcing a stop.")
                 return AgentResult(success=False, error="Agent stuck in a loop", duration=time.time() - start)

            if action.get("action") == "tool":
                tool_name = action.get("tool", "")
                
                # Build kwargs based on tool type
                kwargs = {}
                if tool_name == "console":
                    kwargs["query"] = action.get("query", "")
                elif tool_name == "files":
                    kwargs["op"] = action.get("op", "read")
                    kwargs["path"] = action.get("path", "")
                    kwargs["content"] = action.get("content", "")
                else:
                    for k, v in action.items():
                        if k not in ["action", "tool"]:
                            kwargs[k] = v
                
                self._emit("tool", {"tool_name": tool_name, "input": str(kwargs), "status": "running", "expanded": True})
                
                result = self.tools.execute(
                    tool_name,
                    sandbox=self.sandbox,
                    llm=self.llm,
                    **kwargs
                )
                
                output = result.output if result.success else f"Error: {result.error}"
                self._emit("tool", {"tool_name": tool_name, "input": str(kwargs), "output": output[:1000], "status": "completed", "expanded": True})
                
                self.add_message("tool", f"{action.get('tool')}: {output}")
                full.append({"role": "tool", "content": f"{action.get('tool')}: {output}"})
                
                # Continue loop to process tool result - don't return here!

            elif action.get("action") == "delegate" and self.agent_factory:
                target = action.get("agent", "")
                task = action.get("task", "")
                self._emit("system", {"message": f"Delegating to {target}: {task[:50]}..."})
                
                sub = self.agent_factory(name=target, role=f"Execute {target}", tools=["tool"])
                sub_result = sub.run(task)
                
                self._emit("tool", {"tool_name": "delegate", "output": sub_result.output[:500], "status": "completed"})
                
                # Add delegate result to messages and continue loop
                self.add_message("tool", f"delegate to {target}: {sub_result.output}")
                full.append({"role": "tool", "content": f"delegate to {target}: {sub_result.output}"})

            elif action.get("action") == "done":
                self._emit("result", {"content": action.get("result", "")})
                return AgentResult(success=True, output=action.get("result", ""), duration=time.time() - start)

        return AgentResult(success=False, error="Max iterations", duration=time.time() - start)

    def _parse(self, response: str) -> Dict[str, Any]:
        import re
        import json
        
        # Try to find JSON block using a stack-based approach for nested braces
        def extract_json_objects(text):
            objects = []
            stack = []
            start_index = -1
            
            for i, char in enumerate(text):
                if char == '{':
                    if not stack:
                        start_index = i
                    stack.append(char)
                elif char == '}':
                    if stack:
                        stack.pop()
                        if not stack:
                            try:
                                json_str = text[start_index:i+1]
                                obj = json.loads(json_str)
                                objects.append(obj)
                            except json.JSONDecodeError:
                                pass
            return objects

        json_objects = extract_json_objects(response)
        
        # If simple extraction failed, try regex for markdown code blocks
        if not json_objects:
            code_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            for block in code_blocks:
                try:
                    json_objects.append(json.loads(block))
                except:
                    pass

        # Prioritize actions
        for obj in json_objects:
            if isinstance(obj, dict) and obj.get("action") == "done":
                return obj
        
        for obj in json_objects:
            if isinstance(obj, dict) and obj.get("action") in ("tool", "delegate"):
                return obj
                
        for obj in json_objects:
            if isinstance(obj, dict) and "action" in obj:
                return obj

        # If no valid JSON action found, but it looks like they tried (contains "action":),
        # we might want to retry. But for now, fallback to text result.
        # Improvement: If response is short and looks like a thought, maybe continue?
        
        return {"action": "done", "result": response}
