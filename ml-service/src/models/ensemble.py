"""
Ensemble Flood Prediction Model.

Combines ARIMA, Prophet, and LSTM predictions using weighted voting.

NOTE: Heavy ML dependencies (PyTorch, LightGBM, Prophet) are optional.
In production (HuggingFace Spaces), only XGBoost and MobileNet are used.
"""

import numpy as np
from pathlib import Path
import json
import logging
from typing import Dict, List, Optional, Any, Type

from .base import FloodPredictionModel

logger = logging.getLogger(__name__)

# Optional model imports - these require heavy dependencies
# PyTorch models (ConvLSTM, GNN, LSTM)
ConvLSTMFloodModel: Optional[Type] = None
GNNFloodModel: Optional[Type] = None
LSTMFloodModel: Optional[Type] = None

# LightGBM model
LightGBMFloodModel: Optional[Type] = None

# Prophet model
ProphetFloodModel: Optional[Type] = None

# ARIMA model
ARIMAFloodModel: Optional[Type] = None

# Try importing PyTorch-based models
try:
    from .convlstm_model import ConvLSTMFloodModel as _ConvLSTM
    from .gnn_model import GNNFloodModel as _GNN
    from .lstm_model import LSTMFloodModel as _LSTM
    ConvLSTMFloodModel = _ConvLSTM
    GNNFloodModel = _GNN
    LSTMFloodModel = _LSTM
    logger.debug("PyTorch models available")
except ImportError as e:
    logger.info(f"PyTorch models not available (missing torch): {e}")

# Try importing LightGBM model
try:
    from .lightgbm_model import LightGBMFloodModel as _LightGBM
    LightGBMFloodModel = _LightGBM
    logger.debug("LightGBM model available")
except ImportError as e:
    logger.info(f"LightGBM model not available: {e}")

# Try importing Prophet model
try:
    from .prophet_model import ProphetFloodModel as _Prophet
    ProphetFloodModel = _Prophet
    logger.debug("Prophet model available")
except ImportError as e:
    logger.info(f"Prophet model not available: {e}")

# Try importing ARIMA model
try:
    from .arima_model import ARIMAFloodModel as _ARIMA
    ARIMAFloodModel = _ARIMA
    logger.debug("ARIMA model available")
except ImportError as e:
    logger.info(f"ARIMA model not available: {e}")


