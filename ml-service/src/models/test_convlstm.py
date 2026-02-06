"""
Test script for CNN-ConvLSTM model and Focal Loss.

Verifies:
1. Focal Loss computation and gradient flow
2. ConvLSTM model forward pass
3. Training loop with focal loss
4. Attention weight extraction
5. Save/load functionality
"""

import torch
import numpy as np
from pathlib import Path
import tempfile

from .losses import FocalLoss, BinaryFocalLoss, CombinedLoss
from .convlstm_model import CNNConvLSTM, ConvLSTMFloodModel


def test_focal_loss():
    """Test Focal Loss computation."""
    print("\n" + "="*60)
    print("Test 1: Focal Loss")
    print("="*60)

    loss_fn = FocalLoss(alpha=0.75, gamma=2.0)

    # Create sample data with gradient tracking
    logits = torch.randn(32, 1, requires_grad=True)
    targets = torch.randint(0, 2, (32, 1)).float()

    # Compute loss
    loss = loss_fn(logits, targets)

    print(f"Logits shape: {logits.shape}")
    print(f"Targets shape: {targets.shape}")
    print(f"Focal Loss: {loss.item():.4f}")
    print(f"Loss requires_grad: {loss.requires_grad}")

    # Compare with standard BCE
    bce_loss = torch.nn.BCEWithLogitsLoss()(logits, targets)
    print(f"BCE Loss (comparison): {bce_loss.item():.4f}")

    # Test backward pass
    loss.backward()
    assert logits.grad is not None, "Gradients should be computed"
    print(f"Gradient computed: Yes (mean grad: {logits.grad.mean().item():.6f})")

    assert loss.requires_grad, "Loss should require gradients"
    print("PASS: Focal Loss computation")


def test_binary_focal_loss():
    """Test BinaryFocalLoss (flood-optimized)."""
    print("\n" + "="*60)
    print("Test 2: BinaryFocalLoss (flood-optimized)")
    print("="*60)

    loss_fn = BinaryFocalLoss()  # alpha=0.75, gamma=2.0

    # Simulate class imbalance (3.6% positive class)
    n_samples = 1000
    n_positive = int(n_samples * 0.036)

    logits = torch.randn(n_samples, 1)
    targets = torch.zeros(n_samples, 1)
    targets[:n_positive] = 1.0

    loss = loss_fn(logits, targets)

    print(f"Samples: {n_samples}, Positive class: {n_positive} ({100*n_positive/n_samples:.1f}%)")
    print(f"BinaryFocalLoss: {loss.item():.4f}")
    print("PASS: BinaryFocalLoss with class imbalance")


def test_combined_loss():
    """Test CombinedLoss (Focal + Dice)."""
    print("\n" + "="*60)
    print("Test 3: CombinedLoss (Focal + Dice)")
    print("="*60)

    loss_fn = CombinedLoss(focal_weight=0.7, dice_weight=0.3)

    logits = torch.randn(32, 1)
    targets = torch.randint(0, 2, (32, 1)).float()

    loss = loss_fn(logits, targets)

    print(f"CombinedLoss: {loss.item():.4f}")
    print("PASS: CombinedLoss computation")


def test_cnn_convlstm_forward():
    """Test CNN-ConvLSTM forward pass."""
    print("\n" + "="*60)
    print("Test 4: CNN-ConvLSTM Forward Pass")
    print("="*60)

    model = CNNConvLSTM(
        input_dim=37,
        conv_filters=64,
        lstm_units=32,
        num_conv_layers=2
    )

    # Create sample input (batch, seq_len, features)
    batch_size = 8
    seq_len = 30
    input_dim = 37

    x = torch.randn(batch_size, seq_len, input_dim)

    # Forward pass
    logits = model(x)

    print(f"Input shape: {x.shape}")
    print(f"Output logits shape: {logits.shape}")
    print(f"Expected shape: ({batch_size}, 1)")

    assert logits.shape == (batch_size, 1), "Output shape mismatch"
    print("PASS: CNN-ConvLSTM forward pass")


def test_convlstm_attention():
    """Test attention weight extraction."""
    print("\n" + "="*60)
    print("Test 5: Attention Weight Extraction")
    print("="*60)

    model = CNNConvLSTM(input_dim=37)
    x = torch.randn(4, 30, 37)

    # Forward pass
    logits = model(x)

    # Get attention weights
    attn_weights = model.get_attention_weights()

    print(f"Input shape: {x.shape}")
    print(f"Attention weights shape: {attn_weights.shape}")

    assert attn_weights is not None, "Attention weights should not be None"
    print("PASS: Attention weight extraction")


