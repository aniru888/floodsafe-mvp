# ARIMA Flood Model

## Overview

The `ARIMAFloodModel` is a baseline time series forecasting model for flood prediction. It uses ARIMA (AutoRegressive Integrated Moving Average) or SARIMA (Seasonal ARIMA) to forecast water levels, precipitation, or other flood indicators.

## Model Architecture

```
ARIMA(p, d, q) or SARIMA(p, d, q)(P, D, Q, s)

Components:
- AR(p): Autoregressive terms - past values
- I(d): Integration - differencing for stationarity
- MA(q): Moving average - past errors
- Seasonal(P,D,Q,s): Seasonal components (optional)
```

## Features

1. **Automatic Stationarity Testing**: Uses Augmented Dickey-Fuller (ADF) test
2. **Seasonal Support**: SARIMA for monsoon/seasonal patterns
3. **Probability Estimation**: Converts forecasts to flood probabilities
4. **Model Persistence**: Save/load with joblib
5. **Diagnostic Metrics**: AIC, BIC, HQIC for model selection

## Usage

### Basic Example

```python
from models import ARIMAFloodModel
import numpy as np

# Load your time series data
y_train = np.array([...])  # Water levels, precipitation, etc.

# Initialize model
model = ARIMAFloodModel(
    order=(5, 1, 0),      # (p, d, q)
    seasonal_order=None,   # No seasonality
    threshold=0.5          # Flood threshold
)

# Train
model.fit(X=None, y=y_train)

# Forecast 7 days ahead
predictions = model.predict(steps=7)
probabilities = model.predict_proba(steps=7)

# Save model
model.save(Path('models/saved/arima'))
```

### With Seasonal Pattern (Monsoon)

```python
# For data with monthly seasonality (e.g., monsoon patterns)
model = ARIMAFloodModel(
    order=(5, 1, 0),
    seasonal_order=(1, 1, 1, 12),  # Monthly cycle
    threshold=55.0
)

model.fit(X=None, y=y_train)
```

### Load Existing Model

```python
model = ARIMAFloodModel()
model.load(Path('models/saved/arima'))

# Use immediately
predictions = model.predict(steps=7)
```

## Parameters

### Constructor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `order` | Tuple[int,int,int] | (5,1,0) | ARIMA order (p, d, q) |
| `seasonal_order` | Optional[Tuple] | None | SARIMA order (P, D, Q, s) |
| `threshold` | float | 0.5 | Flood classification threshold |

**Order Guidelines:**
- **p (AR)**: 1-5 for short-term dependencies
- **d (I)**: Usually 1 for non-stationary series, 0 if already stationary
- **q (MA)**: 0-2 for error correction

### Methods

#### `fit(X, y, check_stationarity=True, **kwargs)`
Train the model on time series data.

**Args:**
- `X`: Not used (ARIMA is univariate), can be None
- `y`: Target time series array of shape (n_samples,)
- `check_stationarity`: Run ADF test before fitting
- `**kwargs`: Passed to statsmodels ARIMA/SARIMAX

**Returns:** self

#### `predict(X=None, steps=7, **kwargs)`
Forecast future values.

**Args:**
- `X`: Not used, can be None
- `steps`: Forecast horizon
- `**kwargs`: Additional forecast parameters

**Returns:** Predictions array of shape (steps,)

#### `predict_proba(X=None, steps=7, **kwargs)`
Predict flood probabilities (0-1 scale).

Uses confidence intervals and baseline statistics to estimate probability.

**Returns:** Probability array of shape (steps,)

#### `save(path)` / `load(path)`
Persist/restore model using joblib.

## Model Selection

### Choosing ARIMA Order

Use grid search or auto-selection based on AIC/BIC:

```python
from itertools import product

# Parameter grid
p_values = [1, 2, 5]
d_values = [0, 1]
q_values = [0, 1, 2]

best_aic = np.inf
best_order = None

for p, d, q in product(p_values, d_values, q_values):
    try:
        model = ARIMAFloodModel(order=(p, d, q))
        model.fit(X=None, y=y_train, check_stationarity=False)

        aic = model.training_history['aic']
        if aic < best_aic:
            best_aic = aic
            best_order = (p, d, q)
    except:
        continue

print(f"Best order: {best_order} with AIC={best_aic:.2f}")
```

### Stationarity

If ADF test shows non-stationary (p-value > 0.05):
1. Increase differencing order `d`
2. Consider log transformation if variance increases over time
3. Remove trend using detrending

## Integration with FloodSafe

### Data Sources

Use ARIMA for:
- **Water level sensors**: IoT real-time data
- **River discharge**: GloFAS historical data
- **Precipitation**: CHIRPS daily rainfall

### Baseline Model

ARIMA serves as the baseline in the model progression:
1. **ARIMA** ← Baseline (simple, interpretable)
2. **Prophet** ← Handles seasonality better
3. **LSTM** ← Captures complex patterns
4. **Ensemble** ← Production (combines all)

Compare other models against ARIMA metrics.

## Evaluation

```python
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Split data
train_size = int(0.8 * len(y))
y_train, y_test = y[:train_size], y[train_size:]

# Train
model = ARIMAFloodModel(order=(5, 1, 0))
model.fit(X=None, y=y_train)

# Predict
steps = len(y_test)
y_pred = model.predict(steps=steps)

# Metrics
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))

print(f"MAE: {mae:.2f}")
print(f"RMSE: {rmse:.2f}")
```

## Limitations

1. **Univariate**: Only uses single time series (no external features)
2. **Linear**: Assumes linear relationships
3. **Stationarity**: Requires stationary data (after differencing)
4. **Short-term**: Best for short forecast horizons (7-14 days)

For multivariate or non-linear patterns, use LSTM or ensemble model.

## References

- statsmodels ARIMA: https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMA.html
- Box, G. E. P., & Jenkins, G. M. (1970). Time Series Analysis: Forecasting and Control
- Hyndman, R. J., & Athanasopoulos, G. (2021). Forecasting: Principles and Practice

## See Also

- `base.py` - Abstract FloodPredictionModel interface
- `prophet_model.py` - Prophet-based model (better seasonality)
- `lstm_model.py` - LSTM with attention (complex patterns)
- `ensemble.py` - Multi-model voting
