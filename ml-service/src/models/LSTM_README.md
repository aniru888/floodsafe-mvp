# LSTM Flood Prediction Model

Bidirectional LSTM with self-attention mechanism for flood prediction in the FloodSafe ML service.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LSTM-Attention-Flood                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Temporal Features (seq_length, n_features)                 │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────┐                                    │
│  │ Bidirectional LSTM  │ ──► hidden_size * 2               │
│  │  (2 layers, 128dim) │                                    │
│  └─────────────────────┘                                    │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────┐                                    │
│  │  Self-Attention     │ ──► Context Vector                │
│  │  (learns weights)    │     (weighted sum)                │
│  └─────────────────────┘                                    │
│         │                                                    │
│         └──────────────┬─────────────┐                      │
│                        │             │                      │
│  Spatial Embeddings    │             │                      │
│  (AlphaEarth 64-dim)   │             │                      │
│         │              │             │                      │
│         ▼              │             │                      │
│  ┌─────────────┐       │             │                      │
│  │     MLP     │       │             │                      │
│  │  128 → 64   │       │             │                      │
│  └─────────────┘       │             │                      │
│         │              │             │                      │
│         └──────────────┴─────────────┘                      │
│                        │                                     │
│                        ▼                                     │
│              ┌─────────────────┐                            │
│              │  Final Layers   │                            │
│              │  256 → 128 → 1  │                            │
│              │   (Sigmoid)     │                            │
│              └─────────────────┘                            │
│                        │                                     │
│                        ▼                                     │
│                 Flood Probability                           │
│                    [0.0, 1.0]                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. AttentionLayer
- Self-attention mechanism on LSTM outputs
- Computes attention weights over temporal sequence
- Returns context vector (weighted sum) and attention weights
- Enables interpretability: which time steps matter most

### 2. FloodLSTM (nn.Module)
- **Bidirectional LSTM**: Captures temporal patterns in both directions
- **Attention**: Focuses on relevant time steps
- **Embedding MLP**: Processes AlphaEarth spatial features
- **Output Layers**: Combines features and predicts probability

### 3. LSTMFloodModel (FloodPredictionModel)
- High-level interface implementing abstract base class
- Training with early stopping and validation monitoring
- Device management (CUDA/CPU)
- Save/load functionality

## Features

### Training
- **Early Stopping**: Monitors validation loss, stops when no improvement
- **Gradient Clipping**: Prevents exploding gradients (threshold: 1.0)
- **Learning Rate Scheduling**: ReduceLROnPlateau for adaptive learning
- **Batch Processing**: Efficient mini-batch training
- **Validation Split**: Automatic train/val split (default 20%)

### Prediction
- `predict()`: Binary predictions (0 or 1)
- `predict_proba()`: Probability predictions [0, 1]
- `get_attention_weights()`: Extract attention for interpretability

### Device Support
- Automatic CUDA detection
- Falls back to CPU if GPU unavailable
- Efficient tensor operations

## Usage

### Basic Training

```python
from lstm_model import LSTMFloodModel
import numpy as np

# Initialize model
model = LSTMFloodModel(
    input_size=8,           # Number of temporal features
    hidden_size=128,        # LSTM hidden size (from config)
    num_layers=2,           # LSTM layers (from config)
    embedding_dim=64,       # AlphaEarth dimension
    dropout=0.2
)

# Prepare data
# X: (n_samples, sequence_length, n_features)
# y: (n_samples,) binary labels
# embeddings: (n_samples, 64) AlphaEarth embeddings

X_train = np.random.randn(1000, 30, 8)  # 1000 samples, 30 timesteps, 8 features
y_train = np.random.randint(0, 2, 1000)  # Binary labels
embeddings = np.random.randn(1000, 64)   # Spatial embeddings

# Train
model.fit(
    X_train, y_train,
    embeddings=embeddings,
    epochs=100,
    batch_size=32,
    validation_split=0.2,
    patience=10
)
```

### Making Predictions

