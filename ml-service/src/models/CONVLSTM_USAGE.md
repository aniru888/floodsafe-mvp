# CNN-ConvLSTM Model and Focal Loss - Usage Guide

## Overview

This module provides:
1. **Focal Loss** - Handles class imbalance (3.6% positive flood events)
2. **CNN-ConvLSTM** - Temporal model combining convolutional and LSTM layers
3. **Self-Attention** - Interpretable attention over time steps

## Architecture

```
Input: (batch, seq_len, features)
  ↓
Temporal Conv Blocks (1D Conv + BatchNorm + Residual)
  ↓
Bidirectional LSTM (2 layers)
  ↓
Self-Attention (Multi-head)
  ↓
Global Average Pooling
  ↓
Dense Layers (128 → 64 → 1)
  ↓
Output: (batch, 1) logits
```

### Model Configuration

**Research-based parameters for Delhi flood prediction:**
- Conv filters: 64
- LSTM units: 32
- Attention heads: 4
- Sequence length: 30 days
- Input features: 37 (temporal + spatial)

## Quick Start

### 1. Basic Training

```python
from src.models import ConvLSTMFloodModel
import numpy as np

# Prepare data
X_train = np.random.randn(1000, 30, 37)  # (samples, seq_len, features)
y_train = np.random.randint(0, 2, 1000)  # Binary labels

# Initialize model
model = ConvLSTMFloodModel(
    input_dim=37,
    conv_filters=64,
    lstm_units=32,
    dropout=0.2,
    device='cuda'  # or 'cpu'
)

# Train
model.fit(
    X_train, y_train,
    epochs=100,
    batch_size=32,
    validation_split=0.2,
    learning_rate=1e-3,
    patience=10
)

# Predict
X_test = np.random.randn(100, 30, 37)
probabilities = model.predict_proba(X_test)  # (100, 1)
predictions = model.predict(X_test)           # (100,) binary
```

### 2. Using Focal Loss Directly

```python
from src.models.losses import BinaryFocalLoss
import torch

# Initialize loss
criterion = BinaryFocalLoss(alpha=0.75, gamma=2.0)

# During training
logits = model(x_batch)  # Raw logits
loss = criterion(logits, targets)
loss.backward()
```

### 3. Extract Attention Weights

```python
# Get attention weights for interpretability
attention = model.get_attention_weights(X_test)
# Shape: (samples, seq_len, seq_len)

# Visualize which timesteps the model focuses on
import matplotlib.pyplot as plt

sample_idx = 0
plt.imshow(attention[sample_idx], cmap='hot')
plt.xlabel('Time step')
plt.ylabel('Time step')
plt.title('Self-Attention Weights')
plt.colorbar()
plt.show()
```

### 4. Save and Load

```python
from pathlib import Path

# Save trained model
model.save(Path('models/convlstm_v1'))

# Load later
new_model = ConvLSTMFloodModel(input_dim=37)
new_model.load(Path('models/convlstm_v1'))
```

## Loss Functions

### FocalLoss

Down-weights easy examples, focuses on hard-to-classify cases.

```python
from src.models.losses import FocalLoss

loss = FocalLoss(
    alpha=0.25,      # Weight for positive class
    gamma=2.0,       # Focusing parameter
    reduction='mean' # 'mean', 'sum', or 'none'
)
```

**Parameters:**
- `alpha`: Higher values (0.75) prioritize positive (flood) class
- `gamma`: Higher values (2.0-5.0) focus more on hard examples

### BinaryFocalLoss

Flood-optimized defaults:

```python
from src.models.losses import BinaryFocalLoss

loss = BinaryFocalLoss(alpha=0.75, gamma=2.0)
```

### CombinedLoss

Focal Loss + Dice Loss for better gradient flow:

```python
from src.models.losses import CombinedLoss

loss = CombinedLoss(
    focal_weight=0.7,  # Weight for focal loss
    dice_weight=0.3,   # Weight for dice loss
    alpha=0.75,
    gamma=2.0
)
```

## Model Info

```python
info = model.get_model_info()
print(info)
# {
#   'name': 'ConvLSTM-Flood',
#   'architecture': 'CNN-ConvLSTM + Self-Attention',
#   'input_dim': 37,
#   'conv_filters': 64,
#   'lstm_units': 32,
#   'total_parameters': 105793,
#   'device': 'cuda',
#   ...
# }
```

## Integration with Feature Extractor

```python
from src.features.extractor import FeatureExtractor
from src.models import ConvLSTMFloodModel

# Extract 37-dim features
extractor = FeatureExtractor(delhi_geometry)
features = extractor.extract_sequential(
    lat=28.6139,
    lon=77.2090,
    start_date='2023-01-01',
    end_date='2023-01-30',
    ee_point=ee_point
)
# Shape: (30, 37)

# Batch for model (add batch dimension)
X = features[np.newaxis, :, :]  # (1, 30, 37)

# Predict
prob = model.predict_proba(X)
print(f"Flood probability: {prob[0, 0]:.2%}")
```

## Training Tips

1. **Class Imbalance**: Use `BinaryFocalLoss` with alpha=0.75
2. **Gradient Clipping**: Default 1.0 prevents exploding gradients
3. **Early Stopping**: Patience=10 epochs typical
4. **Learning Rate**: Start with 1e-3, scheduler reduces on plateau
5. **Batch Size**: 32-64 works well for most datasets

## Performance Comparison

| Model | Accuracy | F1-Score | Parameters |
|-------|----------|----------|------------|
| LSTM-Attention | 96.2% | 0.89 | ~250K |
| **ConvLSTM** | **TBD** | **TBD** | ~106K |
| ARIMA | 82.3% | 0.65 | N/A |

## References

1. Lin et al., "Focal Loss for Dense Object Detection" (2017)
2. ArXiv 2024: "Deep Learning for Short-Term Precipitation Prediction in Four Major Indian Cities"
3. FloodSafe Feature Extractor: 37-dim feature vector
   - [0:64] AlphaEarth embeddings (currently 0-padded for 37-dim)
   - [64:70] Terrain (elevation, slope, aspect)
   - [70:75] Precipitation (24h, 3d, 7d, max, wet_days)
   - [75:79] Temporal (day_of_year, month, monsoon flags)
   - [79:81] GloFAS (discharge_mean, discharge_max)

## Files

- `losses.py` - Focal Loss implementations
- `convlstm_model.py` - CNN-ConvLSTM model
- `test_convlstm.py` - Comprehensive test suite
- `CONVLSTM_USAGE.md` - This file

## Next Steps

1. Train on real Delhi flood data
2. Compare against LSTM-Attention baseline
3. Hyperparameter tuning (grid search on alpha, gamma, filters)
4. Add to ensemble model
5. Deploy to prediction API
