# Data Preprocessing for Kaggle Competitions

## Missing Value Handling

### Detection
```python
import pandas as pd
missing = df.isnull().sum()
missing_pct = missing / len(df) * 100
print(missing_pct[missing_pct > 0].sort_values(ascending=False))
```

### Strategies by Missing Rate
- **< 5% missing**: Simple imputation (mean/median/mode) usually fine.
- **5-30% missing**: Use model-based imputation or add missing indicator.
- **> 30% missing**: Consider dropping feature, or use as-is (tree models handle NaN natively).
- **> 70% missing**: Usually drop the feature.

### Imputation Methods
- **Mean imputation**: For normally distributed numerical features.
- **Median imputation**: For skewed numerical features (more robust to outliers).
- **Mode imputation**: For categorical features.
- **KNN imputation**: Uses K nearest neighbors. Better quality, slower.
  ```python
  from sklearn.impute import KNNImputer
  imputer = KNNImputer(n_neighbors=5)
  X_imputed = imputer.fit_transform(X)
  ```
- **Iterative imputation (MICE)**: Models each feature as function of others. Best quality.
  ```python
  from sklearn.impute import IterativeImputer
  imputer = IterativeImputer(max_iter=10, random_state=42)
  ```
- **Forward/backward fill**: For time series data.
- **Constant fill**: Fill with -999 or "MISSING" — lets model learn from missingness.
- **Missing indicator**: Add binary column `feature_is_missing`. Captures missingness pattern.

### Tree Models and Missing Values
- LightGBM, XGBoost, CatBoost handle NaN natively — no imputation needed.
- They learn optimal direction for missing values during training.
- For linear models and neural nets, always impute.

## Outlier Handling

### Detection
```python
# IQR method
Q1 = df[col].quantile(0.25)
Q3 = df[col].quantile(0.75)
IQR = Q3 - Q1
outliers = df[(df[col] < Q1 - 1.5*IQR) | (df[col] > Q3 + 1.5*IQR)]

# Z-score method
from scipy import stats
z_scores = stats.zscore(df[col].dropna())
outliers = df[abs(z_scores) > 3]
```

### Strategies
- **Clipping**: Clip to 1st/99th percentile. `df[col].clip(lower=p1, upper=p99)`.
- **Log transform**: Reduces impact of large values. `np.log1p(x)`.
- **Winsorization**: Replace outliers with percentile values.
- **Remove**: Only if outliers are data errors, not real extreme values.
- **Keep**: Tree models are robust to outliers — often best to keep them.

## Scaling and Normalization

### When to Scale
- **Linear models**: Always scale (StandardScaler or MinMaxScaler).
- **Neural networks**: Always scale (StandardScaler or MinMaxScaler).
- **Tree models**: Never need scaling (LightGBM, XGBoost, Random Forest).
- **KNN, SVM**: Always scale.

### Methods
- **StandardScaler**: Zero mean, unit variance. `(x - mean) / std`.
- **MinMaxScaler**: Scale to [0, 1]. `(x - min) / (max - min)`.
- **RobustScaler**: Uses median and IQR. Robust to outliers.
- **QuantileTransformer**: Maps to uniform or normal distribution. Very robust.
- **PowerTransformer (Yeo-Johnson)**: Makes distribution more Gaussian.

```python
from sklearn.preprocessing import StandardScaler, RobustScaler
scaler = RobustScaler()
X_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)  # Use fit from train only!
```

## Categorical Encoding

### Low Cardinality (< 10 unique values)
- One-hot encoding: `pd.get_dummies()` or `OneHotEncoder`.
- Ordinal encoding if natural order exists.

### Medium Cardinality (10-100 unique values)
- Target encoding with cross-validation.
- Frequency encoding.
- Embedding (for neural networks).

### High Cardinality (> 100 unique values)
- Target encoding with strong smoothing.
- Hash encoding.
- Frequency encoding.
- CatBoost native handling.

### Target Encoding (Correct Implementation)
```python
from category_encoders import TargetEncoder
from sklearn.model_selection import StratifiedKFold

def target_encode_cv(train, test, col, target, n_folds=5):
    oof_encoded = np.zeros(len(train))
    test_encoded = np.zeros(len(test))
    
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    
    for train_idx, val_idx in skf.split(train, target):
        encoder = TargetEncoder(smoothing=10)
        encoder.fit(train.iloc[train_idx][col], target.iloc[train_idx])
        oof_encoded[val_idx] = encoder.transform(train.iloc[val_idx][col]).values.ravel()
        test_encoded += encoder.transform(test[col]).values.ravel() / n_folds
    
    return oof_encoded, test_encoded
```

## Class Imbalance

### Resampling
```python
from imblearn.over_sampling import SMOTE, ADASYN
from imblearn.under_sampling import RandomUnderSampler
from imblearn.pipeline import Pipeline

# SMOTE oversampling
smote = SMOTE(sampling_strategy=0.5, random_state=42)
X_resampled, y_resampled = smote.fit_resample(X_train, y_train)

# Combined over + under sampling
pipeline = Pipeline([
    ('over', SMOTE(sampling_strategy=0.5)),
    ('under', RandomUnderSampler(sampling_strategy=0.8))
])
```

### Class Weights
```python
from sklearn.utils.class_weight import compute_class_weight
class_weights = compute_class_weight('balanced', classes=np.unique(y), y=y)
weight_dict = dict(zip(np.unique(y), class_weights))

# In LightGBM
model = lgb.LGBMClassifier(class_weight='balanced')
# Or manually: scale_pos_weight = neg_count / pos_count
```

## Train/Test Distribution Shift

### Detection
```python
# Adversarial validation
train_df['is_test'] = 0
test_df['is_test'] = 1
combined = pd.concat([train_df, test_df])

# Train classifier to distinguish train vs test
# If AUC > 0.6, there's distribution shift
```

### Handling
- Remove features that distinguish train from test (high adversarial importance).
- Use importance weighting to reweight training samples.
- Pseudo-labeling to adapt to test distribution.

## Data Cleaning
- Remove duplicate rows: `df.drop_duplicates()`.
- Fix data types: ensure numerical columns are float/int, not object.
- Handle inconsistent categories: lowercase, strip whitespace, fix typos.
- Validate ranges: age should be 0-120, probability should be 0-1.
- Check for constant features: `df.nunique() == 1` — drop them.
