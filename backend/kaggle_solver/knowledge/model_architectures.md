# Model Architectures for Kaggle Competitions

## Gradient Boosting (Best for Tabular Data)

### LightGBM
- **Best for**: Large datasets, high cardinality categoricals, fast training.
- **Key advantages**: Leaf-wise tree growth (vs level-wise in XGBoost), faster, lower memory.
- **Native categorical support**: Pass `categorical_feature` parameter, no need to encode.
- **Key parameters**: `num_leaves` (31-255), `learning_rate` (0.01-0.1), `n_estimators` (100-5000), `min_child_samples` (20-100), `subsample` (0.6-1.0), `colsample_bytree` (0.6-1.0), `reg_alpha`, `reg_lambda`.
- **Dart mode**: Dropout for trees, often improves generalization.
- **GOSS**: Gradient-based One-Side Sampling for faster training on large datasets.

```python
import lightgbm as lgb
model = lgb.LGBMClassifier(
    n_estimators=1000, learning_rate=0.05, num_leaves=63,
    min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
    reg_alpha=0.1, reg_lambda=0.1, random_state=42
)
```

### XGBoost
- **Best for**: Medium datasets, when you need fine control over regularization.
- **Key parameters**: `max_depth` (3-10), `learning_rate`, `n_estimators`, `subsample`, `colsample_bytree`, `gamma`, `min_child_weight`, `reg_alpha`, `reg_lambda`.
- **GPU support**: `tree_method='gpu_hist'` for fast GPU training.
- **Monotone constraints**: Enforce monotonic relationships between features and target.

```python
import xgboost as xgb
model = xgb.XGBClassifier(
    n_estimators=1000, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, gamma=0.1,
    min_child_weight=5, reg_alpha=0.1, reg_lambda=1.0,
    use_label_encoder=False, eval_metric='logloss', random_state=42
)
```

### CatBoost
- **Best for**: Datasets with many categorical features, minimal preprocessing needed.
- **Key advantages**: Ordered boosting prevents target leakage, native categorical handling.
- **Key parameters**: `iterations`, `learning_rate`, `depth` (4-10), `l2_leaf_reg`, `border_count`, `cat_features`.
- **Symmetric trees**: More regularized, less prone to overfitting.

```python
from catboost import CatBoostClassifier
model = CatBoostClassifier(
    iterations=1000, learning_rate=0.05, depth=6,
    l2_leaf_reg=3, border_count=128,
    cat_features=categorical_cols, random_seed=42, verbose=100
)
```

## Neural Networks for Tabular Data

### TabNet
- Attention-based neural network for tabular data.
- Self-supervised pretraining on unlabeled data.
- Feature selection built-in via attention masks.
- Use `pytorch-tabnet` library.

### NODE (Neural Oblivious Decision Ensembles)
- Differentiable oblivious decision trees.
- Often competitive with gradient boosting.

### FT-Transformer (Feature Tokenizer + Transformer)
- Tokenize each feature, apply transformer attention.
- Strong on datasets where feature interactions matter.
- Use `rtdl` library.

### MLP with Embeddings
- Embed categorical features, concatenate with numerical.
- Add batch normalization, dropout.
- Works well when you have many features.

```python
import torch.nn as nn
class TabularMLP(nn.Module):
    def __init__(self, input_dim, hidden_dims, output_dim, dropout=0.3):
        super().__init__()
        layers = []
        prev_dim = input_dim
        for dim in hidden_dims:
            layers.extend([nn.Linear(prev_dim, dim), nn.BatchNorm1d(dim), nn.ReLU(), nn.Dropout(dropout)])
            prev_dim = dim
        layers.append(nn.Linear(prev_dim, output_dim))
        self.net = nn.Sequential(*layers)
```

## Random Forest & Ensemble Trees
- **Random Forest**: Good baseline, robust to overfitting, parallelizable.
- **Extra Trees**: More randomized splits, faster, sometimes better.
- **Key parameters**: `n_estimators` (100-1000), `max_depth`, `min_samples_leaf`, `max_features` ('sqrt', 'log2').

## Linear Models
- **Logistic Regression**: Strong baseline for classification, interpretable.
- **Ridge/Lasso**: For regression with regularization.
- **ElasticNet**: Combines L1 and L2 regularization.
- **SGD Classifier**: For very large datasets.
- **LinearSVC**: Fast SVM for classification.

## When to Use What
- **Tabular structured data**: LightGBM/XGBoost/CatBoost first, then neural nets.
- **Text data**: BERT/RoBERTa fine-tuning, or TF-IDF + LightGBM.
- **Image data**: ResNet, EfficientNet, ViT.
- **Time series**: LightGBM with lag features, LSTM, Temporal Fusion Transformer.
- **Graph data**: GNN (Graph Neural Networks).
- **Small dataset (<1000 samples)**: Random Forest, SVM, simple neural nets.
- **Large dataset (>1M rows)**: LightGBM with GOSS, mini-batch neural nets.

## Model Selection Strategy
1. Start with LightGBM as baseline — fast, strong, interpretable.
2. Try XGBoost and CatBoost for comparison.
3. Add neural network (MLP or TabNet) for diversity in ensemble.
4. Ensemble top models with weighted average or stacking.
