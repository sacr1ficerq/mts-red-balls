#!/usr/bin/env python3
"""
Real test with actual LLM via OpenRouter
"""
import sys
import os
import json
import logging
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from kaggle_solver.core.config import Config
from kaggle_solver.core.orchestrator import Orchestrator
import kaggle_solver.tools
import kaggle_solver.agents

print("=" * 80)
print("REAL LLM TEST")
print("=" * 80)

config = Config.load("config.yaml")
print(f"LLM Model: {config.llm.model}")

orch = Orchestrator(config)

def event_logger(event):
    print(f"\n>>> EVENT: {event.get('type')}")
    data = event.get('data', {})
    if event.get('type') == 'delegate':
        print(f"    -> {data.get('target_agent')}: {data.get('task')[:50]}...")
    elif event.get('type') == 'tool':
        print(f"    tool={data.get('tool_name')}, success={data.get('success')}")
        output = str(data.get('output', ''))[:100]
        print(f"    output: {output}...")
    elif event.get('type') == 'result':
        print(f"    RESULT: {str(data.get('content', ''))[:200]}")

# Test 1: Simple search query
print("\n" + "="*80)
print("TEST 1: Search query - 'What is Python?'")
print("="*80)

session1 = orch.run("What is Python?", session_id=None)
print(f"\nSession status: {session1.status}")
print(f"Result: {session1.artifacts.get('result', 'NO RESULT')[:300]}...")

# Test 2: Code execution  
print("\n" + "="*80)
print("TEST 2: Code execution - 'Calculate 2+2'")
print("="*80)

session2 = orch.run("Calculate 2+2 and print the result", session_id=None)
print(f"\nSession status: {session2.status}")
print(f"Result: {session2.artifacts.get('result', 'NO RESULT')[:300]}...")

# Test 3: Multi-step task
print("\n" + "="*80)
print("TEST 3: Multi-step - 'Create a hello world file and run it'")
print("="*80)

session3 = orch.run("Create a file hello.py with 'print(\"Hello World\")' and run it", session_id=None)
print(f"\nSession status: {session3.status}")
print(f"Result: {session3.artifacts.get('result', 'NO RESULT')[:500]}...")

print("\n" + "="*80)
print("ALL TESTS COMPLETED")
print("="*80)
