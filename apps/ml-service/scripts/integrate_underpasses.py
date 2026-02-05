"""
Integrate OSM Underpasses into Delhi Waterlogging Hotspots.

This script:
1. Adds `source: "mcd_reports"` to all 62 existing hotspots
2. Adds 28 high-risk underpasses (20 EXTREME + 8 HIGH) from XGBoost analysis
3. Assigns zones to new underpasses based on coordinates
4. Updates metadata

Usage:
    cd apps/ml-service
    python scripts/integrate_underpasses.py
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple


# Zone boundaries (approximate, based on Delhi geography)
# Each zone is defined by a bounding box or polygon
ZONE_DEFINITIONS = {
    "ring_road": {
        # Inner Ring Road corridor
        "bounds": [(28.55, 77.15), (28.65, 77.28)],
        "check": lambda lat, lng: 28.55 <= lat <= 28.65 and 77.15 <= lng <= 77.28
    },
    "rohtak_road_west": {
        # Western corridor along Rohtak Road
        "check": lambda lat, lng: lat > 28.62 and lng < 77.15
    },
    "central_north": {
        # Central/North Delhi
        "check": lambda lat, lng: lat > 28.65 and 77.15 <= lng <= 77.28
    },
    "south_east": {
        # South and East Delhi (including trans-Yamuna)
        "check": lambda lat, lng: (lat < 28.62 and lng > 77.20) or (lng > 77.28)
    },
    "rural_outlying": {
        # Outer areas, Dwarka, Narela, Najafgarh, Kapashera
        "check": lambda lat, lng: lng < 77.10 or lat > 28.78 or lat < 28.52
    }
}


def assign_zone(lat: float, lng: float) -> str:
    """
    Assign a zone to a coordinate based on Delhi geography.

    Zone assignment priority (checked in order):
    1. rural_outlying - Outer areas first (lng < 77.10, lat extremes)
    2. rohtak_road_west - Western corridor (lat > 28.62, lng < 77.15)
    3. ring_road - Inner Ring Road (28.55-28.65, 77.15-77.28)
    4. central_north - Central/North (lat > 28.65, lng 77.15-77.28)
    5. south_east - Default for remaining areas
    """
    # Check rural_outlying first (outer boundaries)
    if lng < 77.10 or lat > 28.78 or lat < 28.52:
        return "rural_outlying"

    # Check rohtak_road_west (western corridor)
    if lat > 28.62 and lng < 77.15:
        return "rohtak_road_west"

    # Check ring_road (inner corridor)
    if 28.55 <= lat <= 28.65 and 77.15 <= lng <= 77.28:
        return "ring_road"

    # Check central_north
    if lat > 28.65 and 77.15 <= lng <= 77.28:
        return "central_north"

    # Default to south_east
    return "south_east"


def load_hotspots(path: Path) -> Dict:
    """Load existing hotspots JSON."""
    with open(path) as f:
        return json.load(f)


def load_underpass_predictions(path: Path) -> List[Dict]:
    """Load underpass predictions and filter for EXTREME and HIGH risk."""
    with open(path) as f:
        data = json.load(f)

    results = data.get("results", [])
    high_risk = [
        r for r in results
        if r.get("risk_level") in ("EXTREME", "HIGH")
    ]
    return high_risk


def add_source_to_existing(hotspots: List[Dict]) -> List[Dict]:
    """Add source field to existing hotspots."""
    for hotspot in hotspots:
        hotspot["source"] = "mcd_reports"
    return hotspots


def create_hotspot_from_underpass(underpass: Dict, hotspot_id: int) -> Dict:
    """Create a hotspot entry from an underpass prediction."""
    zone = assign_zone(underpass["lat"], underpass["lng"])

    # Map risk level to severity_history
    risk_to_severity = {
        "EXTREME": "predicted_extreme",
        "HIGH": "predicted_high",
    }

    return {
        "id": hotspot_id,
        "name": underpass["name"],
        "lat": underpass["lat"],
        "lng": underpass["lng"],
        "description": f"OSM underpass ({underpass['highway_type']}) - XGBoost predicted {underpass['risk_level']} risk",
        "zone": zone,
        "severity_history": risk_to_severity.get(underpass["risk_level"], "predicted"),
        "source": "osm_underpass",
        "osm_id": underpass["osm_id"],
        "xgboost_prob": underpass["xgboost_prob"],
        "adjusted_prob": underpass["adjusted_prob"],
        "risk_level": underpass["risk_level"]
    }


def update_metadata(metadata: Dict, new_hotspots: List[Dict], total: int) -> Dict:
    """Update metadata with new totals and zone counts."""
    # Count zones for all hotspots
    zone_counts = {}
    for hotspot in new_hotspots:
        zone = hotspot.get("zone", "unknown")
        zone_counts[zone] = zone_counts.get(zone, 0) + 1

    metadata["version"] = "2.0"
    metadata["updated"] = datetime.now().isoformat()[:10]
    metadata["source"] = "MCD Delhi Reports + OSM Underpass Discovery"
    metadata["total_hotspots"] = total
    metadata["zones"] = zone_counts
    metadata["composition"] = {
        "mcd_reports": 62,
        "osm_underpass": total - 62
    }

    return metadata


def main():
    project_root = Path(__file__).parent.parent

    # File paths
    hotspots_path = project_root / "data" / "delhi_waterlogging_hotspots.json"
    predictions_path = project_root / "data" / "underpass_real_features_predictions.json"
    output_path = hotspots_path  # Overwrite original
    backup_path = project_root / "data" / "delhi_waterlogging_hotspots_backup.json"

    print("=" * 70)
    print("UNDERPASS INTEGRATION INTO HOTSPOTS")
    print("=" * 70)

    # Load existing data
    print(f"\nLoading hotspots from: {hotspots_path}")
    data = load_hotspots(hotspots_path)
    existing_hotspots = data["hotspots"]
    metadata = data["metadata"]
    print(f"  Loaded {len(existing_hotspots)} existing hotspots")

    # Create backup
    print(f"\nCreating backup: {backup_path}")
    with open(backup_path, "w") as f:
        json.dump(data, f, indent=2)

    # Load underpass predictions
    print(f"\nLoading underpass predictions from: {predictions_path}")
    high_risk_underpasses = load_underpass_predictions(predictions_path)
    print(f"  Found {len(high_risk_underpasses)} high-risk underpasses (EXTREME + HIGH)")

    # Step 1: Add source to existing hotspots
    print("\n[Step 1] Adding 'source: mcd_reports' to existing hotspots...")
    existing_hotspots = add_source_to_existing(existing_hotspots)
    print(f"  Updated {len(existing_hotspots)} hotspots")

    # Step 2: Create new hotspots from underpasses
    print("\n[Step 2] Creating new hotspots from underpasses...")
    next_id = 63  # Start after existing 62
    new_hotspots = []

    for underpass in high_risk_underpasses:
        hotspot = create_hotspot_from_underpass(underpass, next_id)
        new_hotspots.append(hotspot)
        zone = hotspot["zone"]
        print(f"  [{next_id}] {hotspot['name'][:40]} -> {zone} ({hotspot['risk_level']})")
        next_id += 1

    print(f"\n  Created {len(new_hotspots)} new hotspots")

    # Step 3: Combine all hotspots
    all_hotspots = existing_hotspots + new_hotspots
    total_hotspots = len(all_hotspots)
    print(f"\n[Step 3] Combined total: {total_hotspots} hotspots")

    # Step 4: Update metadata
    print("\n[Step 4] Updating metadata...")
    metadata = update_metadata(metadata, all_hotspots, total_hotspots)
    print(f"  Version: {metadata['version']}")
    print(f"  Zone distribution: {metadata['zones']}")
    print(f"  Composition: {metadata['composition']}")

    # Step 5: Save updated file
    output_data = {
        "metadata": metadata,
        "hotspots": all_hotspots
    }

    print(f"\n[Step 5] Saving to: {output_path}")
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print("\n" + "=" * 70)
    print("INTEGRATION COMPLETE")
    print("=" * 70)
    print(f"\nSummary:")
    print(f"  Original hotspots: 62 (source: mcd_reports)")
    print(f"  New underpasses:   {len(new_hotspots)} (source: osm_underpass)")
    print(f"  Total hotspots:    {total_hotspots}")
    print(f"\nBackup saved to: {backup_path}")
    print(f"Updated file:    {output_path}")

    # Zone breakdown
    print(f"\nZone breakdown:")
    for zone, count in sorted(metadata['zones'].items()):
        print(f"  {zone}: {count}")

    return output_data


if __name__ == "__main__":
    main()
