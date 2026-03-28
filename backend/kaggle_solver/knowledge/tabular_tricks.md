# Advanced Tabular Data Tricks for Kaggle

## Target Transformation

### Log Transform for Regression
```python
import numpy as np
# Transform target
y_train_log = np.log1p(y_train)
model.fit(X_train, y_train_log)
# Inverse transform predictions
y_pred = np.expm1(model.predict(X_test))
```
- Use when target is right-skewed (prices, counts, sales).
- RMSLE metric implies log-transforming target.

### Box-Cox Transform
```python
from scipy.stats import boxcox
y_transformed, lambda_ = boxcox(y_train + 1)  # +1 to handle zeros
# Inverse: scipy.special.inv_boxcox(y_pred, lambda_)
```

## Pseudo-Labeling
```python
# Step 1: Train on labeled data
model.fit(X_train, y_train)

# Step 2: Predict on test with confidence
test_probs = model.predict_proba(X_test)
confidence = test_probs.max(axis=1)

# Step 3: Select high-confidence predictions
threshold = 0.95
mask = confidence > threshold
X_pseudo = X_test[mask]
y_pseudo = test_probs[mask].argmax(axis=1)

# Step 4: Retrain with pseudo-labels
X_combined = np.vstack([X_train, X_pseudo])
y_combined = np.concatenate([y_train, y_pseudo])
model.fit(X_combined, y_combined)
```

## Adversarial Validation
```python
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import cross_val_score

# Combine train and test, label them
train_adv = X_train.copy(); train_adv['is_test'] = 0
test_adv = X_test.copy(); test_adv['is_test'] = 1
combined = pd.concat([train_adv, test_adv], ignore_index=True)

X_adv = combined.drop('is_test', axis=1)
y_adv = combined['is_test']

# Train classifier
adv_model = lgb.LGBMClassifier(n_estimators=100, random_state=42)
auc = cross_val_score(adv_model, X_adv, y_adv, cv=5, scoring='roc_auc').mean()
print(f"Adversarial AUC: {auc:.4f}")  # > 0.6 means distribution shift

# Find features causing shift
adv_model.fit(X_adv, y_adv)
importance = pd.Series(adv_model.feature_importances_, index=X_adv.columns)
print("Top features causing shift:", importance.nlargest(10))
# Consider removing these features
```

## Out-of-Fold (OOF) Predictions
```python
import numpy as np
from sklearn.model_selection import StratifiedKFold

def train_oof(model, X, y, X_test, n_folds=5, task='classification'):
    oof_preds = np.zeros(len(X))
    test_preds = np.zeros(len(X_test))
    scores = []
    
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    
    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]
        
        model.fit(X_tr, y_tr)
        
        if task == 'classification':
            oof_preds[val_idx] = model.predict_proba(X_val)[:, 1]
            test_preds += model.predict_proba(X_test)[:, 1] / n_folds
        else:
            oof_preds[val_idx] = model.predict(X_val)
            test_preds += model.predict(X_test) / n_folds
        
        # Score this fold
        from sklearn.metrics import roc_auc_score
        score = roc_auc_score(y_val, oof_preds[val_idx])
        scores.append(score)
        print(f"Fold {fold+1}: {score:.4f}")
    
    print(f"Mean CV: {np.mean(scores):.4f} ± {np.std(scores):.4f}")
    return oof_preds, test_preds
```

## Feature Importance Analysis
```python
import shap
import matplotlib.pyplot as plt

# SHAP values for LightGBM
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_val)

# Summary plot
shap.summary_plot(shap_values, X_val, plot_type="bar")

# Dependence plot for top feature
shap.dependence_plot("feature_name", shap_values, X_val)

# Feature importance from SHAP
shap_importance = pd.DataFrame({
    'feature': X_val.columns,
    'importance': np.abs(shap_values).mean(0)
}).sort_values('importance', ascending=False)
```

## Threshold Optimization
```python
from sklearn.metrics import f1_score
import numpy as np

def optimize_threshold(y_true, y_prob, metric='f1'):
    thresholds = np.arange(0.1, 0.9, 0.01)
    scores = []
    for t in thresholds:
        y_pred = (y_prob >= t).astype(int)
        if metric == 'f1':
            score = f1_score(y_true, y_pred)
        scores.append(score)
    best_threshold = thresholds[np.argmax(scores)]
    print(f"Best threshold: {best_threshold:.2f}, Score: {max(scores):.4f}")
    return best_threshold
```

## Memory Optimization
```python
def reduce_memory(df):
    for col in df.columns:
        col_type = df[col].dtype
        if col_type != object:
            c_min = df[col].min()
            c_max = df[col].max()
            if str(col_type)[:3] == 'int':
                if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                    df[col] = df[col].astype(np.int8)
                elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                    df[col] = df[col].astype(np.int16)
                elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                    df[col] = df[col].astype(np.int32)
            else:
                if c_min > np.finfo(np.float16).min and c_max < np.finfo(np.float16).max:
                    df[col] = df[col].astype(np.float32)  # float16 often causes issues
    return df
```

## Aggregation Features (Group Statistics)
```python
def add_group_features(df, group_col, agg_col, prefix=''):
    stats = df.groupby(group_col)[agg_col].agg(['mean', 'std', 'min', 'max', 'median', 'count'])
    stats.columns = [f'{prefix}{group_col}_{agg_col}_{s}' for s in stats.columns]
    return df.merge(stats, on=group_col, how='left')

# Example: add user-level statistics
df = add_group_features(df, 'user_id', 'purchase_amount', prefix='user_')
df = add_group_features(df, 'category', 'price', prefix='cat_')
```

## Frequency Encoding
```python
def frequency_encode(train, test, col):
    freq = train[col].value_counts(normalize=True)
    train[f'{col}_freq'] = train[col].map(freq)
    test[f'{col}_freq'] = test[col].map(freq).fillna(0)
    return train, test
```

## Interaction Features for Top Features
```python
from itertools import combinations

def add_interactions(df, top_features, operations=['multiply', 'divide', 'add', 'subtract']):
    for f1, f2 in combinations(top_features, 2):
        if 'multiply' in operations:
            df[f'{f1}_x_{f2}'] = df[f1] * df[f2]
        if 'divide' in operations:
            df[f'{f1}_div_{f2}'] = df[f1] / (df[f2] + 1e-8)
        if 'add' in operations:
            df[f'{f1}_plus_{f2}'] = df[f1] + df[f2]
        if 'subtract' in operations:
            df[f'{f1}_minus_{f2}'] = df[f1] - df[f2]
    return df
```

## Noise Injection for Regularization
```python
# Add small Gaussian noise to numerical features during training
def add_noise(X, noise_std=0.01):
    noise = np.random.normal(0, noise_std, X.shape)
    return X + noise * X.std(axis=0)
```

## Label Smoothing
```python
# For classification, smooth labels to prevent overconfidence
def smooth_labels(y, smoothing=0.1):
    n_classes = len(np.unique(y))
    y_smooth = y * (1 - smoothing) + smoothing / n_classes
    return y_smooth
```