```python
# New data
X_test = np.random.randn(10, 30, 8)
emb_test = np.random.randn(10, 64)

# Probability predictions
probas = model.predict_proba(X_test, emb_test)
print(f"Flood probabilities: {probas}")

# Binary predictions (threshold = 0.5)
preds = model.predict(X_test, emb_test)
print(f"Binary predictions: {preds}")
```

### Attention Visualization

```python
# Get attention weights to see which timesteps the model focuses on
attention = model.get_attention_weights(X_test[:1], emb_test[:1])

# attention shape: (1, sequence_length)
# Values sum to 1.0 for each sample

import matplotlib.pyplot as plt

plt.figure(figsize=(12, 4))
plt.bar(range(30), attention[0])
plt.xlabel('Time Step')
plt.ylabel('Attention Weight')
plt.title('Model Attention Over Time')
plt.show()
```

### Save and Load

```python
from pathlib import Path

# Save trained model
save_path = Path("./models/lstm_model_v1")
model.save(save_path)

# Load model later
model2 = LSTMFloodModel(input_size=8, hidden_size=128, num_layers=2)
model2.load(save_path)

# Use loaded model
probas = model2.predict_proba(X_test, emb_test)
```

### Without Embeddings (Temporal Only)

```python
# If AlphaEarth embeddings are not available
model = LSTMFloodModel(input_size=8)

model.fit(X_train, y_train, embeddings=None, epochs=100)
probas = model.predict_proba(X_test, embeddings=None)

# Model will zero-pad the embedding dimension internally
```

## Configuration

Model uses settings from `core/config.py`:

```python
LSTM_SEQUENCE_LENGTH = 30    # Temporal window size
LSTM_HIDDEN_SIZE = 128       # LSTM hidden dimension
LSTM_NUM_LAYERS = 2          # Number of LSTM layers
BATCH_SIZE = 32              # Training batch size
LEARNING_RATE = 0.001        # Initial learning rate
```

## Input Data Format

### Temporal Features (X)
- **Shape**: `(n_samples, sequence_length, n_features)`
- **Type**: `np.ndarray` (float32)
- **Example features**:
  - Precipitation (mm/day)
  - Temperature (°C)
  - Humidity (%)
  - Soil moisture
  - River discharge
  - Historical water levels
  - Weather forecasts
  - Derived features (rolling means, etc.)

### Target (y)
- **Shape**: `(n_samples,)` or `(n_samples, 1)`
- **Type**: `np.ndarray` (float32)
- **Values**: Binary (0 = no flood, 1 = flood)

### Spatial Embeddings
- **Shape**: `(n_samples, 64)`
- **Type**: `np.ndarray` (float32)
- **Source**: AlphaEarth (Google Earth Engine)
- **Bands**: A00 to A63
- **Optional**: Can be None for temporal-only predictions

## Model Parameters

```python
LSTMFloodModel(
    input_size: int,              # Required: number of temporal features
    hidden_size: int = 128,       # LSTM hidden dimension
    num_layers: int = 2,          # LSTM layers
    embedding_dim: int = 64,      # AlphaEarth dimension
    dropout: float = 0.2,         # Dropout rate
    device: str = None            # 'cuda', 'cpu', or None (auto)
)
```

### Training Parameters

```python
model.fit(
    X: np.ndarray,                # Temporal features
    y: np.ndarray,                # Binary labels
    embeddings: np.ndarray,       # Spatial embeddings (optional)
    epochs: int = 100,            # Max training epochs
    batch_size: int = 32,         # Batch size
    validation_split: float = 0.2,  # Validation fraction
    learning_rate: float = 0.001, # Initial learning rate
    patience: int = 10,           # Early stopping patience
    min_delta: float = 1e-4,      # Minimum improvement
    grad_clip: float = 1.0        # Gradient clipping threshold
)
```

## Performance Considerations

### Memory Usage
- **LSTM**: `O(num_layers * hidden_size^2)`
- **Attention**: `O(sequence_length * hidden_size)`
- **Batch size**: Adjust based on GPU memory

