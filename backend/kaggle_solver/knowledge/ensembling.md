# Ensembling Techniques for Kaggle Competitions

## Why Ensemble?
Ensembling combines multiple models to reduce variance and bias, almost always improving performance. Top Kaggle solutions are almost always ensembles.

## Simple Averaging

### Arithmetic Mean
```python
pred_ensemble = (pred1 + pred2 + pred3) / 3
```
- Works well when models have similar performance.
- Use for regression and probability outputs.

### Weighted Average
```python
weights = [0.4, 0.35, 0.25]  # Based on CV scores
pred_ensemble = sum(w * p for w, p in zip(weights, [pred1, pred2, pred3]))
```
- Weight by CV score: better models get higher weight.
- Optimize weights with scipy.optimize or Optuna.

### Geometric Mean
```python
import numpy as np
pred_ensemble = (pred1 * pred2 * pred3) ** (1/3)
```
- Better for probability outputs, especially when probabilities are extreme.

### Rank Averaging
```python
from scipy.stats import rankdata
rank1 = rankdata(pred1) / len(pred1)
rank2 = rankdata(pred2) / len(pred2)
pred_ensemble = (rank1 + rank2) / 2
```
- Robust to scale differences between models.
- Useful when models output different scales.

## Stacking (Meta-Learning)

### Basic Stacking
1. Split training data into K folds.
2. For each fold: train base models on K-1 folds, predict on held-out fold.
3. Collect out-of-fold (OOF) predictions as meta-features.
4. Train meta-model on OOF predictions.
5. For test: average base model predictions across all K folds.

```python
from sklearn.model_selection import StratifiedKFold
import numpy as np

def get_oof_predictions(model, X_train, y_train, X_test, n_folds=5):
    oof_preds = np.zeros(len(X_train))
    test_preds = np.zeros(len(X_test))
    
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    
    for fold, (train_idx, val_idx) in enumerate(skf.split(X_train, y_train)):
        X_tr, X_val = X_train[train_idx], X_train[val_idx]
        y_tr, y_val = y_train[train_idx], y_train[val_idx]
        
        model.fit(X_tr, y_tr)
        oof_preds[val_idx] = model.predict_proba(X_val)[:, 1]
        test_preds += model.predict_proba(X_test)[:, 1] / n_folds
    
    return oof_preds, test_preds

# Get OOF predictions for each base model
oof_lgb, test_lgb = get_oof_predictions(lgb_model, X_train, y_train, X_test)
oof_xgb, test_xgb = get_oof_predictions(xgb_model, X_train, y_train, X_test)
oof_cat, test_cat = get_oof_predictions(cat_model, X_train, y_train, X_test)

# Stack as meta-features
meta_train = np.column_stack([oof_lgb, oof_xgb, oof_cat])
meta_test = np.column_stack([test_lgb, test_xgb, test_cat])

# Train meta-model (logistic regression works well)
from sklearn.linear_model import LogisticRegression
meta_model = LogisticRegression()
meta_model.fit(meta_train, y_train)
final_pred = meta_model.predict_proba(meta_test)[:, 1]
```

### Multi-Level Stacking
- Level 0: Base models (LightGBM, XGBoost, CatBoost, Neural Net).
- Level 1: Meta-model trained on OOF predictions.
- Level 2: Another meta-model (rarely needed, risk of overfitting).

### Meta-Model Choices
- **Logistic Regression**: Simple, interpretable, good regularization.
- **LightGBM**: Can capture non-linear interactions between base models.
- **Ridge Regression**: For regression tasks.
- **Neural Network**: For complex interactions.

## Blending
- Simpler than stacking: use a holdout set instead of cross-validation.
- Split training data: 80% for base models, 20% for blending.
- Train base models on 80%, predict on 20% and test.
- Train meta-model on 20% predictions.
- Faster but uses less data for training.

## Snapshot Ensembling
- Train one model with cyclic learning rate.
- Save model at each learning rate minimum (snapshot).
- Ensemble snapshots — diverse models from single training run.

## Diversity is Key
- Ensemble models that make different errors.
- Diversity sources:
  - Different algorithms (LightGBM + XGBoost + Neural Net).
  - Different feature sets.
  - Different random seeds.
  - Different hyperparameters.
  - Different preprocessing.
  - Different CV folds.

## Correlation Analysis
```python
import pandas as pd
oof_df = pd.DataFrame({'lgb': oof_lgb, 'xgb': oof_xgb, 'cat': oof_cat, 'nn': oof_nn})
print(oof_df.corr())
# Low correlation = high diversity = better ensemble
```

## Practical Tips
- Always compute OOF score for each model before ensembling.
- Ensemble models with similar OOF scores — don't include weak models.
- Start with simple average, then try weighted average, then stacking.
- Stacking with logistic regression on 3-5 base models is usually sufficient.
- More models ≠ better ensemble. Quality > quantity.
- Keep a holdout set to evaluate ensemble performance honestly.

## Post-Processing
- **Calibration**: Calibrate probabilities with `sklearn.calibration.CalibratedClassifierCV`.
- **Rank transformation**: Convert predictions to ranks before averaging.
- **Clipping**: Clip predictions to valid range (e.g., [0, 1] for probabilities).
- **Threshold optimization**: Find optimal classification threshold on validation set.
