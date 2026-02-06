# Ensemble v4 Training Guide

## Overview

FloodSafe ML service now uses a modernized ensemble architecture (v4) that combines three state-of-the-art models:

```
Ensemble v4 = ConvLSTM (40%) + GNN (30%) + LightGBM (30%)
```

This replaces the legacy v3 architecture (ARIMA + Prophet + LSTM + LightGBM).

---

## Architecture Components

### 1. ConvLSTM (40% weight)
**Purpose**: Capture temporal patterns with spatial convolutions

**Features**:
- 1D temporal convolutions for local pattern extraction
- Bidirectional LSTM for long-term dependencies
- Multi-head self-attention for interpretability
- Focal loss for handling class imbalance

**Input**: `(batch, 30, 37)` - 30-day sequences of 37 features
**Output**: Flood probability

### 2. GNN (30% weight)
**Purpose**: Model spatial flood propagation patterns

**Features**:
- Graph Convolutional Network (GCN) or Graph Attention Network (GAT)
- k-NN spatial graph construction
- 3 message-passing layers with residual connections
- Batch normalization and dropout

**Input**: `(batch, 37)` + spatial coordinates
**Output**: Flood probability per node

### 3. LightGBM (30% weight)
**Purpose**: Fast gradient boosting for tabular features

**Features**:
- Gradient-boosted decision trees
- 10x faster inference than LSTM
- Handles non-linear feature interactions
- Feature importance interpretability

**Input**: `(batch, 37)` - flat feature vectors
**Output**: Flood probability

---

## Feature Vector (37 dimensions)

```python
features = [
    # Dynamic World (9): Land cover probabilities
    'water', 'trees', 'grass', 'flooded_vegetation', 'crops',
    'shrub_and_scrub', 'built', 'bare', 'snow_and_ice',

    # ESA WorldCover (6): Static land cover percentages
    'tree_cover_pct', 'grassland_pct', 'cropland_pct',
    'built_up_pct', 'bare_pct', 'water_bodies_pct',

    # Sentinel-2 (5): Spectral indices
    'ndvi', 'ndwi', 'evi', 'savi', 'mndwi',

    # Terrain (6): DEM-derived features
    'elevation', 'slope', 'aspect', 'tpi', 'twi', 'flow_accumulation',

    # Precipitation (5): CHIRPS rainfall
    'rain_24h', 'rain_3d', 'rain_7d', 'rain_max', 'wet_days',

    # Temporal (4): Time encoding
    'day_of_year', 'month', 'is_monsoon', 'days_since_monsoon',

    # GloFAS (2): River discharge
    'discharge_mean', 'discharge_max'
]
```

---

## Training Pipeline

### Prerequisites

1. **Python dependencies**:
   ```bash
   pip install torch torch-geometric lightgbm numpy scipy
   ```

2. **Training data**:
   - File: `apps/ml-service/data/delhi_monsoon_5years.npz`
   - Format: `{'X': (n_days, 37), 'y': (n_days,)}`
   - Generate with: `05b_generate_multiyear_training_data.py`

### Step 1: Train Ensemble v4

```bash
cd apps/ml-service/scripts
python 06_train_ensemble_v4.py
```

This will:
1. Load 5-year training dataset
2. Create 30-day sequences for ConvLSTM
3. Train ConvLSTM with Focal Loss (handles class imbalance)
4. Train GNN with spatial graph
5. Train LightGBM with early stopping
6. Create weighted ensemble
7. Evaluate on validation set
8. Save to `apps/ml-service/models/ensemble_v4/`

### Step 2: Verify Model

```python
from pathlib import Path
from src.models.ensemble import EnsembleFloodModel

# Load ensemble
ensemble = EnsembleFloodModel()
ensemble.load(Path('../models/ensemble_v4'))

# Check models
info = ensemble.get_model_info()
print(info)
# Output:
# {
#   'name': 'Ensemble-Flood',
#   'trained': True,
#   'n_models': 3,
#   'models': [
#     {'name': 'ConvLSTM-Flood', 'weight': 0.40},
#     {'name': 'GNN-Flood', 'weight': 0.30},
#     {'name': 'LightGBM', 'weight': 0.30}
#   ]
# }
```

---

## Making Predictions

### Single Point Prediction

```python
import numpy as np

# Prepare features (37-dim)
X = np.random.randn(1, 30, 37)  # 1 sample, 30 timesteps, 37 features

# Predict
probabilities = ensemble.predict_proba(X)
predictions = ensemble.predict(X)

print(f"Flood probability: {probabilities[0]:.2%}")
print(f"Binary prediction: {'Flood' if predictions[0] == 1 else 'No Flood'}")
```

### Grid Prediction (with GNN spatial modeling)

```python
# Grid features (100 points)
X = np.random.randn(100, 37)

# Spatial coordinates (lat, lng)
coordinates = np.array([
    [28.61, 77.21],  # Point 1
    [28.62, 77.22],  # Point 2
    # ... 98 more points
])

# Predict with spatial modeling
probabilities = ensemble.predict_proba(
    X,
    coordinates=coordinates  # GNN uses this for graph construction
)
```

---

## Model Input Requirements

