"""
Rescale hotspot predictions to show meaningful risk differentiation.

Problem: All 62 hotspots have high ML probability (0.58-0.99) because
they're ALL known flood locations. This makes risk levels meaningless.

Solution: Blend ML probability with historical severity to create
a more informative risk distribution.

Risk = (ML_normalized * 0.4) + (severity_weight * 0.6)

This ensures:
- Extreme historical locations stay high risk
- Moderate historical locations show moderate risk
- ML model still influences the final score
"""

import json
from pathlib import Path
from datetime import datetime
import numpy as np

# Paths
data_dir = Path(__file__).parent.parent / "data"
cache_file = data_dir / "hotspot_predictions_cache.json"
hotspots_file = data_dir / "delhi_waterlogging_hotspots.json"
output_file = data_dir / "hotspot_predictions_cache.json"

# Severity weights (same as original fallback)
SEVERITY_WEIGHTS = {
    "extreme": 0.85,
    "high": 0.65,
    "moderate": 0.45,
    "low": 0.25,
}

def main():
    print("=" * 60)
    print("RESCALING HOTSPOT PREDICTIONS FOR BETTER DIFFERENTIATION")
    print("=" * 60)

    # Load current predictions
    print("\n1. Loading current predictions...")
    with open(cache_file) as f:
        cache = json.load(f)

    # Load hotspots for severity history
    print("2. Loading hotspot severity history...")
    with open(hotspots_file) as f:
        hotspots_json = json.load(f)
    hotspots = {str(h["id"]): h for h in hotspots_json["hotspots"]}

    # Calculate current distribution
    predictions = cache["predictions"]
    raw_probs = [p["base_susceptibility"] for p in predictions.values()]
    print(f"\n   Current distribution:")
    print(f"   Min: {min(raw_probs):.4f}, Max: {max(raw_probs):.4f}, Mean: {np.mean(raw_probs):.4f}")

    # Normalize ML probabilities to 0-1 range (relative to min/max)
    min_prob = min(raw_probs)
    max_prob = max(raw_probs)
    prob_range = max_prob - min_prob

    print(f"\n3. Rescaling predictions...")
    print(f"   Formula: risk = (ML_normalized * 0.4) + (severity * 0.6)")

    rescaled_predictions = {}
    for hotspot_id, pred in predictions.items():
        raw_ml = pred["base_susceptibility"]

        # Normalize ML prediction to 0-1 within the data range
        ml_normalized = (raw_ml - min_prob) / prob_range if prob_range > 0 else 0.5

        # Get historical severity
        hotspot = hotspots.get(hotspot_id, {})
        severity = hotspot.get("severity_history", "moderate")
        severity_weight = SEVERITY_WEIGHTS.get(severity, 0.5)

        # Blend: 40% ML (normalized), 60% severity
        blended_risk = (ml_normalized * 0.4) + (severity_weight * 0.6)

        rescaled_predictions[hotspot_id] = {
            **pred,
            "base_susceptibility": round(blended_risk, 4),
            "raw_ml_probability": raw_ml,
            "severity_history": severity,
        }

    # Calculate new distribution
    new_probs = [p["base_susceptibility"] for p in rescaled_predictions.values()]
    print(f"\n   New distribution:")
    print(f"   Min: {min(new_probs):.4f}, Max: {max(new_probs):.4f}, Mean: {np.mean(new_probs):.4f}")

    # Count by risk level
    levels = {"low": 0, "moderate": 0, "high": 0, "extreme": 0}
    for p in new_probs:
        if p < 0.25:
            levels["low"] += 1
        elif p < 0.50:
            levels["moderate"] += 1
        elif p < 0.75:
            levels["high"] += 1
        else:
            levels["extreme"] += 1

    print(f"\n   Risk distribution:")
    print(f"   Low (0-0.25):      {levels['low']}")
    print(f"   Moderate (0.25-0.5): {levels['moderate']}")
    print(f"   High (0.5-0.75):   {levels['high']}")
    print(f"   Extreme (0.75+):   {levels['extreme']}")

    # Update cache
    cache["predictions"] = rescaled_predictions
    cache["generated_at"] = datetime.now().isoformat()
    cache["rescaled"] = True
    cache["blend_formula"] = "risk = (ML_normalized * 0.4) + (severity * 0.6)"

    # Save
    print(f"\n4. Saving rescaled predictions to {output_file}...")
    with open(output_file, "w") as f:
        json.dump(cache, f, indent=2)

    # Print sample
    print("\n" + "=" * 60)
    print("SAMPLE RESCALED PREDICTIONS:")
    print("=" * 60)
    for hotspot_id in list(rescaled_predictions.keys())[:10]:
        p = rescaled_predictions[hotspot_id]
        risk = p["base_susceptibility"]
        raw_ml = p["raw_ml_probability"]
        sev = p["severity_history"]
        level = "low" if risk < 0.25 else "moderate" if risk < 0.5 else "high" if risk < 0.75 else "extreme"
        print(f"  {p['name'][:25]:25} | ML:{raw_ml:.2f} Sev:{sev:8} → Risk:{risk:.2f} ({level})")

    print("\n" + "=" * 60)
    print("DONE! Predictions rescaled for better differentiation.")
    print("=" * 60)

if __name__ == "__main__":
    main()
