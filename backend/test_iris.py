#!/usr/bin/env python3
"""
Kaggle test - Iris classification with CatBoost (no download needed)
"""
import sys
import logging
from pathlib import Path
import signal

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
config.agents["Coordinator"].max_iterations = 15
config.agents["CodeAgent"].max_iterations = 15

orch = Orchestrator(config)

signal.alarm(600)

task = """
Solve Iris classification problem using CatBoost:

1. Use sklearn.datasets.load_iris() to get data
2. Split into train/test
3. Train CatBoostClassifier
4. Report accuracy score
5. Save predictions to submission.csv with columns: id, species (predicted class)

This is a multi-class classification with 3 classes: setosa, versicolor, virginica

Write Python code that:
- Loads Iris dataset from sklearn
- Splits data 80/20
- Trains CatBoost with some hyperparameters
- Calculates accuracy on test set
- Prints accuracy score
- Creates submission.csv with predicted species names (not numbers)
"""

print("="*80)
print("KAGGLE TEST: Iris with CatBoost")
print("="*80)

try:
    session = orch.run(task, session_id=None)
    
    print(f"\n{'='*80}")
    print("RESULT")
    print(f"{'='*80}")
    print(f"Status: {session.status}")
    print(f"Duration: {session.artifacts.get('duration', 'N/A'):.1f}s")
    print(f"\nOutput:\n{session.artifacts.get('result', 'NO RESULT')}")
    
    workspace = Path(f"./workspace/{session.id}")
    if workspace.exists():
        files = list(workspace.glob("*.csv")) + list(workspace.glob("*.py"))
        print(f"\n{'='*80}")
        print("FILES CREATED")
        print(f"{'='*80}")
        for f in files:
            print(f"  - {f.name}")
            if f.suffix == '.csv':
                print(f.read_text()[:300])
    
except TimeoutException:
    print("\nTIMEOUT!")
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
