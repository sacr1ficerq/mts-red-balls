#!/usr/bin/env python3
"""
Simple test with new model
"""
import sys
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

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Timeout!")

config = Config.load("config.yaml")
config.agents["Coordinator"].max_iterations = 10
config.agents["CodeAgent"].max_iterations = 10

orch = Orchestrator(config)

signal.alarm(300)

try:
    print("="*80)
    print("TEST: Write hello.py and run it")
    print("="*80)
    
    session = orch.run('Write hello.py with "print(Hello World)" and run it', session_id=None)
    
    print(f"\nStatus: {session.status}")
    print(f"Result: {session.artifacts.get('result', 'NO RESULT')}")
    
    # Check files
    workspace = Path(f"./workspace/{session.id}")
    if workspace.exists():
        files = list(workspace.glob("*"))
        print(f"\nFiles created: {[f.name for f in files]}")
        for f in files:
            print(f"\n--- {f.name} ---")
            print(f.read_text()[:500])
    else:
        print(f"\nWorkspace not found: {workspace}")

except TimeoutException:
    print("TIMEOUT!")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
