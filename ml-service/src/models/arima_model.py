"""
ARIMA-based flood prediction model.

Uses ARIMA/SARIMA for time series forecasting of water levels,
precipitation, or other flood indicators.
"""

from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import logging

import numpy as np
import joblib
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller

from .base import FloodPredictionModel

logger = logging.getLogger(__name__)


class ARIMAFloodModel(FloodPredictionModel):
    """
    ARIMA-based flood prediction model.

    Implements time series forecasting using ARIMA (AutoRegressive Integrated
    Moving Average) or SARIMA (Seasonal ARIMA) for flood-related variables.

    This model serves as the baseline for comparison with more complex models
    like Prophet and LSTM.

    Attributes:
        order: (p, d, q) tuple for ARIMA parameters
            - p: number of autoregressive terms
            - d: degree of differencing
            - q: number of moving average terms
        seasonal_order: Optional (P, D, Q, s) tuple for seasonal components
            - P, D, Q: seasonal equivalents of p, d, q
            - s: seasonal period (e.g., 12 for monthly data)
        threshold: Water level threshold for flood classification
    """

    def __init__(
        self,
        order: Tuple[int, int, int] = (5, 1, 0),
        seasonal_order: Optional[Tuple[int, int, int, int]] = None,
        threshold: float = 0.5,
    ):
        """
        Initialize ARIMA flood model.

        Args:
            order: ARIMA order (p, d, q). Default (5,1,0) is a good baseline.
            seasonal_order: Optional seasonal ARIMA order (P, D, Q, s).
                Example: (1, 1, 1, 12) for monthly seasonality.
            threshold: Threshold for converting predictions to probabilities.
        """
        super().__init__(model_name='ARIMA-Flood')
        self.order = order
        self.seasonal_order = seasonal_order
        self.threshold = threshold
        self.model = None
        self.fitted_model = None
        self._baseline_mean: Optional[float] = None
        self._baseline_std: Optional[float] = None
        self._y_scale: Optional[float] = None

    def _check_stationarity(self, y: np.ndarray) -> Dict[str, Any]:
        """
        Check if time series is stationary using Augmented Dickey-Fuller test.

        Args:
            y: Time series data

        Returns:
            Dictionary with test results
        """
        try:
            result = adfuller(y, autolag='AIC')
            return {
                'statistic': result[0],
                'pvalue': result[1],
                'usedlag': result[2],
                'nobs': result[3],
                'critical_values': result[4],
                'is_stationary': result[1] < 0.05  # p-value < 0.05 means stationary
            }
        except Exception as e:
            logger.warning(f"Stationarity test failed: {e}")
            return {'is_stationary': None}

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        check_stationarity: bool = True,
        **kwargs
    ) -> "ARIMAFloodModel":
        """
        Train ARIMA model on time series data.

        Args:
            X: Feature matrix (not used for ARIMA, can be None)
            y: Target time series of shape (n_samples,)
            check_stationarity: Whether to run stationarity diagnostics
            **kwargs: Additional parameters passed to ARIMA/SARIMAX

        Returns:
            self

        Raises:
            ValueError: If y is empty or has insufficient data
            RuntimeError: If model fitting fails
        """
        if y is None or len(y) == 0:
            raise ValueError("Target y cannot be empty")

        if len(y) < max(self.order) + 10:
            raise ValueError(
                f"Insufficient data: need at least {max(self.order) + 10} samples, got {len(y)}"
            )

        try:
            # Store baseline statistics
            self._baseline_mean = float(np.mean(y))
            self._baseline_std = float(np.std(y))
            self._y_scale = float(np.max(np.abs(y)))

            # Check stationarity
            if check_stationarity:
                stationarity_result = self._check_stationarity(y)
                self._training_history['stationarity_test'] = stationarity_result

                if stationarity_result.get('is_stationary') is False:
                    logger.warning(
                        f"Time series appears non-stationary (p={stationarity_result['pvalue']:.4f}). "
                        f"Consider increasing differencing order (d={self.order[1]})"
                    )

            # Fit model
            logger.info(f"Fitting {self.model_name} with order={self.order}")

            if self.seasonal_order is not None:
                # Use SARIMAX for seasonal data
                self.model = SARIMAX(
                    y,
                    order=self.order,
                    seasonal_order=self.seasonal_order,
                    **kwargs
                )
                logger.info(f"Using SARIMA with seasonal_order={self.seasonal_order}")
            else:
                # Use standard ARIMA
                self.model = ARIMA(y, order=self.order, **kwargs)

            self.fitted_model = self.model.fit()

            # Store training metrics
            self._training_history.update({
                'aic': float(self.fitted_model.aic),
                'bic': float(self.fitted_model.bic),
                'hqic': float(self.fitted_model.hqic),
                'n_observations': len(y),
                'order': self.order,
                'seasonal_order': self.seasonal_order,
            })

            self._trained = True
            logger.info(
                f"Model trained successfully. AIC={self.fitted_model.aic:.2f}, "
                f"BIC={self.fitted_model.bic:.2f}"
            )

            return self

        except Exception as e:
            logger.error(f"Failed to fit {self.model_name}: {e}")
            raise RuntimeError(f"Model fitting failed: {e}") from e

    def predict(
        self,
        X: Optional[np.ndarray] = None,
        steps: int = 7,
        **kwargs
    ) -> np.ndarray:
        """
        Forecast future values.

        Args:
            X: Not used for ARIMA (can be None)
            steps: Number of steps ahead to forecast
            **kwargs: Additional parameters for forecast

        Returns:
            Array of forecasted values of shape (steps,)

        Raises:
            RuntimeError: If model not trained
        """
        if not self._trained or self.fitted_model is None:
            raise RuntimeError(f"{self.model_name} must be trained before prediction")

        if steps <= 0:
            raise ValueError(f"steps must be positive, got {steps}")

        try:
            # Get forecast
            forecast = self.fitted_model.forecast(steps=steps, **kwargs)

            # Convert to numpy array
            predictions = np.array(forecast)

            logger.debug(f"Generated forecast for {steps} steps ahead")
            return predictions

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise RuntimeError(f"Prediction failed: {e}") from e

    def predict_proba(
        self,
        X: Optional[np.ndarray] = None,
        steps: int = 7,
        **kwargs
    ) -> np.ndarray:
        """
        Predict flood probability based on forecasted values.

        Probability is estimated using:
        1. Point forecast and confidence intervals
        2. Probability that forecast exceeds threshold

        Args:
            X: Not used for ARIMA (can be None)
            steps: Number of steps ahead to forecast
            **kwargs: Additional parameters

        Returns:
            Array of flood probabilities of shape (steps,) with values in [0, 1]

        Raises:
            RuntimeError: If model not trained
        """
        if not self._trained or self.fitted_model is None:
            raise RuntimeError(f"{self.model_name} must be trained before prediction")

        try:
            # Get forecast with prediction intervals
            forecast_result = self.fitted_model.get_forecast(steps=steps)

            # Point forecast
            forecast_mean = forecast_result.predicted_mean.values

            # Confidence intervals (default 95%)
            conf_int = forecast_result.conf_int(alpha=0.05)

            # Calculate probability using normalized forecast
            # Probability increases as forecast approaches/exceeds threshold
            if self._baseline_std is not None and self._baseline_std > 0:
                # Normalize by baseline statistics
                normalized_forecast = (forecast_mean - self._baseline_mean) / self._baseline_std

                # Use sigmoid-like transformation
                # Positive z-scores (above mean) map to higher probabilities
                probabilities = 1 / (1 + np.exp(-normalized_forecast))
            else:
                # Fallback: simple threshold comparison
                probabilities = np.where(
                    forecast_mean > self.threshold,
                    np.clip((forecast_mean - self.threshold) / self.threshold, 0, 1),
                    0.0
                )

            # Clip to [0, 1] range
            probabilities = np.clip(probabilities, 0.0, 1.0)

            logger.debug(f"Generated probability forecast for {steps} steps")
            return probabilities

        except Exception as e:
            logger.error(f"Probability prediction failed: {e}")
            raise RuntimeError(f"Probability prediction failed: {e}") from e

    def save(self, path: Path) -> None:
        """
        Save model to disk using joblib.

        Args:
            path: Directory path to save model files

        Raises:
            RuntimeError: If model not trained
        """
        if not self._trained or self.fitted_model is None:
            raise RuntimeError("Cannot save untrained model")

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        try:
            # Save fitted model and metadata
            model_data = {
                'fitted_model': self.fitted_model,
                'order': self.order,
                'seasonal_order': self.seasonal_order,
                'threshold': self.threshold,
                'baseline_mean': self._baseline_mean,
                'baseline_std': self._baseline_std,
                'y_scale': self._y_scale,
                'training_history': self._training_history,
                'model_name': self.model_name,
            }

            save_path = path / f"{self.model_name.lower()}_model.pkl"
            joblib.dump(model_data, save_path)

            logger.info(f"Model saved to {save_path}")

        except Exception as e:
            logger.error(f"Failed to save model: {e}")
            raise RuntimeError(f"Model save failed: {e}") from e

    def load(self, path: Path) -> "ARIMAFloodModel":
        """
        Load model from disk.

        Args:
            path: Directory path containing saved model

        Returns:
            self

        Raises:
            FileNotFoundError: If model file not found
            RuntimeError: If loading fails
        """
        path = Path(path)
        load_path = path / f"{self.model_name.lower()}_model.pkl"

        if not load_path.exists():
            raise FileNotFoundError(f"Model file not found: {load_path}")

        try:
            model_data = joblib.load(load_path)

            # Restore model state
            self.fitted_model = model_data['fitted_model']
            self.order = model_data['order']
            self.seasonal_order = model_data['seasonal_order']
            self.threshold = model_data['threshold']
            self._baseline_mean = model_data['baseline_mean']
            self._baseline_std = model_data['baseline_std']
            self._y_scale = model_data['y_scale']
            self._training_history = model_data['training_history']
            self._trained = True

            logger.info(f"Model loaded from {load_path}")
            return self

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise RuntimeError(f"Model load failed: {e}") from e

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get detailed model information.

        Returns:
            Dictionary with model metadata and diagnostics
        """
        info = super().get_model_info()
        info.update({
            'order': self.order,
            'seasonal_order': self.seasonal_order,
            'threshold': self.threshold,
            'baseline_mean': self._baseline_mean,
            'baseline_std': self._baseline_std,
        })

        if self._trained and self.fitted_model is not None:
            info.update({
                'aic': float(self.fitted_model.aic),
                'bic': float(self.fitted_model.bic),
                'params': self.fitted_model.params.tolist(),
            })

        return info

    def __repr__(self) -> str:
        seasonal_str = f", seasonal={self.seasonal_order}" if self.seasonal_order else ""
        return (
            f"ARIMAFloodModel(order={self.order}{seasonal_str}, "
            f"trained={self._trained})"
        )