def test_convlstm_training():
    """Test ConvLSTM training loop."""
    print("\n" + "="*60)
    print("Test 6: ConvLSTM Training Loop")
    print("="*60)

    # Create synthetic dataset
    n_samples = 100
    seq_len = 30
    input_dim = 37

    X = np.random.randn(n_samples, seq_len, input_dim).astype(np.float32)
    y = np.random.randint(0, 2, (n_samples, 1)).astype(np.float32)

    # Initialize model
    model = ConvLSTMFloodModel(
        input_dim=input_dim,
        conv_filters=32,  # Smaller for faster testing
        lstm_units=16,
        device='cpu'
    )

    print(f"Model parameters: {model._count_parameters():,}")

    # Train for a few epochs
    model.fit(
        X, y,
        epochs=5,
        batch_size=16,
        validation_split=0.2,
        learning_rate=1e-3,
        patience=5
    )

    assert model.is_trained, "Model should be marked as trained"
    print(f"Training history keys: {list(model.training_history.keys())}")
    print(f"Final train loss: {model.training_history['train_loss'][-1]:.4f}")
    print(f"Final val loss: {model.training_history['val_loss'][-1]:.4f}")
    print("PASS: ConvLSTM training loop")


def test_convlstm_prediction():
    """Test ConvLSTM prediction."""
    print("\n" + "="*60)
    print("Test 7: ConvLSTM Prediction")
    print("="*60)

    # Create and train model
    n_samples = 50
    seq_len = 30
    input_dim = 37

    X_train = np.random.randn(n_samples, seq_len, input_dim).astype(np.float32)
    y_train = np.random.randint(0, 2, (n_samples, 1)).astype(np.float32)

    model = ConvLSTMFloodModel(input_dim=input_dim, device='cpu')
    model.fit(X_train, y_train, epochs=3, batch_size=16)

    # Make predictions
    X_test = np.random.randn(10, seq_len, input_dim).astype(np.float32)

    probas = model.predict_proba(X_test)
    preds = model.predict(X_test)

    print(f"Test samples: {X_test.shape[0]}")
    print(f"Probability predictions shape: {probas.shape}")
    print(f"Binary predictions shape: {preds.shape}")
    print(f"Sample probabilities: {probas[:3].flatten()}")
    print(f"Sample predictions: {preds[:3]}")

    assert probas.shape == (10, 1), "Probability shape mismatch"
    assert preds.shape == (10,), "Binary prediction shape mismatch"
    assert np.all((probas >= 0) & (probas <= 1)), "Probabilities should be in [0, 1]"
    assert np.all((preds == 0) | (preds == 1)), "Predictions should be 0 or 1"
    print("PASS: ConvLSTM prediction")


def test_convlstm_save_load():
    """Test save/load functionality."""
    print("\n" + "="*60)
    print("Test 8: Save/Load Model")
    print("="*60)

    # Train a small model
    X = np.random.randn(30, 30, 37).astype(np.float32)
    y = np.random.randint(0, 2, (30, 1)).astype(np.float32)

    model1 = ConvLSTMFloodModel(input_dim=37, device='cpu')
    model1.fit(X, y, epochs=2, batch_size=8)

    # Save model
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test_model"
        model1.save(save_path)

        print(f"Model saved to: {save_path}")
        print(f"Files: {list(save_path.iterdir())}")

        # Load model
        model2 = ConvLSTMFloodModel(input_dim=37, device='cpu')
        model2.load(save_path)

        print(f"Model loaded successfully")

        # Compare predictions
        X_test = np.random.randn(5, 30, 37).astype(np.float32)
        pred1 = model1.predict_proba(X_test)
        pred2 = model2.predict_proba(X_test)

        diff = np.abs(pred1 - pred2).max()
        print(f"Max prediction difference: {diff:.6f}")

        assert diff < 1e-5, "Loaded model predictions should match original"
        print("PASS: Save/load functionality")


def test_convlstm_model_info():
    """Test model info retrieval."""
    print("\n" + "="*60)
    print("Test 9: Model Info")
    print("="*60)

    model = ConvLSTMFloodModel(
        input_dim=37,
        conv_filters=64,
        lstm_units=32,
        device='cpu'
    )

    info = model.get_model_info()

    print("Model Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")

    assert info['architecture'] == 'CNN-ConvLSTM + Self-Attention'
    assert info['input_dim'] == 37
    assert info['conv_filters'] == 64
    assert info['lstm_units'] == 32
    print("PASS: Model info retrieval")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("CNN-ConvLSTM and Focal Loss Test Suite")
    print("="*60)

    tests = [
        test_focal_loss,
        test_binary_focal_loss,
        test_combined_loss,
        test_cnn_convlstm_forward,
        test_convlstm_attention,
        test_convlstm_training,
        test_convlstm_prediction,
        test_convlstm_save_load,
        test_convlstm_model_info,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test_fn.__name__}")
            print(f"Error: {e}")
            failed += 1

    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\nAll tests passed!")
    else:
        print(f"\n{failed} test(s) failed")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
