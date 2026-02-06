"""
Train ensemble model on real GEE data.

This script:
1. Loads the multi-year training dataset (37-dim features)
2. Creates sequences for LSTM (30-day windows)
3. Trains the ensemble (ARIMA + Prophet + LSTM + LightGBM)
4. Evaluates and saves the trained model

Note: AlphaEarth embeddings removed - new 37-dim feature vector includes
Dynamic World, WorldCover, and Sentinel-2 data instead.
"""

import sys
sys.path.insert(0, '../')

import numpy as np
import json
from pathlib import Path
from datetime import datetime
import logging

from src.models.ensemble import create_default_ensemble, EnsembleFloodModel
from src.models.lstm_model import LSTMFloodModel
from src.models.arima_model import ARIMAFloodModel
from src.models.prophet_model import ProphetFloodModel
from src.models.lightgbm_model import LightGBMFloodModel
from src.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sequences(X: np.ndarray, y: np.ndarray, seq_length: int = 30):
    """
    Create sequences for LSTM training.

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


def train_ensemble_on_data(
    X: np.ndarray,
    y: np.ndarray,
    seq_length: int = 30,
    epochs: int = 50,
    batch_size: int = 16,
    validation_split: float = 0.2,
    save_path: str = '../models/ensemble'
):
    """
    Train the ensemble model on the provided data.

    Args:
        X: Feature matrix (n_days, 37 features)
        y: Continuous risk scores (n_days,)
        seq_length: LSTM sequence length
        epochs: Training epochs
        batch_size: Batch size
        validation_split: Validation split ratio
        save_path: Where to save the trained model

    Returns:
        Trained ensemble model
    """
    print("\n" + "=" * 70)
    print("ENSEMBLE TRAINING")
    print("=" * 70)

    # Create sequences for LSTM
    print(f"\n[1/5] Creating {seq_length}-day sequences...")
    X_seq, y_seq = create_sequences(X, y, seq_length)
    print(f"      Created {len(X_seq)} sequences of shape {X_seq.shape}")

    # Create ensemble with custom LSTM input size
    print(f"\n[2/5] Initializing ensemble model...")
    n_features = X.shape[1]  # 37 features (Dynamic World + WorldCover + Sentinel-2 + DEM + CHIRPS + Temporal + GloFAS)

    ensemble = EnsembleFloodModel(strategy="weighted_average")

    # Add ARIMA (works on 1D time series - use mean of features or first feature)
    arima = ARIMAFloodModel()
    ensemble.add_model(arima, weight=0.15)
    print(f"      Added ARIMA model (weight: 0.15)")

    # Add Prophet (also 1D time series)
    prophet = ProphetFloodModel()
    ensemble.add_model(prophet, weight=0.25)
    print(f"      Added Prophet model (weight: 0.25)")

    # Add LSTM with correct input size (no embeddings - features are self-contained)
    lstm = LSTMFloodModel(
        input_size=n_features,
        hidden_size=settings.LSTM_HIDDEN_SIZE,
        num_layers=settings.LSTM_NUM_LAYERS,
        embedding_dim=0,  # No external embeddings
        dropout=0.2
    )
    ensemble.add_model(lstm, weight=0.35)
    print(f"      Added LSTM model (weight: 0.35, input_size={n_features})")

    # Add LightGBM (gradient boosting for non-linear patterns)
    lightgbm = LightGBMFloodModel()
    ensemble.add_model(lightgbm, weight=0.25)
    print(f"      Added LightGBM model (weight: 0.25)")

    # Train individual models
    print(f"\n[3/5] Training models...")

    # Train ARIMA on the mean risk score time series
    print(f"\n      Training ARIMA...")
    try:
        # ARIMA needs 1D time series
        # Use the target values directly as a time series
        arima.fit(y.reshape(-1, 1), y)
        print(f"      [OK] ARIMA trained")
    except Exception as e:
        print(f"      [FAIL] ARIMA training failed: {e}")

    # Train Prophet
    print(f"\n      Training Prophet...")
    try:
        # Prophet also needs 1D time series with dates
        prophet.fit(y.reshape(-1, 1), y)
        print(f"      [OK] Prophet trained")
    except Exception as e:
        print(f"      [FAIL] Prophet training failed: {e}")

    # Train LightGBM
    print(f"\n      Training LightGBM...")
    try:
        # LightGBM uses non-sequential data (no sequences needed)
        lightgbm.fit(X, y)
        print(f"      [OK] LightGBM trained")
    except Exception as e:
        print(f"      [FAIL] LightGBM training failed: {e}")
        import traceback
        traceback.print_exc()

    # Train LSTM (main model)
    print(f"\n      Training LSTM (this may take a while)...")
    try:
        lstm.fit(
            X_seq,
            y_seq,
            embeddings=None,  # No external embeddings - features are self-contained
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            patience=15,
            grad_clip=1.0
        )
        print(f"      [OK] LSTM trained")
    except Exception as e:
        print(f"      [FAIL] LSTM training failed: {e}")
        import traceback
        traceback.print_exc()

    # Mark ensemble as trained
    ensemble._trained = True

    # Evaluate on training data
    print(f"\n[4/5] Evaluating model...")
    try:
        # Get LSTM predictions
        y_pred = lstm.predict_proba(X_seq, embeddings=None)
        y_pred = y_pred.flatten()

        # Calculate metrics
        mse = np.mean((y_seq - y_pred) ** 2)
        mae = np.mean(np.abs(y_seq - y_pred))
        correlation = np.corrcoef(y_seq, y_pred)[0, 1]

        print(f"\n      Training Metrics (LSTM):")
        print(f"      - MSE:  {mse:.4f}")
        print(f"      - MAE:  {mae:.4f}")
        print(f"      - Correlation: {correlation:.4f}")

        # Risk level accuracy
        # Convert continuous to risk levels
        def to_risk_level(score):
            if score < 0.2:
                return 0  # Low
            elif score < 0.5:
                return 1  # Moderate
            elif score < 0.9:
                return 2  # High
            else:
                return 3  # Very High

        y_true_levels = np.array([to_risk_level(s) for s in y_seq])
        y_pred_levels = np.array([to_risk_level(s) for s in y_pred])
        level_accuracy = (y_true_levels == y_pred_levels).mean()

        print(f"      - Risk Level Accuracy: {level_accuracy*100:.1f}%")

    except Exception as e:
        print(f"      [FAIL] Evaluation failed: {e}")

    # Save ensemble
    print(f"\n[5/5] Saving trained ensemble to {save_path}...")
    try:
        ensemble.save(Path(save_path))
        print(f"      [OK] Ensemble saved successfully")
    except Exception as e:
        print(f"      [FAIL] Save failed: {e}")

    return ensemble


def main():
    """Main training pipeline."""
    print("\n" + "=" * 70)
    print("FLOODSAFE ML - ENSEMBLE TRAINING PIPELINE")
    print("=" * 70)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Configuration
    dataset_path = '../data/delhi_monsoon_5years.npz'  # Updated: 5-year dataset with 37-dim features
    save_path = '../models/ensemble_v3'  # New model version without AlphaEarth (v3)
    seq_length = 30
    epochs = 50
    batch_size = 16

    # Check dataset exists
    if not Path(dataset_path).exists():
        print(f"\n[ERROR] Dataset not found: {dataset_path}")
        print(f"        Please run 05b_generate_multiyear_training_data.py first")
        return

    # Load dataset
    X, y, dates, rainfall = load_dataset(dataset_path)

    # Verify feature dimensions
    if X.shape[1] != 37:
        print(f"\n[ERROR] Expected 37 features, got {X.shape[1]}")
        print(f"        Please regenerate training data with new feature vector")
        return

    print(f"\n[INFO] Using 37-dim feature vector (no external embeddings needed)")
    print(f"        - Dynamic World: 9 land cover probabilities")
    print(f"        - ESA WorldCover: 6 static land cover percentages")
    print(f"        - Sentinel-2: 5 spectral indices")
    print(f"        - Terrain: 6 DEM features")
    print(f"        - Precipitation: 5 CHIRPS features")
    print(f"        - Temporal: 4 time features")
    print(f"        - GloFAS: 2 river discharge features")

    # Train ensemble
    ensemble = train_ensemble_on_data(
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
