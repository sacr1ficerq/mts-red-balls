# Hyperparameter Tuning for Kaggle Competitions

## Strategies Overview

### Optuna (Recommended)
- Bayesian optimization with Tree-structured Parzen Estimator (TPE).
- Pruning: Stop unpromising trials early with `MedianPruner` or `HyperbandPruner`.
- Parallelization: Run multiple trials in parallel.
- Best for: Any model, flexible, fast convergence.

```python
import optuna
from sklearn.model_selection import cross_val_score

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 100, 2000),
        'learning_rate': trial.suggest_float('learning_rate', 0.005, 0.3, log=True),
        'num_leaves': trial.suggest_int('num_leaves', 20, 300),
        'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
        'subsample': trial.suggest_float('subsample', 0.5, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
    }
    model = lgb.LGBMClassifier(**params, random_state=42)
    score = cross_val_score(model, X_train, y_train, cv=5, scoring='roc_auc').mean()
    return score

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=100, timeout=3600)
best_params = study.best_params
```

### Hyperopt
- Also TPE-based, older but widely used.
- `hp.choice`, `hp.uniform`, `hp.loguniform`, `hp.quniform`.

### Ray Tune
- Distributed hyperparameter search.
- Supports ASHA (Asynchronous Successive Halving) for early stopping.
- Best for: Large-scale experiments, GPU clusters.

### Grid Search / Random Search
- Grid search: Exhaustive, only for small search spaces.
- Random search: Better than grid for high-dimensional spaces.
- Use `sklearn.model_selection.RandomizedSearchCV`.

## LightGBM Hyperparameter Guide

### Most Important Parameters
1. `num_leaves` (31-255): Controls model complexity. Higher = more complex, more overfit risk.
2. `learning_rate` (0.01-0.3): Lower = better generalization, needs more trees.
3. `min_child_samples` (20-100): Minimum samples per leaf. Higher = more regularization.
4. `subsample` (0.6-1.0): Row subsampling. Reduces overfitting.
5. `colsample_bytree` (0.6-1.0): Feature subsampling per tree.
6. `reg_alpha` (L1) and `reg_lambda` (L2): Regularization terms.

### Tuning Strategy
1. Fix `learning_rate=0.1`, tune `num_leaves`, `min_child_samples`.
2. Tune `subsample`, `colsample_bytree`.
3. Tune `reg_alpha`, `reg_lambda`.
4. Lower `learning_rate` to 0.01-0.05, increase `n_estimators` with early stopping.

### Early Stopping
```python
model.fit(X_train, y_train,
    eval_set=[(X_val, y_val)],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)])
```

## XGBoost Hyperparameter Guide

### Key Parameters
- `max_depth` (3-10): Tree depth. Start with 6.
- `min_child_weight` (1-10): Minimum sum of instance weight in child.
- `gamma` (0-5): Minimum loss reduction for split.
- `subsample` (0.5-1.0): Row subsampling.
- `colsample_bytree` (0.5-1.0): Feature subsampling.
- `reg_alpha`, `reg_lambda`: L1/L2 regularization.
- `scale_pos_weight`: For imbalanced datasets, set to `neg/pos` ratio.

## CatBoost Hyperparameter Guide

### Key Parameters
- `depth` (4-10): Tree depth. Symmetric trees, so shallower than XGBoost.
- `learning_rate` (0.01-0.3).
- `l2_leaf_reg` (1-10): L2 regularization.
- `border_count` (32-255): Number of splits for numerical features.
- `bagging_temperature` (0-1): Bayesian bootstrap.
- `random_strength` (0-10): Randomness for scoring splits.

## Neural Network Hyperparameter Guide

### Architecture Search
- Number of layers: 2-5 for tabular data.
- Hidden dimensions: 64-1024, typically decreasing (512 → 256 → 128).
- Activation: ReLU, GELU, Swish.
- Batch normalization: Usually helps for tabular.
- Dropout: 0.1-0.5.

### Training Hyperparameters
- Learning rate: 1e-4 to 1e-2. Use cosine annealing or OneCycleLR.
- Batch size: 256-4096 for tabular.
- Weight decay: 1e-5 to 1e-3.
- Optimizer: AdamW usually best.

```python
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)
```

## Cross-Validation Strategy

### Stratified K-Fold (Classification)
```python
from sklearn.model_selection import StratifiedKFold
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
```

### Group K-Fold (When samples have groups)
```python
from sklearn.model_selection import GroupKFold
gkf = GroupKFold(n_splits=5)
```

### Time Series Split
```python
from sklearn.model_selection import TimeSeriesSplit
tss = TimeSeriesSplit(n_splits=5, gap=0)
```

### Repeated K-Fold
```python
from sklearn.model_selection import RepeatedStratifiedKFold
rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=42)
```

## Avoiding Overfitting
- Use early stopping with validation set.
- Increase regularization (reg_alpha, reg_lambda, dropout).
- Reduce model complexity (fewer leaves, shallower depth).
- Add more data augmentation.
- Use cross-validation instead of single train/val split.
- Pseudo-labeling: Use model predictions on test set as additional training data.

## Practical Tips
- Always use `random_state` for reproducibility.
- Log all experiments (MLflow, Weights & Biases, or simple CSV).
- Start with default parameters, then tune.
- Use `n_jobs=-1` for parallel training.
- Monitor both train and validation metrics to detect overfitting.
- Use `optuna.visualization` to understand parameter importance.
