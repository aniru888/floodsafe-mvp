"""
Integrate MODERATE and LOW risk underpasses into training data.

Phase 1 of the AUC improvement plan:
- Add 11 MODERATE risk underpasses as hotspots (IDs 91-101) - positives for training
- Add 11 LOW risk underpasses as explicit negatives (more realistic than random points)

This adds spatial diversity WITHOUT requiring additional GEE calls since features
are already extracted in underpass_real_features_predictions.json.

Usage:
    python scripts/integrate_moderate_low_underpasses.py
"""

import json
from pathlib import Path
from datetime import datetime
import shutil

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Input file
UNDERPASS_PREDICTIONS = DATA_DIR / "underpass_real_features_predictions.json"
HOTSPOTS_FILE = DATA_DIR / "delhi_waterlogging_hotspots.json"

# Output files
LOW_UNDERPASSES_FILE = DATA_DIR / "low_risk_underpasses.json"

# Zone classification based on coordinates
def classify_zone(lat: float, lng: float) -> str:
    """Classify underpass into zone based on coordinates."""
    lat_mid = 28.65
    lng_mid = 77.1

    # Ring road is central band
    if 28.55 < lat < 28.75 and 77.15 < lng < 77.35:
        return "ring_road"
    elif lat >= lat_mid and lng < lng_mid:
        return "rohtak_road_west"
    elif lat >= lat_mid and lng >= lng_mid:
        return "central_north"
    elif lat < lat_mid and lng >= lng_mid:
        return "south_east"
    else:
        return "rural_outlying"


def main():
    print("\n" + "=" * 60)
    print("PHASE 1: INTEGRATE MODERATE/LOW UNDERPASSES")
    print("=" * 60)

    # Load underpass predictions
    with open(UNDERPASS_PREDICTIONS) as f:
        predictions_data = json.load(f)

    predictions = predictions_data["results"]
    print(f"\nLoaded {len(predictions)} underpass predictions")

    # Separate by risk level
    moderate_underpasses = [p for p in predictions if p["risk_level"] == "MODERATE"]
    low_underpasses = [p for p in predictions if p["risk_level"] == "LOW"]

    print(f"  MODERATE risk: {len(moderate_underpasses)}")
    print(f"  LOW risk: {len(low_underpasses)}")

    # Load existing hotspots
    with open(HOTSPOTS_FILE) as f:
        hotspots_data = json.load(f)

    existing_count = len(hotspots_data["hotspots"])
    print(f"\nExisting hotspots: {existing_count}")

    # Backup current hotspots file
    backup_path = HOTSPOTS_FILE.with_suffix(".json.backup")
    shutil.copy(HOTSPOTS_FILE, backup_path)
    print(f"Backup created: {backup_path}")

    # Add MODERATE underpasses as new hotspots
    print("\n" + "-" * 40)
    print("ADDING 11 MODERATE RISK UNDERPASSES AS HOTSPOTS")
    print("-" * 40)

    new_hotspots = []
    for i, up in enumerate(moderate_underpasses):
        new_id = existing_count + 1 + i  # IDs 91-101
        zone = classify_zone(up["lat"], up["lng"])

        new_hotspot = {
            "id": new_id,
            "name": up["name"],
            "lat": up["lat"],
            "lng": up["lng"],
            "description": f"OSM underpass ({up['highway_type']}) - XGBoost predicted MODERATE risk",
            "zone": zone,
            "severity_history": "predicted_moderate",
            "source": "osm_underpass",
            "osm_id": up["osm_id"],
            "xgboost_prob": up["xgboost_prob"],
            "adjusted_prob": up["adjusted_prob"],
            "risk_level": "MODERATE"
        }
        new_hotspots.append(new_hotspot)
        print(f"  ID {new_id}: {up['name'][:40]} ({zone}, prob={up['adjusted_prob']:.3f})")

    # Update hotspots data
    hotspots_data["hotspots"].extend(new_hotspots)
    hotspots_data["metadata"]["total_hotspots"] = len(hotspots_data["hotspots"])
    hotspots_data["metadata"]["updated"] = datetime.now().strftime("%Y-%m-%d")
    hotspots_data["metadata"]["composition"]["osm_underpass"] += len(new_hotspots)

    # Update zone counts
    for hotspot in new_hotspots:
        zone = hotspot["zone"]
        if zone in hotspots_data["metadata"]["zones"]:
            hotspots_data["metadata"]["zones"][zone] += 1

    # Save updated hotspots
    with open(HOTSPOTS_FILE, "w") as f:
        json.dump(hotspots_data, f, indent=2)

    print(f"\nUpdated {HOTSPOTS_FILE}")
    print(f"  Total hotspots: {len(hotspots_data['hotspots'])}")

    # Save LOW risk underpasses for use as negatives
    print("\n" + "-" * 40)
    print("SAVING 11 LOW RISK UNDERPASSES AS EXPLICIT NEGATIVES")
    print("-" * 40)

    low_negatives = []
    for i, up in enumerate(low_underpasses):
        zone = classify_zone(up["lat"], up["lng"])

        negative = {
            "id": f"low_underpass_{i + 1}",
            "name": up["name"],
            "lat": up["lat"],
            "lng": up["lng"],
            "zone": zone,
            "source": "osm_underpass",
            "osm_id": up["osm_id"],
            "highway_type": up["highway_type"],
            "xgboost_prob": up["xgboost_prob"],
            "adjusted_prob": up["adjusted_prob"],
            "risk_level": "LOW",
            # Include pre-extracted features to avoid GEE calls
            "features": up["features"],
            "label": 0  # Explicitly marked as negative
        }
        low_negatives.append(negative)
        print(f"  {i + 1}. {up['name'][:40]} ({zone}, prob={up['adjusted_prob']:.3f})")

    low_data = {
        "metadata": {
            "created": datetime.now().isoformat(),
            "source": "underpass_real_features_predictions.json",
            "purpose": "Explicit negative samples for training (underpass infrastructure, LOW flood risk)",
            "count": len(low_negatives)
        },
        "negatives": low_negatives
    }

    with open(LOW_UNDERPASSES_FILE, "w") as f:
        json.dump(low_data, f, indent=2)

    print(f"\nSaved to {LOW_UNDERPASSES_FILE}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  MODERATE underpasses added as hotspots: 11 (IDs 91-101)")
    print(f"  LOW underpasses saved as negatives: 11")
    print(f"  Total hotspots now: {len(hotspots_data['hotspots'])}")
    print(f"\nNEXT STEPS:")
    print("  1. Run generate_hotspot_training_data.py with updated hotspots")
    print("  2. The script needs modification to include LOW underpasses as explicit negatives")
    print("  3. Retrain XGBoost model")
    print("  4. Run verification to check Location-Aware AUC")
    print("=" * 60)


if __name__ == "__main__":
    main()
