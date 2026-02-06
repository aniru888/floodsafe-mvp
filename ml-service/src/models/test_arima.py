"""
Quick test script for ARIMA model.
Run: python -m src.models.test_arima
"""

import numpy as np
from pathlib import Path
import tempfile

from arima_model import ARIMAFloodModel


def test_arima_basic():
    """Test basic ARIMA functionality."""
    print("Testing ARIMA Flood Model...")

    # Generate synthetic time series data (upward trend with noise)
    np.random.seed(42)
    n_samples = 100
    t = np.arange(n_samples)
    trend = 0.1 * t
    seasonal = 5 * np.sin(2 * np.pi * t / 12)
    noise = np.random.normal(0, 1, n_samples)
    y = trend + seasonal + noise + 50  # Base level at 50

    print(f"Generated {n_samples} samples")
    print(f"Mean: {y.mean():.2f}, Std: {y.std():.2f}")

    # Initialize model
    model = ARIMAFloodModel(
        order=(5, 1, 0),
        seasonal_order=(1, 0, 1, 12),  # Monthly seasonality
        threshold=55.0
    )
    print(f"\nModel: {model}")

    # Train
    print("\nFitting model...")
    model.fit(X=None, y=y)
    print(f"Training complete. AIC={model.training_history.get('aic', 'N/A')}")

    # Predict
    print("\nMaking predictions...")
    steps = 7
    predictions = model.predict(steps=steps)
    print(f"Predictions (next {steps} steps): {predictions}")

    # Predict probabilities
    print("\nCalculating flood probabilities...")
    probabilities = model.predict_proba(steps=steps)
    print(f"Probabilities: {probabilities}")

    # Test save/load
    print("\nTesting save/load...")
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir)
        model.save(save_path)
        print(f"Saved to {save_path}")

        # Load
        model_loaded = ARIMAFloodModel()
        model_loaded.load(save_path)
        print(f"Loaded: {model_loaded}")

        # Verify predictions match
        predictions_loaded = model_loaded.predict(steps=steps)
        assert np.allclose(predictions, predictions_loaded), "Predictions don't match!"
        print("Save/load verification passed!")

    # Model info
    print("\nModel info:")
    info = model.get_model_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    print("\n✓ All tests passed!")


if __name__ == "__main__":
    test_arima_basic()