| Model | Input Shape | Coordinates Required |
|-------|-------------|---------------------|
| ConvLSTM | `(batch, 30, 37)` | No |
| GNN | `(batch, 37)` | Yes (for graph) |
| LightGBM | `(batch, 37)` | No |
| **Ensemble** | `(batch, 30, 37)` or `(batch, 37)` | Optional |

The ensemble automatically handles input shape conversion:
- If `X` is 2D `(batch, 37)`: Creates dummy sequences for ConvLSTM
- If `X` is 3D `(batch, 30, 37)`: Uses last timestep for GNN/LightGBM
- Coordinates are optional (GNN falls back to grid layout)

---

## Loss Function: Focal Loss

Focal Loss is used to handle class imbalance (floods are rare events):

```python
FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)
```

**Parameters**:
- `alpha = 0.75`: Higher weight for flood class
- `gamma = 2.0`: Down-weight easy examples

**Benefits**:
- Focuses training on hard-to-classify samples
- Improves recall for rare flood events
- Better than standard BCE for imbalanced datasets

---

## Evaluation Metrics

The training script reports:

```
Validation Metrics (Ensemble):
  - MSE:         0.0234    # Mean Squared Error
  - MAE:         0.1123    # Mean Absolute Error
  - Accuracy:    96.20%    # Binary classification accuracy
  - Focal Loss:  0.0456    # Class-imbalance aware loss
```

### Individual Model Performance

During training, each model is evaluated separately:

```
ConvLSTM Validation Focal Loss: 0.0512
GNN Validation Focal Loss: 0.0623
LightGBM Validation Focal Loss: 0.0489
```

This helps identify which models contribute most to ensemble performance.

---

## Saved Files

After training, the ensemble is saved to `models/ensemble_v4/`:

```
ensemble_v4/
├── ensemble_metadata.json          # Ensemble config
├── v4_metadata.json                # Training metrics
├── model_0_ConvLSTM-Flood/
│   ├── model.pt                    # PyTorch weights
│   └── config.json
├── model_1_GNN-Flood/
│   ├── GNN-Flood_gnn.pt            # GNN weights
│   └── GNN-Flood_metadata.pkl
└── model_2_lightgbm/
    ├── lightgbm_booster.txt        # LightGBM model
    └── lightgbm_metadata.pkl
```

---

## Migration from v3 (Legacy)

### Loading Legacy Models

The ensemble can still load v3 models:

```python
ensemble = EnsembleFloodModel()
ensemble.load(Path('../models/ensemble_v3'))  # Legacy format
```

### Creating Legacy Ensemble

```python
from src.models.ensemble import create_default_ensemble

# Create v3 ensemble (not recommended)
ensemble_v3 = create_default_ensemble(version='v3_legacy')
```

### Differences

| Feature | v3 (Legacy) | v4 (Current) |
|---------|------------|--------------|
| Models | ARIMA + Prophet + LSTM + LightGBM | ConvLSTM + GNN + LightGBM |
| Weights | 15% + 25% + 35% + 25% | 40% + 30% + 30% |
| Spatial Modeling | No | Yes (GNN) |
| Attention | No | Yes (ConvLSTM) |
| Loss Function | MSE | Focal Loss |
| Recommended | No | **Yes** |

---

## Troubleshooting

### Error: "torch-geometric not found"

```bash
pip install torch-geometric
```

### Error: "Not enough data for sequence length 30"

You need at least 31 days of data. Reduce `seq_length`:

```python
train_ensemble_v4(X, y, seq_length=7)  # Use 7-day sequences
```

### Warning: "No coordinates provided, using grid layout"

GNN will create a dummy spatial graph. For best results, provide real coordinates:

```python
coordinates = np.array([
    [lat1, lng1],
    [lat2, lng2],
    ...
])

ensemble.fit(X, y, coordinates=coordinates)
```

### Poor Performance

1. **Check data quality**: Verify no NaN/inf values
2. **Check class balance**: Use `np.unique(y, return_counts=True)`
3. **Increase epochs**: Try `epochs=200` for ConvLSTM
4. **Adjust weights**: Experiment with different model weights

---

## API Integration

The v4 ensemble is compatible with the existing ML service API:

```bash
# Start ML service
cd apps/ml-service
python -m src.main

# Test prediction endpoint
curl -X POST http://localhost:8002/api/v1/predictions/forecast \
  -H 'Content-Type: application/json' \
  -d '{
    "latitude": 28.6315,
    "longitude": 77.2167,
    "horizon_days": 7
  }'
```

The API automatically loads the latest ensemble from `models/ensemble_v4/`.

---

## Next Steps

1. **Train ensemble**: Run `06_train_ensemble_v4.py`
2. **Evaluate metrics**: Check validation performance
3. **Deploy to production**: Restart ML service
4. **Monitor predictions**: Use API to test real-world performance
5. **Iterate**: Adjust hyperparameters based on results

---

## References

- **ConvLSTM**: ArXiv 2024 - "Deep Learning for Short-Term Precipitation Prediction"
- **GNN**: Kipf & Welling 2017 - "Semi-Supervised Classification with Graph Convolutional Networks"
- **Focal Loss**: Lin et al. 2017 - "Focal Loss for Dense Object Detection"
- **LightGBM**: Ke et al. 2017 - "LightGBM: A Highly Efficient Gradient Boosting Decision Tree"
