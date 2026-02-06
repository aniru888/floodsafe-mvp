"""
Facebook Prophet-based flood prediction model.

Features:
- Custom monsoon seasonality for India (June-September)
- Support for external regressors (precipitation, soil moisture, etc.)
- Uncertainty intervals for probabilistic predictions
- Multiplicative seasonality mode for flood patterns
"""

from pathlib import Path
from typing import Dict, List, Optional, Union
import logging
import json

import numpy as np
import pandas as pd
from prophet import Prophet
from prophet.serialize import model_to_json, model_from_json

from .base import FloodPredictionModel

logger = logging.getLogger(__name__)


class ProphetFloodModel(FloodPredictionModel):
    """
    Prophet-based flood prediction model with custom seasonality.

    This model uses Facebook Prophet to capture:
    - Yearly seasonality (monsoon patterns)
    - Weekly seasonality (if relevant)
    - Custom monsoon period seasonality (June-September for India)
    - External regressors (precipitation, temperature, etc.)

    Example:
        >>> model = ProphetFloodModel(seasonality_mode='multiplicative')
        >>> model.add_regressor('precipitation')
        >>> model.add_regressor('soil_moisture')
        >>> model.fit(dates, flood_values, regressors_df)
        >>> predictions = model.predict(future_dates, future_regressors_df)
    """

    def __init__(
        self,
        seasonality_mode: str = 'multiplicative',
        yearly_seasonality: bool = True,
        weekly_seasonality: bool = False,
        daily_seasonality: bool = False,
        changepoint_prior_scale: float = 0.05,
        seasonality_prior_scale: float = 10.0,
        interval_width: float = 0.80,
        growth: str = 'linear',
    ):
        """
        Initialize Prophet flood model.

        Args:
            seasonality_mode: 'additive' or 'multiplicative'. Use multiplicative
                            for flood data where seasonal effects scale with trend.
            yearly_seasonality: Enable yearly seasonality (monsoon cycles)
            weekly_seasonality: Enable weekly seasonality (typically False for floods)
            daily_seasonality: Enable daily seasonality (typically False for daily aggregates)
            changepoint_prior_scale: Flexibility of trend (lower = less flexible)
            seasonality_prior_scale: Strength of seasonality (higher = stronger)
            interval_width: Width of uncertainty intervals (0.80 = 80% CI)
            growth: 'linear' or 'logistic' trend
        """
        super().__init__(model_name='Prophet-Flood')

        self.seasonality_mode = seasonality_mode
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self.changepoint_prior_scale = changepoint_prior_scale
        self.seasonality_prior_scale = seasonality_prior_scale
        self.interval_width = interval_width
        self.growth = growth

        # Initialize Prophet model
        self.model: Optional[Prophet] = None
        self._regressors: List[str] = []
        self._flood_threshold: Optional[float] = None

        # Store fit statistics for probability conversion
        self._y_mean: Optional[float] = None
        self._y_std: Optional[float] = None

    def add_regressor(
        self,
        name: str,
        prior_scale: Optional[float] = None,
        standardize: str = 'auto',
        mode: Optional[str] = None
    ) -> "ProphetFloodModel":
        """
        Add an external regressor to the model.

        Must be called before fit(). The regressor data must be provided
        during both training and prediction.

        Args:
            name: Name of the regressor column
            prior_scale: Scale for regressor prior (None = use default)
            standardize: Whether to standardize regressor ('auto', True, False)
            mode: 'additive' or 'multiplicative' (None = use model default)

        Returns:
            self for method chaining

        Example:
            >>> model.add_regressor('precipitation', prior_scale=0.5)
            >>> model.add_regressor('soil_moisture')
        """
        if name not in self._regressors:
            self._regressors.append(name)
            logger.info(f"Added regressor: {name}")
        return self

    def add_monsoon_seasonality(self, fourier_order: int = 5) -> "ProphetFloodModel":
        """
        Add custom seasonality for Indian monsoon period (June-September).

        Args:
            fourier_order: Number of Fourier terms (higher = more flexible)

        Returns:
            self for method chaining
        """
        if self.model is not None:
            self.model.add_seasonality(
                name='monsoon',
                period=365.25,
                fourier_order=fourier_order,
                mode=self.seasonality_mode
            )
            logger.info(f"Added monsoon seasonality with Fourier order {fourier_order}")
        return self

    def _prepare_dataframe(
        self,
        dates: Union[np.ndarray, pd.DatetimeIndex],
        values: Optional[np.ndarray] = None,
        regressors: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Convert input data to Prophet's required format.

        Prophet requires a DataFrame with:
        - 'ds': datetime column
        - 'y': target values (optional for prediction)
        - Additional columns for regressors

        Args:
            dates: Array of timestamps or DatetimeIndex
            values: Target values (None for prediction mode)
            regressors: DataFrame with regressor columns

        Returns:
            DataFrame in Prophet format
        """
        # Create base dataframe
        if isinstance(dates, pd.DatetimeIndex):
            df = pd.DataFrame({'ds': dates})
        else:
            df = pd.DataFrame({'ds': pd.to_datetime(dates)})

        # Add target values if provided (training mode)
        if values is not None:
            df['y'] = values

        # Add regressors
        if regressors is not None:
            if isinstance(regressors, pd.DataFrame):
                for col in self._regressors:
                    if col not in regressors.columns:
                        raise ValueError(f"Regressor '{col}' not found in regressors DataFrame")
                    df[col] = regressors[col].values
            else:
                raise TypeError("regressors must be a pandas DataFrame")

        return df

    def fit(
        self,
        X: Union[np.ndarray, pd.DatetimeIndex],
        y: np.ndarray,
        regressors: Optional[pd.DataFrame] = None,
        flood_threshold: Optional[float] = None,
        add_monsoon: bool = True,
        **kwargs
    ) -> "ProphetFloodModel":
        """
        Train the Prophet model.

        Args:
            X: Either datetime array/index, or feature matrix where first column is dates
            y: Target values (e.g., water levels, flood indicators)
            regressors: DataFrame containing external regressors (must include
                       all columns specified via add_regressor())
            flood_threshold: Threshold value to classify floods for probability
                           estimation (if None, uses mean + 2*std)
            add_monsoon: Whether to add custom monsoon seasonality
            **kwargs: Additional Prophet fit parameters

        Returns:
            self

        Example:
            >>> dates = pd.date_range('2020-01-01', periods=365, freq='D')
            >>> water_levels = np.random.randn(365) + 10
            >>> regressors_df = pd.DataFrame({
            ...     'precipitation': np.random.randn(365),
            ...     'soil_moisture': np.random.randn(365)
            ... })
            >>> model.add_regressor('precipitation')
            >>> model.add_regressor('soil_moisture')
            >>> model.fit(dates, water_levels, regressors=regressors_df)
        """
        try:
            # Extract dates from X if it's a matrix
            if isinstance(X, np.ndarray) and X.ndim == 2:
                dates = X[:, 0]
            else:
                dates = X

            # Store statistics for probability conversion
            self._y_mean = float(np.mean(y))
            self._y_std = float(np.std(y))

            # Set flood threshold
            if flood_threshold is not None:
                self._flood_threshold = flood_threshold
            else:
                # Default: mean + 2 standard deviations
                self._flood_threshold = self._y_mean + 2 * self._y_std

            logger.info(f"Flood threshold set to: {self._flood_threshold:.2f}")

            # Initialize Prophet model
            self.model = Prophet(
                seasonality_mode=self.seasonality_mode,
                yearly_seasonality=self.yearly_seasonality,
                weekly_seasonality=self.weekly_seasonality,
                daily_seasonality=self.daily_seasonality,
                changepoint_prior_scale=self.changepoint_prior_scale,
                seasonality_prior_scale=self.seasonality_prior_scale,
                interval_width=self.interval_width,
                growth=self.growth
            )

            # Add custom monsoon seasonality
            if add_monsoon:
                self.add_monsoon_seasonality()

            # Add regressors to model
            for regressor in self._regressors:
                self.model.add_regressor(regressor)

            # Prepare training data
            train_df = self._prepare_dataframe(dates, y, regressors)

            # Fit model
            logger.info(f"Fitting {self.model_name} with {len(train_df)} samples...")
            self.model.fit(train_df, **kwargs)

            # Mark as trained and store history
            self._trained = True
            self._training_history = {
                'n_samples': len(train_df),
                'date_range': (train_df['ds'].min(), train_df['ds'].max()),
                'y_mean': self._y_mean,
                'y_std': self._y_std,
                'flood_threshold': self._flood_threshold,
                'regressors': self._regressors,
                'seasonality_mode': self.seasonality_mode
            }

            logger.info(f"{self.model_name} training complete")
            return self

        except Exception as e:
            logger.error(f"Error during training: {str(e)}")
            raise

    def predict(
        self,
        X: Union[np.ndarray, pd.DatetimeIndex],
        regressors: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Make predictions for future dates.

        Args:
            X: Future dates (datetime array or DatetimeIndex)
            regressors: DataFrame with future regressor values (required if
                       regressors were used during training)
            **kwargs: Additional prediction parameters

        Returns:
            Array of predicted values (yhat)

        Raises:
            RuntimeError: If model hasn't been trained
            ValueError: If required regressors are missing
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model must be trained before prediction")

        try:
            # Extract dates from X if it's a matrix
            if isinstance(X, np.ndarray) and X.ndim == 2:
                dates = X[:, 0]
            else:
                dates = X

            # Prepare future dataframe
            future_df = self._prepare_dataframe(dates, values=None, regressors=regressors)

            # Make predictions
            forecast = self.model.predict(future_df)

            return forecast['yhat'].values

        except Exception as e:
            logger.error(f"Error during prediction: {str(e)}")
            raise

    def predict_proba(
        self,
        X: Union[np.ndarray, pd.DatetimeIndex],
        regressors: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Predict flood probability using uncertainty intervals.

        Uses Prophet's uncertainty intervals to estimate probability.
        The probability is computed as:
        1. P(flood) = P(yhat_upper > threshold)
        2. Scaled by distance from mean prediction to threshold

        Args:
            X: Future dates
            regressors: Future regressor values
            **kwargs: Additional parameters

        Returns:
            Array of flood probabilities (0-1)

        Raises:
            RuntimeError: If model hasn't been trained
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model must be trained before prediction")

        try:
            # Extract dates
            if isinstance(X, np.ndarray) and X.ndim == 2:
                dates = X[:, 0]
            else:
                dates = X

            # Prepare future dataframe
            future_df = self._prepare_dataframe(dates, values=None, regressors=regressors)

            # Get forecast with uncertainty
            forecast = self.model.predict(future_df)

            yhat = forecast['yhat'].values
            yhat_lower = forecast['yhat_lower'].values
            yhat_upper = forecast['yhat_upper'].values

            # Estimate probability based on uncertainty intervals
            # P(flood) increases as prediction approaches/exceeds threshold
            probabilities = np.zeros(len(yhat))

            for i in range(len(yhat)):
                if yhat[i] >= self._flood_threshold:
                    # Above threshold: high probability
                    # Scale based on how far above threshold
                    excess = (yhat[i] - self._flood_threshold) / self._y_std
                    probabilities[i] = min(0.5 + 0.4 * np.tanh(excess), 0.99)
                else:
                    # Below threshold: check if upper bound exceeds threshold
                    if yhat_upper[i] >= self._flood_threshold:
                        # Upper bound exceeds threshold: moderate probability
                        # Scale based on uncertainty
                        uncertainty = (yhat_upper[i] - yhat_lower[i]) / (2 * self._y_std)
                        distance = (self._flood_threshold - yhat[i]) / self._y_std
                        probabilities[i] = min(0.5 * (1 - distance / uncertainty), 0.5)
                    else:
                        # Entirely below threshold: low probability
                        distance = (self._flood_threshold - yhat_upper[i]) / self._y_std
                        probabilities[i] = max(0.01, 0.1 * np.exp(-distance))

            return np.clip(probabilities, 0.0, 1.0)

        except Exception as e:
            logger.error(f"Error during probability prediction: {str(e)}")
            raise

    def get_forecast_components(
        self,
        X: Union[np.ndarray, pd.DatetimeIndex],
        regressors: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Get detailed forecast breakdown (trend, seasonality, etc.).

        Args:
            X: Future dates
            regressors: Future regressor values

        Returns:
            DataFrame with forecast components
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model must be trained before prediction")

        # Extract dates
        if isinstance(X, np.ndarray) and X.ndim == 2:
            dates = X[:, 0]
        else:
            dates = X

        # Prepare future dataframe
        future_df = self._prepare_dataframe(dates, values=None, regressors=regressors)

        # Get full forecast
        forecast = self.model.predict(future_df)

        return forecast

    def save(self, path: Path) -> None:
        """
        Save model to disk using Prophet's serialization.

        Args:
            path: Directory path to save model (will create if doesn't exist)
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Cannot save untrained model")

        try:
            path = Path(path)
            path.mkdir(parents=True, exist_ok=True)

            # Save Prophet model using serialization
            model_path = path / 'prophet_model.json'
            with open(model_path, 'w') as f:
                f.write(model_to_json(self.model))

            # Save metadata
            metadata = {
                'model_name': self.model_name,
                'regressors': self._regressors,
                'flood_threshold': self._flood_threshold,
                'y_mean': self._y_mean,
                'y_std': self._y_std,
                'training_history': self._training_history,
                'seasonality_mode': self.seasonality_mode,
                'yearly_seasonality': self.yearly_seasonality,
                'weekly_seasonality': self.weekly_seasonality,
                'daily_seasonality': self.daily_seasonality,
                'changepoint_prior_scale': self.changepoint_prior_scale,
                'seasonality_prior_scale': self.seasonality_prior_scale,
                'interval_width': self.interval_width,
                'growth': self.growth
            }

            metadata_path = path / 'metadata.json'
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)

            logger.info(f"Model saved to {path}")

        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
            raise

    def load(self, path: Path) -> "ProphetFloodModel":
        """
        Load model from disk.

        Args:
            path: Directory path containing saved model

        Returns:
            self
        """
        try:
            path = Path(path)

            # Load metadata
            metadata_path = path / 'metadata.json'
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Restore instance variables
            self.model_name = metadata['model_name']
            self._regressors = metadata['regressors']
            self._flood_threshold = metadata['flood_threshold']
            self._y_mean = metadata['y_mean']
            self._y_std = metadata['y_std']
            self._training_history = metadata['training_history']
            self.seasonality_mode = metadata['seasonality_mode']
            self.yearly_seasonality = metadata['yearly_seasonality']
            self.weekly_seasonality = metadata['weekly_seasonality']
            self.daily_seasonality = metadata['daily_seasonality']
            self.changepoint_prior_scale = metadata['changepoint_prior_scale']
            self.seasonality_prior_scale = metadata['seasonality_prior_scale']
            self.interval_width = metadata['interval_width']
            self.growth = metadata['growth']

            # Load Prophet model
            model_path = path / 'prophet_model.json'
            with open(model_path, 'r') as f:
                self.model = model_from_json(f.read())

            self._trained = True
            logger.info(f"Model loaded from {path}")

            return self

        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise

    def get_model_info(self) -> Dict:
        """
        Get extended model information.

        Returns:
            Dictionary with model metadata
        """
        info = super().get_model_info()
        info.update({
            'regressors': self._regressors,
            'flood_threshold': self._flood_threshold,
            'seasonality_mode': self.seasonality_mode,
            'interval_width': self.interval_width
        })
        return info
