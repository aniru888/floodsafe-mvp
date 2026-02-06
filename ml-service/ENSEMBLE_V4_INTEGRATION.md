# Ensemble v4 Integration Summary

## Changes Made

### 1. Updated Ensemble Model (`src/models/ensemble.py`)

#### Import Changes
- **Added**: `ConvLSTMFloodModel` import
- **Moved**: ARIMA, Prophet, LSTM to "legacy imports" section
- **Order**: ConvLSTM, GNN, LightGBM (v4 models first)

#### Method Updates: `predict()` and `predict_proba()`

**New signature**:
```python
def predict(self, X: np.ndarray, coordinates: Optional[np.ndarray] = None, **kwargs)
def predict_proba(self, X: np.ndarray, coordinates: Optional[np.ndarray] = None, **kwargs)
```

**Key improvements**:
- Accepts `coordinates` parameter for GNN spatial modeling
- Automatically handles input shape conversion:
  - ConvLSTM expects 3D `(batch, seq_len, features)`
  - GNN expects 2D `(batch, features)` + coordinates
  - LightGBM expects 2D `(batch, features)`
- Fallback logic for missing sequences/coordinates

**Shape conversion logic**:
```python
if model.model_name == "ConvLSTM-Flood":
    if X.ndim == 2:
        X_seq = np.tile(X.reshape(-1, 1, X.shape[-1]), (1, 30, 1))
    else:
        X_seq = X
    pred = model.predict(X_seq)

elif model.model_name == "GNN-Flood":
    if X.ndim == 3:
        X_flat = X[:, -1, :]  # Use last timestep
    else:
        X_flat = X
    pred = model.predict(X_flat, coordinates=coordinates)

elif model.model_name in ["LightGBM", "lightgbm"]:
    if X.ndim == 3:
        X_flat = X[:, -1, :]
    else:
        X_flat = X
    pred = model.predict(X_flat)
```

#### Load Function Updates

**Added ConvLSTM detection**:
```python
if "ConvLSTM" in name:
    model = ConvLSTMFloodModel(input_dim=37)
elif "LSTM" in name and "ConvLSTM" not in name:
    model = LSTMFloodModel(input_size=37, embedding_dim=0)
```

This ensures backward compatibility while prioritizing v4 models.

#### New Function: `create_default_ensemble(version)`

**Replaced**:
```python
create_default_ensemble(include_gnn: bool = False)
```

**With**:
```python
create_default_ensemble(version: str = "v4")
```

**Supported versions**:
- `"v4"` (default): ConvLSTM + GNN + LightGBM
- `"v3_legacy"`: ARIMA + Prophet + LSTM + LightGBM

**v4 weights**:
```python
ConvLSTM:  40%  # Temporal patterns with attention
GNN:       30%  # Spatial flood propagation
LightGBM:  30%  # Fast gradient boosting
```

---

### 2. New Training Script (`scripts/06_train_ensemble_v4.py`)

**Key features**:
- Trains all three v4 models sequentially
- Uses Focal Loss for all models (handles class imbalance)
- Evaluates each model individually
- Creates weighted ensemble
- Saves comprehensive metadata

**Training flow**:
```
1. Load dataset (37-dim features)
2. Create 30-day sequences for ConvLSTM
3. Split train/validation
4. Train ConvLSTM (100 epochs, focal loss)
5. Train GNN (100 epochs, k-NN graph)
6. Train LightGBM (200 rounds, early stopping)
7. Create ensemble with weights [0.40, 0.30, 0.30]
8. Evaluate on validation set
9. Save to models/ensemble_v4/
```

**Evaluation metrics**:
- MSE (Mean Squared Error)
- MAE (Mean Absolute Error)
- Accuracy (binary classification)
- Focal Loss (class-imbalance aware)

**Output files**:
```
models/ensemble_v4/
├── ensemble_metadata.json       # Ensemble configuration
├── v4_metadata.json             # Training metrics + timestamps
├── model_0_ConvLSTM-Flood/      # ConvLSTM weights
├── model_1_GNN-Flood/           # GNN weights
└── model_2_lightgbm/            # LightGBM booster
```

---

### 3. Documentation (`ENSEMBLE_V4_GUIDE.md`)

Comprehensive guide covering:
- Architecture overview
- Feature vector (37 dimensions)
- Training pipeline
- Making predictions
- Model input requirements
- Focal Loss explanation
- Evaluation metrics
- Migration from v3
- Troubleshooting
- API integration

---

## Backward Compatibility

### Loading Legacy Models

The ensemble can still load v3 models:
```python
ensemble.load(Path('models/ensemble_v3'))
```

### Creating Legacy Ensembles

```python
ensemble = create_default_ensemble(version='v3_legacy')
```

### Model Detection

