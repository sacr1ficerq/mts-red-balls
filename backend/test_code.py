#!/usr/bin/env python3
"""
Real test with code execution
"""
import sys
import os
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

from kaggle_solver.core.config import Config
from kaggle_solver.core.orchestrator import Orchestrator
import kaggle_solver.tools
import kaggle_solver.agents

config = Config.load("config.yaml")

orch = Orchestrator(config)

print("="*80)
print("TEST: Create and run Python code")
print("="*80)

session = orch.run('Create file test.py with "print(2+2)" and run it', session_id=None)

print(f"\nStatus: {session.status}")
print(f"Result: {session.artifacts.get('result', 'NO RESULT')}")
print("\nEvents:")
for i, event in enumerate(session.events):
    etype = event.get('type')
    data = event.get('data', {})
    if etype == 'delegate':
        print(f"  {i+1}. DELEGATE -> {data.get('target_agent')}: {data.get('task')[:50]}...")
    elif etype == 'tool':
        print(f"  {i+1}. TOOL: {data.get('tool_name')} -> {str(data.get('output',''))[:80]}...")
    elif etype == 'result':
        print(f"  {i+1}. RESULT: {str(data.get('content',''))[:80]}...")
