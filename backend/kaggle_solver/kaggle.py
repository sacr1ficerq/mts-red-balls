from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class KagglePipeline:
    def __init__(self, sandbox, llm):
        self.sandbox = sandbox
        self.llm = llm
        self.current_phase = None

    def run(self, competition: str, target_col: str = None) -> Dict[str, Any]:
        results = {
            "competition": competition,
            "phases": [],
            "success": False,
            "error": None
        }

        phases = [
            ("analyze", self._analyze_data),
            ("preprocess", self._preprocess),
            ("features", self._feature_engineering),
            ("train", self._train_model),
            ("predict", self._generate_predictions)
        ]

        for phase_name, phase_func in phases:
            self.current_phase = phase_name
            try:
                result = phase_func(competition, target_col)
                results["phases"].append({
                    "name": phase_name,
                    "success": True,
                    "result": result
                })
                logger.info(f"Phase {phase_name} completed")
            except Exception as e:
                logger.error(f"Phase {phase_name} failed: {e}")
                results["phases"].append({
                    "name": phase_name,
                    "success": False,
                    "error": str(e)
                })
                results["error"] = str(e)
                break
        else:
            results["success"] = True

        return results

    def _analyze_data(self, competition: str, target_col: str = None) -> Dict:
        code = self._get_analysis_code(competition)
        result = self.sandbox.execute_python(code)
        
        if not result.success:
            raise Exception(f"Analysis failed: {result.error}")
        
        return {"output": result.output[:1000]}

    def _preprocess(self, competition: str, target_col: str = None) -> Dict:
        code = self._get_preprocess_code(competition, target_col)
        result = self.sandbox.execute_python(code)
        
        if not result.success:
            raise Exception(f"Preprocessing failed: {result.error}")
        
        return {"output": result.output[:1000]}

    def _feature_engineering(self, competition: str, target_col: str = None) -> Dict:
        code = self._get_feature_code(competition)
        result = self.sandbox.execute_python(code)
        
        if not result.success:
            raise Exception(f"Feature engineering failed: {result.error}")
        
        return {"output": result.output[:1000]}

    def _train_model(self, competition: str, target_col: str = None) -> Dict:
        code = self._get_train_code(competition, target_col)
        result = self.sandbox.execute_python(code, timeout=600)
        
        if not result.success:
            raise Exception(f"Training failed: {result.error}")
        
        return {"output": result.output[:1000]}

    def _generate_predictions(self, competition: str, target_col: str = None) -> Dict:
        code = self._get_predict_code(competition)
        result = self.sandbox.execute_python(code)
        
        if not result.success:
            raise Exception(f"Prediction failed: {result.error}")
        
        return {"output": result.output[:1000], "submission_file": "submission.csv"}

    def _get_analysis_code(self, competition: str) -> str:
        return f"""
import pandas as pd
import sys

print("Loading data...")
try:
    train = pd.read_csv('train.csv')
    test = pd.read_csv('test.csv')
    print(f"Train shape: {{train.shape}}")
    print(f"Test shape: {{test.shape}}")
    print("\\nTrain columns:")
    print(train.columns.tolist())
    print("\\nData types:")
    print(train.dtypes)
    print("\\nMissing values:")
    print(train.isnull().sum())
    print("\\nFirst 5 rows:")
    print(train.head())
except Exception as e:
    print(f"Error: {{e}}", file=sys.stderr)
    sys.exit(1)
"""

    def _get_preprocess_code(self, competition: str, target_col: str = None) -> str:
        return f"""
import pandas as pd
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder

print("Preprocessing data...")
train = pd.read_csv('train.csv')
test = pd.read_csv('test.csv')

numeric_cols = train.select_dtypes(include=[np.number]).columns
categorical_cols = train.select_dtypes(include=['object']).columns

print(f"Numeric columns: {{len(numeric_cols)}}")
print(f"Categorical columns: {{len(categorical_cols)}}")

train.to_csv('train_preprocessed.csv', index=False)
test.to_csv('test_preprocessed.csv', index=False)
print("Preprocessing complete")
"""

    def _get_feature_code(self, competition: str) -> str:
        return f"""
import pandas as pd
import numpy as np

print("Feature engineering...")
train = pd.read_csv('train_preprocessed.csv')
test = pd.read_csv('test_preprocessed.csv')

print(f"Features created: {{len(train.columns)}}")
train.to_csv('train_features.csv', index=False)
test.to_csv('test_features.csv', index=False)
print("Feature engineering complete")
"""

    def _get_train_code(self, competition: str, target_col: str = None) -> str:
        target = target_col or "target"
        return f"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

print("Training model...")
train = pd.read_csv('train_features.csv')

if '{target}' not in train.columns:
    print("Target column not found, using last column")
    target = train.columns[-1]

X = train.drop(columns=[target])
y = train[target]

X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

train_score = model.score(X_train, y_train)
val_score = model.score(X_val, y_val)

print(f"Train score: {{train_score:.4f}}")
print(f"Validation score: {{val_score:.4f}}")

import joblib
joblib.dump(model, 'model.pkl')
print("Model saved")
"""

    def _get_predict_code(self, competition: str) -> str:
        return f"""
import pandas as pd
import joblib

print("Generating predictions...")
test = pd.read_csv('test_features.csv')
model = joblib.load('model.pkl')

predictions = model.predict(test)

submission = pd.DataFrame({{'id': test.index, 'target': predictions}})
submission.to_csv('submission.csv', index=False)

print(f"Predictions generated: {{len(predictions)}}")
print("Submission saved to submission.csv")
"""
