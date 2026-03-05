"""
Train per-city XGBoost model with feature importance for hotspot analysis.

Trains the same XGBoost architecture as Delhi for any supported city.
Outputs:
- Model files in apps/ml-service/models/{city}_xgboost/
- Predictions cache with per-hotspot feature contributions (top_features)
- City-level top predictors (top_city_predictors)

Usage:
    python scripts/train_city_xgboost.py --city bangalore
    python scripts/train_city_xgboost.py --city delhi --regenerate-cache

Prerequisites:
    - Run extract_city_features.py first (or existing training data)
    - pip install xgboost scikit-learn numpy
"""
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
ML_SERVICE_ROOT = PROJECT_ROOT / "apps" / "ml-service"
BACKEND_DATA = PROJECT_ROOT / "apps" / "backend" / "data"

# 18 feature names (must match metadata.json)
FEATURE_NAMES = [
    "elevation", "slope", "tpi", "tri", "twi", "spi",
    "rainfall_24h", "rainfall_3d", "rainfall_7d", "max_daily_7d", "wet_days_7d",
    "impervious_pct", "built_up_pct",
    "sar_vv_mean", "sar_vh_mean", "sar_vv_vh_ratio", "sar_change_mag",
    "is_monsoon",
]

# Human-readable feature labels for frontend display
FEATURE_LABELS = {
    "elevation": "Low elevation area",
    "slope": "Flat terrain (low slope)",
    "tpi": "Topographic depression",
    "tri": "Low terrain roughness",
    "twi": "High wetness index",
    "spi": "Stream power convergence",
    "rainfall_24h": "Recent rainfall (24h)",
    "rainfall_3d": "3-day rainfall accumulation",
    "rainfall_7d": "Weekly rainfall accumulation",
    "max_daily_7d": "Peak daily rainfall (7d)",
    "wet_days_7d": "Consecutive wet days",
    "impervious_pct": "Impervious surface coverage",
    "built_up_pct": "Urban built-up density",
    "sar_vv_mean": "SAR water detection (VV)",
    "sar_vh_mean": "SAR water detection (VH)",
    "sar_vv_vh_ratio": "SAR polarization ratio",
    "sar_change_mag": "SAR change magnitude",
    "is_monsoon": "Monsoon season",
}

# XGBoost hyperparameters (same as Delhi model)
XGBOOST_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "max_depth": 5,
    "learning_rate": 0.1,
    "n_estimators": 100,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
}


