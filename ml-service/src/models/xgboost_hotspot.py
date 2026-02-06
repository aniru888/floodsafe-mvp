"""
XGBoost Model for Urban Waterlogging Hotspot Prediction.

Research-backed implementation targeting 0.93 AUC based on
Mumbai Flood Susceptibility Study (Taylor & Francis, 2025).

Features:
- 18-dimensional input (terrain, rainfall, land cover, SAR, temporal)
- Binary classification (flood-prone vs. safe)
- SHAP-based feature importance analysis
- 5-fold stratified cross-validation
"""

import json
import pickle
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import (
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    confusion_matrix,
    classification_report,
)

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

from .base import FloodPredictionModel

logger = logging.getLogger(__name__)

# Research-based XGBoost parameters
DEFAULT_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "max_depth": 5,              # Prevent overfitting on small dataset
    "learning_rate": 0.1,
    "n_estimators": 100,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "scale_pos_weight": 3,       # Handle class imbalance (1:3 ratio)
    "random_state": 42,
    "use_label_encoder": False,
    "verbosity": 0,
}

# Feature names for SHAP analysis (18-dimensional)
FEATURE_NAMES = [
    # Terrain (6)
    "elevation",
    "slope",
    "tpi",
    "tri",
    "twi",
    "spi",
    # Precipitation (5)
    "rainfall_24h",
    "rainfall_3d",
    "rainfall_7d",
    "max_daily_7d",
    "wet_days_7d",
    # Land Cover (2)
    "impervious_pct",
    "built_up_pct",
    # SAR (4)
    "sar_vv_mean",
    "sar_vh_mean",
    "sar_vv_vh_ratio",
    "sar_change_mag",
    # Temporal (1)
    "is_monsoon",
]


