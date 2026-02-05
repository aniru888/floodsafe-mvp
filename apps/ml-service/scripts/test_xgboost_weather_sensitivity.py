"""
XGBoost Weather Sensitivity Test.

Tests whether the model's predictions CHANGE based on weather features
for the SAME hotspot location across different dates.

Purpose: Verify if model calculates dynamic risk (responds to weather)
         or just memorizes "this is a hotspot" (ignores weather)

Usage:
    cd apps/ml-service
    python scripts/test_xgboost_weather_sensitivity.py

Expected Results:
    - Weather-sensitive: Variance > 0.1 per location, correlation with rainfall
    - Just memorizing: Variance < 0.01, constant predictions regardless of weather
"""

import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from xgboost import XGBClassifier
from scipy import stats


def load_model_and_data() -> Tuple[XGBClassifier, np.ndarray, np.ndarray, List[Dict]]:
    """Load trained XGBoost model and training data."""
    # Load model
    model_path = project_root / "models" / "xgboost_hotspot" / "xgboost_model.json"
    model = XGBClassifier()
    model.load_model(str(model_path))

    # Load training data
    data_file = project_root / "data" / "hotspot_training_data.npz"
    metadata_file = project_root / "data" / "hotspot_training_metadata.json"

    data = np.load(data_file, allow_pickle=True)
    X = data["features"]
    y = data["labels"]

    with open(metadata_file) as f:
        meta = json.load(f)

    samples = meta["samples"]

    return model, X, y, samples


