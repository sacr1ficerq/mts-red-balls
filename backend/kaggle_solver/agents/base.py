import json
import re
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


def parse_json_output(text: str) -> Dict[str, Any]:
    """Parse JSON from LLM output, handling extra text"""
    if not text:
        return {}
    
    text = text.strip()
    
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Find JSON in text
    start = text.find('{')
    if start >= 0:
        # Find matching closing brace
        depth = 0
        for i, char in enumerate(text[start:], start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        pass
    
    return {}


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


class AgentConstants:
    """Agent behavior constants.
    
    These values control agent behavior and limits.
    """
    
    # Maximum number of context events to subscribe to
    # Prevents context window overflow while maintaining relevance
    MAX_CONTEXT_EVENTS = 3
    
    # Maximum consecutive plan actions before forcing delegation
    # Prevents infinite planning loops
    MAX_CONSECUTIVE_PLANS = 2
    
    # Maximum tokens for LLM output
    # Based on model limits and response quality tradeoff
    MAX_OUTPUT_TOKENS = 8192
    
    # Approximate tokens per character (rough estimate)
    # Used for token counting when exact tokenizer unavailable
    CHARS_PER_TOKEN = 4


class BaseAgent(ABC):
    MAX_CONTEXT_EVENTS = AgentConstants.MAX_CONTEXT_EVENTS
    MAX_CONSECUTIVE_PLANS = AgentConstants.MAX_CONSECUTIVE_PLANS
    
    def __init__(
        self,
        config: AgentConfig,
        llm,
        sandbox,
        tool_registry,
        event_callback: Optional[Callable] = None,
        agent_factory: Optional[Any] = None,
        session=None
    ):
        self.config = config
        self.llm = llm
        self.sandbox = sandbox
        self.tools = tool_registry
        self.event_callback = event_callback
        self.agent_factory = agent_factory
        self.session = session
        self.state = AgentState.IDLE
        self.messages: List[Dict[str, str]] = []
        self._iteration = 0

    def _emit(self, event_type: str, data: Dict[str, Any]):
        if self.event_callback:
            data["expanded"] = True
            self.event_callback({"type": event_type, "data": data, "agent": self.config.name, "timestamp": datetime.now().isoformat()})

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    @abstractmethod
    def system_prompt(self) -> str:
        pass

    def run(self, user_input: str, context: Optional[Dict[str, Any]] = None, is_sub_call: bool = False) -> AgentResult:
        start = time.time()
        
        self.messages = []
        self.add_message("user", user_input)
        
        # Handle context subscription (event_ids)
        if context:
            if "session" in context:
                self.session = context["session"]
            
            # Subscribe to events by ID
            if "event_ids" in context and self.session:
                event_ids = context["event_ids"][:self.MAX_CONTEXT_EVENTS]
                subscribed_events = self.session.get_events_by_ids(event_ids)
                
                # Add context events to the beginning of messages
                for e in subscribed_events:
                    event_type = e.get("type", "event")
                    event_data = e.get("data", {})
                    content = str(event_data) if event_data else ""
                    context_msg = f"[Context #{e['event_id']}] {event_type}: {content}"
                    self.messages.insert(0, {"role": "system", "content": context_msg})
        
        system = self.system_prompt()
        
        full = [{"role": "system", "content": system}] + self.messages
        
        # Track consecutive plans to prevent infinite loop
        consecutive_plans = 0
        
        # Only emit "system" if NOT a sub-call (sub-call events are nested under parent)
        if not is_sub_call:
            self._emit("system", {"message": f"Starting: {user_input}"})

        for self._iteration in range(1, self.config.max_iterations + 1):
            try:
                max_output_tokens = AgentConstants.MAX_OUTPUT_TOKENS
                resp = self.llm.chat(
                    model=self.config.model,
                    messages=full,
                    temperature=self.config.temperature,
                    max_tokens=max_output_tokens
                )
                input_tokens = sum(len(m.get("content", "")) // 4 for m in full)
                output_tokens = len(resp) // 4
                if hasattr(self, 'session') and self.session:
                    self.session.add_tokens(input_tokens + output_tokens)
            except Exception as e:
                logger.error(f"LLM error: {e}")
                return AgentResult(success=False, error=str(e), duration=time.time() - start)

            self.add_message("assistant", resp)
            self._emit("thought", {"content": resp, "raw_response": resp, "expanded": True})
            
            action = self._parse(resp)
            
            # Track consecutive plans
            if action.get("action") == "plan":
                consecutive_plans += 1
            else:
                consecutive_plans = 0
            
            # Force delegate after 2 consecutive plans (prevent infinite loop)
            if consecutive_plans >= self.MAX_CONSECUTIVE_PLANS and self.agent_factory:
                logger.warning("Consecutive plans detected, forcing delegation")
                steps = action.get("steps", [])
                if steps:
                    task = steps[0].get("task", "search")
                    self._emit("delegate", {
                        "target_agent": "SearchAgent", 
                        "task": task,
                        "expanded": True
                    })
                    sub = self.agent_factory(name="SearchAgent", role="Execute SearchAgent", tools=["tool"])
                    sub_context = {"event_ids": []}
                    if self.session:
                        sub_context["session"] = self.session
                    sub_result = sub.run(task, context=sub_context, is_sub_call=True)
                    self._emit("result", {"content": sub_result.output})
                    return AgentResult(success=True, output=sub_result.output, duration=time.time() - start)
            
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
                    kwargs["search"] = action.get("search", "")
                    kwargs["replace"] = action.get("replace", "")
                else:
                    for k, v in action.items():
                        if k not in ["action", "tool"]:
                            kwargs[k] = v
                
                result = self.tools.execute(
                    tool_name,
                    sandbox=self.sandbox,
                    llm=self.llm,
                    **kwargs
                )
                
                output = result.output if result.success else f"Error: {result.error}"
                self._emit("tool", {
                    "tool_name": tool_name, 
                    "input": str(kwargs), 
                    "output": output[:2000],
                    "success": result.success,
                    "expanded": True
                })
                
                # Add tool message with tool_call_id to satisfy providers that require it
                tool_call_id = f"call_{action.get('tool', 'tool')}_{self._iteration}"
                tool_msg = {"role": "tool", "content": f"{action.get('tool')}: {output}", "tool_call_id": tool_call_id}
                self.add_message("tool", f"{action.get('tool')}: {output}")
                full.append(tool_msg)
                
                # Continue loop to process tool result - don't return here!

            elif action.get("action") == "delegate" and self.agent_factory:
                target = action.get("agent", "")
                task = action.get("task", "")
                context_ids = action.get("context_ids", [])[:3]
                plan_id = action.get("plan_id", "")
                step_id = action.get("step_id", 0)
                
                self._emit("delegate", {
                    "target_agent": target, 
                    "task": task,
                    "context_ids": context_ids,
                    "plan_id": plan_id,
                    "step_id": step_id,
                    "expanded": True
                })
                
                sub = self.agent_factory(name=target, role=f"Execute {target}", tools=["tool"])
                
                # Pass context with event IDs and plan info
                sub_context = {"event_ids": context_ids}
                if self.session:
                    sub_context["session"] = self.session
                
                sub_result = sub.run(task, context=sub_context, is_sub_call=True)
                
                # Emit delegate result as tool event
                self._emit("tool", {
                    "tool_name": "delegate", 
                    "input": f"delegate to {target}: {task}",
                    "output": sub_result.output[:2000],
                    "success": sub_result.success,
                    "expanded": True
                })
                
                # Add tool message with tool_call_id
                tool_call_id = f"call_delegate_{self._iteration}"
                tool_msg = {"role": "tool", "content": f"delegate to {target}: {sub_result.output}", "tool_call_id": tool_call_id}
                self.add_message("tool", f"delegate to {target}: {sub_result.output}")
                full.append(tool_msg)

                # After delegate, optionally run CriticAgent for validation
                if self.agent_factory and sub_result.output:
                    critic = self.agent_factory(name="CriticAgent", role="Validate results", tools=["tool"])
                    critic_result = critic.run(f"Validate and improve this answer: {sub_result.output}", context=sub_context, is_sub_call=True)
                    if critic_result.output:
                        # Emit critic result
                        self._emit("tool", {
                            "tool_name": "critic",
                            "input": "validate and improve",
                            "output": critic_result.output[:2000],
                            "success": critic_result.success,
                            "expanded": True
                        })
                        self.add_message("tool", f"CriticAgent: {critic_result.output}")
                        full.append({"role": "tool", "content": f"CriticAgent: {critic_result.output}"})

            elif action.get("action") == "done":
                self._emit("result", {"content": action.get("result", "")})
                return AgentResult(success=True, output=action.get("result", ""), duration=time.time() - start)

            elif action.get("action") == "options":
                options = action.get("options", [])
                question = action.get("question", "Выберите опцию:")
                self._emit("button_options", {
                    "question": question,
                    "options": options,
                    "expanded": True
                })
                self.add_message("tool", f"options: {question}")
                full.append({"role": "tool", "content": f"options: {question}"})

            elif action.get("action") == "plan":
                plan_id = action.get("plan_id", "")
                steps = action.get("steps", [])
                self._emit("plan", {
                    "plan_id": plan_id,
                    "steps": steps,
                    "expanded": True
                })
                
                # Just emit plan - coordinator decides when and how to delegate
                plan_text = f"Plan created with {len(steps)} steps. Now delegate the first step."
                tool_call_id = f"call_plan_{self._iteration}"
                tool_msg = {"role": "tool", "content": plan_text, "tool_call_id": tool_call_id}
                self.add_message("tool", plan_text)
                full.append(tool_msg)

            elif action.get("action") == "update_plan":
                plan_id = action.get("plan_id", "")
                update = action.get("update", {})
                update_type = update.get("type", "")
                self._emit("update_plan", {
                    "plan_id": plan_id,
                    "update": update,
                    "expanded": True
                })
                self.add_message("tool", f"plan updated: {update_type}")
                full.append({"role": "tool", "content": f"plan updated: {update_type}"})

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

        # Take ONLY THE FIRST valid action - execute one at a time!
        # Multiple actions in one response is NOT allowed - this causes loops
        if json_objects:
            # First, try to find a "done" action - prefer final results over intermediate actions
            for obj in json_objects:
                if isinstance(obj, dict) and obj.get("action") == "done":
                    return obj
            
            # Otherwise take the first valid action
            first_obj = json_objects[0]
            if isinstance(first_obj, dict) and "action" in first_obj:
                action = first_obj.get("action", "")
                # Only these actions are allowed
                if action in ("tool", "delegate", "options", "plan", "update_plan", "done"):
                    return first_obj
        
        # Try to handle truncated JSON - response might be cut off mid-JSON
        response_stripped = response.strip()
        
        # If it starts with { but doesn't end with }, try to find complete JSON
        if response_stripped.startswith('{') and not response_stripped.endswith('}'):
            # Try to complete the JSON by finding action field
            action_match = re.search(r'"action"\s*:\s*"([^"]+)"', response_stripped)
            if action_match:
                action_type = action_match.group(1)
                # Extract what we can
                partial_result = {"action": action_type}
                
                # Try to extract other fields
                task_match = re.search(r'"task"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', response_stripped)
                if task_match:
                    partial_result["task"] = task_match.group(1)
                
                plan_match = re.search(r'"plan"\s*:\s*\{', response_stripped)
                if plan_match:
                    partial_result["plan"] = "..."
                
                if action_type in ("tool", "delegate", "options", "plan", "update_plan", "done"):
                    logger.warning(f"Using truncated JSON with action: {action_type}")
                    return partial_result
        
        # If response looks like JSON but wasn't parsed correctly, try direct parsing
        if response_stripped.startswith('{') and response_stripped.endswith('}'):
            try:
                direct_parse = json.loads(response_stripped)
                if isinstance(direct_parse, dict) and "action" in direct_parse:
                    action = direct_parse.get("action", "")
                    if action in ("tool", "delegate", "options", "plan", "update_plan", "done"):
                        return direct_parse
            except:
                pass
        
        # If no valid JSON action found, treat entire response as text result
        # Clean up the response - remove markdown code blocks if present
        cleaned_response = re.sub(r'^```json\s*', '', response.strip())
        cleaned_response = re.sub(r'^```\s*', '', cleaned_response)
        cleaned_response = re.sub(r'```$', '', cleaned_response).strip()
        
        # If it still looks like JSON after cleaning, extract just the result
        if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
            try:
                json_resp = json.loads(cleaned_response)
                if "result" in json_resp:
                    return {"action": "done", "result": json_resp["result"]}
            except:
                pass
        
        return {"action": "done", "result": cleaned_response if cleaned_response else response}
