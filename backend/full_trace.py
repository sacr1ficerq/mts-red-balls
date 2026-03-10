#!/usr/bin/env python3
"""
FULL TRACE - Detailed debugging with full visibility into system
"""
import sys
import os
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

from kaggle_solver.core.config import Config
from kaggle_solver.core.orchestrator import Orchestrator
import kaggle_solver.tools
import kaggle_solver.agents
from kaggle_solver.llm import LLM

config = Config.load("config.yaml")
print("="*100)
print("FULL TRACE - DETAILED SYSTEM DEBUGGING")
print("="*100)
print(f"Model: {config.llm.model}")

# Patch LLM to log everything
original_chat = LLM.chat

def logged_chat(self, model, messages, temperature=0.7, max_tokens=4096, tools=None, tool_choice=None):
    print("\n" + "="*100)
    print(">>> LLM CHAT CALL")
    print("="*100)
    print(f"Model: {model}")
    print(f"Temperature: {temperature}")
    print(f"Max tokens: {max_tokens}")
    print("\n--- MESSAGES SENT TO LLM ---")
    for i, msg in enumerate(messages):
        print(f"\n[{i}] ROLE: {msg['role']}")
        content = msg.get('content', '')
        if len(content) > 500:
            print(content[:500] + "\n... [TRUNCATED]")
        else:
            print(content)
    print("\n" + "-"*50)
    
    result = original_chat(self, model, messages, temperature, max_tokens, tools, tool_choice)
    
    print("\n--- LLM RESPONSE ---")
    if len(result) > 800:
        print(result[:800] + "\n... [TRUNCATED]")
    else:
        print(result)
    print("="*100 + "\n")
    
    return result

LLM.chat = logged_chat

# Patch ToolRegistry to log tool calls
from kaggle_solver.tools.registry import ToolRegistry
original_execute = ToolRegistry.execute

def logged_execute(cls, name, query="", **kwargs):
    print("\n" + "#"*100)
    print(f"### TOOL CALL: {name}")
    print("#"*100)
    print(f"Query: {query}")
    print(f"kwargs: {kwargs}")
    
    result = original_execute(cls, name, query, **kwargs)
    
    print(f"\n--- TOOL RESULT ---")
    print(f"Success: {result.success}")
    output = result.output if result.success else result.error
    if len(output) > 500:
        print(output[:500] + "\n... [TRUNCATED]")
    else:
        print(output)
    print("#"*100 + "\n")
    
    return result

ToolRegistry.execute = classmethod(logged_execute)

# Now run the orchestrator
orch = Orchestrator(config)

print("\n" + "="*100)
print("RUNNING QUERY: 'What is 2+2?'")
print("="*100)

session = orch.run("What is 2+2?", session_id=None)

print("\n" + "="*100)
print("FINAL RESULT")
print("="*100)
print(f"Status: {session.status}")
print(f"Result: {session.artifacts.get('result', 'NO RESULT')}")
print("\nAll events:")
for i, event in enumerate(session.events):
    print(f"  {i+1}. {event.get('type')}: {str(event.get('data', {}))[:100]}")
