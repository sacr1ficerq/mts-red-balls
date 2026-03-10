#!/usr/bin/env python3
"""
Test 1: Multi-step with search + code
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

from kaggle_solver.core.config import Config
from kaggle_solver.core.orchestrator import Orchestrator

config = Config.load("config.yaml")
config.agents["Coordinator"].max_iterations = 15
config.agents["CodeAgent"].max_iterations = 10

orch = Orchestrator(config)

task1 = """
Find information about the best hyperparameters for CatBoost classifier.
Then create a Python script that uses those hyperparameters to train on the Iris dataset.
Save the script as catboost_tuned.py and run it.
Report the accuracy.
"""

print("="*80)
print("TEST 1: Search + Code")
print("="*80)
print(f"Task: {task1[:100]}...")

try:
    session = orch.run(task1, session_id=None)
    
    print(f"\nStatus: {session.status}")
    print(f"Output: {session.artifacts.get('result', 'NO RESULT')[:500]}")
    
    workspace = Path(f"./workspace/{session.id}")
    if workspace.exists():
        files = list(workspace.glob("*.py"))
        print(f"\nFiles created: {[f.name for f in files]}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
