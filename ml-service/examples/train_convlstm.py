"""
Example: Training CNN-ConvLSTM model for flood prediction.

This script demonstrates:
1. Loading preprocessed training data
2. Training ConvLSTM with Focal Loss
3. Evaluating model performance
4. Saving trained model

Usage:
    python examples/train_convlstm.py
"""

import numpy as np
import logging
from pathlib import Path
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import matplotlib.pyplot as plt

from src.models import ConvLSTMFloodModel
from src.models.losses import BinaryFocalLoss

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_training_data(data_dir: Path):
    """
    Load preprocessed training data.

    Expected structure:
    - data_dir/X_train.npy: (n_samples, seq_len, 37)
    - data_dir/y_train.npy: (n_samples,)
    - data_dir/X_test.npy: (n_samples, seq_len, 37)
    - data_dir/y_test.npy: (n_samples,)
    """
    logger.info(f"Loading data from {data_dir}")

    X_train = np.load(data_dir / "X_train.npy")
    y_train = np.load(data_dir / "y_train.npy")
    X_test = np.load(data_dir / "X_test.npy")
    y_test = np.load(data_dir / "y_test.npy")

    logger.info(f"Train: X={X_train.shape}, y={y_train.shape}")
    logger.info(f"Test: X={X_test.shape}, y={y_test.shape}")
    logger.info(f"Positive class ratio: {y_train.mean():.3%}")

    return X_train, y_train, X_test, y_test


def train_model(X_train, y_train, config):
    """Train ConvLSTM model with given configuration."""
    logger.info("Initializing ConvLSTM model...")

    model = ConvLSTMFloodModel(
        input_dim=config['input_dim'],
        conv_filters=config['conv_filters'],
        lstm_units=config['lstm_units'],
        num_conv_layers=config['num_conv_layers'],
        dropout=config['dropout'],
        num_attention_heads=config['num_attention_heads'],
        device=config['device']
    )

    logger.info(f"Model parameters: {model._count_parameters():,}")

    logger.info("Starting training...")
    model.fit(
        X_train, y_train,
        epochs=config['epochs'],
        batch_size=config['batch_size'],
        validation_split=config['validation_split'],
        learning_rate=config['learning_rate'],
        patience=config['patience'],
        min_delta=config['min_delta']
    )

    return model


def evaluate_model(model, X_test, y_test):
    """Evaluate model on test set."""
    logger.info("Evaluating model on test set...")

    # Predictions
    y_prob = model.predict_proba(X_test).flatten()
    y_pred = model.predict(X_test)

    # Metrics
    logger.info("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['No Flood', 'Flood']))

    logger.info("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(cm)

    # ROC-AUC
    try:
        auc = roc_auc_score(y_test, y_prob)
        logger.info(f"\nROC-AUC Score: {auc:.4f}")
    except ValueError:
        logger.warning("Cannot compute ROC-AUC (only one class present)")

    return {
        'y_true': y_test,
        'y_pred': y_pred,
        'y_prob': y_prob,
        'confusion_matrix': cm
    }


def plot_training_history(model, save_dir: Path):
    """Plot training history."""
    history = model.training_history

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # Loss curves
    axes[0].plot(history['train_loss'], label='Train Loss')
    axes[0].plot(history['val_loss'], label='Val Loss')
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Focal Loss')
    axes[0].set_title('Training and Validation Loss')
    axes[0].legend()
    axes[0].grid(True)

    # Learning rate
    axes[1].plot(history['learning_rates'])
    axes[1].set_xlabel('Epoch')
    axes[1].set_ylabel('Learning Rate')
    axes[1].set_title('Learning Rate Schedule')
    axes[1].set_yscale('log')
    axes[1].grid(True)

    plt.tight_layout()
    save_path = save_dir / "training_history.png"
    plt.savefig(save_path, dpi=150)
    logger.info(f"Training history plot saved to {save_path}")
    plt.close()


def plot_attention_heatmap(model, X_sample, save_dir: Path):
    """Plot attention heatmap for a sample."""
    attention = model.get_attention_weights(X_sample[:1])

    if attention is None:
        logger.warning("No attention weights available")
        return

    plt.figure(figsize=(8, 6))
    plt.imshow(attention[0], cmap='hot', aspect='auto')
    plt.colorbar(label='Attention Weight')
    plt.xlabel('Time Step (Key)')
    plt.ylabel('Time Step (Query)')
    plt.title('Self-Attention Heatmap')

    save_path = save_dir / "attention_heatmap.png"
    plt.savefig(save_path, dpi=150)
    logger.info(f"Attention heatmap saved to {save_path}")
    plt.close()


def main():
    """Main training pipeline."""
    # Configuration
    config = {
        'input_dim': 37,
        'conv_filters': 64,
        'lstm_units': 32,
        'num_conv_layers': 2,
        'dropout': 0.2,
        'num_attention_heads': 4,
        'device': 'cuda',  # Change to 'cpu' if no GPU
        'epochs': 100,
        'batch_size': 32,
        'validation_split': 0.2,
        'learning_rate': 1e-3,
        'patience': 10,
        'min_delta': 1e-4,
    }

    # Paths
    data_dir = Path("data/processed/delhi")
    model_dir = Path("models/convlstm_v1")
    results_dir = Path("results/convlstm_v1")
    results_dir.mkdir(parents=True, exist_ok=True)

    # Check if data exists
    if not (data_dir / "X_train.npy").exists():
        logger.error(f"Training data not found in {data_dir}")
        logger.info("Please run preprocessing first to generate training data")
        logger.info("Expected files: X_train.npy, y_train.npy, X_test.npy, y_test.npy")
        return

    # Load data
    X_train, y_train, X_test, y_test = load_training_data(data_dir)

    # Train model
    model = train_model(X_train, y_train, config)

    # Evaluate
    results = evaluate_model(model, X_test, y_test)

    # Save model
    logger.info(f"Saving model to {model_dir}")
    model.save(model_dir)

    # Save config
    import json
    with open(results_dir / "config.json", 'w') as f:
        json.dump(config, f, indent=2)

    # Plot results
    plot_training_history(model, results_dir)
    plot_attention_heatmap(model, X_test, results_dir)

    # Model info
    info = model.get_model_info()
    logger.info(f"\nFinal Model Info:")
    for key, value in info.items():
        logger.info(f"  {key}: {value}")

    logger.info(f"\nTraining complete! Results saved to {results_dir}")


if __name__ == "__main__":
    main()
