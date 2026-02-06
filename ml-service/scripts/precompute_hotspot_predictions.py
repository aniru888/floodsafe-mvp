"""
Pre-compute base susceptibility scores for all 62 hotspots.

This script loads the trained XGBoost model and training features,
generates predictions, and saves them to a JSON file for fast API responses.
"""

import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("=" * 60)
    print("PRE-COMPUTING HOTSPOT BASE SUSCEPTIBILITY SCORES")
    print("=" * 60)

    # Paths
    model_dir = project_root / "models" / "xgboost_hotspot"
    data_path = project_root / "data" / "hotspot_training_data.npz"
    metadata_path = project_root / "data" / "hotspot_training_metadata.json"
    hotspots_path = project_root / "data" / "delhi_waterlogging_hotspots.json"
    output_path = project_root / "data" / "hotspot_predictions_cache.json"

    # Load trained model
    print("\n1. Loading trained XGBoost model...")
    try:
        from src.models.xgboost_hotspot import load_trained_model
        model = load_trained_model(model_dir)
        print(f"   Model loaded: {model.model_name}")
        print(f"   Trained: {model.is_trained}")
    except Exception as e:
        print(f"   ERROR: Failed to load model: {e}")
        sys.exit(1)

    # Load training data
    print("\n2. Loading training data...")
    try:
        data = np.load(data_path, allow_pickle=True)
        features = data["features"]
        labels = data["labels"]
        print(f"   Features shape: {features.shape}")
        print(f"   Labels shape: {labels.shape}")
    except Exception as e:
        print(f"   ERROR: Failed to load training data: {e}")
        sys.exit(1)

    # Load metadata
    print("\n3. Loading training metadata...")
    try:
        with open(metadata_path) as f:
            metadata = json.load(f)
        samples = metadata["samples"]
        print(f"   Loaded {len(samples)} sample metadata records")
    except Exception as e:
        print(f"   ERROR: Failed to load metadata: {e}")
        sys.exit(1)

    # Load hotspots JSON
    print("\n4. Loading hotspots data...")
    try:
        with open(hotspots_path) as f:
            hotspots_json = json.load(f)
        # Handle both formats: list or {"metadata": ..., "hotspots": [...]}
        if isinstance(hotspots_json, dict) and "hotspots" in hotspots_json:
            hotspots = hotspots_json["hotspots"]
        else:
            hotspots = hotspots_json
        print(f"   Loaded {len(hotspots)} hotspots")
    except Exception as e:
        print(f"   ERROR: Failed to load hotspots: {e}")
        sys.exit(1)

    # Create mapping from hotspot ID to sample indices
    print("\n5. Mapping samples to hotspots...")
    # The samples list has metadata for each training sample in order
    # samples[i] corresponds to features[i]
    hotspot_samples = defaultdict(list)  # hotspot_id -> list of (sample_idx, features, label)

    for i, sample_meta in enumerate(samples):
        sample_id = sample_meta["sample_id"]
        if sample_meta["label"] == 1:  # Only positive samples (flood locations)
            hotspot_samples[sample_id].append(i)

    print(f"   Found samples for {len(hotspot_samples)} hotspots")

    # Generate predictions for each hotspot
    print("\n6. Generating predictions...")
    predictions_by_id = {}

    for hotspot in hotspots:
        hotspot_id = hotspot["id"]
        sample_indices = hotspot_samples.get(hotspot_id, [])

        if sample_indices:
            # Get features for all samples of this hotspot
            hotspot_features = features[sample_indices]
            # Predict probabilities
            probs = model.predict_proba(hotspot_features)
            # Use the mean probability across all date samples
            base_susceptibility = float(np.mean(probs))
        else:
            # Fallback if no samples found
            severity_map = {"extreme": 0.85, "high": 0.65, "moderate": 0.45, "low": 0.25}
            base_susceptibility = severity_map.get(hotspot.get("severity_history", "moderate"), 0.5)
            print(f"   WARNING: No samples for hotspot {hotspot_id} ({hotspot['name']}), using fallback")

        predictions_by_id[hotspot_id] = {
            "name": hotspot["name"],
            "base_susceptibility": round(base_susceptibility, 4),
            "lat": hotspot["lat"],
            "lng": hotspot["lng"],
            "zone": hotspot.get("zone", "unknown"),
            "n_samples": len(sample_indices),
        }

    # Build predictions cache
    print("\n7. Building predictions cache...")
    predictions_cache = {
        "generated_at": datetime.now().isoformat(),
        "model_name": model.model_name,
        "n_hotspots": len(hotspots),
        "predictions": {str(k): v for k, v in predictions_by_id.items()}
    }

    # Save cache
    print(f"\n8. Saving predictions cache to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(predictions_cache, f, indent=2)

    # Print summary statistics
    all_probs = [v["base_susceptibility"] for v in predictions_by_id.values()]
    print("\n" + "=" * 60)
    print("PREDICTION STATISTICS:")
    print("=" * 60)
    print(f"  Min:    {min(all_probs):.4f}")
    print(f"  Max:    {max(all_probs):.4f}")
    print(f"  Mean:   {np.mean(all_probs):.4f}")
    print(f"  Median: {np.median(all_probs):.4f}")

    # Count by risk level
    levels = {"low": 0, "moderate": 0, "high": 0, "extreme": 0}
    for p in all_probs:
        if p < 0.25:
            levels["low"] += 1
        elif p < 0.50:
            levels["moderate"] += 1
        elif p < 0.75:
            levels["high"] += 1
        else:
            levels["extreme"] += 1

    print("\nRisk Distribution:")
    print(f"  Low (0-0.25):      {levels['low']}")
    print(f"  Moderate (0.25-0.5): {levels['moderate']}")
    print(f"  High (0.5-0.75):   {levels['high']}")
    print(f"  Extreme (0.75+):   {levels['extreme']}")

    # Print sample predictions
    print("\n" + "=" * 60)
    print("SAMPLE PREDICTIONS (first 10):")
    print("=" * 60)
    for hotspot_id, pred_data in list(predictions_by_id.items())[:10]:
        risk = pred_data["base_susceptibility"]
        level = "low" if risk < 0.25 else "moderate" if risk < 0.5 else "high" if risk < 0.75 else "extreme"
        print(f"  {pred_data['name'][:30]:30} | {risk:.4f} ({level})")

    print("\n" + "=" * 60)
    print("DONE! Pre-computed predictions saved.")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