The `load()` method checks model names:
- `"ConvLSTM"` → ConvLSTMFloodModel
- `"GNN"` or `"gnn"` → GNNFloodModel
- `"LightGBM"` → LightGBMFloodModel
- `"ARIMA"` → ARIMAFloodModel (legacy)
- `"Prophet"` → ProphetFloodModel (legacy)
- `"LSTM"` (excluding ConvLSTM) → LSTMFloodModel (legacy)

---

## Key Design Decisions

### 1. Automatic Shape Conversion

**Rationale**: Different models expect different input formats. The ensemble should handle this transparently.

**Implementation**: Check input dimensions and model type, then convert:
- 2D → 3D for ConvLSTM (create dummy sequences)
- 3D → 2D for GNN/LightGBM (use last timestep)

### 2. Optional Coordinates Parameter

**Rationale**: GNN benefits from spatial coordinates, but they may not always be available.

**Implementation**:
- If provided, GNN uses k-NN spatial graph
- If missing, GNN creates dummy grid layout

### 3. Focal Loss for All Models

**Rationale**: Flood events are rare (class imbalance). Focal Loss down-weights easy examples and focuses on hard cases.

**Parameters**:
- `alpha = 0.75`: Higher weight for flood class
- `gamma = 2.0`: Strong focusing on hard examples

### 4. Separate Training Script

**Rationale**: v4 has different training requirements (sequences, spatial graphs, focal loss). Keeping separate scripts allows users to choose.

**Files**:
- `06_train_ensemble.py` → v3 (legacy)
- `06_train_ensemble_v4.py` → v4 (current)

---

## Testing Checklist

### Unit Tests
- [ ] Ensemble loads v4 models correctly
- [ ] Ensemble loads v3 models (backward compatibility)
- [ ] `predict()` handles 2D and 3D inputs
- [ ] `predict_proba()` handles 2D and 3D inputs
- [ ] Shape conversion for ConvLSTM, GNN, LightGBM
- [ ] Coordinates parameter passed to GNN
- [ ] `create_default_ensemble('v4')` creates correct models
- [ ] `create_default_ensemble('v3_legacy')` creates legacy models

### Integration Tests
- [ ] Train v4 ensemble on sample data
- [ ] Save and load v4 ensemble
- [ ] Make predictions with v4 ensemble
- [ ] API integration (ML service loads v4)
- [ ] Grid predictions with spatial coordinates

### End-to-End Tests
- [ ] Full training pipeline (06_train_ensemble_v4.py)
- [ ] Model evaluation metrics
- [ ] Prediction accuracy on validation set
- [ ] API endpoint returns predictions

---

## Migration Guide

### From v3 to v4

1. **Train new ensemble**:
   ```bash
   cd apps/ml-service/scripts
   python 06_train_ensemble_v4.py
   ```

2. **Update model loading** (if hardcoded):
   ```python
   # Old
   ensemble.load(Path('models/ensemble_v3'))

   # New
   ensemble.load(Path('models/ensemble_v4'))
   ```

3. **Add coordinates** (optional, for GNN):
   ```python
   # Old
   predictions = ensemble.predict(X)

   # New (with spatial modeling)
   predictions = ensemble.predict(X, coordinates=coords)
   ```

4. **Restart ML service**:
   ```bash
   docker-compose restart ml-service
   ```

---

## Performance Expectations

### Training Time (5-year dataset)

| Model | Epochs | Time (GPU) | Time (CPU) |
|-------|--------|------------|------------|
| ConvLSTM | 100 | ~15 min | ~2 hours |
| GNN | 100 | ~10 min | ~1 hour |
| LightGBM | 200 rounds | ~2 min | ~5 min |
| **Total** | - | ~30 min | ~3.5 hours |

### Inference Speed

| Model | Samples | Time (GPU) | Time (CPU) |
|-------|---------|------------|------------|
| ConvLSTM | 1000 | 0.5 sec | 2 sec |
| GNN | 1000 | 0.3 sec | 1 sec |
| LightGBM | 1000 | 0.05 sec | 0.1 sec |
| **Ensemble** | 1000 | 1 sec | 3.5 sec |

### Accuracy Improvements

Expected improvements over v3:
- **Temporal modeling**: +3-5% (ConvLSTM attention)
- **Spatial modeling**: +5-7% (GNN graph structure)
- **Class imbalance**: +2-4% (Focal loss)
- **Total expected**: +10-15% accuracy improvement

---

## Next Steps

1. **Run training script**: `python 06_train_ensemble_v4.py`
2. **Verify metrics**: Check validation accuracy and focal loss
3. **Test predictions**: Use Python script or API
4. **Deploy to staging**: Update ML service
5. **Monitor performance**: Track real-world accuracy
6. **Iterate**: Adjust weights or hyperparameters as needed

---

## Questions & Support

- **Training issues**: Check `ENSEMBLE_V4_GUIDE.md` troubleshooting section
- **Model architecture**: See ConvLSTM, GNN, LightGBM documentation
- **API integration**: Refer to ML service API docs
- **Performance tuning**: Adjust weights in `create_default_ensemble()`
