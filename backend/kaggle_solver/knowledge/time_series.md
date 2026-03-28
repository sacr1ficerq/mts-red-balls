# Time Series for Kaggle Competitions

## Key Concepts

### Stationarity
- A time series is stationary if its statistical properties (mean, variance) don't change over time.
- Test with Augmented Dickey-Fuller (ADF) test: `from statsmodels.tsa.stattools import adfuller`.
- Make stationary: differencing (`df.diff()`), log transform, seasonal decomposition.

### Seasonality and Trend
- Decompose: `from statsmodels.tsa.seasonal import seasonal_decompose`.
- Trend: long-term direction.
- Seasonality: periodic patterns (daily, weekly, yearly).
- Residual: what's left after removing trend and seasonality.

## Feature Engineering for Time Series

### Lag Features
```python
def add_lag_features(df, target_col, lags=[1, 7, 14, 30, 90]):
    for lag in lags:
        df[f'{target_col}_lag_{lag}'] = df[target_col].shift(lag)
    return df
```
- Lag 1: yesterday's value.
- Lag 7: same day last week.
- Lag 30: same day last month.
- Always shift by at least 1 to avoid leakage.

### Rolling Statistics
```python
def add_rolling_features(df, target_col, windows=[7, 14, 30, 90]):
    for window in windows:
        df[f'{target_col}_roll_mean_{window}'] = df[target_col].shift(1).rolling(window).mean()
        df[f'{target_col}_roll_std_{window}'] = df[target_col].shift(1).rolling(window).std()
        df[f'{target_col}_roll_min_{window}'] = df[target_col].shift(1).rolling(window).min()
        df[f'{target_col}_roll_max_{window}'] = df[target_col).shift(1).rolling(window).max()
    return df
```

### Expanding Window Features
```python
df['cumulative_mean'] = df[target_col].shift(1).expanding().mean()
df['cumulative_std'] = df[target_col].shift(1).expanding().std()
```

### Date Features
```python
def add_date_features(df, date_col):
    df['year'] = df[date_col].dt.year
    df['month'] = df[date_col].dt.month
    df['day'] = df[date_col].dt.day
    df['dayofweek'] = df[date_col].dt.dayofweek
    df['dayofyear'] = df[date_col].dt.dayofyear
    df['weekofyear'] = df[date_col].dt.isocalendar().week
    df['quarter'] = df[date_col].dt.quarter
    df['is_weekend'] = df['dayofweek'].isin([5, 6]).astype(int)
    df['is_month_start'] = df[date_col].dt.is_month_start.astype(int)
    df['is_month_end'] = df[date_col].dt.is_month_end.astype(int)
    
    # Cyclical encoding
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
    df['dow_sin'] = np.sin(2 * np.pi * df['dayofweek'] / 7)
    df['dow_cos'] = np.cos(2 * np.pi * df['dayofweek'] / 7)
    return df
```

### Fourier Features (for Seasonality)
```python
def add_fourier_features(df, period, n_harmonics=3):
    t = np.arange(len(df))
    for k in range(1, n_harmonics + 1):
        df[f'fourier_sin_{period}_{k}'] = np.sin(2 * np.pi * k * t / period)
        df[f'fourier_cos_{period}_{k}'] = np.cos(2 * np.pi * k * t / period)
    return df
```

## Models for Time Series

### LightGBM with Lag Features (Often Best)
- Create lag features, rolling statistics, date features.
- Train LightGBM on these features.
- Fast, interpretable, handles non-linear patterns.
- Works well for multi-step forecasting with recursive strategy.

### ARIMA / SARIMA
- Classical statistical model.
- ARIMA(p, d, q): autoregressive, integrated, moving average.
- SARIMA adds seasonal component.
- Use `statsmodels.tsa.arima.model.ARIMA`.
- Good for univariate, stationary series.

### Prophet (Facebook)
```python
from prophet import Prophet
model = Prophet(seasonality_mode='multiplicative', yearly_seasonality=True)
model.fit(df[['ds', 'y']])
future = model.make_future_dataframe(periods=30)
forecast = model.predict(future)
```
- Handles holidays, multiple seasonalities.
- Robust to missing data and outliers.
- Easy to use, interpretable.

### LSTM / GRU
```python
import torch.nn as nn
class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, output_size):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_size, output_size)
    
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])
```
- Good for complex sequential patterns.
- Needs more data than classical methods.
- Harder to tune than LightGBM.

### Temporal Fusion Transformer (TFT)
- State-of-the-art for multi-horizon forecasting.
- Handles static covariates, known future inputs, observed inputs.
- Use `pytorch-forecasting` library.
- Best for complex multi-variate time series.

### N-BEATS / N-HiTS
- Pure neural network for time series.
- No feature engineering needed.
- Use `neuralforecast` library.

## Cross-Validation for Time Series

### TimeSeriesSplit
```python
from sklearn.model_selection import TimeSeriesSplit
tss = TimeSeriesSplit(n_splits=5, gap=0, test_size=None)
for train_idx, val_idx in tss.split(X):
    # Always train on past, validate on future
```

### Walk-Forward Validation
```python
def walk_forward_cv(df, n_splits=5, gap=0):
    n = len(df)
    fold_size = n // (n_splits + 1)
    for i in range(n_splits):
        train_end = fold_size * (i + 1)
        val_start = train_end + gap
        val_end = val_start + fold_size
        yield df.iloc[:train_end], df.iloc[val_start:val_end]
```

## Forecasting Strategies

### Direct Multi-Step
- Train separate model for each horizon (h=1, h=2, ..., h=n).
- More accurate but requires n models.

### Recursive Multi-Step
- Train one model for h=1.
- Use predictions as inputs for next step.
- Error accumulates over horizon.

### MIMO (Multi-Input Multi-Output)
- Train one model to predict all horizons simultaneously.
- Good balance of accuracy and efficiency.

## Handling Multiple Time Series (Panel Data)
- Global model: train one model on all series with series ID as feature.
- Local model: train separate model per series (only if enough data).
- Hierarchical forecasting: forecast at multiple aggregation levels.

## Common Pitfalls
- **Data leakage**: Using future information in features. Always shift by at least 1.
- **Wrong CV**: Using random split instead of time-based split.
- **Ignoring seasonality**: Always check for seasonal patterns.
- **Not handling missing dates**: Fill gaps with NaN or interpolate.
