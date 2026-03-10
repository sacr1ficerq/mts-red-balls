#!/usr/bin/env python3
"""
Simple CatBoost test - just run the code directly
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

config = Config.load("config.yaml")
config.agents["Coordinator"].max_iterations = 20
config.agents["CodeAgent"].max_iterations = 20

orch = Orchestrator(config)

signal.alarm(600)

task = """
Load Iris dataset from sklearn, train CatBoost, predict and save to submission.csv

Steps:
1. from sklearn.datasets import load_iris
2. from sklearn.model_selection import train_test_split
3. from catboost import CatBoostClassifier
4. X, y = load_iris(return_X_y=True)
5. X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
6. model = CatBoostClassifier(iterations=100, verbose=0)
7. model.fit(X_train, y_train)
8. accuracy = model.score(X_test, y_test)
9. print(f"Accuracy: {accuracy}")
10. predictions = model.predict(X_test)
11. species_names = ['setosa', 'versicolor', 'virginica']
12. predicted_species = [species_names[p] for p in predictions]
13. Save to submission.csv with columns: id, species

IMPORTANT: Write code to iris.py file, then run it with python3 iris.py
"""

print("="*80)
print("CATBOOST IRIS TEST")
print("="*80)

try:
    session = orch.run(task, session_id=None)
    
    print(f"\nStatus: {session.status}")
    print(f"Duration: {session.artifacts.get('duration', 0):.1f}s")
    print(f"\nOutput:\n{session.artifacts.get('result', 'NO RESULT')[:2000]}")
    
    workspace = Path(f"./workspace/{session.id}")
    if workspace.exists():
        files = list(workspace.glob("*"))
        print(f"\nFiles: {[f.name for f in files]}")
        for f in files:
            if f.suffix == '.csv':
                print(f"\n--- {f.name} ---")
                print(f.read_text()[:500])
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