### Training Speed
- **GPU**: Highly recommended for sequences > 30 timesteps
- **CPU**: Feasible for small datasets (< 10,000 samples)
- **Typical**: ~1-2 seconds/epoch for 1000 samples on GPU

### Hyperparameter Tuning
- `hidden_size`: 64-256 (larger = more capacity, slower)
- `num_layers`: 1-3 (diminishing returns after 3)
- `dropout`: 0.1-0.3 (higher for larger models)
- `learning_rate`: 0.0001-0.01 (start with 0.001)

## Comparison with Other Models

| Model | Pros | Cons | Use When |
|-------|------|------|----------|
| **LSTM** | Captures long-term patterns, attention interpretability | Slower training, needs more data | Have sequence data, need interpretability |
| **ARIMA** | Fast, simple, no training needed | No spatial features, linear assumptions | Quick baseline, small data |
| **Prophet** | Handles seasonality, trends | No spatial features | Strong seasonal patterns |
| **Ensemble** | Best accuracy | Slowest | Production deployment |

## Testing

Run tests to verify installation:

```bash
cd apps/ml-service/src/models
python test_lstm.py
```

Expected output:
```
============================================================
LSTM Flood Model Test
============================================================

1. Generating synthetic data...
   - Samples: 200
   - Sequence length: 30
   - Features: 8
   - Embedding dim: 64
   - Flood samples: 102 (51.0%)

2. Initializing LSTM model...
   - Model: LSTM-Attention-Flood
   - Parameters: 234,497
   - Device: cuda:0

3. Training model...
   - Training complete!
   - Final train loss: 0.4823
   - Final val loss: 0.5012

...

ALL TESTS PASSED!
============================================================
```

## Integration with FloodSafe

### Data Pipeline

```python
from data.gee_client import GEEClient
from embeddings.alphaearth import AlphaEarthExtractor
from models.lstm_model import LSTMFloodModel

# 1. Fetch temporal data (precipitation, ERA5, etc.)
gee = GEEClient()
temporal_data = gee.fetch_time_series(
    lat=28.6139, lon=77.2090,
    start_date='2023-01-01',
    end_date='2023-12-31',
    features=['precipitation', 'temperature', 'humidity']
)

# 2. Fetch AlphaEarth embeddings
ae = AlphaEarthExtractor()
embeddings = ae.extract(lat=28.6139, lon=77.2090)

# 3. Prepare sequences
X, y = prepare_sequences(temporal_data, window=30)

# 4. Train model
model = LSTMFloodModel(input_size=X.shape[-1])
model.fit(X, y, embeddings=embeddings)

# 5. Make predictions
future_X = prepare_forecast_sequence(...)
flood_proba = model.predict_proba(future_X, embeddings)
```

## References

- **ml_flood**: ECMWF's flood forecasting architecture
- **AlphaEarth**: Google's 64-dimensional Earth embeddings
- **GEE Datasets**: CHIRPS, ERA5-Land, SRTM DEM
- **FloodSafe**: Nonprofit flood monitoring platform

## Troubleshooting

### CUDA Out of Memory
```python
# Reduce batch size
model.fit(X, y, batch_size=16)  # Instead of 32

# Reduce model size
model = LSTMFloodModel(hidden_size=64, num_layers=1)
```

### Poor Convergence
```python
# Increase training epochs
model.fit(X, y, epochs=200, patience=20)

# Adjust learning rate
model.fit(X, y, learning_rate=0.0001)

# Check data normalization
X_normalized = (X - X.mean(axis=0)) / X.std(axis=0)
```

### Long Training Time
```python
# Use smaller model
model = LSTMFloodModel(hidden_size=64, num_layers=1)

# Reduce sequence length
# Trim X to shorter sequences: X[:, -20:, :]

# Use early stopping
model.fit(X, y, patience=5)  # Stop early if no improvement
```

## Future Enhancements

- [ ] Multi-horizon predictions (1-day, 3-day, 7-day)
- [ ] Uncertainty quantification (Bayesian LSTM)
- [ ] Transfer learning across regions
- [ ] Multi-task learning (flood severity + duration)
- [ ] Attention visualization dashboard
