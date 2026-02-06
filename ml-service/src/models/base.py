"""
Abstract base class for all flood prediction models.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from pathlib import Path
import numpy as np
import logging

logger = logging.getLogger(__name__)


class FloodPredictionModel(ABC):
    """
    Base class for flood prediction models.

    All models (ARIMA, Prophet, LSTM) inherit from this class
    and implement the same interface for consistency.
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._trained = False
        self._training_history: Dict = {}

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray, **kwargs) -> "FloodPredictionModel":
        """
        Train the model.

        Args:
            X: Feature matrix of shape (n_samples, n_features) or
               (n_samples, sequence_length, n_features) for sequence models
            y: Target values of shape (n_samples,) or (n_samples, horizon)
            **kwargs: Model-specific training parameters

        Returns:
            self
        """
        pass

    @abstractmethod
    def predict(self, X: np.ndarray, **kwargs) -> np.ndarray:
        """
        Make predictions.

        Args:
            X: Feature matrix
            **kwargs: Model-specific prediction parameters

        Returns:
            Predictions array
        """
        pass

    @abstractmethod
    def predict_proba(self, X: np.ndarray, **kwargs) -> np.ndarray:
        """
        Predict flood probability.

        Args:
            X: Feature matrix
            **kwargs: Model-specific parameters

        Returns:
            Probability array (values between 0-1)
        """
        pass

    @abstractmethod
    def save(self, path: Path) -> None:
        """
        Save model to disk.

        Args:
            path: Directory path to save model
        """
        pass

    @abstractmethod
    def load(self, path: Path) -> "FloodPredictionModel":
        """
        Load model from disk.

        Args:
            path: Directory path containing saved model

        Returns:
            self
        """
        pass

    @property
    def is_trained(self) -> bool:
        """Check if model has been trained."""
        return self._trained

    @property
    def training_history(self) -> Dict:
        """Get training history (loss, metrics, etc.)."""
        return self._training_history

    def get_model_info(self) -> Dict:
        """Return model metadata."""
        return {
            "name": self.model_name,
            "trained": self._trained,
            "type": self.__class__.__name__,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.model_name}', trained={self._trained})"
