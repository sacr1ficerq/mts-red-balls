#!/usr/bin/env python3
"""
Test: Plan + Delegate + Multiple steps
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

task = """
Find best hyperparameters for CatBoost on Iris dataset, then train a model and save to file.
This requires multiple steps:
1. Search for best hyperparameters
2. Train model with those hyperparameters
3. Save the trained model
"""

print("="*80)
print("TEST: PLAN + MULTIPLE STEPS")
print("="*80)

try:
    session = orch.run(task, session_id=None)
    
    print(f"\nStatus: {session.status}")
    print(f"Output: {session.artifacts.get('result', 'NO RESULT')[:500]}")
    
    workspace = Path(f"./workspace/{session.id}")
    if workspace.exists():
        files = list(workspace.glob("*"))
        print(f"\nFiles: {[f.name for f in files]}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