def analyze_weather_sensitivity(
    model: XGBClassifier,
    X: np.ndarray,
    y: np.ndarray,
    samples: List[Dict]
) -> Dict:
    """
    Analyze if model predictions vary with weather for same location.
    """
    print("\n" + "=" * 60)
    print("WEATHER SENSITIVITY ANALYSIS")
    print("=" * 60)

    # Get predictions for all samples
    predictions = model.predict_proba(X)[:, 1]

    # Feature names for reference
    feature_names = [
        "elevation", "slope", "tpi", "tri", "twi", "spi",
        "rainfall_24h", "rainfall_3d", "rainfall_7d", "max_daily_7d", "wet_days_7d",
        "impervious_pct", "built_up_pct",
        "sar_vv_mean", "sar_vh_mean", "sar_vv_vh_ratio", "sar_change_mag",
        "is_monsoon"
    ]

    # Weather feature indices
    weather_indices = {
        "rainfall_24h": 6,
        "rainfall_3d": 7,
        "rainfall_7d": 8,
        "max_daily_7d": 9,
        "wet_days_7d": 10,
        "sar_vv_mean": 13,
        "sar_vh_mean": 14,
        "sar_change_mag": 16,
    }

    # Terrain feature indices (should be constant per location)
    terrain_indices = {
        "elevation": 0,
        "slope": 1,
        "tpi": 2,
        "tri": 3,
        "twi": 4,
        "spi": 5,
    }

    # Group samples by location
    location_groups = defaultdict(list)
    for i, sample in enumerate(samples):
        sample_id = sample["sample_id"]
        location_groups[sample_id].append({
            "index": i,
            "date": sample["date"],
            "label": sample["label"],
            "prediction": predictions[i],
            "features": X[i],
        })

    # Analyze variance per location
    print("\n1. PREDICTION VARIANCE PER LOCATION")
    print("-" * 40)

    variances = []
    prediction_ranges = []
    location_details = []

    for loc_id, loc_samples in location_groups.items():
        if len(loc_samples) > 1:
            preds = [s["prediction"] for s in loc_samples]
            var = np.var(preds)
            pred_range = max(preds) - min(preds)
            variances.append(var)
            prediction_ranges.append(pred_range)

            location_details.append({
                "location_id": loc_id,
                "n_samples": len(loc_samples),
                "predictions": preds,
                "variance": var,
                "range": pred_range,
                "min_pred": min(preds),
                "max_pred": max(preds),
            })

    avg_variance = np.mean(variances)
    avg_range = np.mean(prediction_ranges)
    max_variance = np.max(variances)
    max_range = np.max(prediction_ranges)

    print(f"  Locations with multiple samples: {len(variances)}")
    print(f"  Average prediction variance: {avg_variance:.6f}")
    print(f"  Max prediction variance: {max_variance:.6f}")
    print(f"  Average prediction range: {avg_range:.4f}")
    print(f"  Max prediction range: {max_range:.4f}")

    # Show top 5 most variable locations
    sorted_locs = sorted(location_details, key=lambda x: x["variance"], reverse=True)
    print(f"\n  Top 5 most variable locations:")
    for loc in sorted_locs[:5]:
        print(f"    Loc {loc['location_id']}: var={loc['variance']:.4f}, "
              f"range={loc['range']:.4f}, preds={[f'{p:.3f}' for p in loc['predictions']]}")

    # Analyze hotspots vs negatives separately
    print("\n2. HOTSPOTS vs NEGATIVE LOCATIONS")
    print("-" * 40)

    hotspot_variances = []
    negative_variances = []

    for loc_id, loc_samples in location_groups.items():
        if len(loc_samples) > 1:
            preds = [s["prediction"] for s in loc_samples]
            var = np.var(preds)
            label = loc_samples[0]["label"]

            if label == 1:
                hotspot_variances.append(var)
            else:
                negative_variances.append(var)

    print(f"  Hotspots: avg variance = {np.mean(hotspot_variances):.6f} (n={len(hotspot_variances)})")
    print(f"  Negatives: avg variance = {np.mean(negative_variances):.6f} (n={len(negative_variances)})")

    # Analyze weather feature variance
    print("\n3. WEATHER FEATURE VARIANCE PER LOCATION")
    print("-" * 40)

    weather_variances = {}
    for feat_name, feat_idx in weather_indices.items():
        feat_vars = []
        for loc_id, loc_samples in location_groups.items():
            if len(loc_samples) > 1:
                feat_values = [s["features"][feat_idx] for s in loc_samples]
                feat_vars.append(np.var(feat_values))
        weather_variances[feat_name] = {
            "avg_variance": np.mean(feat_vars),
            "max_variance": np.max(feat_vars),
        }
        print(f"  {feat_name:15}: avg_var={np.mean(feat_vars):.4f}, max_var={np.max(feat_vars):.4f}")

    # Analyze terrain feature variance (should be ~0)
    print("\n4. TERRAIN FEATURE VARIANCE PER LOCATION (Should be ~0)")
    print("-" * 40)

    terrain_variances = {}
    for feat_name, feat_idx in terrain_indices.items():
        feat_vars = []
        for loc_id, loc_samples in location_groups.items():
            if len(loc_samples) > 1:
                feat_values = [s["features"][feat_idx] for s in loc_samples]
                feat_vars.append(np.var(feat_values))
        terrain_variances[feat_name] = np.mean(feat_vars)
        print(f"  {feat_name:15}: avg_var={np.mean(feat_vars):.6f}")

    # Correlation analysis: Do weather features correlate with predictions?
    print("\n5. WEATHER FEATURE - PREDICTION CORRELATION")
    print("-" * 40)

    correlations = {}
    for feat_name, feat_idx in weather_indices.items():
        feat_values = X[:, feat_idx]
        corr, p_value = stats.pearsonr(feat_values, predictions)
        correlations[feat_name] = {
            "correlation": corr,
            "p_value": p_value,
            "significant": p_value < 0.05,
        }
        sig_marker = "*" if p_value < 0.05 else ""
        print(f"  {feat_name:15}: r={corr:+.4f}, p={p_value:.4f} {sig_marker}")

    # VERDICT
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)

    weather_sensitive = avg_variance > 0.01 or avg_range > 0.05
    significant_correlations = sum(1 for c in correlations.values() if c["significant"])

    if weather_sensitive:
        print("\n  [PASS] Model shows SOME weather sensitivity")
        print(f"    - Average prediction variance: {avg_variance:.6f}")
        print(f"    - Average prediction range: {avg_range:.4f}")
        print(f"    - Significant weather correlations: {significant_correlations}/8")
    else:
        print("\n  [FAIL] Model shows NO weather sensitivity")
        print(f"    - Average prediction variance: {avg_variance:.6f} (< 0.01 threshold)")
        print(f"    - Predictions are nearly constant regardless of weather")

    # Strong vs weak sensitivity
    if avg_range > 0.1:
        sensitivity_level = "STRONG"
        print(f"\n  Sensitivity Level: STRONG (range > 0.1)")
    elif avg_range > 0.05:
        sensitivity_level = "MODERATE"
        print(f"\n  Sensitivity Level: MODERATE (range 0.05-0.1)")
    elif avg_range > 0.01:
        sensitivity_level = "WEAK"
        print(f"\n  Sensitivity Level: WEAK (range 0.01-0.05)")
    else:
        sensitivity_level = "NONE"
        print(f"\n  Sensitivity Level: NONE (range < 0.01)")

    # Interpretation
    print("\n  INTERPRETATION:")
    if sensitivity_level in ["STRONG", "MODERATE"]:
        print("    -> Model DOES respond to weather changes for known hotspots")
        print("    -> Works for PURPOSE 1: Dynamic risk at known locations")
        print("    -> Still FAILS PURPOSE 2: Generalizing to new locations (AUC 0.71)")
    elif sensitivity_level == "WEAK":
        print("    -> Model has WEAK weather response")
        print("    -> Weather features have minimal impact on predictions")
        print("    -> Primarily memorizing location terrain patterns")
    else:
        print("    -> Model IGNORES weather features entirely")
        print("    -> Just memorizing 'this is a hotspot'")
        print("    -> Not useful for dynamic risk calculation")

    # Summary results
    results = {
        "timestamp": datetime.now().isoformat(),
        "prediction_variance": {
            "avg": avg_variance,
            "max": max_variance,
        },
        "prediction_range": {
            "avg": avg_range,
            "max": max_range,
        },
        "hotspot_variance_avg": np.mean(hotspot_variances),
        "negative_variance_avg": np.mean(negative_variances),
        "weather_correlations": correlations,
        "significant_correlations": significant_correlations,
        "weather_feature_variances": weather_variances,
        "terrain_feature_variances": terrain_variances,
        "weather_sensitive": weather_sensitive,
        "sensitivity_level": sensitivity_level,
        "verdict": {
            "purpose_1_works": sensitivity_level in ["STRONG", "MODERATE"],
            "purpose_2_works": False,  # Already tested - AUC 0.71
        }
    }

    return results


def main():
    """Run weather sensitivity test."""
    print("\n" + "#" * 60)
    print("#  XGBOOST WEATHER SENSITIVITY TEST")
    print("#  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("#" * 60)

    # Load model and data
    print("\nLoading model and training data...")
    model, X, y, samples = load_model_and_data()

    print(f"  Model loaded from: models/xgboost_hotspot/xgboost_model.json")
    print(f"  Samples: {len(samples)}")
    print(f"  Features: {X.shape[1]}")

    # Run analysis
    results = analyze_weather_sensitivity(model, X, y, samples)

    # Save results
    output_file = project_root / "xgboost_weather_sensitivity_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n  Results saved to: {output_file}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    results = main()
