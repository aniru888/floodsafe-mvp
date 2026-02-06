"""
Evaluation metrics for flood prediction models.

Includes standard metrics (RMSE, F1) and flood-specific metrics
that prioritize safety (minimizing missed floods).
"""

import numpy as np
from typing import Dict, Optional
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Calculate regression metrics for continuous predictions.

    Args:
        y_true: Ground truth values
        y_pred: Predicted values

    Returns:
        Dict with RMSE, MAE, R2, MAPE
    """
    y_true = np.array(y_true).flatten()
    y_pred = np.array(y_pred).flatten()

    # Handle empty arrays
    if len(y_true) == 0:
        return {"rmse": 0.0, "mae": 0.0, "r2": 0.0, "mape": 0.0}

    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred) if len(y_true) > 1 else 0.0

    # MAPE (handle zeros)
    mask = y_true != 0
    if mask.any():
        mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
    else:
        mape = 0.0

    return {
        "rmse": float(rmse),
        "mae": float(mae),
        "r2": float(r2),
        "mape": float(mape),
    }


def classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray] = None,
    threshold: float = 0.5,
) -> Dict[str, float]:
    """
    Calculate classification metrics for flood/no-flood predictions.

    Args:
        y_true: True binary labels (or continuous values to threshold)
        y_pred: Predicted labels (or probabilities to threshold)
        y_prob: Prediction probabilities (for ROC-AUC)
        threshold: Probability threshold for classification

    Returns:
        Dict with accuracy, precision, recall, F1, ROC-AUC, confusion matrix values
    """
    y_true = np.array(y_true).flatten()
    y_pred = np.array(y_pred).flatten()

    # Handle empty arrays
    if len(y_true) == 0:
        return {
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": 0.0,
            "true_negatives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "true_positives": 0,
        }

    # Convert probabilities to binary if needed
    if y_pred.max() <= 1.0 and y_pred.min() >= 0.0 and not np.all(np.isin(y_pred, [0, 1])):
        y_prob = y_pred if y_prob is None else y_prob
        y_pred = (y_pred >= threshold).astype(int)

    # Ensure y_true is binary
    if not np.all(np.isin(y_true, [0, 1])):
        y_true = (y_true >= threshold).astype(int)

    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }

    # ROC-AUC if probabilities available
    if y_prob is not None:
        try:
            # Need both classes present for ROC-AUC
            if len(np.unique(y_true)) > 1:
                metrics["roc_auc"] = float(roc_auc_score(y_true, y_prob))
            else:
                metrics["roc_auc"] = 0.0
        except ValueError:
            metrics["roc_auc"] = 0.0
    else:
        metrics["roc_auc"] = 0.0

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    metrics["true_negatives"] = int(cm[0, 0])
    metrics["false_positives"] = int(cm[0, 1])
    metrics["false_negatives"] = int(cm[1, 0])
    metrics["true_positives"] = int(cm[1, 1])

    return metrics


def flood_specific_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    threshold: float = 0.5,
) -> Dict[str, float]:
    """
    Flood-specific metrics prioritizing safety (minimizing missed floods).

    Args:
        y_true: True labels
        y_pred: Predicted labels or probabilities
        threshold: Classification threshold

    Returns:
        Dict with:
            - critical_safety_ratio: Penalizes false negatives 3x more than false positives
            - flood_detection_rate: True positive rate for floods
            - false_alarm_rate: False positive rate
            - miss_rate: False negative rate (CRITICAL for safety)
    """
    y_true = np.array(y_true).flatten()
    y_pred = np.array(y_pred).flatten()

    # Convert to binary
    y_true = (y_true >= threshold).astype(int)
    y_pred = (y_pred >= threshold).astype(int)

    # Handle empty arrays
    if len(y_true) == 0:
        return {
            "critical_safety_ratio": 0.0,
            "flood_detection_rate": 0.0,
            "false_alarm_rate": 0.0,
            "miss_rate": 0.0,
        }

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm[0, 0], cm[0, 1], cm[1, 0], cm[1, 1]

    # Critical Safety Ratio: penalizes false negatives 3x more than false positives
    # Higher is better (max 1.0)
    # CSR = 1 - weighted_error_rate
    total_samples = tn + fp + fn + tp
    if total_samples > 0:
        weighted_errors = 3 * fn + fp  # FN weighted 3x
        max_weighted = 3 * (tp + fn) + (tn + fp)  # Max possible weighted errors
        csr = 1 - (weighted_errors / max_weighted) if max_weighted > 0 else 0
        csr = max(0, csr)
    else:
        csr = 0.0

    # Flood Detection Rate (Recall/Sensitivity)
    # How many actual floods did we catch?
    fdr = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    # False Alarm Rate (Fall-out)
    # How often did we cry wolf?
    far = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    # Miss Rate (False Negative Rate)
    # How many floods did we miss? CRITICAL for safety
    miss_rate = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    return {
        "critical_safety_ratio": float(csr),
        "flood_detection_rate": float(fdr),
        "false_alarm_rate": float(far),
        "miss_rate": float(miss_rate),
    }


def compare_models(
    y_true: np.ndarray,
    predictions: Dict[str, np.ndarray],
    threshold: float = 0.5,
) -> Dict[str, Dict[str, float]]:
    """
    Compare multiple models on all metrics.

    Args:
        y_true: Ground truth
        predictions: Dict of model_name -> predictions
        threshold: Classification threshold

    Returns:
        Nested dict of model_name -> metric_name -> value
    """
    results = {}

    for model_name, y_pred in predictions.items():
        reg_metrics = regression_metrics(y_true, y_pred)
        cls_metrics = classification_metrics(y_true, y_pred, threshold=threshold)
        flood_metrics = flood_specific_metrics(y_true, y_pred, threshold=threshold)

        results[model_name] = {
            **reg_metrics,
            **cls_metrics,
            **flood_metrics,
        }

    return results


def print_metrics_table(metrics: Dict[str, Dict[str, float]]) -> None:
    """Pretty print model comparison table."""
    if not metrics:
        print("No metrics to display")
        return

    # Get all metric names
    all_metrics = set()
    for model_metrics in metrics.values():
        all_metrics.update(model_metrics.keys())

    # Key metrics to display
    key_metrics = [
        "rmse",
        "f1",
        "recall",
        "precision",
        "roc_auc",
        "critical_safety_ratio",
        "flood_detection_rate",
        "miss_rate",
    ]

    # Print header
    model_names = list(metrics.keys())
    header = f"{'Metric':<25}" + "".join(f"{name:<15}" for name in model_names)
    print(header)
    print("-" * len(header))

    # Print metrics
    for metric in key_metrics:
        if metric in all_metrics:
            row = f"{metric:<25}"
            for model_name in model_names:
                value = metrics[model_name].get(metric, 0)
                if isinstance(value, float):
                    row += f"{value:<15.4f}"
                else:
                    row += f"{value:<15}"
            print(row)
