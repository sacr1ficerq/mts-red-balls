#!/usr/bin/env python3
"""
Kaggle competition test - Titanic classification with CatBoost
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

signal.alarm(600)  # 10 minutes

task = """
Solve Titanic classification problem:
1. Download Titanic dataset from Kaggle (train.csv, test.csv)
2. Use CatBoost to predict survival (Survived column)
3. Create submission.csv with PassengerId and Survived columns
4. Report the accuracy/score

The data is at: https://www.kaggle.com/competitions/titanic/data
Train columns: PassengerId, Survived, Pclass, Name, Sex, Age, SibSp, Parch, Ticket, Fare, Cabin, Embarked
Target: Survived (0 or 1)

Write code that:
- Loads train.csv and test.csv
- Preprocesses data (handle missing values, encode categorical features)
- Trains CatBoost classifier
- Makes predictions on test set
- Saves submission.csv
- Reports cross-validation score
"""

print("="*80)
print("KAGGLE TEST: Titanic with CatBoost")
print("="*80)

try:
    session = orch.run(task, session_id=None)
    
    print(f"\n{'='*80}")
    print("RESULT")
    print(f"{'='*80}")
    print(f"Status: {session.status}")
    print(f"Duration: {session.artifacts.get('duration', 'N/A'):.1f}s")
    print(f"\nOutput:\n{session.artifacts.get('result', 'NO RESULT')}")
    
    # Check workspace files
    workspace = Path(f"./workspace/{session.id}")
    if workspace.exists():
        files = list(workspace.glob("*.csv")) + list(workspace.glob("*.py"))
        print(f"\n{'='*80}")
        print("FILES CREATED")
        print(f"{'='*80}")
        for f in files:
            print(f"  - {f.name}")
            if f.suffix == '.py':
                print(f"    (Python file)")
            elif f.suffix == '.csv':
                lines = f.read_text().split('\n')[:5]
                print(f"    First rows: {lines[:3]}")
    
except TimeoutException:
    print("\nTIMEOUT - task did not complete!")
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