class XGBoostHotspotModel(FloodPredictionModel):
    """
    XGBoost classifier for waterlogging hotspot prediction.

    This model predicts the susceptibility of a location to waterlogging
    based on terrain, precipitation, land cover, and temporal features.

    Target Performance (from research):
    - AUC: >= 0.85 (conservative) / 0.93+ (optimal)
    - Precision: >= 0.70
    - Recall: >= 0.70
    """

    def __init__(
        self,
        model_name: str = "xgboost_hotspot",
        params: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize XGBoost hotspot model.

        Args:
            model_name: Name identifier for the model
            params: XGBoost parameters (uses research-based defaults if None)
        """
        super().__init__(model_name)

        if not XGBOOST_AVAILABLE:
            raise ImportError(
                "XGBoost is required. Install with: pip install xgboost"
            )

        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.model: Optional[xgb.XGBClassifier] = None
        self.feature_names = FEATURE_NAMES.copy()
        self.cv_results: Optional[Dict] = None
        self.feature_importance: Optional[Dict[str, float]] = None
        self.shap_values: Optional[np.ndarray] = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2,
        early_stopping_rounds: int = 20,
        verbose: bool = True,
        **kwargs,
    ) -> "XGBoostHotspotModel":
        """
        Train the XGBoost model.

        Args:
            X: Feature matrix of shape (n_samples, 18)
            y: Binary labels of shape (n_samples,)
            validation_split: Fraction of data for validation
            early_stopping_rounds: Stop if no improvement after N rounds
            verbose: Print training progress
            **kwargs: Additional XGBoost fit parameters

        Returns:
            self
        """
        if X.shape[1] != len(self.feature_names):
            raise ValueError(
                f"Expected {len(self.feature_names)} features, got {X.shape[1]}"
            )

        # Update scale_pos_weight based on actual class ratio
        n_neg = np.sum(y == 0)
        n_pos = np.sum(y == 1)
        if n_pos > 0:
            self.params["scale_pos_weight"] = n_neg / n_pos
            logger.info(f"Class ratio: {n_neg}:{n_pos}, scale_pos_weight: {self.params['scale_pos_weight']:.2f}")

        # Create model
        self.model = xgb.XGBClassifier(**self.params)

        # Split for validation
        if validation_split > 0:
            from sklearn.model_selection import train_test_split
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=validation_split, stratify=y, random_state=42
            )
            eval_set = [(X_val, y_val)]
        else:
            X_train, y_train = X, y
            eval_set = None

        # Train
        logger.info(f"Training XGBoost on {X_train.shape[0]} samples...")
        self.model.fit(
            X_train,
            y_train,
            eval_set=eval_set,
            verbose=verbose,
            **kwargs,
        )

        self._trained = True

        # Calculate feature importance
        self._calculate_feature_importance()

        # Store training metrics
        if validation_split > 0:
            val_probs = self.model.predict_proba(X_val)[:, 1]
            val_preds = self.model.predict(X_val)
            self._training_history = {
                "val_auc": roc_auc_score(y_val, val_probs),
                "val_precision": precision_score(y_val, val_preds),
                "val_recall": recall_score(y_val, val_preds),
                "val_f1": f1_score(y_val, val_preds),
                "val_accuracy": accuracy_score(y_val, val_preds),
            }
            logger.info(f"Validation AUC: {self._training_history['val_auc']:.4f}")

        return self

    def cross_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        n_folds: int = 5,
    ) -> Dict[str, float]:
        """
        Perform stratified k-fold cross-validation.

        Args:
            X: Feature matrix of shape (n_samples, 18)
            y: Binary labels
            n_folds: Number of CV folds

        Returns:
            Dict with CV metrics (mean and std)
        """
        logger.info(f"Running {n_folds}-fold stratified cross-validation...")

        # Use fresh model for CV
        model = xgb.XGBClassifier(**self.params)

        # Stratified K-Fold
        skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

        # Metrics storage
        aucs = []
        precisions = []
        recalls = []
        f1s = []

        for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # Fit
            model.fit(X_train, y_train, verbose=False)

            # Predict
            val_probs = model.predict_proba(X_val)[:, 1]
            val_preds = model.predict(X_val)

            # Metrics
            auc = roc_auc_score(y_val, val_probs)
            prec = precision_score(y_val, val_preds)
            rec = recall_score(y_val, val_preds)
            f1 = f1_score(y_val, val_preds)

            aucs.append(auc)
            precisions.append(prec)
            recalls.append(rec)
            f1s.append(f1)

            logger.info(
                f"  Fold {fold+1}: AUC={auc:.4f}, Prec={prec:.4f}, Rec={rec:.4f}, F1={f1:.4f}"
            )

        self.cv_results = {
            "auc_mean": np.mean(aucs),
            "auc_std": np.std(aucs),
            "precision_mean": np.mean(precisions),
            "precision_std": np.std(precisions),
            "recall_mean": np.mean(recalls),
            "recall_std": np.std(recalls),
            "f1_mean": np.mean(f1s),
            "f1_std": np.std(f1s),
            "n_folds": n_folds,
            "fold_aucs": aucs,
        }

        logger.info(f"\nCV Results:")
        logger.info(f"  AUC:       {self.cv_results['auc_mean']:.4f} +/- {self.cv_results['auc_std']:.4f}")
        logger.info(f"  Precision: {self.cv_results['precision_mean']:.4f} +/- {self.cv_results['precision_std']:.4f}")
        logger.info(f"  Recall:    {self.cv_results['recall_mean']:.4f} +/- {self.cv_results['recall_std']:.4f}")
        logger.info(f"  F1:        {self.cv_results['f1_mean']:.4f} +/- {self.cv_results['f1_std']:.4f}")

        return self.cv_results

    def predict(self, X: np.ndarray, **kwargs) -> np.ndarray:
        """
        Predict binary class labels.

        Args:
            X: Feature matrix of shape (n_samples, 10)

        Returns:
            Binary predictions (0 or 1)
        """
        if not self._trained or self.model is None:
            raise RuntimeError("Model must be trained before prediction")

        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray, **kwargs) -> np.ndarray:
        """
        Predict flood susceptibility probability.

        Args:
            X: Feature matrix of shape (n_samples, 10)

        Returns:
            Probability of positive class (flood-prone)
        """
        if not self._trained or self.model is None:
            raise RuntimeError("Model must be trained before prediction")

        return self.model.predict_proba(X)[:, 1]

    def _calculate_feature_importance(self) -> None:
        """Calculate feature importance from trained model."""
        if self.model is None:
            return

        importance = self.model.feature_importances_
        self.feature_importance = {
            name: float(imp)
            for name, imp in zip(self.feature_names, importance)
        }

        # Sort by importance
        self.feature_importance = dict(
            sorted(self.feature_importance.items(), key=lambda x: -x[1])
        )

        logger.info("Feature Importance (XGBoost gain):")
        for name, imp in self.feature_importance.items():
            logger.info(f"  {name:15}: {imp:.4f}")

    def calculate_shap_values(self, X: np.ndarray) -> np.ndarray:
        """
        Calculate SHAP values for feature importance analysis.

        Args:
            X: Feature matrix for SHAP analysis

        Returns:
            SHAP values array
        """
        if not SHAP_AVAILABLE:
            raise ImportError("SHAP is required. Install with: pip install shap")

        if not self._trained or self.model is None:
            raise RuntimeError("Model must be trained before SHAP analysis")

        logger.info("Calculating SHAP values...")
        explainer = shap.TreeExplainer(self.model)
        self.shap_values = explainer.shap_values(X)

        # Log mean absolute SHAP values
        mean_abs_shap = np.abs(self.shap_values).mean(axis=0)
        logger.info("Mean |SHAP| values:")
        for name, val in sorted(
            zip(self.feature_names, mean_abs_shap), key=lambda x: -x[1]
        ):
            logger.info(f"  {name:15}: {val:.4f}")

        return self.shap_values

    def save(self, path: Path) -> None:
        """
        Save model to disk.

        Args:
            path: Directory path to save model
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save XGBoost model
        model_file = path / "xgboost_model.json"
        self.model.save_model(str(model_file))

        # Save metadata
        metadata = {
            "model_name": self.model_name,
            "feature_names": self.feature_names,
            "params": self.params,
            "cv_results": self.cv_results,
            "feature_importance": self.feature_importance,
            "training_history": self._training_history,
            "trained": self._trained,
        }

        metadata_file = path / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Model saved to {path}")

    def load(self, path: Path) -> "XGBoostHotspotModel":
        """
        Load model from disk.

        Args:
            path: Directory path containing saved model

        Returns:
            self
        """
        path = Path(path)

        # Load XGBoost model
        model_file = path / "xgboost_model.json"
        self.model = xgb.XGBClassifier()
        self.model.load_model(str(model_file))

        # Load metadata
        metadata_file = path / "metadata.json"
        with open(metadata_file) as f:
            metadata = json.load(f)

        self.model_name = metadata["model_name"]
        self.feature_names = metadata["feature_names"]
        self.params = metadata["params"]
        self.cv_results = metadata.get("cv_results")
        self.feature_importance = metadata.get("feature_importance")
        self._training_history = metadata.get("training_history", {})
        self._trained = metadata["trained"]

        logger.info(f"Model loaded from {path}")
        return self

    def get_model_info(self) -> Dict:
        """Return comprehensive model metadata."""
        info = super().get_model_info()
        info.update({
            "params": self.params,
            "cv_results": self.cv_results,
            "feature_importance": self.feature_importance,
            "feature_names": self.feature_names,
        })
        return info


def get_risk_level(probability: float) -> Tuple[str, str]:
    """
    Convert probability to risk level and color.

    Args:
        probability: Flood susceptibility probability (0-1)

    Returns:
        Tuple of (risk_level, color_hex)
    """
    if probability < 0.25:
        return "low", "#22c55e"  # green-500
    elif probability < 0.50:
        return "moderate", "#eab308"  # yellow-500
    elif probability < 0.75:
        return "high", "#f97316"  # orange-500
    else:
        return "extreme", "#ef4444"  # red-500


# Default instance (lazy loaded)
_model_instance: Optional[XGBoostHotspotModel] = None


def get_model() -> XGBoostHotspotModel:
    """Get or create the default model instance."""
    global _model_instance
    if _model_instance is None:
        _model_instance = XGBoostHotspotModel()
    return _model_instance


def load_trained_model(model_path: Path) -> XGBoostHotspotModel:
    """Load a trained model from disk."""
    model = XGBoostHotspotModel()
    model.load(model_path)
    return model
