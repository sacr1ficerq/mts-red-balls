# Feature Engineering for Kaggle Competitions

## Tabular Data Feature Engineering

### Numerical Features
- **Log transform**: Apply `log1p` to right-skewed features (income, prices, counts). Reduces outlier impact.
- **Box-Cox / Yeo-Johnson**: More general power transforms for normalization. Use `sklearn.preprocessing.PowerTransformer`.
- **Binning / Quantile binning**: Convert continuous to categorical bins. Useful when relationship is non-linear.
- **Polynomial features**: Create `x^2`, `x^3`, `x*y` interactions. Use `sklearn.preprocessing.PolynomialFeatures(degree=2)`.
- **Rank transform**: Replace values with their rank. Robust to outliers, useful for tree models.
- **Clipping**: Clip extreme values at 1st/99th percentile to reduce outlier noise.
- **Normalization**: StandardScaler for linear models, MinMaxScaler for neural nets. Trees don't need scaling.
- **Ratio features**: `feature_a / feature_b` — often captures important relationships (e.g., debt-to-income ratio).
- **Difference features**: `feature_a - feature_b` — captures relative changes.
- **Aggregation features**: Group by categorical, compute mean/std/min/max/median of numerical. Very powerful for tabular.

### Categorical Features
- **Label encoding**: Simple integer mapping. Good for tree-based models (LightGBM, XGBoost, CatBoost).
- **One-hot encoding**: Binary columns per category. Good for linear models, bad for high-cardinality.
- **Target encoding (mean encoding)**: Replace category with mean target value. Very powerful but needs cross-validation to avoid leakage.
  - Use `category_encoders.TargetEncoder` with `smoothing` parameter.
  - Always encode within CV folds to prevent leakage.
- **Frequency encoding**: Replace category with its frequency in dataset. Captures popularity.
- **Ordinal encoding**: When categories have natural order (low/medium/high).
- **Hash encoding**: For very high cardinality (millions of categories). Use `category_encoders.HashingEncoder`.
- **Leave-one-out encoding**: Variant of target encoding, more robust.
- **CatBoost encoding**: Built-in ordered target encoding in CatBoost, handles leakage automatically.
- **Embedding**: For neural networks, learn dense representations of categories.

### Datetime Features
- Extract: year, month, day, hour, minute, weekday, week_of_year, quarter, day_of_year.
- **Cyclical encoding**: For periodic features (hour, month, weekday), use `sin/cos` encoding:
  - `hour_sin = sin(2π * hour / 24)`, `hour_cos = cos(2π * hour / 24)`
- **Time since event**: Days since last purchase, days until next holiday.
- **Is weekend / is holiday**: Binary flags.
- **Business days**: Number of business days between dates.
- **Lag features**: Previous values at t-1, t-7, t-30 (critical for time series).
- **Rolling statistics**: Rolling mean/std/min/max over windows (7d, 30d, 90d).

### Text Features
- **TF-IDF**: Classic bag-of-words with inverse document frequency weighting.
- **Count vectorizer**: Simple word counts.
- **N-grams**: Capture phrases (bigrams, trigrams).
- **Sentence embeddings**: Use `sentence-transformers` for semantic features.
- **BERT embeddings**: Fine-tune or use as features. `transformers` library.
- **Text statistics**: Length, word count, unique words, punctuation count, capital ratio.
- **Readability scores**: Flesch-Kincaid, Gunning Fog.
- **Named entity counts**: Number of persons, organizations, locations.

### Interaction Features
- **Pairwise interactions**: For top N important features, create all pairwise products/ratios.
- **Group statistics**: For each (cat_a, cat_b) pair, compute target statistics.
- **Cross features**: Concatenate two categorical features into one (e.g., "city_category").

## Feature Selection
- **Correlation filter**: Remove features with correlation > 0.95 with another feature.
- **Variance threshold**: Remove near-zero variance features.
- **Permutation importance**: Shuffle each feature, measure accuracy drop. Use `eli5` or `sklearn`.
- **SHAP values**: Most reliable importance measure. Use `shap` library.
- **Recursive Feature Elimination (RFE)**: Iteratively remove least important features.
- **Boruta**: Wrapper around Random Forest for robust feature selection.
- **L1 regularization**: Lasso/ElasticNet automatically zeros out unimportant features.
- **Forward/backward selection**: Greedy search for best feature subset.

## Feature Engineering Pipelines
```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer

preprocessor = ColumnTransformer([
    ('num', Pipeline([('scaler', StandardScaler())]), numerical_cols),
    ('cat', Pipeline([('ohe', OneHotEncoder(handle_unknown='ignore'))]), categorical_cols),
])
```

## Target Leakage Prevention
- Never use future information to predict past.
- Always encode within CV folds (target encoding, etc.).
- Be careful with aggregation features — compute on training set only, then apply to test.
- Use `sklearn.pipeline.Pipeline` to prevent leakage in cross-validation.
