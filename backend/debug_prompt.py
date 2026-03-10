#!/usr/bin/env python3
"""
Debug - show exact prompt and context to LLM
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kaggle_solver.core.config import Config
from kaggle_solver.agents.base import BaseAgent, AgentConfig
from kaggle_solver.llm import LLM
from kaggle_solver.sandbox import Sandbox
from kaggle_solver.tools.registry import ToolRegistry
from kaggle_solver.agents.coordinator import get_agent_prompts
import kaggle_solver.tools

config = Config.load("config.yaml")
llm = LLM()

print("="*80)
print("LLM CONFIG")
print("="*80)
print(f"Model: {config.llm.model}")

print("\n" + "="*80)
print("COORDINATOR SYSTEM PROMPT")
print("="*80)
print(get_agent_prompts("Coordinator"))

print("\n" + "="*80)
print("CODE AGENT SYSTEM PROMPT")
print("="*80)
print(get_agent_prompts("CodeAgent"))

print("\n" + "="*80)
print("WHAT LLM RECEIVES")
print("="*80)

# Simulate what CodeAgent receives
sandbox = Sandbox(Path("./workspace/test"), timeout=60)

class TestAgent(BaseAgent):
    def system_prompt(self) -> str:
        return get_agent_prompts("CodeAgent")

config_ag = AgentConfig(
    name="CodeAgent",
    role="Python Developer",
    tools=["console", "files"],
    model=config.llm.model,
    max_iterations=5,
    temperature=0.7
)

agent = TestAgent(config_ag, llm, sandbox, ToolRegistry)

# Simulate run
messages = [
    {"role": "system", "content": agent.system_prompt()},
    {"role": "user", "content": "Write train.py and run it"}
]

print("Messages sent to LLM:")
print("-"*40)
for i, m in enumerate(messages):
    print(f"\n[{i}] ROLE: {m['role']}")
    print(f"CONTENT:\n{m['content'][:500]}...")

print("\n" + "="*80)
print("LLM RESPONSE")
print("="*80)
response = llm.chat(config.llm.model, messages, temperature=0.7)
print(response[:1000])
