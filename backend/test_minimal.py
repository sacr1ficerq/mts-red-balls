#!/usr/bin/env python3
"""
Minimal test - just execute code directly
"""
import sys
import logging
from pathlib import Path
import signal

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

from kaggle_solver.core.config import Config
from kaggle_solver.core.orchestrator import Orchestrator

config = Config.load("config.yaml")
config.agents["Coordinator"].max_iterations = 20
config.agents["CodeAgent"].max_iterations = 20

orch = Orchestrator(config)

task = """
Write file train.py with:
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
X, y = load_iris(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model = RandomForestClassifier(n_estimators=50)
model.fit(X_train, y_train)
print('Accuracy:', model.score(X_test, y_test))

Then run: python3 train.py

Then return: Accuracy: X.XX
"""

print("="*80)
print("MINIMAL TEST")
print("="*80)

try:
    session = orch.run(task, session_id=None)
    
    print(f"\nStatus: {session.status}")
    print(f"Output: {session.artifacts.get('result', 'NO RESULT')[:1000]}")
    
    workspace = Path(f"./workspace/{session.id}")
    if workspace.exists():
        files = list(workspace.glob("*"))
        print(f"\nFiles: {[f.name for f in files]}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
