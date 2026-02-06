# CNN-ConvLSTM Quick Start

## 30-Second Setup

```python
from src.models import ConvLSTMFloodModel
import numpy as np

# 1. Load data (30-day sequences, 37 features)
X = np.load("data/X_train.npy")  # Shape: (samples, 30, 37)
y = np.load("data/y_train.npy")  # Shape: (samples,)

# 2. Train
model = ConvLSTMFloodModel(input_dim=37, device='cuda')
model.fit(X, y, epochs=100, batch_size=32)

# 3. Predict
probs = model.predict_proba(X_test)  # Flood probabilities

# 4. Save
model.save("models/my_model")
```

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `src/models/losses.py` | Focal Loss (class imbalance) | 104 |
| `src/models/convlstm_model.py` | CNN-ConvLSTM architecture | 612 |
| `src/models/test_convlstm.py` | Test suite (9 tests) | - |
| `examples/train_convlstm.py` | End-to-end training | - |

## Architecture Summary

```
Input: (batch, 30, 37)
├─ Temporal Conv: 64 filters
├─ BiLSTM: 32 units × 2 layers
├─ Attention: 4 heads
└─ Dense: 128 → 64 → 1
Output: (batch, 1) flood probability

Parameters: 105,793
```

## Loss Functions

```python
from src.models.losses import BinaryFocalLoss, CombinedLoss

# Option 1: Focal Loss (default, automatic)
model.fit(X, y)  # Uses BinaryFocalLoss(alpha=0.75, gamma=2.0)

# Option 2: Custom Combined Loss
criterion = CombinedLoss(focal_weight=0.7, dice_weight=0.3)
```

## Feature Vector (37 dims)

```
[0:6]   Terrain: elevation, slope, aspect, roughness, TPI, TWI
[6:11]  Precipitation: 24h, 3d, 7d, max_intensity, wet_days
[11:15] Temporal: day_of_year, month, is_monsoon, days_since_monsoon
[15:17] Discharge: GloFAS mean, max
[17:37] Reserved for AlphaEarth (not yet implemented)
```

## Test Suite

```bash
cd apps/ml-service
python -m src.models.test_convlstm
# Result: All 9 tests passed ✓
```

## Training Example

```bash
cd apps/ml-service
python examples/train_convlstm.py
```

**Outputs:**
- `models/convlstm_v1/model.pt` - Trained weights
- `results/convlstm_v1/training_history.png` - Loss curves
- `results/convlstm_v1/attention_heatmap.png` - Attention visualization

## Integration Points

### With Feature Extractor
```python
from src.features.extractor import FeatureExtractor

# Extract 30-day sequence
features = extractor.extract_sequential(
    lat=28.6139, lon=77.2090,
    start_date='2023-01-01', end_date='2023-01-30'
)  # Shape: (30, 37)

# Predict
X = features[np.newaxis, :, :]  # Add batch dimension
prob = model.predict_proba(X)
```

### With Ensemble
```python
from src.models import EnsembleFloodModel

ensemble = EnsembleFloodModel([
    LSTMFloodModel(input_size=37),
    ConvLSTMFloodModel(input_dim=37)
])
```

### With API
```python
# src/api/predictions.py
model = ConvLSTMFloodModel.load("models/convlstm_v1")
risk = model.predict_proba(features)
```

## Model Comparison

| Model | Params | Accuracy | F1 |
|-------|--------|----------|-----|
| LSTM-Attention | 250K | 96.2% | 0.89 |
| **ConvLSTM** | **106K** | **TBD** | **TBD** |

## Hyperparameters

```python
ConvLSTMFloodModel(
    input_dim=37,           # Features per timestep
    conv_filters=64,        # Conv layer filters (research-based)
    lstm_units=32,          # LSTM hidden size (research-based)
    num_conv_layers=2,      # Number of conv blocks
    dropout=0.2,            # Dropout rate
    num_attention_heads=4,  # Attention heads
    device='cuda'           # 'cuda' or 'cpu'
)
```

## Focal Loss Parameters

```python
BinaryFocalLoss(
    alpha=0.75,  # Weight for positive (flood) class
    gamma=2.0    # Focusing parameter (higher = focus on hard examples)
)
```

## Attention Visualization

```python
# Extract attention weights
attention = model.get_attention_weights(X_test)
# Shape: (samples, seq_len, seq_len) = (N, 30, 30)

# Plot heatmap
import matplotlib.pyplot as plt
plt.imshow(attention[0], cmap='hot')
plt.xlabel('Time step')
plt.ylabel('Time step')
plt.colorbar()
plt.show()
```

## Documentation

- **Full guide**: `src/models/CONVLSTM_USAGE.md`
- **Implementation summary**: `CONVLSTM_IMPLEMENTATION_SUMMARY.md`
- **Project guide**: `CLAUDE.md`

## Status

- [x] Focal Loss implementation
- [x] CNN-ConvLSTM architecture
- [x] Test suite (9/9 passing)
- [x] Training example
- [x] Documentation
- [ ] Train on real Delhi data
- [ ] Compare vs LSTM baseline
- [ ] Add to ensemble
- [ ] Deploy to API

## Contact Points

- ML Service: `apps/ml-service/`
- Models: `apps/ml-service/src/models/`
- Tests: Run with `python -m src.models.test_convlstm`
