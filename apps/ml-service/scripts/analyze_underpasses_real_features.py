"""
Analyze Delhi Underpasses with XGBoost Model - REAL FEATURES VERSION.

This script uses HotspotFeatureExtractor to extract REAL features from:
- CHIRPS (rainfall) via GEE - Same as training data
- Sentinel-1 SAR via GEE - Same as training data
- SRTM DEM via GEE - Same as training data
- WorldCover via GEE - Same as training data

IMPORTANT: This replaces the broken analyze_underpasses_xgboost.py which used
placeholder values OUTSIDE the training data distribution:
- rainfall_24h: 50mm (training range: 0-12.54mm) - 4x too high!
- rainfall_3d: 120mm (training range: 0-19.85mm) - 6x too high!
- rainfall_7d: 250mm (training range: 17-122mm) - 2x too high!

Usage:
    cd apps/ml-service
    python scripts/analyze_underpasses_real_features.py
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from xgboost import XGBClassifier
from src.features.hotspot_features import HotspotFeatureExtractor, FEATURE_NAMES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Monsoon dates matching training data
SAMPLE_DATES = [
    datetime(2023, 7, 15),  # Monsoon 2023
    datetime(2023, 8, 10),  # Monsoon 2023
    datetime(2022, 7, 20),  # Monsoon 2022
]


def load_xgboost_model() -> XGBClassifier:
    """Load trained XGBoost model."""
    model_path = project_root / "models" / "xgboost_hotspot" / "xgboost_model.json"
    model = XGBClassifier()
    model.load_model(str(model_path))
    return model


def analyze_underpasses_real(
    max_samples: int = 10,
    reference_date: datetime = None,
) -> Dict:
    """
    Analyze underpasses with XGBoost using REAL features.

    Args:
        max_samples: Maximum number of underpasses to analyze
        reference_date: Date for feature extraction (default: 2023-07-15)

    Returns:
        Dict with analysis results
    """
    if reference_date is None:
        reference_date = SAMPLE_DATES[0]  # Default: 2023-07-15

    print("\n" + "=" * 70)
    print("UNDERPASS ANALYSIS WITH XGBOOST - REAL FEATURES")
    print("=" * 70)
    print(f"Reference Date: {reference_date.date()}")
    print(f"Data Sources: CHIRPS, Sentinel-1, SRTM, WorldCover (same as training)")
    print("=" * 70)

    # Load underpasses
    underpasses_file = project_root / "data" / "delhi_underpasses_osm.json"
    with open(underpasses_file) as f:
        data = json.load(f)

    candidates = data.get("new_candidates", [])
    print(f"\nLoaded {len(candidates)} new underpass candidates")

    # Prioritize named underpasses (more likely to be significant)
    named = [c for c in candidates if c.get("name") and not c["name"].startswith("Underpass_")]
    unnamed = [c for c in candidates if not c.get("name") or c["name"].startswith("Underpass_")]

    # Sample: prioritize named, then add unnamed
    sample = named[:max_samples]
    if len(sample) < max_samples:
        sample.extend(unnamed[:max_samples - len(sample)])

    print(f"Analyzing {len(sample)} underpasses ({len(named)} named)")

    # Load model
    print("\nLoading XGBoost model...")
    model = load_xgboost_model()

    # Initialize feature extractor (uses REAL data sources)
    print("Initializing HotspotFeatureExtractor (REAL data sources)...")
    extractor = HotspotFeatureExtractor(
        lazy_load=False,  # Load fetchers immediately
        use_sar=True,     # Include SAR features
        use_terrain_indices=True  # Include TPI, TRI, TWI, SPI
    )

    # Process each underpass
    results = []
    failed = []

    for i, up in enumerate(sample):
        name = up.get("name", f"Underpass_{up['osm_id']}")
        lat, lng = up["lat"], up["lng"]

        if len(name) > 35:
            display_name = name[:32] + "..."
        else:
            display_name = name

        print(f"\n[{i+1}/{len(sample)}] {display_name}")
        print(f"  Location: ({lat:.4f}, {lng:.4f})")

        # Extract REAL features using HotspotFeatureExtractor
        try:
            features = extractor.extract_features_for_hotspot(
                lat=lat,
                lng=lng,
                reference_date=reference_date,
                buffer_km=0.3
            )

            # Log key feature values to verify they're in training range
            print(f"  Features (REAL from GEE):")
            print(f"    rainfall_24h: {features[6]:.1f}mm (training range: 0-12.54mm)")
            print(f"    rainfall_3d:  {features[7]:.1f}mm (training range: 0-19.85mm)")
            print(f"    rainfall_7d:  {features[8]:.1f}mm (training range: 17-122mm)")
            print(f"    SAR VV:       {features[13]:.1f}dB (training range: -17.74 to 1.34)")
            print(f"    elevation:    {features[0]:.0f}m")
            print(f"    impervious:   {features[11]:.1f}%")

            # Predict
            features_2d = features.reshape(1, -1)
            prob = model.predict_proba(features_2d)[0, 1]

            # Add underpass bonus (infrastructure context)
            underpass_bonus = 0.15
            adjusted_prob = min(1.0, prob + underpass_bonus)

            risk_level = (
                "EXTREME" if adjusted_prob >= 0.7 else
                "HIGH" if adjusted_prob >= 0.5 else
                "MODERATE" if adjusted_prob >= 0.3 else
                "LOW"
            )

            print(f"  XGBoost prob: {prob:.3f}")
            print(f"  Adjusted (+{underpass_bonus} underpass bonus): {adjusted_prob:.3f} [{risk_level}]")

            # Store all features for analysis
            feature_dict = {name: float(features[i]) for i, name in enumerate(FEATURE_NAMES)}

            results.append({
                "osm_id": up["osm_id"],
                "name": up.get("name", f"Underpass_{up['osm_id']}"),
                "lat": lat,
                "lng": lng,
                "highway_type": up.get("highway_type", "unknown"),
                "reference_date": reference_date.isoformat(),
                "xgboost_prob": float(prob),
                "underpass_bonus": underpass_bonus,
                "adjusted_prob": float(adjusted_prob),
                "risk_level": risk_level,
                "features": feature_dict,
                "feature_validation": {
                    "rainfall_24h_in_range": bool(0 <= features[6] <= 15),  # Allow slight buffer
                    "rainfall_3d_in_range": bool(0 <= features[7] <= 25),
                    "rainfall_7d_in_range": bool(10 <= features[8] <= 150),
                    "sar_vv_in_range": bool(-20 <= features[13] <= 5),
                }
            })

        except Exception as e:
            logger.warning(f"Failed to extract features for {name}: {e}")
            failed.append({
                "osm_id": up["osm_id"],
                "name": name,
                "lat": lat,
                "lng": lng,
                "error": str(e)
            })
            print(f"  -> FAILED: {e}")

    # Sort by risk
    results.sort(key=lambda x: x["adjusted_prob"], reverse=True)

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    risk_counts = {"EXTREME": 0, "HIGH": 0, "MODERATE": 0, "LOW": 0}
    for r in results:
        risk_counts[r["risk_level"]] += 1

    print(f"\nProcessed: {len(results)} successful, {len(failed)} failed")
    print(f"\nRisk Distribution:")
    for level, count in risk_counts.items():
        pct = count / len(results) * 100 if results else 0
        print(f"  {level}: {count} ({pct:.1f}%)")

    if results:
        print(f"\nTop 5 Highest Risk Underpasses:")
        for r in results[:5]:
            print(f"  [{r['risk_level']:8}] {r['name'][:40]}")
            print(f"            Prob: {r['adjusted_prob']:.3f}, Rain24h: {r['features']['rainfall_24h']:.1f}mm, Elev: {r['features']['elevation']:.0f}m")

    # Feature validation summary
    in_range_count = sum(
        1 for r in results
        if all(r["feature_validation"].values())
    )
    print(f"\nFeature Validation: {in_range_count}/{len(results)} samples have ALL features within training range")

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "reference_date": reference_date.isoformat(),
        "data_sources": {
            "rainfall": "CHIRPS via GEE (same as training)",
            "sar": "Sentinel-1 GRD via GEE (same as training)",
            "terrain": "SRTM 30m via GEE (same as training)",
            "landcover": "WorldCover via GEE (same as training)",
        },
        "total_processed": len(results),
        "total_failed": len(failed),
        "risk_counts": risk_counts,
        "model_caveat": "XGBoost AUC=0.71 on new locations. Underpass bonus +0.15 applied. Features extracted with REAL data (not placeholders).",
        "results": results,
        "failed": failed,
    }

    output_file = project_root / "data" / "underpass_real_features_predictions.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {output_file}")
    print("=" * 70)

    return output


def compare_with_placeholder_predictions():
    """
    Compare real feature predictions with the original placeholder-based predictions.
    """
    print("\n" + "=" * 70)
    print("COMPARISON: REAL vs PLACEHOLDER FEATURES")
    print("=" * 70)

    # Load placeholder predictions (old script output)
    placeholder_file = project_root / "data" / "underpass_xgboost_predictions.json"
    if not placeholder_file.exists():
        print("No placeholder predictions found. Run the comparison after both analyses.")
        return

    with open(placeholder_file) as f:
        placeholder_data = json.load(f)

    # Load real predictions
    real_file = project_root / "data" / "underpass_real_features_predictions.json"
    if not real_file.exists():
        print("No real feature predictions found. Run analyze_underpasses_real() first.")
        return

    with open(real_file) as f:
        real_data = json.load(f)

    # Build lookup by OSM ID
    placeholder_by_id = {r["osm_id"]: r for r in placeholder_data["results"]}
    real_by_id = {r["osm_id"]: r for r in real_data["results"]}

    # Find common underpasses
    common_ids = set(placeholder_by_id.keys()) & set(real_by_id.keys())

    print(f"\nComparing {len(common_ids)} underpasses analyzed by both methods")

    if not common_ids:
        print("No common underpasses to compare.")
        return

    # Compare predictions
    print("\nPrediction Comparison:")
    print("-" * 70)
    print(f"{'Name':<35} {'Placeholder':>12} {'Real':>12} {'Diff':>10}")
    print("-" * 70)

    diffs = []
    for osm_id in list(common_ids)[:10]:  # Show first 10
        p = placeholder_by_id[osm_id]
        r = real_by_id[osm_id]
        diff = r["adjusted_prob"] - p["adjusted_prob"]
        diffs.append(diff)

        name = p["name"][:35]
        print(f"{name:<35} {p['adjusted_prob']:>12.3f} {r['adjusted_prob']:>12.3f} {diff:>+10.3f}")

    print("-" * 70)
    print(f"\nAverage difference: {np.mean(diffs):+.3f}")
    print(f"Std deviation: {np.std(diffs):.3f}")

    # Feature comparison for one underpass
    if common_ids:
        example_id = list(common_ids)[0]
        p = placeholder_by_id[example_id]
        r = real_by_id[example_id]

        print(f"\n\nDetailed Feature Comparison for: {p['name']}")
        print("-" * 70)
        print(f"{'Feature':<20} {'Placeholder':>15} {'Real':>15} {'Training Range':>20}")
        print("-" * 70)

        feature_ranges = {
            "rainfall_24h": (0, 12.54),
            "rainfall_3d": (0, 19.85),
            "rainfall_7d": (17.50, 122.36),
            "max_daily_7d": (0, 50),
            "wet_days_7d": (2, 6),
            "sar_vv_mean": (-17.74, 1.34),
            "sar_vh_mean": (-22.30, -6.55),
            "elevation": (200, 280),
            "slope": (1, 6),
        }

        for feat, (low, high) in feature_ranges.items():
            p_val = p["features"].get(feat, "N/A")
            r_val = r["features"].get(feat, "N/A")
            range_str = f"{low:.1f} - {high:.1f}"

            if isinstance(p_val, (int, float)) and isinstance(r_val, (int, float)):
                p_ok = low <= p_val <= high * 1.5  # Allow some buffer
                r_ok = low <= r_val <= high * 1.5
                p_str = f"{p_val:>12.2f}" + ("" if p_ok else " [!]")
                r_str = f"{r_val:>12.2f}" + ("" if r_ok else " [!]")
            else:
                p_str = str(p_val)[:12]
                r_str = str(r_val)[:12]

            print(f"{feat:<20} {p_str:>15} {r_str:>15} {range_str:>20}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze underpasses with REAL features")
    parser.add_argument("--samples", type=int, default=5, help="Number of underpasses to analyze")
    parser.add_argument("--compare", action="store_true", help="Compare with placeholder predictions")
    args = parser.parse_args()

    # Run analysis with real features
    results = analyze_underpasses_real(max_samples=args.samples)

    # Optionally compare with placeholder predictions
    if args.compare:
        compare_with_placeholder_predictions()
