"""
Train GNN (Graph Neural Network) model for spatial flood prediction.

Usage:
    python 07_train_gnn.py --data delhi_monsoon_5years.npz --output ../models/gnn_v1/
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import argparse
import logging
from datetime import datetime

from src.models.gnn_model import GNNFloodModel
from src.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_training_data(data_path: Path, test_split: float = 0.2):
    """
    Load training data from NPZ file and split into train/test.

    Expected structure:
    - X: (n_samples, n_features) - feature matrix
    - y: (n_samples,) - continuous risk scores (0-1)
    - dates: (n_samples,) - date strings (optional)
    - rainfall: (n_samples,) - rainfall values (optional)
    """
    logger.info(f"Loading data from {data_path}")
    data = np.load(data_path, allow_pickle=True)

    X = data['X']
    y = data['y']

    # Convert continuous risk scores to binary labels (threshold at 0.2)
    y_binary = (y >= 0.2).astype(np.float32)

    logger.info(f"Loaded {len(X)} samples with {X.shape[1]} features")
    logger.info(f"Risk score range: {y.min():.3f} - {y.max():.3f}")
    logger.info(f"Binary labels: {y_binary.sum():.0f} positive, {(1-y_binary).sum():.0f} negative")

    # Split into train/test
    n_samples = len(X)
    n_test = int(n_samples * test_split)
    n_train = n_samples - n_test

    # Random shuffle
    indices = np.random.permutation(n_samples)
    train_idx = indices[:n_train]
    test_idx = indices[n_train:]

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y_binary[train_idx], y_binary[test_idx]

    logger.info(f"Split: {n_train} train, {n_test} test")
    logger.info(f"  X_train: {X_train.shape}")
    logger.info(f"  y_train: {y_train.shape}")
    logger.info(f"  X_test: {X_test.shape}")
    logger.info(f"  y_test: {y_test.shape}")

    return X_train, y_train, X_test, y_test, None, None


def generate_grid_coordinates(n_samples: int, region: str = "delhi") -> np.ndarray:
    """
    Generate grid coordinates for samples if not available.

    Args:
        n_samples: Number of samples
        region: Region name (for bounds)

    Returns:
        (n_samples, 2) array of (lat, lng)
    """
    from src.core.config import REGIONS

    if region not in REGIONS:
        logger.warning(f"Region '{region}' not found, using Delhi")
        region = "delhi"

    bounds = REGIONS[region]["bounds"]
    lat_min, lng_min, lat_max, lng_max = bounds

    # Generate grid
    grid_size = int(np.ceil(np.sqrt(n_samples)))
    lats = np.linspace(lat_min, lat_max, grid_size)
    lngs = np.linspace(lng_min, lng_max, grid_size)

    lat_grid, lng_grid = np.meshgrid(lats, lngs, indexing='ij')
    coordinates = np.stack([lat_grid.ravel(), lng_grid.ravel()], axis=1)

    # Trim to exact sample count
    coordinates = coordinates[:n_samples]

    logger.info(f"Generated {n_samples} grid coordinates for {region}")
    return coordinates


def train_gnn(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    coordinates_train: np.ndarray,
    coordinates_test: np.ndarray,
    output_dir: Path,
    config: dict
):
    """
    Train GNN model.

    Args:
        X_train, y_train: Training data
        X_test, y_test: Test data
        coordinates_train, coordinates_test: Spatial coordinates
        output_dir: Directory to save model
        config: Training configuration
    """
    logger.info("=" * 60)
    logger.info("Training GNN Model")
    logger.info("=" * 60)

    # Initialize GNN model
    model = GNNFloodModel(
        model_name="GNN-Flood",
        input_dim=config['input_dim'],
        hidden_dim=config['hidden_dim'],
        num_layers=config['num_layers'],
        gnn_type=config['gnn_type'],
        k_neighbors=config['k_neighbors'],
        dropout=config['dropout']
    )

    logger.info(f"Model: {model}")

    # Train
    logger.info(f"Training for {config['epochs']} epochs...")
    model.fit(
        X=X_train,
        y=y_train,
        coordinates=coordinates_train,
        epochs=config['epochs'],
        lr=config['learning_rate'],
        weight_decay=config['weight_decay'],
        validation_split=0.2
    )

    # Evaluate on test set
    logger.info("Evaluating on test set...")
    y_pred_proba = model.predict_proba(X_test, coordinates=coordinates_test)
    y_pred = (y_pred_proba >= 0.5).astype(int)

    # Compute metrics
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    auc = roc_auc_score(y_test, y_pred_proba)

    logger.info("=" * 60)
    logger.info("Test Set Results:")
    logger.info(f"  Accuracy:  {accuracy:.4f}")
    logger.info(f"  Precision: {precision:.4f}")
    logger.info(f"  Recall:    {recall:.4f}")
    logger.info(f"  F1 Score:  {f1:.4f}")
    logger.info(f"  AUC:       {auc:.4f}")
    logger.info("=" * 60)

    # Save model
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save(output_dir)

    # Save metrics
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'config': config,
        'test_accuracy': float(accuracy),
        'test_precision': float(precision),
        'test_recall': float(recall),
        'test_f1': float(f1),
        'test_auc': float(auc),
        'training_samples': len(X_train),
        'test_samples': len(X_test),
    }

    import json
    metrics_path = output_dir / 'metrics.json'
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"Model and metrics saved to {output_dir}")

    return model, metrics


def main():
    parser = argparse.ArgumentParser(description="Train GNN flood prediction model")
    parser.add_argument(
        '--data',
        type=str,
        default='../data/delhi_monsoon_5years.npz',
        help='Path to training data (NPZ file)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='../models/gnn_v1/',
        help='Output directory for model'
    )
    parser.add_argument(
        '--region',
        type=str,
        default='delhi',
        help='Region for coordinate generation (if not in data)'
    )
    parser.add_argument(
        '--input-dim',
        type=int,
        default=37,
        help='Input feature dimension (37 for new feature vector)'
    )
    parser.add_argument(
        '--hidden-dim',
        type=int,
        default=settings.GNN_HIDDEN_DIM,
        help='Hidden layer dimension'
    )
    parser.add_argument(
        '--num-layers',
        type=int,
        default=settings.GNN_NUM_LAYERS,
        help='Number of GNN layers'
    )
    parser.add_argument(
        '--gnn-type',
        type=str,
        default=settings.GNN_TYPE,
        choices=['gcn', 'gat'],
        help='GNN type: gcn or gat'
    )
    parser.add_argument(
        '--k-neighbors',
        type=int,
        default=settings.GNN_K_NEIGHBORS,
        help='Number of nearest neighbors'
    )
    parser.add_argument(
        '--dropout',
        type=float,
        default=settings.GNN_DROPOUT,
        help='Dropout rate'
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=settings.GNN_EPOCHS,
        help='Number of training epochs'
    )
    parser.add_argument(
        '--learning-rate',
        type=float,
        default=settings.GNN_LEARNING_RATE,
        help='Learning rate'
    )
    parser.add_argument(
        '--weight-decay',
        type=float,
        default=settings.GNN_WEIGHT_DECAY,
        help='L2 weight decay'
    )

    args = parser.parse_args()

    # Resolve paths
    data_path = Path(__file__).parent / args.data
    output_dir = Path(__file__).parent / args.output

    if not data_path.exists():
        logger.error(f"Data file not found: {data_path}")
        logger.info("Please run 05b_generate_multiyear_training_data.py first")
        return

    # Load data
    X_train, y_train, X_test, y_test, coords_train, coords_test = load_training_data(data_path)

    # Generate coordinates if not available
    if coords_train is None:
        logger.warning("No training coordinates found, generating grid coordinates")
        coords_train = generate_grid_coordinates(len(X_train), region=args.region)

    if coords_test is None:
        logger.warning("No test coordinates found, generating grid coordinates")
        coords_test = generate_grid_coordinates(len(X_test), region=args.region)

    # Training configuration
    config = {
        'input_dim': args.input_dim,
        'hidden_dim': args.hidden_dim,
        'num_layers': args.num_layers,
        'gnn_type': args.gnn_type,
        'k_neighbors': args.k_neighbors,
        'dropout': args.dropout,
        'epochs': args.epochs,
        'learning_rate': args.learning_rate,
        'weight_decay': args.weight_decay,
    }

    logger.info("Configuration:")
    for key, value in config.items():
        logger.info(f"  {key}: {value}")

    # Train model
    model, metrics = train_gnn(
        X_train, y_train,
        X_test, y_test,
        coords_train, coords_test,
        output_dir,
        config
    )

    logger.info("✓ GNN training complete!")


if __name__ == "__main__":
    main()
