"""
Train v4 ensemble model: ConvLSTM + GNN + LightGBM.

This script:
1. Loads the multi-year training dataset (37-dim features)
2. Creates sequences for ConvLSTM (30-day windows)
3. Trains the v4 ensemble (ConvLSTM 40% + GNN 30% + LightGBM 30%)
4. Evaluates using Focal Loss metric
5. Saves the trained model

Architecture:
- ConvLSTM: Temporal convolutions + BiLSTM + Attention
- GNN: Graph Neural Network for spatial patterns
- LightGBM: Gradient boosting for tabular features
"""

import sys
sys.path.insert(0, '../')

import numpy as np
import json
from pathlib import Path
from datetime import datetime
import logging

from src.models.ensemble import EnsembleFloodModel, create_default_ensemble
from src.models.convlstm_model import ConvLSTMFloodModel
from src.models.gnn_model import GNNFloodModel
from src.models.lightgbm_model import LightGBMFloodModel
from src.models.losses import BinaryFocalLoss
from src.core.config import settings

import torch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sequences(X: np.ndarray, y: np.ndarray, seq_length: int = 30):
    """
    Create sequences for ConvLSTM training.

    Args:
        X: Feature matrix of shape (n_days, n_features)
        y: Labels of shape (n_days,)
        seq_length: Sequence length (default 30 days)

    Returns:
        X_seq: Sequences of shape (n_samples, seq_length, n_features)
        y_seq: Labels for each sequence (predicting last day)
    """
    n_days, n_features = X.shape
    n_sequences = n_days - seq_length

    if n_sequences <= 0:
        raise ValueError(f"Not enough data for sequence length {seq_length}. "
                        f"Have {n_days} days, need at least {seq_length + 1}")

    X_seq = []
    y_seq = []

    for i in range(n_sequences):
        X_seq.append(X[i:i + seq_length])
        y_seq.append(y[i + seq_length])  # Predict the day after the sequence

    # Ensure float32 dtype for PyTorch compatibility
    return np.array(X_seq, dtype=np.float32), np.array(y_seq, dtype=np.float32)


def load_dataset(path: str):
    """Load training dataset from npz file."""
    logger.info(f"Loading dataset from {path}...")
    data = np.load(path, allow_pickle=True)

    X = data['X']
    y = data['y']
    dates = data['dates'] if 'dates' in data else None
    rainfall = data['rainfall'] if 'rainfall' in data else None

    # Ensure proper numeric dtypes (fix object_ arrays)
    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)
    if rainfall is not None:
        rainfall = np.array(rainfall, dtype=np.float32)

    # Replace any NaN/inf values with 0
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    y = np.nan_to_num(y, nan=0.0, posinf=1.0, neginf=0.0)

    logger.info(f"Dataset loaded: {X.shape[0]} samples, {X.shape[1]} features")
    logger.info(f"X dtype: {X.dtype}, y dtype: {y.dtype}")
    logger.info(f"Label range: {y.min():.3f} - {y.max():.3f}")

    return X, y, dates, rainfall


def evaluate_with_focal_loss(model, X_val, y_val):
    """Evaluate using focal loss metric."""
    preds = model.predict_proba(X_val)

    # Ensure 1D arrays
    if preds.ndim > 1:
        preds = preds.flatten()
    if y_val.ndim > 1:
        y_val = y_val.flatten()

    focal = BinaryFocalLoss()
    loss = focal(torch.tensor(preds), torch.tensor(y_val))
    return loss.item()