class EnsembleFloodModel(FloodPredictionModel):
    """
    Ensemble model using weighted voting from multiple models.

    Weights can be:
    - Set manually
    - Learned from historical performance
    - Adapted dynamically based on recent accuracy
    """

    def __init__(
        self,
        models: Optional[List[FloodPredictionModel]] = None,
        weights: Optional[List[float]] = None,
        strategy: str = "weighted_average",
    ):
        """
        Initialize ensemble.

        Args:
            models: List of models to ensemble (optional, can add later)
            weights: Initial weights for each model (must sum to 1)
            strategy: Voting strategy - 'weighted_average', 'voting', 'stacking'
        """
        super().__init__(model_name="Ensemble-Flood")

        self.models = models or []
        self.strategy = strategy

        # Initialize weights
        if weights:
            self.weights = weights
        else:
            n = len(self.models)
            self.weights = [1.0 / n] * n if n > 0 else []

        self._normalize_weights()

        # Performance tracking for adaptive weighting
        self.model_performance: Dict[str, float] = {}
        self._prediction_history: List[Dict] = []

    def add_model(self, model: FloodPredictionModel, weight: float = 1.0) -> None:
        """
        Add a model to the ensemble.

        Args:
            model: FloodPredictionModel instance
            weight: Initial weight for this model
        """
        self.models.append(model)
        self.weights.append(weight)
        self._normalize_weights()
        logger.info(f"Added {model.model_name} to ensemble (weight: {weight:.3f})")

    def remove_model(self, model_name: str) -> bool:
        """Remove a model from the ensemble by name."""
        for i, model in enumerate(self.models):
            if model.model_name == model_name:
                self.models.pop(i)
                self.weights.pop(i)
                self._normalize_weights()
                logger.info(f"Removed {model_name} from ensemble")
                return True
        return False

    def set_weights(self, weights: List[float]) -> None:
        """Set model weights manually."""
        if len(weights) != len(self.models):
            raise ValueError(f"Need {len(self.models)} weights, got {len(weights)}")
        self.weights = weights
        self._normalize_weights()

    def update_weights_from_performance(
        self, performance_scores: Dict[str, float]
    ) -> None:
        """
        Update model weights based on performance scores.

        Args:
            performance_scores: Dict of model_name -> score (higher is better)
        """
        self.model_performance = performance_scores

        new_weights = []
        for model in self.models:
            score = performance_scores.get(model.model_name, 1.0)
            # Minimum weight of 0.05 to keep all models in play
            new_weights.append(max(0.05, score))

        self.weights = new_weights
        self._normalize_weights()

        logger.info(
            f"Updated weights: {[(m.model_name, w) for m, w in zip(self.models, self.weights)]}"
        )

    def _normalize_weights(self) -> None:
        """Normalize weights to sum to 1."""
        total = sum(self.weights)
        if total > 0:
            self.weights = [w / total for w in self.weights]

    def fit(self, X: np.ndarray, y: np.ndarray, **kwargs) -> "EnsembleFloodModel":
        """
        Fit all constituent models.

        Note: Different models may need different data formats.
        Use model-specific kwargs prefixed with model name (e.g., ARIMA-Flood_order=(5,1,0))

        Args:
            X: Feature matrix
            y: Target values
            **kwargs: Model-specific parameters
        """
        for model in self.models:
            # Extract model-specific kwargs
            model_kwargs = {
                k.replace(f"{model.model_name}_", ""): v
                for k, v in kwargs.items()
                if k.startswith(f"{model.model_name}_")
            }

            # Also pass through common kwargs
            for k, v in kwargs.items():
                if not any(k.startswith(f"{m.model_name}_") for m in self.models):
                    model_kwargs[k] = v

            try:
                logger.info(f"Training {model.model_name}...")
                model.fit(X, y, **model_kwargs)
                logger.info(f"✓ {model.model_name} trained successfully")
            except Exception as e:
                logger.error(f"✗ Failed to train {model.model_name}: {e}")
                # Continue training other models

        self._trained = any(m.is_trained for m in self.models)
        return self

    def predict(self, X: np.ndarray, coordinates: Optional[np.ndarray] = None, **kwargs) -> np.ndarray:
        """
        Make predictions using ensemble strategy.

        Args:
            X: Feature matrix - can be 2D (batch, features) or 3D (batch, seq, features)
            coordinates: Optional (n_samples, 2) coordinates for GNN spatial modeling
            **kwargs: Model-specific prediction parameters

        Returns:
            Ensemble predictions
        """
        if not self._trained:
            raise ValueError("No models trained. Call fit() first.")

        predictions = []
        valid_weights = []

        for model, weight in zip(self.models, self.weights):
            if not model.is_trained:
                continue

            try:
                # Extract model-specific kwargs
                model_kwargs = {
                    k.replace(f"{model.model_name}_", ""): v
                    for k, v in kwargs.items()
                    if k.startswith(f"{model.model_name}_")
                }

                # Handle different model input requirements
                if model.model_name == "ConvLSTM-Flood":
                    # ConvLSTM expects 3D input (batch, seq_len, features)
                    if X.ndim == 2:
                        # Create dummy sequence by repeating current state
                        X_seq = np.tile(X.reshape(-1, 1, X.shape[-1]), (1, 30, 1))
                    else:
                        X_seq = X
                    pred = model.predict(X_seq, **model_kwargs)

                elif model.model_name == "GNN-Flood":
                    # GNN expects 2D input + coordinates for graph construction
                    if X.ndim == 3:
                        X_flat = X[:, -1, :]  # Use last timestep
                    else:
                        X_flat = X
                    pred = model.predict(X_flat, coordinates=coordinates, **model_kwargs)

                elif model.model_name in ["LightGBM", "lightgbm"]:
                    # LightGBM expects 2D input (flattened if needed)
                    if X.ndim == 3:
                        X_flat = X[:, -1, :]  # Use last timestep
                    else:
                        X_flat = X
                    pred = model.predict(X_flat, **model_kwargs)

                else:
                    # Legacy models (ARIMA, Prophet, LSTM)
                    pred = model.predict(X, **model_kwargs)

                predictions.append(np.array(pred))
                valid_weights.append(weight)

            except Exception as e:
                logger.warning(f"Prediction failed for {model.model_name}: {e}")

        if not predictions:
            raise ValueError("All model predictions failed")

        # Normalize valid weights
        total_weight = sum(valid_weights)
        valid_weights = [w / total_weight for w in valid_weights]

        # Apply strategy
        if self.strategy == "weighted_average":
            result = np.zeros_like(predictions[0], dtype=float)
            for pred, weight in zip(predictions, valid_weights):
                result += pred * weight
            return result

        elif self.strategy == "voting":
            # Majority voting (for binary classification)
            stacked = np.stack(predictions)
            return np.round(np.mean(stacked, axis=0))

        elif self.strategy == "median":
            # Median of predictions
            stacked = np.stack(predictions)
            return np.median(stacked, axis=0)

        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

    def predict_proba(self, X: np.ndarray, coordinates: Optional[np.ndarray] = None, **kwargs) -> np.ndarray:
        """
        Predict probabilities using weighted average.

        Args:
            X: Feature matrix - can be 2D (batch, features) or 3D (batch, seq, features)
            coordinates: Optional (n_samples, 2) coordinates for GNN spatial modeling
            **kwargs: Model-specific parameters

        Returns:
            Ensemble probability predictions
        """
        if not self._trained:
            raise ValueError("No models trained. Call fit() first.")

        probabilities = []
        valid_weights = []

        for model, weight in zip(self.models, self.weights):
            if not model.is_trained:
                continue

            try:
                model_kwargs = {
                    k.replace(f"{model.model_name}_", ""): v
                    for k, v in kwargs.items()
                    if k.startswith(f"{model.model_name}_")
                }

                # Handle different model input requirements
                if model.model_name == "ConvLSTM-Flood":
                    # ConvLSTM expects 3D input
                    if X.ndim == 2:
                        X_seq = np.tile(X.reshape(-1, 1, X.shape[-1]), (1, 30, 1))
                    else:
                        X_seq = X
                    prob = model.predict_proba(X_seq, **model_kwargs)

                elif model.model_name == "GNN-Flood":
                    # GNN expects 2D input + coordinates
                    if X.ndim == 3:
                        X_flat = X[:, -1, :]
                    else:
                        X_flat = X
                    prob = model.predict_proba(X_flat, coordinates=coordinates, **model_kwargs)

                elif model.model_name in ["LightGBM", "lightgbm"]:
                    # LightGBM expects 2D input
                    if X.ndim == 3:
                        X_flat = X[:, -1, :]
                    else:
                        X_flat = X
                    prob = model.predict_proba(X_flat, **model_kwargs)

                else:
                    # Legacy models
                    prob = model.predict_proba(X, **model_kwargs)

                probabilities.append(np.array(prob))
                valid_weights.append(weight)

            except Exception as e:
                logger.warning(
                    f"Probability prediction failed for {model.model_name}: {e}"
                )

        if not probabilities:
            raise ValueError("All model probability predictions failed")

        # Weighted average of probabilities
        total_weight = sum(valid_weights)
        valid_weights = [w / total_weight for w in valid_weights]

        result = np.zeros_like(probabilities[0], dtype=float)
        for prob, weight in zip(probabilities, valid_weights):
            result += prob * weight

        return result

    def get_model_contributions(self, X: np.ndarray, **kwargs) -> Dict[str, np.ndarray]:
        """
        Get individual model predictions for analysis.

        Args:
            X: Feature matrix

        Returns:
            Dict of model_name -> predictions
        """
        contributions = {}

        for model in self.models:
            if not model.is_trained:
                continue

            try:
                model_kwargs = {
                    k.replace(f"{model.model_name}_", ""): v
                    for k, v in kwargs.items()
                    if k.startswith(f"{model.model_name}_")
                }
                contributions[model.model_name] = model.predict(X, **model_kwargs)
            except Exception as e:
                logger.warning(f"Contribution failed for {model.model_name}: {e}")

        return contributions

    def get_model_info(self) -> Dict:
        """Get ensemble and constituent model information."""
        return {
            "name": self.model_name,
            "trained": self._trained,
            "strategy": self.strategy,
            "n_models": len(self.models),
            "models": [
                {
                    "name": m.model_name,
                    "trained": m.is_trained,
                    "weight": w,
                }
                for m, w in zip(self.models, self.weights)
            ],
            "performance": self.model_performance,
        }

    def save(self, path: Path) -> None:
        """Save ensemble and all constituent models."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save each model
        for i, model in enumerate(self.models):
            model_path = path / f"model_{i}_{model.model_name.replace(' ', '_')}"
            try:
                model.save(model_path)
                logger.info(f"Saved {model.model_name}")
            except Exception as e:
                logger.error(f"Failed to save {model.model_name}: {e}")

        # Save ensemble metadata
        metadata = {
            "model_names": [m.model_name for m in self.models],
            "weights": self.weights,
            "strategy": self.strategy,
            "performance": self.model_performance,
            "trained": self._trained,
        }

        with open(path / "ensemble_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Ensemble saved to {path}")

    def load(self, path: Path) -> "EnsembleFloodModel":
        """Load ensemble from disk."""
        path = Path(path)

        # Load metadata
        with open(path / "ensemble_metadata.json", "r") as f:
            metadata = json.load(f)

        self.weights = metadata["weights"]
        self.strategy = metadata["strategy"]
        self.model_performance = metadata["performance"]
        self._trained = metadata["trained"]

        # Load models
        self.models = []
        for i, name in enumerate(metadata["model_names"]):
            model_path = path / f"model_{i}_{name.replace(' ', '_')}"

            # Instantiate appropriate model class
            if "ConvLSTM" in name:
                model = ConvLSTMFloodModel(input_dim=37)
            elif "GNN" in name or "gnn" in name.lower():
                model = GNNFloodModel(input_dim=37)
            elif "LightGBM" in name or "lightgbm" in name.lower():
                model = LightGBMFloodModel()
            # Legacy models
            elif "ARIMA" in name:
                model = ARIMAFloodModel()
            elif "Prophet" in name:
                model = ProphetFloodModel()
            elif "LSTM" in name and "ConvLSTM" not in name:
                # LSTM needs input_size=37 and embedding_dim=0 (no external embeddings)
                model = LSTMFloodModel(input_size=37, embedding_dim=0)
            else:
                logger.warning(f"Unknown model type: {name}, skipping")
                continue

            try:
                model.load(model_path)
                self.models.append(model)
                logger.info(f"Loaded {name}")
            except Exception as e:
                logger.error(f"Failed to load {name}: {e}")

        logger.info(f"Ensemble loaded from {path}")
        return self


def create_default_ensemble(version: str = "v4") -> EnsembleFloodModel:
    """
    Create a default ensemble model.

    Args:
        version: Ensemble version
                 - 'v4': ConvLSTM (40%) + GNN (30%) + LightGBM (30%) [RECOMMENDED]
                 - 'v3_legacy': ARIMA + Prophet + LSTM + LightGBM (deprecated)

    Returns:
        Configured ensemble model
    """
    ensemble = EnsembleFloodModel(strategy="weighted_average")

    if version == "v4":
        # v4: Modern deep learning architecture (2024+)
        # ConvLSTM: Highest weight - temporal convolutions + attention
        # GNN: High weight - spatial flood propagation patterns
        # LightGBM: Medium weight - fast gradient boosting, handles tabular features
        logger.info("Creating v4 ensemble: ConvLSTM + GNN + LightGBM")

        # Create models
        convlstm = ConvLSTMFloodModel(input_dim=37, conv_filters=64, lstm_units=32)
        gnn = GNNFloodModel(input_dim=37, hidden_dim=64, num_layers=3)
        lightgbm = LightGBMFloodModel()

        # Add to ensemble with exact weights
        ensemble.models = [convlstm, gnn, lightgbm]
        ensemble.weights = [0.40, 0.30, 0.30]

        logger.info(f"  - ConvLSTM: 40%")
        logger.info(f"  - GNN: 30%")
        logger.info(f"  - LightGBM: 30%")

    elif version == "v3_legacy":
        # Legacy v3: Classical + early deep learning (deprecated)
        logger.warning("Using legacy v3 ensemble. Consider upgrading to v4.")
        ensemble.add_model(ARIMAFloodModel(), weight=0.15)
        ensemble.add_model(ProphetFloodModel(), weight=0.25)
        ensemble.add_model(LSTMFloodModel(input_size=37, embedding_dim=0), weight=0.35)
        ensemble.add_model(LightGBMFloodModel(), weight=0.25)

    else:
        raise ValueError(f"Unknown ensemble version: {version}. Use 'v4' or 'v3_legacy'.")

    return ensemble
