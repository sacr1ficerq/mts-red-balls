#!/usr/bin/env python3
"""
Test 2: Create visualization + save to file
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

task2 = """
Create a Python script that:
1. Loads the Iris dataset using sklearn
2. Trains a RandomForest classifier
3. Creates a scatter plot visualization showing the data and predictions
4. Saves the plot as iris_plot.png
5. Also saves the model to iris_model.joblib
6. Prints the accuracy score

Use matplotlib and joblib libraries.
"""

print("="*80)
print("TEST 2: Visualization + Model Saving")
print("="*80)
print(f"Task: {task2[:100]}...")

try:
    session = orch.run(task2, session_id=None)
    
    print(f"\nStatus: {session.status}")
    print(f"Output: {session.artifacts.get('result', 'NO RESULT')[:500]}")
    
    workspace = Path(f"./workspace/{session.id}")
    if workspace.exists():
        files = list(workspace.glob("*"))
        print(f"\nFiles created: {[f.name for f in files]}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
