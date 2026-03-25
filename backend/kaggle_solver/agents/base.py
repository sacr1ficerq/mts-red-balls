import json
import re
import logging
import time
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from kaggle_solver.constants import (
    AgentAction,
    AgentConstants,
    AgentType,
    ToolType,
)
from kaggle_solver.llm import LLMError

logger = logging.getLogger(__name__)


def parse_json_output(text: str) -> Dict[str, Any]:
    """Parse JSON from LLM output, handling extra text"""
    if not text:
        return {}

    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.debug(f"Direct JSON parse failed: {e}")

    # Find JSON in text
    start = text.find("{")
    if start >= 0:
        # Find matching closing brace
        depth = 0
        for i, char in enumerate(text[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError as e:
                        logger.debug(f"JSON extraction failed: {e}")

    logger.warning(f"Failed to parse JSON from text: {text[:100]}...")
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


class BaseAgent(ABC):
    MAX_CONTEXT_EVENTS = AgentConstants.MAX_CONTEXT_EVENTS
    MAX_CONSECUTIVE_PLANS = AgentConstants.MAX_CONSECUTIVE_PLANS
    MAX_CONTEXT_MESSAGES = AgentConstants.MAX_CONTEXT_MESSAGES
    AGENT_TOOLS = AgentConstants.AGENT_TOOLS

    @staticmethod
    def get_tools_for_agent(agent_name: str) -> List[str]:
        """Get the list of tools for a given agent name."""
        return BaseAgent.AGENT_TOOLS.get(agent_name, ["tool"])

    def __init__(
        self,
        config: AgentConfig,
        llm: Any,
        sandbox: Any,
        tool_registry: Any,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        agent_factory: Optional[Callable[..., "BaseAgent"]] = None,
        session: Optional[Any] = None,
    ) -> None:
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
        self._active_plan: Optional[Dict[str, Any]] = None

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event to the event callback."""
        if self.event_callback:
            data["expanded"] = True
            self.event_callback(
                {
                    "type": event_type,
                    "data": data,
                    "agent": self.config.name,
                    "timestamp": datetime.now().isoformat(),
                }
            )

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history with memory limit."""
        self.messages.append({"role": role, "content": content})
        # Prevent unbounded memory growth - keep only recent messages
        if len(self.messages) > self.MAX_CONTEXT_MESSAGES:
            # Keep system messages and recent messages
            system_messages = [m for m in self.messages if m.get("role") == "system"]
            other_messages = [m for m in self.messages if m.get("role") != "system"]
            # Keep most recent non-system messages
            kept_other = other_messages[
                -(self.MAX_CONTEXT_MESSAGES - len(system_messages)) :
            ]
            self.messages = system_messages + kept_other
            logger.debug(f"Trimmed message history to {len(self.messages)} messages")

    def _normalize_plan_steps(
        self, steps: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        normalized = []
        for step in steps:
            step_copy = dict(step)
            step_copy.setdefault("status", "pending")
            normalized.append(step_copy)
        return normalized

    def _sync_session_plan_artifact(self) -> None:
        if not self.session:
            return

        if not self._active_plan:
            self.session.delete_artifact("current_plan")
            return

        self.session.set_artifact(
            "current_plan",
            {
                "plan_id": self._active_plan.get("plan_id", ""),
                "steps": [dict(step) for step in self._active_plan.get("steps", [])],
            },
        )

    def _restore_active_plan_from_session(self) -> None:
        if not self.session:
            return

        current_plan = self.session.get_artifact("current_plan")
        if not isinstance(current_plan, dict):
            return

        steps = current_plan.get("steps", [])
        if not isinstance(steps, list):
            return

        self._active_plan = {
            "plan_id": current_plan.get("plan_id", ""),
            "steps": self._normalize_plan_steps(steps),
        }

    def _set_active_plan_step_status(self, step_id: Any, status: str) -> None:
        if not self._active_plan or not step_id:
            return

        for index, step in enumerate(self._active_plan.get("steps", [])):
            if step.get("id") == step_id:
                next_step = dict(step)
                next_step["status"] = status
                self._active_plan["steps"][index] = next_step
                self._sync_session_plan_artifact()
                return

    def _plan_has_unresolved_steps(self) -> bool:
        if not self._active_plan:
            return False

        for step in self._active_plan.get("steps", []):
            if step.get("status", "pending") not in {"completed", "blocked", "skipped"}:
                return True
        return False

    def _next_unfinished_plan_step(self) -> Optional[Dict[str, Any]]:
        if not self._active_plan:
            return None

        for step in self._active_plan.get("steps", []):
            if step.get("status", "pending") not in {"completed", "blocked", "skipped"}:
                return step
        return None

    def _format_plan_progress_message(self) -> str:
        next_step = self._next_unfinished_plan_step()
        if next_step:
            return (
                f"Plan still has unfinished work. Next step ({next_step.get('id')}): "
                f"delegate to {next_step.get('agent', 'CodeAgent')} with task: "
                f"{next_step.get('task', '')}. Do not use 'done' until the full plan is resolved."
            )
        return "All plan steps are resolved. You may now return the final answer using the 'done' action."

    def _apply_plan_updates(self, action: Dict[str, Any]) -> Dict[str, Any]:
        plan_id = action.get("plan_id", "")
        if not self._active_plan or (
            plan_id and self._active_plan.get("plan_id") != plan_id
        ):
            return {"plan_id": plan_id, "step_updates": [], "add_steps": []}

        raw_step_updates = action.get("step_updates", [])
        add_steps = action.get("add_steps", [])
        legacy_update = action.get("update", {})

        if legacy_update:
            legacy_step_id = legacy_update.get("step_id") or action.get("step_id")
            if legacy_step_id is not None:
                raw_step_updates = raw_step_updates + [
                    {
                        "id": legacy_step_id,
                        "status": legacy_update.get("status", "pending"),
                        "task": legacy_update.get("task"),
                        "agent": legacy_update.get("agent"),
                        "note": legacy_update.get("note", ""),
                    }
                ]

        normalized_updates = []
        steps = self._active_plan.get("steps", [])
        step_index = {step.get("id"): idx for idx, step in enumerate(steps)}

        for update in raw_step_updates:
            step_id = update.get("id")
            if step_id not in step_index:
                continue

            step = dict(steps[step_index[step_id]])
            for key in ("status", "task", "agent", "note"):
                value = update.get(key)
                if value not in (None, ""):
                    step[key] = value
            steps[step_index[step_id]] = step
            normalized_updates.append(step)

        if add_steps:
            steps.extend(self._normalize_plan_steps(add_steps))

        self._active_plan["steps"] = steps
        return {
            "plan_id": self._active_plan.get("plan_id", plan_id),
            "step_updates": normalized_updates,
            "add_steps": add_steps,
        }

    def _extract_artifacts(self, output: str) -> str:
        """Extract inline artifact directives from final output.

        Supported format:
        [[artifact:key=value]]
        """
        if not output or not self.session:
            return output

        pattern = re.compile(r"\[\[artifact:([A-Za-z0-9_.-]+)=(.*?)\]\]", re.DOTALL)
        matches = pattern.findall(output)
        for key, value in matches:
            cleaned = value.strip()
            if cleaned:
                self.session.set_artifact(key, cleaned)

        return pattern.sub("", output).strip()

    def _should_defer_subagent_failure(self) -> bool:
        return self.config.name == AgentType.COORDINATOR.value

    def _build_subagent_failure_feedback(
        self,
        target: str,
        task: str,
        error_output: str,
        plan_id: str = "",
        step_id: int = 0,
    ) -> str:
        base_feedback = (
            f"Delegation to {target} failed while executing task: {task}\n\n"
            f"Sub-agent error: {error_output}"
        )

        if plan_id or step_id:
            return (
                f"{base_feedback}\n\n"
                "Decide the next step yourself. Do not stop automatically. "
                "Use update_plan to mark the step failed/blocked or add a corrective step, "
                "then either delegate the recovery work or return an error action if the task is truly blocked."
            )

        return (
            f"{base_feedback}\n\n"
            "Decide the next step yourself. Either delegate a recovery attempt, create a plan, "
            "or return an error action if the task cannot continue."
        )

    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    async def run(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        is_sub_call: bool = False,
        timeout: int = 300,
    ) -> AgentResult:
        """Execute the agent loop to accomplish the user's task.

        The agent follows a think-act-observe loop:
        1. Receive user input and context
        2. Query LLM for next action
        3. Execute action (tool use, delegation, or completion)
        4. Observe results and repeat

        Args:
            user_input: User's request or task description
            context: Optional context including session, event IDs, etc.
            is_sub_call: Whether this is a delegated sub-call
            timeout: Maximum execution time in seconds (default: 300)

        Returns:
            AgentResult with success status, output, and execution duration
        """
        start = time.time()
        execution_timeout = start + timeout

        self.messages = []
        self._active_plan = None
        self.add_message("user", user_input)

        # Handle context subscription (event_ids)
        if context:
            if "session" in context:
                self.session = context["session"]

            self._restore_active_plan_from_session()

            # Handle shared artifacts from previous agents
            if "artifacts" in context and self.session:
                artifacts = context["artifacts"]
                if artifacts:
                    # Add artifacts as system context for the agent
                    artifact_summary = []
                    for key, value in artifacts.items():
                        if isinstance(value, (str, int, float, bool)):
                            artifact_summary.append(f"{key}: {value}")
                        elif isinstance(value, dict):
                            artifact_summary.append(
                                f"{key}: {json.dumps(value, ensure_ascii=False)[:500]}"
                            )
                        else:
                            artifact_summary.append(f"{key}: {str(value)[:500]}")

                    if artifact_summary:
                        artifact_msg = (
                            f"[Shared Context from Previous Agents]\n"
                            + "\n".join(artifact_summary)
                        )
                        self.messages.insert(
                            0, {"role": "system", "content": artifact_msg}
                        )
                        logger.info(
                            f"Agent received {len(artifacts)} artifacts from context"
                        )

            # Subscribe to events by ID
            if "event_ids" in context and self.session:
                event_ids = context["event_ids"][: self.MAX_CONTEXT_EVENTS]
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
            # Check timeout
            if time.time() > execution_timeout:
                logger.error(f"Agent execution timeout after {timeout}s")
                return AgentResult(
                    success=False,
                    error=f"Execution timeout after {timeout}s",
                    duration=time.time() - start,
                )

            # Retry logic for LLM calls using centralized constants
            max_retries = AgentConstants.LLM_MAX_RETRIES
            retry_delay = AgentConstants.LLM_RETRY_DELAY
            llm_timeout = AgentConstants.LLM_CALL_TIMEOUT
            resp = None

            for attempt in range(max_retries):
                try:
                    max_output_tokens = AgentConstants.MAX_OUTPUT_TOKENS
                    resp = await asyncio.wait_for(
                        self.llm.chat(
                            model=self.config.model,
                            messages=full,
                            temperature=self.config.temperature,
                            max_tokens=max_output_tokens,
                        ),
                        timeout=llm_timeout,
                    )
                    input_tokens = sum(len(m.get("content", "")) // 4 for m in full)
                    output_tokens = len(resp) // 4
                    if hasattr(self, "session") and self.session:
                        self.session.add_tokens(input_tokens + output_tokens)
                    break  # Success, exit retry loop
                except asyncio.TimeoutError:
                    logger.warning(
                        f"LLM call timeout on attempt {attempt + 1}/{max_retries}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error(f"LLM call failed after {max_retries} attempts")
                        return AgentResult(
                            success=False,
                            error="LLM call timeout",
                            duration=time.time() - start,
                        )
                except LLMError as e:
                    logger.error(f"LLM configuration/runtime error: {e}")
                    return AgentResult(
                        success=False,
                        error=str(e),
                        duration=time.time() - start,
                    )
                except Exception as e:
                    logger.warning(
                        f"LLM error on attempt {attempt + 1}/{max_retries}: {e}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error(
                            f"LLM call failed after {max_retries} attempts: {e}"
                        )
                        return AgentResult(
                            success=False, error=str(e), duration=time.time() - start
                        )

            if resp is None:
                logger.error("LLM returned None response")
                return AgentResult(
                    success=False,
                    error="LLM returned None response",
                    duration=time.time() - start,
                )

            self.add_message("assistant", resp)
            self._emit(
                "thought", {"content": resp, "raw_response": resp, "expanded": True}
            )

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
                    first_step = steps[0]
                    target_agent = first_step.get("agent", "SearchAgent")
                    task = first_step.get("task", "search")
                    self._emit(
                        "delegate",
                        {"target_agent": target_agent, "task": task, "expanded": True},
                    )
                    agent_tools = self.get_tools_for_agent(target_agent)
                    sub = self.agent_factory(
                        name=target_agent,
                        role=f"Execute {target_agent}",
                        tools=agent_tools,
                    )
                    sub_context = {"event_ids": []}
                    if self.session:
                        sub_context["session"] = self.session
                    sub_result = await sub.run(
                        task, context=sub_context, is_sub_call=True
                    )

                    if not sub_result.success:
                        error_output = (
                            sub_result.error
                            or sub_result.output
                            or "Delegated agent failed"
                        )
                        if self._should_defer_subagent_failure():
                            feedback = self._build_subagent_failure_feedback(
                                target_agent,
                                task,
                                error_output,
                            )
                            self.add_message("user", feedback)
                            full.append({"role": "user", "content": feedback})
                            continue

                        return AgentResult(
                            success=False,
                            error=error_output,
                            output=error_output,
                            duration=time.time() - start,
                        )

                    self._emit("result", {"content": sub_result.output})
                    return AgentResult(
                        success=True,
                        output=sub_result.output,
                        duration=time.time() - start,
                    )

            # Check for infinite loops or repeated failures
            if (
                self._iteration > 1
                and self.messages[-2].get("role") == "assistant"
                and self.messages[-2].get("content") == resp
            ):
                logger.warning("Agent is repeating itself. Forcing a stop.")
                return AgentResult(
                    success=False,
                    error="Agent stuck in a loop",
                    duration=time.time() - start,
                )

            if action.get("action") == "tool":
                tool_result = self._handle_tool_action(action, full, start)
                if tool_result is not None:
                    return tool_result
                continue

            elif action.get("action") == "delegate" and self.agent_factory:
                delegate_result = await self._handle_delegate_action(
                    action, full, start
                )
                if delegate_result is not None:
                    return delegate_result
                continue

            elif action.get("action") == "done":
                result_output = self._extract_artifacts(action.get("result", ""))
                self._emit("result", {"content": result_output})
                return AgentResult(
                    success=True, output=result_output, duration=time.time() - start
                )

            elif action.get("action") == "error":
                error_msg = action.get("error", "Unknown error")
                logger.error(f"Agent encountered error: {error_msg}")
                return AgentResult(
                    success=False, error=error_msg, duration=time.time() - start
                )

            elif action.get("action") == "options":
                self._handle_options_action(action, full)

            elif action.get("action") == "plan":
                plan_result = await self._handle_plan_action(action, full, start)
                if plan_result is not None:
                    return plan_result
                continue

            elif action.get("action") == "update_plan":
                self._handle_update_plan_action(action, full)
                continue

        return AgentResult(
            success=False, error="Max iterations", duration=time.time() - start
        )

    def _handle_tool_action(
        self, action: Dict[str, Any], full: List[Dict[str, Any]], start: float
    ) -> Optional[AgentResult]:
        tool_name = action.get("tool", "")

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

        if tool_name.startswith("kaggle_") and "query" not in kwargs:
            for alias in ["competition", "competition_name", "name"]:
                if alias in kwargs and kwargs.get(alias):
                    kwargs["query"] = kwargs[alias]
                    break

        result = self.tools.execute(
            tool_name, sandbox=self.sandbox, llm=self.llm, **kwargs
        )

        output = result.output if result.success else f"Error: {result.error}"
        self._emit(
            "tool",
            {
                "tool_name": tool_name,
                "input": str(kwargs),
                "output": output[:2000],
                "success": result.success,
                "expanded": True,
            },
        )

        # Add the tool action and observation back into the conversation using
        # standard chat roles supported by plain chat-completions APIs.
        self.add_message("assistant", json.dumps(action))

        # Update full list to include new messages
        system = full[0] if full and full[0].get("role") == "system" else None
        if system:
            full[:] = [system] + self.messages
        else:
            full[:] = self.messages

        # Store important tool results in session artifacts for other agents
        if self.session and result.success:
            # Store Kaggle competition info
            if tool_name == "kaggle_get_competition_info":
                try:
                    comp_info = json.loads(output)
                    self.session.set_artifact("competition_info", comp_info)
                    logger.info(f"Stored competition_info in session artifacts")
                except:
                    pass

            # Store data file paths after download
            elif tool_name == "kaggle_download_data":
                self.session.set_artifact("data_downloaded", True)
                self.session.set_artifact("download_path", kwargs.get("path", "./"))
                logger.info(f"Stored data download info in session artifacts")

            # Store model training results
            elif tool_name == "console" and "train" in kwargs.get("query", "").lower():
                # Try to extract metrics from training output
                if "accuracy" in output.lower() or "loss" in output.lower():
                    self.session.set_artifact("training_output", output)
                    logger.info(f"Stored training output in session artifacts")

            # Store file paths for created files
            elif tool_name == "files" and kwargs.get("op") == "write":
                file_path = kwargs.get("path", "")
                if file_path:
                    # Track created files by type
                    if "train" in file_path.lower():
                        self.session.set_artifact("train_script_path", file_path)
                    elif "submission" in file_path.lower():
                        self.session.set_artifact("submission_file_path", file_path)
                    elif "preprocess" in file_path.lower():
                        self.session.set_artifact("preprocess_script_path", file_path)
                    elif "feature" in file_path.lower():
                        self.session.set_artifact("feature_script_path", file_path)

        if not result.success:
            logger.error(
                f">>> TOOL FAILED: {action.get('tool')}, output: {output[:200]}"
            )
            return AgentResult(
                success=False,
                error=output,
                output=output,
                duration=time.time() - start,
            )

        # Add tool result as user message to guide LLM to next step
        # This prevents LLM from thinking the tool result is its own response
        tool_feedback = f"Tool {action.get('tool')} executed successfully. Output: {output}\n\nContinue with the next step of your workflow."
        tool_msg = {"role": "user", "content": tool_feedback}
        self.add_message("user", tool_feedback)
        # Also add to full for current iteration
        full.append(tool_msg)

        logger.info(f">>> TOOL EXECUTED: {action.get('tool')}, output: {output[:100]}")
        logger.info(f">>> CONTINUING LOOP, iteration: {self._iteration}")
        return None

    async def _handle_delegate_action(
        self, action: Dict[str, Any], full: List[Dict[str, Any]], start: float
    ) -> Optional[AgentResult]:
        target = action.get("agent", "")
        task = action.get("task", "")
        context_ids = action.get("context_ids", [])[:3]
        plan_id = action.get("plan_id", "")
        step_id = action.get("step_id", 0)

        self._set_active_plan_step_status(step_id, "active")

        self._emit(
            "delegate",
            {
                "target_agent": target,
                "task": task,
                "context_ids": context_ids,
                "plan_id": plan_id,
                "step_id": step_id,
                "expanded": True,
            },
        )

        if not self.agent_factory:
            raise RuntimeError("agent_factory is required for delegate actions")

        agent_tools = self.get_tools_for_agent(target)
        sub = self.agent_factory(
            name=target, role=f"Execute {target}", tools=agent_tools
        )

        sub_context = {"event_ids": context_ids}
        if self.session:
            sub_context["session"] = self.session
            # Pass relevant artifacts to the delegated agent
            artifacts = self.session.get_all_artifacts()
            if artifacts:
                sub_context["artifacts"] = artifacts
                logger.info(f"Passing {len(artifacts)} artifacts to {target}")

        sub_result = await sub.run(task, context=sub_context, is_sub_call=True)

        self._emit(
            "tool",
            {
                "tool_name": "delegate",
                "input": f"delegate to {target}: {task}",
                "output": (sub_result.output or sub_result.error)[:2000],
                "success": sub_result.success,
                "expanded": True,
            },
        )

        if not sub_result.success:
            error_output = (
                sub_result.error or sub_result.output or "Delegated agent failed"
            )
            logger.error(
                f">>> DELEGATION FAILED: {target}, output: {error_output[:200]}"
            )
            if self._should_defer_subagent_failure():
                feedback = self._build_subagent_failure_feedback(
                    target, task, error_output, plan_id=plan_id, step_id=step_id
                )
                self.add_message("user", feedback)
                full.append({"role": "user", "content": feedback})
                logger.info(
                    f">>> DELEGATION FAILURE RETURNED TO COORDINATOR: {target}, output: {error_output[:100]}"
                )
                return None

            return AgentResult(
                success=False,
                error=error_output,
                output=error_output,
                duration=time.time() - start,
            )

        # Add delegation result as user message (not tool message to avoid tool_call_id issues)
        # This allows the agent to process the result and decide next action
        if self._plan_has_unresolved_steps():
            feedback = (
                f"Delegation to {target} completed. Result: {sub_result.output}\n\n"
                f"If this completed a plan step, call update_plan for that step, then continue with the next unfinished plan step. "
                f"{self._format_plan_progress_message()}"
            )
        else:
            feedback = (
                f"Delegation to {target} completed. Result: {sub_result.output}\n\n"
                "Now provide your final answer to the user using the 'done' action."
            )

        delegate_msg = {"role": "user", "content": feedback}
        self.add_message("user", feedback)
        full.append(delegate_msg)

        # Emit result event immediately to ensure it's displayed
        # This ensures the final answer is shown even if coordinator doesn't use "done" action
        self._emit("result", {"content": sub_result.output})

        logger.info(
            f">>> DELEGATION COMPLETED: {target}, output: {sub_result.output[:100]}"
        )
        logger.info(f">>> CONTINUING LOOP, iteration: {self._iteration}")
        return None

    def _handle_options_action(
        self, action: Dict[str, Any], full: List[Dict[str, Any]]
    ) -> None:
        options = action.get("options", [])
        question = action.get("question", "Выберите опцию:")
        self._emit(
            "button_options",
            {"question": question, "options": options, "expanded": True},
        )
        self.add_message("user", f"options: {question}")
        full.append({"role": "user", "content": f"options: {question}"})

    async def _handle_plan_action(
        self, action: Dict[str, Any], full: List[Dict[str, Any]], start: float
    ) -> Optional[AgentResult]:
        plan_id = action.get("plan_id", "")
        steps = action.get("steps", [])
        self._active_plan = {
            "plan_id": plan_id,
            "steps": self._normalize_plan_steps(steps),
        }
        self._sync_session_plan_artifact()
        self._emit("plan", {"plan_id": plan_id, "steps": steps, "expanded": True})

        logger.info(
            f">>> PLAN CREATED: {len(steps)} steps, agent_factory={self.agent_factory}"
        )

        if steps and self.agent_factory:
            first_step = steps[0]
            target_agent = first_step.get("agent", "CodeAgent")
            task = first_step.get("task", "")
            step_id = first_step.get("id", 0)

            self._set_active_plan_step_status(step_id, "active")

            logger.info(f">>> DELEGATING first step: {target_agent}: {task[:50]}...")

            self._emit(
                "delegate",
                {
                    "target_agent": target_agent,
                    "task": task,
                    "plan_id": plan_id,
                    "step_id": step_id,
                    "expanded": True,
                },
            )

            agent_tools = self.get_tools_for_agent(target_agent)
            sub = self.agent_factory(
                name=target_agent, role=f"Execute {target_agent}", tools=agent_tools
            )
            sub_context = {"event_ids": []}
            if self.session:
                sub_context["session"] = self.session

            sub_result = await sub.run(task, context=sub_context, is_sub_call=True)

            if not sub_result.success:
                error_output = (
                    sub_result.error or sub_result.output or "Plan step failed"
                )
                logger.error(
                    f">>> PLAN STEP FAILED: {target_agent}, output: {error_output[:200]}"
                )
                if self._should_defer_subagent_failure():
                    feedback = self._build_subagent_failure_feedback(
                        target_agent,
                        task,
                        error_output,
                        plan_id=plan_id,
                        step_id=first_step.get("id", 0),
                    )
                    self.add_message("user", feedback)
                    full.append({"role": "user", "content": feedback})
                    logger.info(
                        f">>> PLAN FAILURE RETURNED TO COORDINATOR: {target_agent}, output: {error_output[:100]}"
                    )
                    return None

                return AgentResult(
                    success=False,
                    error=error_output,
                    output=error_output,
                    duration=time.time() - start,
                )

            # Add delegation result as user message (not tool message to avoid tool_call_id issues)
            # This allows the agent to process the result and decide next action
            remaining_steps = len(steps) - 1
            if remaining_steps > 0:
                delegate_msg = {
                    "role": "user",
                    "content": (
                        f"Plan step {steps[0].get('id')} executed by {target_agent}. Result: {sub_result.output}\n\n"
                        f"Call update_plan to mark step {steps[0].get('id')} completed, then continue with the next unfinished plan step. "
                        f"{self._format_plan_progress_message()}"
                    ),
                }
                self.add_message(
                    "user",
                    (
                        f"Plan step {steps[0].get('id')} executed by {target_agent}. Result: {sub_result.output}\n\n"
                        f"Call update_plan to mark step {steps[0].get('id')} completed, then continue with the next unfinished plan step. "
                        f"{self._format_plan_progress_message()}"
                    ),
                )
            else:
                delegate_msg = {
                    "role": "user",
                    "content": (
                        f"Plan step {steps[0].get('id')} executed by {target_agent}. Result: {sub_result.output}\n\n"
                        f"Call update_plan to mark step {steps[0].get('id')} completed. "
                        "After that, if no unfinished steps remain, return the final answer using the 'done' action."
                    ),
                }
                self.add_message(
                    "user",
                    (
                        f"Plan step {steps[0].get('id')} executed by {target_agent}. Result: {sub_result.output}\n\n"
                        f"Call update_plan to mark step {steps[0].get('id')} completed. "
                        "After that, if no unfinished steps remain, return the final answer using the 'done' action."
                    ),
                )
            full.append(delegate_msg)

            logger.info(
                f">>> PLAN STEP COMPLETED: {target_agent}, output: {sub_result.output[:100]}"
            )
            return None

        plan_text = f"Plan created with {len(steps)} steps."
        self.add_message("user", plan_text)
        full.append({"role": "user", "content": plan_text})
        return None

    def _handle_update_plan_action(
        self, action: Dict[str, Any], full: List[Dict[str, Any]]
    ) -> None:
        plan_update = self._apply_plan_updates(action)
        self._sync_session_plan_artifact()
        self._emit("update_plan", {**plan_update, "expanded": True})

        if self._plan_has_unresolved_steps():
            update_feedback = (
                f"Plan updated successfully. {self._format_plan_progress_message()}"
            )
        else:
            update_feedback = (
                "Plan updated successfully. All plan steps are resolved. "
                "Return the final answer using the 'done' action."
            )

        self.add_message("user", update_feedback)
        full.append({"role": "user", "content": update_feedback})

    def _parse(self, response: str) -> Dict[str, Any]:
        import re
        import json

        def repair_json(json_str: str) -> str:
            """Attempt to repair common JSON errors from LLM output."""
            # Fix missing colon between key and value (e.g., "query{"action" -> "query":{"action")
            repaired = re.sub(r'"(\w+)"\s*\{', r'"\1":{', json_str)
            # Fix missing colon before string value (e.g., "query"python" -> "query":"python")
            repaired = re.sub(r'"(\w+)"\s*"([^"]*)"', r'"\1":"\2"', repaired)
            # Fix missing comma between key-value pairs
            repaired = re.sub(r'"\s*"', ',"', repaired)
            # Fix missing quotes around values
            repaired = re.sub(
                r":\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*([,}])", r':"\1"\2', repaired
            )
            return repaired

        # Try to find JSON block using a stack-based approach for nested braces
        def extract_json_objects(text):
            objects = []
            stack = []
            start_index = -1

            for i, char in enumerate(text):
                if char == "{":
                    if not stack:
                        start_index = i
                    stack.append(char)
                elif char == "}":
                    if stack:
                        stack.pop()
                        if not stack:
                            json_str = text[start_index : i + 1]
                            try:
                                obj = json.loads(json_str)
                                objects.append(obj)
                            except json.JSONDecodeError:
                                # Try to repair the JSON
                                try:
                                    repaired = repair_json(json_str)
                                    obj = json.loads(repaired)
                                    logger.warning(
                                        f"Repaired malformed JSON: {json_str[:100]}..."
                                    )
                                    objects.append(obj)
                                except json.JSONDecodeError as e:
                                    logger.debug(f"Failed to repair JSON: {e}")
            return objects

        json_objects = extract_json_objects(response)

        # If simple extraction failed, try regex for markdown code blocks
        if not json_objects:
            code_blocks = re.findall(
                r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL
            )
            for block in code_blocks:
                try:
                    json_objects.append(json.loads(block))
                except json.JSONDecodeError:
                    # Try to repair the block
                    try:
                        repaired = repair_json(block)
                        json_objects.append(json.loads(repaired))
                    except json.JSONDecodeError:
                        pass

        # Final fallback: regex extraction for severely malformed JSON
        # This handles cases where JSON structure is completely broken
        if not json_objects:
            action_match = re.search(
                r'"action"\s*[:=]\s*["\']?(\w+)["\']?', response, re.IGNORECASE
            )
            if action_match:
                action_type = action_match.group(1).lower()
                # Map common variations to standard actions
                action_map = {
                    "tool": AgentAction.TOOL.value,
                    "delegate": AgentAction.DELEGATE.value,
                    "done": AgentAction.DONE.value,
                    "error": AgentAction.ERROR.value,
                    "options": AgentAction.OPTIONS.value,
                    "plan": AgentAction.PLAN.value,
                    "update_plan": AgentAction.UPDATE_PLAN.value,
                }
                normalized_action = action_map.get(action_type)
                if normalized_action:
                    extracted = {"action": normalized_action}
                    # Try to extract other common fields
                    # Use a regex that handles escaped quotes and backslashes
                    for field in ["tool", "query", "task", "result", "error", "agent"]:
                        # Match quoted strings with proper escape handling
                        field_match = re.search(
                            rf'"{field}"\s*[:=]\s*"((?:[^"\\]|\\.)*)"',
                            response,
                            re.DOTALL,
                        )
                        if field_match:
                            # Unescape the captured value
                            value = field_match.group(1)
                            try:
                                # Use json to properly unescape the string
                                extracted[field] = json.loads(f'"{value}"')
                            except json.JSONDecodeError:
                                extracted[field] = value
                    logger.warning(
                        f"Used regex fallback to extract action: {normalized_action}"
                    )
                    return extracted

        # Take ONLY THE FIRST valid action - execute one at a time!
        # Multiple actions in one response is NOT allowed - this causes loops
        # CRITICAL: Always take the FIRST action, never prioritize "done" over other actions
        # This prevents LLM from hallucinating results without actually executing tools
        if json_objects:
            first_obj = json_objects[0]
            if isinstance(first_obj, dict) and "action" in first_obj:
                action = first_obj.get("action", "")
                # Only these actions are allowed
                if action in (
                    AgentAction.TOOL.value,
                    AgentAction.DELEGATE.value,
                    AgentAction.OPTIONS.value,
                    AgentAction.PLAN.value,
                    AgentAction.UPDATE_PLAN.value,
                    AgentAction.ERROR.value,
                    AgentAction.DONE.value,
                ):
                    return first_obj

        # Try to handle truncated JSON - response might be cut off mid-JSON
        response_stripped = response.strip()

        # If it starts with { but doesn't end with }, try to find complete JSON
        if response_stripped.startswith("{") and not response_stripped.endswith("}"):
            # Try to complete the JSON by finding action field
            action_match = re.search(r'"action"\s*:\s*"([^"]+)"', response_stripped)
            if action_match:
                action_type = action_match.group(1)
                # Extract what we can
                partial_result = {"action": action_type}

                # Try to extract other fields
                task_match = re.search(
                    r'"task"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', response_stripped
                )
                if task_match:
                    partial_result["task"] = task_match.group(1)

                plan_match = re.search(r'"plan"\s*:\s*\{', response_stripped)
                if plan_match:
                    partial_result["plan"] = "..."

                if action_type in (
                    AgentAction.TOOL.value,
                    AgentAction.DELEGATE.value,
                    AgentAction.OPTIONS.value,
                    AgentAction.PLAN.value,
                    AgentAction.UPDATE_PLAN.value,
                    AgentAction.ERROR.value,
                    AgentAction.DONE.value,
                ):
                    logger.warning(f"Using truncated JSON with action: {action_type}")
                    return partial_result

        # If response looks like JSON but wasn't parsed correctly, try direct parsing
        if response_stripped.startswith("{") and response_stripped.endswith("}"):
            try:
                direct_parse = json.loads(response_stripped)
                if isinstance(direct_parse, dict) and "action" in direct_parse:
                    action = direct_parse.get("action", "")
                    if action in (
                        AgentAction.TOOL.value,
                        AgentAction.DELEGATE.value,
                        AgentAction.OPTIONS.value,
                        AgentAction.PLAN.value,
                        AgentAction.UPDATE_PLAN.value,
                        AgentAction.ERROR.value,
                        AgentAction.DONE.value,
                    ):
                        return direct_parse
            except:
                pass

        # If no valid JSON action found, treat entire response as text result
        # Clean up the response - remove markdown code blocks if present
        cleaned_response = re.sub(r"^```json\s*", "", response.strip())
        cleaned_response = re.sub(r"^```\s*", "", cleaned_response)
        cleaned_response = re.sub(r"```$", "", cleaned_response).strip()

        # If it still looks like JSON after cleaning, extract just the result
        if cleaned_response.startswith("{") and cleaned_response.endswith("}"):
            try:
                json_resp = json.loads(cleaned_response)
                if "result" in json_resp:
                    return {
                        "action": AgentAction.DONE.value,
                        "result": json_resp["result"],
                    }
            except:
                pass

        # CRITICAL: If response is empty, this is an error - don't return "done"
        # Empty responses from LLM should be treated as errors, not completion
        if not cleaned_response and not response:
            logger.error("LLM returned empty response - treating as error")
            # Return a special error action that will be caught by the main loop
            return {
                "action": AgentAction.ERROR.value,
                "error": "LLM returned empty response",
            }

        return {
            "action": AgentAction.DONE.value,
            "result": cleaned_response if cleaned_response else response,
        }
