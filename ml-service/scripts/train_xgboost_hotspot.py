"""
Train XGBoost Model for Waterlogging Hotspot Prediction.

This script:
1. Loads the generated training data
2. Runs 5-fold stratified cross-validation
3. Trains the final model on all data
4. Calculates SHAP feature importance
5. Saves the model

Usage:
    python scripts/train_xgboost_hotspot.py

Prerequisites:
    - Run generate_hotspot_training_data.py first
    - pip install xgboost shap

Target Metrics (from research):
    - AUC >= 0.85 (minimum acceptable)
    - Precision >= 0.70
    - Recall >= 0.70
"""

import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Validation targets
TARGET_AUC = 0.85
TARGET_PRECISION = 0.70
TARGET_RECALL = 0.70


def load_training_data(data_path: Path):
    """Load training data from npz file."""
    logger.info(f"Loading training data from {data_path}")

    data = np.load(data_path, allow_pickle=True)
    features = data["features"]
    labels = data["labels"]
    feature_names = list(data["feature_names"])

    logger.info(f"  Features shape: {features.shape}")
    logger.info(f"  Labels shape: {labels.shape}")
    logger.info(f"  Positive samples: {int(labels.sum())}")
    logger.info(f"  Negative samples: {int(len(labels) - labels.sum())}")

    return features, labels, feature_names


def main():
    """Train XGBoost hotspot model."""
    print("\n" + "#" * 60)
    print("#  FLOODSAFE XGBOOST HOTSPOT MODEL TRAINING")
    print("#  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("#" * 60)

    # Paths
    data_path = project_root / "data" / "hotspot_training_data.npz"
    model_dir = project_root / "models" / "xgboost_hotspot"

    # Check if training data exists
    if not data_path.exists():
        print(f"\nERROR: Training data not found: {data_path}")
        print("Run generate_hotspot_training_data.py first.")
        sys.exit(1)

    # Load data
    features, labels, feature_names = load_training_data(data_path)

    # Import model (late import to fail fast if XGBoost not installed)
    try:
        from src.models.xgboost_hotspot import XGBoostHotspotModel
    except ImportError as e:
        print(f"\nERROR: {e}")
        print("Install XGBoost with: pip install xgboost")
        sys.exit(1)

    # Create model
    print("\n" + "=" * 60)
    print("INITIALIZING MODEL")
    print("=" * 60)

    model = XGBoostHotspotModel(model_name="xgboost_hotspot_v1")
    print(f"Model: {model.model_name}")
    print(f"Parameters: {json.dumps(model.params, indent=2)}")

    # Cross-validation
    print("\n" + "=" * 60)
    print("5-FOLD CROSS-VALIDATION")
    print("=" * 60)

    cv_results = model.cross_validate(features, labels, n_folds=5)

    # Check if meets targets
    auc_pass = cv_results["auc_mean"] >= TARGET_AUC
    prec_pass = cv_results["precision_mean"] >= TARGET_PRECISION
    rec_pass = cv_results["recall_mean"] >= TARGET_RECALL

    print(f"\nTarget Validation:")
    print(f"  AUC >= {TARGET_AUC}:       {'PASS' if auc_pass else 'FAIL'} ({cv_results['auc_mean']:.4f})")
    print(f"  Precision >= {TARGET_PRECISION}: {'PASS' if prec_pass else 'FAIL'} ({cv_results['precision_mean']:.4f})")
    print(f"  Recall >= {TARGET_RECALL}:    {'PASS' if rec_pass else 'FAIL'} ({cv_results['recall_mean']:.4f})")

    # Train final model on all data
    print("\n" + "=" * 60)
    print("TRAINING FINAL MODEL")
    print("=" * 60)

    model.fit(features, labels, validation_split=0.2, verbose=False)

    # Feature importance
    print("\nFeature Importance (XGBoost):")
    for name, imp in model.feature_importance.items():
        bar = "=" * int(imp * 50)
        print(f"  {name:15}: {imp:.4f} {bar}")

    # SHAP analysis (if available)
    try:
        print("\n" + "=" * 60)
        print("SHAP FEATURE IMPORTANCE")
        print("=" * 60)

        # Use subset for SHAP (faster)
        shap_sample = min(500, len(features))
        indices = np.random.choice(len(features), shap_sample, replace=False)
        shap_values = model.calculate_shap_values(features[indices])

        # Mean absolute SHAP values
        mean_shap = np.abs(shap_values).mean(axis=0)
        sorted_idx = np.argsort(mean_shap)[::-1]

        print("\nSHAP Mean |Value| (most important first):")
        for idx in sorted_idx:
            name = feature_names[idx]
            val = mean_shap[idx]
            bar = "=" * int(val * 20)
            print(f"  {name:15}: {val:.4f} {bar}")

    except ImportError:
        print("\nSHAP not available (pip install shap for feature importance analysis)")
    except Exception as e:
        print(f"\nSHAP analysis failed: {e}")

    # Save model
    print("\n" + "=" * 60)
    print("SAVING MODEL")
    print("=" * 60)

    model_dir.mkdir(parents=True, exist_ok=True)
    model.save(model_dir)

    # Save metrics (convert numpy types to native Python for JSON serialization)
    def convert_numpy(obj):
        """Recursively convert numpy types to Python native types."""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: convert_numpy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy(item) for item in obj]
        return obj

    metrics = convert_numpy({
        "model_name": model.model_name,
        "trained_at": datetime.now().isoformat(),
        "cv_results": cv_results,
        "training_history": model.training_history,
        "feature_importance": model.feature_importance,
        "n_samples": len(labels),
        "n_positive": int(labels.sum()),
        "n_negative": int(len(labels) - labels.sum()),
        "targets_met": {
            "auc": bool(auc_pass),
            "precision": bool(prec_pass),
            "recall": bool(rec_pass),
        }
    })

    metrics_path = model_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Model saved to: {model_dir}")
    print(f"Metrics saved to: {metrics_path}")

    # Final verdict
    print("\n" + "=" * 60)
    all_pass = auc_pass and prec_pass and rec_pass
    if all_pass:
        print("TRAINING COMPLETE: All targets met!")
        print("Model is ready for deployment.")
    else:
        print("TRAINING COMPLETE: Some targets not met.")
        print("Consider:")
        print("  - Adding more training samples")
        print("  - Tuning hyperparameters")
        print("  - Feature engineering")
    print("=" * 60)

    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
