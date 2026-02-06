"""
Backtesting framework for flood prediction models.

Implements walk-forward validation and historical performance evaluation.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
import logging

from .metrics import regression_metrics, classification_metrics, flood_specific_metrics

logger = logging.getLogger(__name__)


class WalkForwardValidator:
    """
    Walk-forward validation for time series models.

    Simulates real-world deployment by:
    1. Training on historical data up to time T
    2. Predicting for time T+1 to T+horizon
    3. Moving forward and repeating
    """

    def __init__(
        self,
        train_window_days: int = 365,
        test_window_days: int = 7,
        step_days: int = 7,
        min_train_samples: int = 100,
    ):
        """
        Initialize walk-forward validator.

        Args:
            train_window_days: Number of days for training window
            test_window_days: Number of days to predict ahead
            step_days: Number of days to step forward each iteration
            min_train_samples: Minimum training samples required
        """
        self.train_window_days = train_window_days
        self.test_window_days = test_window_days
        self.step_days = step_days
        self.min_train_samples = min_train_samples

    def validate(
        self,
        model,
        X: np.ndarray,
        y: np.ndarray,
        dates: Optional[np.ndarray] = None,
        embeddings: Optional[np.ndarray] = None,
    ) -> Dict:
        """
        Run walk-forward validation.

        Args:
            model: Model implementing fit() and predict() methods
            X: Feature matrix (n_samples, n_features) or (n_samples, seq_len, n_features)
            y: Target values (n_samples,)
            dates: Optional date array for each sample
            embeddings: Optional spatial embeddings (n_samples, 64)

        Returns:
            Dict with:
                - predictions: All out-of-sample predictions
                - actuals: Corresponding actual values
                - metrics: Aggregated metrics
                - fold_metrics: Per-fold metrics
        """
        n_samples = len(y)

        if n_samples < self.min_train_samples + self.test_window_days:
            raise ValueError(
                f"Not enough samples ({n_samples}) for validation. "
                f"Need at least {self.min_train_samples + self.test_window_days}."
            )

        all_predictions = []
        all_actuals = []
        fold_metrics = []

        # Calculate fold indices
        start_idx = self.min_train_samples
        fold = 0

        while start_idx + self.test_window_days <= n_samples:
            train_end = start_idx
            test_end = min(start_idx + self.test_window_days, n_samples)

            # Get train/test splits
            X_train = X[:train_end]
            y_train = y[:train_end]
            X_test = X[train_end:test_end]
            y_test = y[train_end:test_end]

            emb_train = embeddings[:train_end] if embeddings is not None else None
            emb_test = embeddings[train_end:test_end] if embeddings is not None else None

            try:
                # Fit model
                if embeddings is not None:
                    model.fit(X_train, y_train, embeddings=emb_train)
                    predictions = model.predict(X_test, embeddings=emb_test)
                else:
                    model.fit(X_train, y_train)
                    predictions = model.predict(X_test)

                predictions = np.array(predictions).flatten()

                # Store results
                all_predictions.extend(predictions)
                all_actuals.extend(y_test)

                # Calculate fold metrics
                fold_result = {
                    "fold": fold,
                    "train_samples": len(y_train),
                    "test_samples": len(y_test),
                    **regression_metrics(y_test, predictions),
                    **classification_metrics(y_test, predictions),
                }
                fold_metrics.append(fold_result)

                logger.info(
                    f"Fold {fold}: train={len(y_train)}, test={len(y_test)}, "
                    f"RMSE={fold_result['rmse']:.4f}"
                )

            except Exception as e:
                logger.warning(f"Fold {fold} failed: {e}")

            start_idx += self.step_days
            fold += 1

        # Aggregate results
        all_predictions = np.array(all_predictions)
        all_actuals = np.array(all_actuals)

        aggregated_metrics = {
            **regression_metrics(all_actuals, all_predictions),
            **classification_metrics(all_actuals, all_predictions),
            **flood_specific_metrics(all_actuals, all_predictions),
            "n_folds": len(fold_metrics),
            "total_predictions": len(all_predictions),
        }

        return {
            "predictions": all_predictions,
            "actuals": all_actuals,
            "metrics": aggregated_metrics,
            "fold_metrics": fold_metrics,
        }


class HistoricalBacktester:
    """
    Backtest models against historical flood events.

    Uses known flood events to evaluate model performance
    on detecting actual floods.
    """

    def __init__(self, flood_events: List[Dict]):
        """
        Initialize with known flood events.

        Args:
            flood_events: List of dicts with:
                - date: datetime of flood
                - location: (lat, lng) tuple
                - severity: float (0-1)
                - description: str
        """
        self.flood_events = flood_events

    def evaluate_detection(
        self,
        model,
        feature_extractor,
        lead_time_days: int = 3,
    ) -> Dict:
        """
        Evaluate how well the model would have predicted known floods.

        Args:
            model: Trained prediction model
            feature_extractor: Feature extraction callable
            lead_time_days: How many days before flood to make prediction

        Returns:
            Dict with detection statistics
        """
        results = []

        for event in self.flood_events:
            event_date = event["date"]
            location = event["location"]
            severity = event.get("severity", 1.0)

            # Get prediction for lead_time_days before flood
            prediction_date = event_date - timedelta(days=lead_time_days)

            try:
                # Extract features for prediction date
                features = feature_extractor(location, prediction_date)
                prediction = model.predict_proba(features.reshape(1, -1))[0]

                results.append({
                    "event_date": event_date,
                    "location": location,
                    "actual_severity": severity,
                    "predicted_probability": float(prediction),
                    "detected": prediction >= 0.5,
                    "lead_time_days": lead_time_days,
                })

            except Exception as e:
                logger.warning(f"Failed to evaluate event {event_date}: {e}")
                results.append({
                    "event_date": event_date,
                    "location": location,
                    "actual_severity": severity,
                    "predicted_probability": None,
                    "detected": False,
                    "lead_time_days": lead_time_days,
                    "error": str(e),
                })

        # Calculate statistics
        valid_results = [r for r in results if r["predicted_probability"] is not None]
        detected = [r for r in valid_results if r["detected"]]

        return {
            "total_events": len(self.flood_events),
            "evaluated_events": len(valid_results),
            "detected_events": len(detected),
            "detection_rate": len(detected) / len(valid_results) if valid_results else 0,
            "mean_prediction": np.mean([r["predicted_probability"] for r in valid_results]) if valid_results else 0,
            "results": results,
        }


# Known Delhi flood events for backtesting
DELHI_FLOOD_EVENTS = [
    {
        "date": datetime(2023, 7, 9),
        "location": (28.6139, 77.2090),
        "severity": 0.8,
        "description": "Yamuna crosses danger mark due to heavy monsoon",
    },
    {
        "date": datetime(2023, 7, 13),
        "location": (28.6369, 77.2900),
        "severity": 0.9,
        "description": "Record Yamuna water level at 208.66m",
    },
    {
        "date": datetime(2021, 8, 20),
        "location": (28.5800, 77.0500),
        "severity": 0.7,
        "description": "Najafgarh drain overflow",
    },
    {
        "date": datetime(2019, 8, 18),
        "location": (28.6139, 77.2090),
        "severity": 0.75,
        "description": "Yamuna at 206.60m, evacuation in low-lying areas",
    },
]


def run_baseline_comparison(
    models: Dict[str, object],
    X: np.ndarray,
    y: np.ndarray,
    embeddings: Optional[np.ndarray] = None,
) -> pd.DataFrame:
    """
    Compare multiple models using walk-forward validation.

    Args:
        models: Dict of model_name -> model instance
        X: Feature matrix
        y: Target values
        embeddings: Optional spatial embeddings

    Returns:
        DataFrame with comparison results
    """
    validator = WalkForwardValidator()
    results = []

    for name, model in models.items():
        logger.info(f"Evaluating {name}...")
        try:
            result = validator.validate(model, X, y, embeddings=embeddings)
            metrics = result["metrics"]
            metrics["model"] = name
            results.append(metrics)
        except Exception as e:
            logger.error(f"Failed to evaluate {name}: {e}")

    return pd.DataFrame(results)