def convert_numpy(obj):
    """Recursively convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy(item) for item in obj]
    return obj


def load_training_data(city: str):
    """Load training data from npz file."""
    data_path = ML_SERVICE_ROOT / "data" / f"{city}_hotspot_training_data.npz"

    if not data_path.exists():
        logger.error(f"Training data not found: {data_path}")
        logger.error(f"Run extract_city_features.py --city {city} first.")
        sys.exit(1)

    data = np.load(data_path, allow_pickle=True)
    features = data["features"]
    labels = data["labels"]
    feature_names = list(data["feature_names"])
    coords = data["coords"] if "coords" in data else None

    logger.info(f"Loaded training data from {data_path}")
    logger.info(f"  Features: {features.shape}, Labels: {labels.shape}")
    logger.info(f"  Positive: {int(labels.sum())}, Negative: {int(len(labels) - labels.sum())}")

    return features, labels, feature_names, coords


def train_xgboost(features, labels, feature_names):
    """Train XGBoost with 5-fold cross-validation."""
    try:
        import xgboost as xgb
        from sklearn.model_selection import StratifiedKFold
        from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Install with: pip install xgboost scikit-learn")
        sys.exit(1)

    # Cross-validation
    logger.info("\n5-fold stratified cross-validation...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    model = xgb.XGBClassifier(**XGBOOST_PARAMS)

    cv_scores = {"auc": [], "precision": [], "recall": [], "f1": []}

    for fold, (train_idx, val_idx) in enumerate(cv.split(features, labels)):
        X_train, X_val = features[train_idx], features[val_idx]
        y_train, y_val = labels[train_idx], labels[val_idx]

        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        y_pred_proba = model.predict_proba(X_val)[:, 1]
        y_pred = model.predict(X_val)

        auc = roc_auc_score(y_val, y_pred_proba)
        prec = precision_score(y_val, y_pred, zero_division=0)
        rec = recall_score(y_val, y_pred, zero_division=0)
        f1 = f1_score(y_val, y_pred, zero_division=0)

        cv_scores["auc"].append(auc)
        cv_scores["precision"].append(prec)
        cv_scores["recall"].append(rec)
        cv_scores["f1"].append(f1)

        logger.info(f"  Fold {fold+1}: AUC={auc:.4f} Prec={prec:.4f} Rec={rec:.4f} F1={f1:.4f}")

    cv_results = {
        "auc_mean": float(np.mean(cv_scores["auc"])),
        "auc_std": float(np.std(cv_scores["auc"])),
        "precision_mean": float(np.mean(cv_scores["precision"])),
        "recall_mean": float(np.mean(cv_scores["recall"])),
        "f1_mean": float(np.mean(cv_scores["f1"])),
    }
    logger.info(f"\nCV Mean AUC: {cv_results['auc_mean']:.4f} ± {cv_results['auc_std']:.4f}")

    # Train final model on all data
    logger.info("\nTraining final model on all data...")
    final_model = xgb.XGBClassifier(**XGBOOST_PARAMS)
    final_model.fit(features, labels, verbose=False)

    # Feature importance (gain-based)
    importance = dict(zip(feature_names, final_model.feature_importances_))
    importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    logger.info("\nFeature importance:")
    for name, imp in list(importance.items())[:10]:
        bar = "=" * int(imp * 50)
        logger.info(f"  {name:20s}: {imp:.4f} {bar}")

    return final_model, cv_results, importance


def compute_per_hotspot_contributions(model, features, labels, coords, feature_names, city):
    """
    Compute per-hotspot feature contributions using XGBoost pred_contribs.

    Returns dict mapping hotspot index to top contributing features.
    """
    import xgboost as xgb

    # Get positive sample indices (hotspots)
    positive_mask = labels == 1
    positive_features = features[positive_mask]
    positive_coords = coords[positive_mask] if coords is not None else None

    # Compute feature contributions via pred_contribs
    booster = model.get_booster()
    dmatrix = xgb.DMatrix(positive_features, feature_names=feature_names)
    contribs = booster.predict(dmatrix, pred_contribs=True)

    # contribs shape: (n_samples, n_features + 1) — last column is bias
    feature_contribs = contribs[:, :-1]  # exclude bias

    # Load hotspot metadata for names
    hotspot_names = load_hotspot_names(city)

    per_hotspot = {}
    for i in range(len(positive_features)):
        abs_contribs = np.abs(feature_contribs[i])
        total = abs_contribs.sum()
        if total == 0:
            total = 1.0  # avoid division by zero

        # Top 5 contributing features
        top_indices = np.argsort(abs_contribs)[::-1][:5]
        top_features = []
        for idx in top_indices:
            fname = feature_names[idx]
            contribution = float(abs_contribs[idx] / total)
            top_features.append({
                "feature": fname,
                "contribution": round(contribution, 3),
                "label": FEATURE_LABELS.get(fname, fname),
            })

        hotspot_id = str(i + 1)  # 1-indexed to match existing cache format
        entry = {
            "base_susceptibility": float(model.predict_proba(positive_features[i:i+1])[0, 1]),
            "top_features": top_features,
        }

        # Add name if available
        if hotspot_id in hotspot_names:
            entry["name"] = hotspot_names[hotspot_id]

        # Add coordinates if available
        if positive_coords is not None and i < len(positive_coords):
            entry["lat"] = float(positive_coords[i][0])
            entry["lng"] = float(positive_coords[i][1])

        per_hotspot[hotspot_id] = entry

    return per_hotspot


def load_hotspot_names(city: str) -> dict:
    """Load hotspot names from backend data, keyed by 1-indexed ID."""
    filename = f"{city}_waterlogging_hotspots.json"
    path = BACKEND_DATA / filename

    if not path.exists():
        return {}

    with open(path) as f:
        data = json.load(f)

    names = {}
    items = data if isinstance(data, list) else data.get("features", list(data.values()))

    for i, item in enumerate(items):
        if isinstance(item, dict):
            name = item.get("name") or item.get("properties", {}).get("name", f"Hotspot {i+1}")
            names[str(i + 1)] = name

    return names


def generate_predictions_cache(city, model, cv_results, importance, per_hotspot, feature_names):
    """Generate predictions cache JSON with feature importance."""
    # Top city-level predictors
    top_city_predictors = []
    for fname, imp in list(importance.items())[:5]:
        top_city_predictors.append({
            "feature": fname,
            "importance": round(float(imp), 4),
            "label": FEATURE_LABELS.get(fname, fname),
        })

    cache = {
        "generated_at": datetime.now().isoformat(),
        "model_name": f"{city}_xgboost_v1",
        "n_hotspots": len(per_hotspot),
        "cv_auc": cv_results["auc_mean"],
        "feature_importance": convert_numpy(importance),
        "top_city_predictors": top_city_predictors,
        "predictions": convert_numpy(per_hotspot),
    }

    return cache


def save_model(model, city, cv_results, importance, feature_names):
    """Save XGBoost model and metadata."""
    model_dir = ML_SERVICE_ROOT / "models" / f"{city}_xgboost"
    model_dir.mkdir(parents=True, exist_ok=True)

    # Save model
    model_path = model_dir / "xgboost_model.json"
    model.save_model(str(model_path))
    logger.info(f"Model saved to: {model_path}")

    # Save metadata
    metadata = convert_numpy({
        "model_name": f"{city}_xgboost_v1",
        "feature_names": feature_names,
        "params": XGBOOST_PARAMS,
        "cv_results": cv_results,
        "feature_importance": importance,
        "trained_at": datetime.now().isoformat(),
    })

    metadata_path = model_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Metadata saved to: {metadata_path}")

    return model_dir


def main():
    parser = argparse.ArgumentParser(description="Train per-city XGBoost model")
    parser.add_argument("--city", required=True,
                        choices=["delhi", "bangalore", "yogyakarta", "singapore", "indore"])
    parser.add_argument("--regenerate-cache", action="store_true",
                        help="Only regenerate predictions cache from existing model")
    args = parser.parse_args()

    city = args.city
    logger.info(f"\n{'='*60}")
    logger.info(f"XGBoost Training: {city.upper()}")
    logger.info(f"{'='*60}")

    # Load data
    features, labels, feature_names, coords = load_training_data(city)

    # Train model
    model, cv_results, importance = train_xgboost(features, labels, feature_names)

    # Save model
    model_dir = save_model(model, city, cv_results, importance, feature_names)

    # Compute per-hotspot feature contributions
    logger.info("\nComputing per-hotspot feature contributions...")
    per_hotspot = compute_per_hotspot_contributions(
        model, features, labels, coords, feature_names, city
    )

    # Generate and save predictions cache
    cache = generate_predictions_cache(city, model, cv_results, importance, per_hotspot, feature_names)

    cache_path = ML_SERVICE_ROOT / "data" / f"{city}_predictions_cache.json"
    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)
    logger.info(f"Predictions cache saved to: {cache_path}")

    # Summary
    print(f"\n{'='*60}")
    print(f"TRAINING COMPLETE: {city.upper()}")
    print(f"{'='*60}")
    print(f"CV AUC: {cv_results['auc_mean']:.4f} ± {cv_results['auc_std']:.4f}")
    print(f"Hotspots with feature importance: {len(per_hotspot)}")
    print(f"\nTop city predictors:")
    for p in cache["top_city_predictors"]:
        print(f"  {p['label']:30s} ({p['importance']:.4f})")
    print(f"\nFiles:")
    print(f"  Model:   {model_dir}")
    print(f"  Cache:   {cache_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
