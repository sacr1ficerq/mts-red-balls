#!/usr/bin/env python3
"""
Complex task test - create a Python project with multiple steps
"""
import sys
import os
import json
import logging
from pathlib import Path
import signal
import time

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

from kaggle_solver.core.config import Config
from kaggle_solver.core.orchestrator import Orchestrator
import kaggle_solver.tools
import kaggle_solver.agents

# Timeout handler
class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Execution timeout!")

config = Config.load("config.yaml")

# Reduce max iterations to prevent infinite loops
config.agents["Coordinator"].max_iterations = 10
config.agents["CodeAgent"].max_iterations = 10

orch = Orchestrator(config)

print("="*80)
print("COMPLEX TASK: Create a calculator project with plan")
print("="*80)

# Set timeout - 5 minutes
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(300)  # 5 minutes

try:
    session = orch.run(
        'Create a simple calculator in Python. It should have functions: add, subtract, multiply, divide. ' +
        'Save to calculator.py and test it by running "python3 calculator.py"',
        session_id=None
    )
    signal.alarm(0)  # Cancel alarm
    
    print(f"\n{'='*80}")
    print("RESULT")
    print(f"{'='*80}")
    print(f"Status: {session.status}")
    print(f"Duration: {session.artifacts.get('duration', 'N/A')}")
    print(f"\nResult:\n{session.artifacts.get('result', 'NO RESULT')}")
    
    print(f"\n{'='*80}")
    print("EVENTS TRACE")
    print(f"{'='*80}")
    for i, event in enumerate(session.events):
        etype = event.get('type')
        data = event.get('data', {})
        if etype == 'delegate':
            print(f"{i+1}. DELEGATE -> {data.get('target_agent')}: {data.get('task')[:60]}...")
        elif etype == 'tool':
            output = str(data.get('output',''))[:60]
            print(f"{i+1}. TOOL: {data.get('tool_name')} -> {output}...")
        elif etype == 'result':
            print(f"{i+1}. RESULT: {str(data.get('content',''))[:80]}...")
        elif etype == 'plan':
            steps = data.get('steps', [])
            print(f"{i+1}. PLAN: {len(steps)} steps created")

except TimeoutException:
    print("\n" + "="*80)
    print("TIMEOUT! Task did not complete in 5 minutes")
    print("="*80)
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