def train_ensemble_v4(
    X: np.ndarray,
    y: np.ndarray,
    seq_length: int = 30,
    epochs: int = 100,
    batch_size: int = 32,
    validation_split: float = 0.2,
    save_path: str = '../models/ensemble_v4'
):
    """
    Train the v4 ensemble model: ConvLSTM + GNN + LightGBM.

    Args:
        X: Feature matrix (n_days, 37 features)
        y: Binary labels (n_days,) - 0=no flood, 1=flood
        seq_length: ConvLSTM sequence length
        epochs: Training epochs
        batch_size: Batch size
        validation_split: Validation split ratio
        save_path: Where to save the trained model

    Returns:
        Trained ensemble model
    """
    print("\n" + "=" * 70)
    print("ENSEMBLE V4 TRAINING")
    print("=" * 70)

    # Create sequences for ConvLSTM
    print(f"\n[1/6] Creating {seq_length}-day sequences...")
    X_seq, y_seq = create_sequences(X, y, seq_length)
    print(f"      Created {len(X_seq)} sequences of shape {X_seq.shape}")

    # Split data
    print(f"\n[2/6] Splitting train/validation...")
    n_samples = len(X_seq)
    n_val = int(n_samples * validation_split)
    n_train = n_samples - n_val

    indices = np.random.permutation(n_samples)
    train_idx, val_idx = indices[:n_train], indices[n_train:]

    X_train_seq, X_val_seq = X_seq[train_idx], X_seq[val_idx]
    y_train_seq, y_val_seq = y_seq[train_idx], y_seq[val_idx]

    # For non-sequential models (GNN, LightGBM), use last timestep
    X_train_flat = X_train_seq[:, -1, :]  # (n_train, 37)
    X_val_flat = X_val_seq[:, -1, :]      # (n_val, 37)

    print(f"      Train: {n_train} samples, Val: {n_val} samples")

    # Initialize models
    print(f"\n[3/6] Initializing models...")

    convlstm = ConvLSTMFloodModel(
        input_dim=37,
        conv_filters=64,
        lstm_units=32,
        num_conv_layers=2,
        dropout=0.2,
        num_attention_heads=4,
        device='cuda' if torch.cuda.is_available() else 'cpu'
    )
    print(f"      [OK] ConvLSTM initialized (device: {convlstm.device})")

    gnn = GNNFloodModel(
        input_dim=37,
        hidden_dim=64,
        num_layers=3,
        gnn_type='gcn',
        k_neighbors=5
    )
    print(f"      [OK] GNN initialized")

    lightgbm = LightGBMFloodModel()
    print(f"      [OK] LightGBM initialized")

    # Train ConvLSTM with Focal Loss
    print(f"\n[4/6] Training models...")
    print(f"\n      Training ConvLSTM (this may take a while)...")
    try:
        convlstm.fit(
            X_train_seq,
            y_train_seq,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.2,  # Internal validation from train set
            learning_rate=1e-3,
            patience=15,
            grad_clip=1.0
        )
        print(f"      [OK] ConvLSTM trained")

        # Evaluate on validation set
        val_loss = evaluate_with_focal_loss(convlstm, X_val_seq, y_val_seq)
        print(f"      ConvLSTM Validation Focal Loss: {val_loss:.4f}")

    except Exception as e:
        print(f"      [FAIL] ConvLSTM training failed: {e}")
        import traceback
        traceback.print_exc()

    # Train GNN
    print(f"\n      Training GNN...")
    try:
        # Generate dummy coordinates for spatial graph construction
        # In production, use actual lat/lng coordinates
        n_train_flat = len(X_train_flat)
        grid_size = int(np.ceil(np.sqrt(n_train_flat)))
        coords_x = np.arange(grid_size)
        coords_y = np.arange(grid_size)
        xx, yy = np.meshgrid(coords_x, coords_y)
        coordinates = np.stack([xx.ravel()[:n_train_flat], yy.ravel()[:n_train_flat]], axis=1)

        gnn.fit(
            X_train_flat,
            y_train_seq,
            coordinates=coordinates,
            epochs=100,
            batch_size=32,
            lr=0.001,
            validation_split=0.2
        )
        print(f"      [OK] GNN trained")

        # Evaluate
        val_loss = evaluate_with_focal_loss(gnn, X_val_flat, y_val_seq)
        print(f"      GNN Validation Focal Loss: {val_loss:.4f}")

    except Exception as e:
        print(f"      [FAIL] GNN training failed: {e}")
        import traceback
        traceback.print_exc()

    # Train LightGBM
    print(f"\n      Training LightGBM...")
    try:
        lightgbm.fit(
            X_train_flat,
            y_train_seq,
            num_boost_round=200,
            early_stopping_rounds=20,
            valid_set=(X_val_flat, y_val_seq)
        )
        print(f"      [OK] LightGBM trained")

        # Evaluate
        val_loss = evaluate_with_focal_loss(lightgbm, X_val_flat, y_val_seq)
        print(f"      LightGBM Validation Focal Loss: {val_loss:.4f}")

    except Exception as e:
        print(f"      [FAIL] LightGBM training failed: {e}")
        import traceback
        traceback.print_exc()

    # Create ensemble
    print(f"\n[5/6] Creating ensemble...")
    ensemble = EnsembleFloodModel(strategy="weighted_average")
    ensemble.add_model(convlstm, weight=0.40)
    ensemble.add_model(gnn, weight=0.30)
    ensemble.add_model(lightgbm, weight=0.30)
    ensemble._trained = True

    # Evaluate ensemble on validation set
    print(f"\n      Evaluating ensemble...")
    try:
        # Get ensemble predictions (use sequences for ConvLSTM compatibility)
        y_pred = ensemble.predict_proba(X_val_seq)
        y_pred = y_pred.flatten()

        # Calculate metrics
        mse = np.mean((y_val_seq - y_pred) ** 2)
        mae = np.mean(np.abs(y_val_seq - y_pred))

        # Binary accuracy
        y_pred_binary = (y_pred >= 0.5).astype(int)
        y_val_binary = (y_val_seq >= 0.5).astype(int)
        accuracy = (y_pred_binary == y_val_binary).mean()

        # Focal loss
        focal_loss = evaluate_with_focal_loss(ensemble, X_val_seq, y_val_seq)

        print(f"\n      Validation Metrics (Ensemble):")
        print(f"      - MSE:         {mse:.4f}")
        print(f"      - MAE:         {mae:.4f}")
        print(f"      - Accuracy:    {accuracy*100:.2f}%")
        print(f"      - Focal Loss:  {focal_loss:.4f}")

    except Exception as e:
        print(f"      [FAIL] Evaluation failed: {e}")
        import traceback
        traceback.print_exc()

    # Save ensemble
    print(f"\n[6/6] Saving trained ensemble to {save_path}...")
    try:
        save_dir = Path(save_path)
        ensemble.save(save_dir)

        # Save additional metadata
        metadata = {
            "version": "v4",
            "architecture": "ConvLSTM + GNN + LightGBM",
            "weights": {
                "ConvLSTM": 0.40,
                "GNN": 0.30,
                "LightGBM": 0.30
            },
            "input_dim": 37,
            "seq_length": seq_length,
            "trained_at": datetime.now().isoformat(),
            "validation_metrics": {
                "mse": float(mse),
                "mae": float(mae),
                "accuracy": float(accuracy),
                "focal_loss": float(focal_loss)
            }
        }

        with open(save_dir / "v4_metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"      [OK] Ensemble saved successfully")
    except Exception as e:
        print(f"      [FAIL] Save failed: {e}")
        import traceback
        traceback.print_exc()

    return ensemble


def main():
    """Main training pipeline."""
    print("\n" + "=" * 70)
    print("FLOODSAFE ML - ENSEMBLE V4 TRAINING PIPELINE")
    print("=" * 70)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Configuration
    dataset_path = '../data/delhi_monsoon_5years.npz'
    save_path = '../models/ensemble_v4'
    seq_length = 30
    epochs = 100
    batch_size = 32

    # Check dataset exists
    if not Path(dataset_path).exists():
        print(f"\n[ERROR] Dataset not found: {dataset_path}")
        print(f"        Please run data generation script first")
        return

    # Load dataset
    X, y, dates, rainfall = load_dataset(dataset_path)

    # Verify feature dimensions
    if X.shape[1] != 37:
        print(f"\n[ERROR] Expected 37 features, got {X.shape[1]}")
        print(f"        Please regenerate training data with correct feature vector")
        return

    print(f"\n[INFO] Using 37-dim feature vector")
    print(f"        - Dynamic World: 9 land cover probabilities")
    print(f"        - ESA WorldCover: 6 static land cover percentages")
    print(f"        - Sentinel-2: 5 spectral indices")
    print(f"        - Terrain: 6 DEM features")
    print(f"        - Precipitation: 5 CHIRPS features")
    print(f"        - Temporal: 4 time features")
    print(f"        - GloFAS: 2 river discharge features")

    # Train ensemble
    ensemble = train_ensemble_v4(
        X=X,
        y=y,
        seq_length=seq_length,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.2,
        save_path=save_path
    )

    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)
    print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nNext steps:")
    print(f"1. Restart ML service to load trained model")
    print(f"2. Test predictions via API:")
    print(f"   curl -X POST http://localhost:8002/api/v1/predictions/forecast \\")
    print(f"     -H 'Content-Type: application/json' \\")
    print(f"     -d '{{\"latitude\": 28.6315, \"longitude\": 77.2167, \"horizon_days\": 7}}'")


if __name__ == "__main__":
    main()
