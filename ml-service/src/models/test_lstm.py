"""
Test script for LSTM flood prediction model.

Verifies model initialization, training, prediction, and save/load functionality.
"""

import numpy as np
from pathlib import Path
import tempfile

from lstm_model import LSTMFloodModel


def test_lstm_model():
    """Test LSTM model end-to-end."""

    print("=" * 60)
    print("LSTM Flood Model Test")
    print("=" * 60)

    # Configuration
    n_samples = 200
    seq_length = 30
    n_features = 8  # e.g., precipitation, temperature, humidity, etc.
    embedding_dim = 64  # AlphaEarth dimension

    print(f"\n1. Generating synthetic data...")
    print(f"   - Samples: {n_samples}")
    print(f"   - Sequence length: {seq_length}")
    print(f"   - Features: {n_features}")
    print(f"   - Embedding dim: {embedding_dim}")

    # Generate synthetic temporal data
    np.random.seed(42)
    X = np.random.randn(n_samples, seq_length, n_features).astype(np.float32)

    # Generate synthetic labels (binary flood/no-flood)
    # Create pattern where high values in certain features lead to flood
    flood_indicator = (X[:, -5:, 0].mean(axis=1) + X[:, -5:, 1].mean(axis=1)) > 0.5
    y = flood_indicator.astype(np.float32)

    # Generate synthetic AlphaEarth embeddings
    embeddings = np.random.randn(n_samples, embedding_dim).astype(np.float32)

    print(f"   - Flood samples: {y.sum():.0f} ({y.mean()*100:.1f}%)")

    # Initialize model
    print(f"\n2. Initializing LSTM model...")
    model = LSTMFloodModel(
        input_size=n_features,
        hidden_size=64,  # Smaller for faster testing
        num_layers=2,
        embedding_dim=embedding_dim,
        dropout=0.2
    )

    print(f"   - Model: {model.model_name}")
    print(f"   - Parameters: {model._count_parameters():,}")
    print(f"   - Device: {model.device}")

    # Train model
    print(f"\n3. Training model...")
    model.fit(
        X, y,
        embeddings=embeddings,
        epochs=20,  # Short for testing
        batch_size=16,
        validation_split=0.2,
        patience=5
    )

    print(f"   - Training complete!")
    print(f"   - Final train loss: {model.training_history['train_loss'][-1]:.4f}")
    print(f"   - Final val loss: {model.training_history['val_loss'][-1]:.4f}")

    # Make predictions
    print(f"\n4. Making predictions...")

    # Test on a small subset
    X_test = X[:10]
    emb_test = embeddings[:10]
    y_test = y[:10]

    # Probability predictions
    probas = model.predict_proba(X_test, emb_test)
    print(f"   - Probability predictions (first 5): {probas[:5].flatten()}")

    # Binary predictions
    preds = model.predict(X_test, emb_test)
    print(f"   - Binary predictions: {preds}")
    print(f"   - Ground truth: {y_test.astype(int)}")

    # Accuracy on test subset
    accuracy = (preds == y_test).mean()
    print(f"   - Accuracy on subset: {accuracy*100:.1f}%")

    # Get attention weights
    print(f"\n5. Extracting attention weights...")
    attention = model.get_attention_weights(X_test[:1], emb_test[:1])
    print(f"   - Attention shape: {attention.shape}")
    print(f"   - Attention sum (should be ~1.0): {attention.sum():.4f}")
    print(f"   - Top 5 attended timesteps: {np.argsort(attention[0])[-5:][::-1]}")

    # Save and load
    print(f"\n6. Testing save/load...")
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test_model"

        # Save
        model.save(save_path)
        print(f"   - Model saved to {save_path}")

        # Create new model and load
        model2 = LSTMFloodModel(
            input_size=n_features,
            hidden_size=64,
            num_layers=2,
            embedding_dim=embedding_dim
        )
        model2.load(save_path)
        print(f"   - Model loaded successfully")

        # Verify predictions match
        probas2 = model2.predict_proba(X_test[:1], emb_test[:1])
        diff = np.abs(probas[:1] - probas2).max()
        print(f"   - Prediction difference: {diff:.6f} (should be ~0)")

        assert diff < 1e-5, "Loaded model predictions don't match!"

    # Model info
    print(f"\n7. Model information:")
    info = model.get_model_info()
    for key, value in info.items():
        print(f"   - {key}: {value}")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


def test_without_embeddings():
    """Test model without spatial embeddings."""

    print("\n\n" + "=" * 60)
    print("LSTM Model Test (Without Embeddings)")
    print("=" * 60)

    n_samples = 100
    seq_length = 30
    n_features = 8

    print(f"\nGenerating data without embeddings...")

    np.random.seed(42)
    X = np.random.randn(n_samples, seq_length, n_features).astype(np.float32)
    y = (X[:, -5:, 0].mean(axis=1) > 0).astype(np.float32)

    model = LSTMFloodModel(input_size=n_features, hidden_size=32, num_layers=1)

    print("Training...")
    model.fit(X, y, embeddings=None, epochs=10, batch_size=16, patience=3)

    print("Predicting...")
    probas = model.predict_proba(X[:5], embeddings=None)
    preds = model.predict(X[:5], embeddings=None)

    print(f"Predictions: {preds}")
    print(f"Probabilities: {probas.flatten()}")

    print("\nTest passed!")


if __name__ == "__main__":
    # Run tests
    test_lstm_model()
    test_without_embeddings()
