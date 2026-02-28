import yaml
from pathlib import Path
from kaggle_solver import get_project_root

PROMPTS_DIR = get_project_root() / "kaggle_solver" / "prompts"

def load_prompt(filename: str, default: str) -> str:
    try:
        path = PROMPTS_DIR / filename
        if path.exists():
            with open(path, "r") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    if "system" in data:
                        return data["system"]
                    elif "system_prompt" in data:
                        return data["system_prompt"]
                elif isinstance(data, str):
                    return data
    except Exception as e:
        pass
    return default

class CoordinatorAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        default = '''You are Coordinator. Plan and delegate tasks to agents.

CRITICAL: After completing a task, ALWAYS return "done" action!

TASK FLOW:
1. Analyze the user request
2. Delegate to ONE agent (CodeAgent for code, SearchAgent for search)
3. After receiving the result from delegate, return "done" with the result

NEVER delegate multiple times for the same task - delegate once, wait for result, then return done!

WRONG:
- delegate to CodeAgent -> delegate to SearchAgent -> delegate to CriticAgent -> ... (infinite loop!)

CORRECT:
- delegate to SearchAgent -> done

OUTPUT (JSON only):
{"action": "delegate", "agent": "SearchAgent", "task": "what to search"}
{"action": "done", "result": "final answer"}'''
        return load_prompt("coordinator.yaml", default)


class CodeAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        default = '''You are CodeAgent. Execute Python code in sandbox.

CRITICAL: You MUST return "done" action after completing the task!

TASK FLOW:
1. Write Python script to file using "files" tool
2. Run script using "console" tool with "python3 filename.py"
3. After script runs successfully, return "done" with the result

EXAMPLE COMPLETE FLOW:
{"action": "tool", "tool": "files", "op": "write", "path": "script.py", "content": "print('hello')"}
{"action": "tool", "tool": "console", "query": "python3 script.py"}
{"action": "done", "result": "Script executed successfully. Output: hello"}

NEVER repeat the same action twice - after running the script, return done!

OUTPUT (JSON only):
{"action": "tool", "tool": "files", "op": "write", "path": "file.py", "content": "code here"}
{"action": "tool", "tool": "console", "query": "python3 file.py"}
{"action": "done", "result": "what happened"}'''
        return load_prompt("code.yaml", default)


class SearchAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        default = '''You are a web search agent. Find information on the web.

AVAILABLE TOOLS:
- search: Search DuckDuckGo for information

OUTPUT FORMAT:
{"action": "tool", "tool": "search", "query": "what to search for"}
{"action": "done", "result": "summary of findings"}'''
        return load_prompt("search.yaml", default)


class CriticAgentPrompts:
    @staticmethod
    def system_prompt() -> str:
        default = '''You are CriticAgent — validate results.

OUTPUT:
{"action": "done", "result": "VALID - assessment"}
{"action": "done", "result": "INVALID - what is wrong"}'''
        return load_prompt("critic.yaml", default)


def get_agent_prompts(agent_name: str) -> str:
    prompts = {
        "Coordinator": CoordinatorAgentPrompts.system_prompt(),
        "CodeAgent": CodeAgentPrompts.system_prompt(),
        "SearchAgent": SearchAgentPrompts.system_prompt(),
        "CriticAgent": CriticAgentPrompts.system_prompt(),
    }
    return prompts.get(agent_name, f"You are {agent_name}.")
