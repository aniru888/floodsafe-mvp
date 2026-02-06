"""
Fix historical floods coordinates by geocoding district names.

The IFI-Impacts dataset only contains district names, not GPS coordinates.
This script assigns approximate coordinates based on Delhi district centroids.
"""

import json
from pathlib import Path
from datetime import datetime
import random

# Delhi district centroids (approximate centers)
DELHI_DISTRICT_COORDS = {
    # Delhi Districts
    "Central": {"lat": 28.6517, "lng": 77.2219},
    "New Delhi": {"lat": 28.6139, "lng": 77.2090},
    "New New Delhi": {"lat": 28.6139, "lng": 77.2090},  # Duplicate entry fix
    "North": {"lat": 28.7041, "lng": 77.1025},
    "North East": {"lat": 28.6920, "lng": 77.2711},
    "North West": {"lat": 28.7350, "lng": 77.0650},
    "North west": {"lat": 28.7350, "lng": 77.0650},  # Lowercase variant
    "East": {"lat": 28.6280, "lng": 77.2960},
    "West": {"lat": 28.6640, "lng": 77.0730},
    "South": {"lat": 28.5276, "lng": 77.2190},
    "South East": {"lat": 28.5550, "lng": 77.2650},
    "South West": {"lat": 28.5850, "lng": 77.0720},
    "Shahdara": {"lat": 28.6731, "lng": 77.2906},

    # Fallback for entire Delhi NCR
    "Delhi": {"lat": 28.6139, "lng": 77.2090},
    "Delhi NCR": {"lat": 28.6139, "lng": 77.2090},
}

# Add slight randomization to prevent exact overlap (within ~1km)
def add_jitter(lat, lng, jitter_km=0.5):
    """Add random offset to coordinates (up to jitter_km in each direction)."""
    # 1 degree lat ≈ 111km, 1 degree lng ≈ 111km * cos(lat)
    lat_jitter = (random.random() - 0.5) * 2 * (jitter_km / 111.0)
    lng_jitter = (random.random() - 0.5) * 2 * (jitter_km / 85.0)  # Approx for Delhi's latitude
    return lat + lat_jitter, lng + lng_jitter


def extract_delhi_district(districts_str):
    """Extract the first Delhi district from a comma-separated string."""
    if not districts_str or districts_str == "nan":
        return None

    parts = [p.strip() for p in districts_str.split(",")]

    # First pass: look for exact matches
    for part in parts:
        if part in DELHI_DISTRICT_COORDS:
            return part

    # Second pass: look for partial matches
    for part in parts:
        for district in DELHI_DISTRICT_COORDS:
            if district.lower() in part.lower() or part.lower() in district.lower():
                return district

    return None


def main():
    print("=" * 60)
    print("FIXING HISTORICAL FLOODS COORDINATES")
    print("=" * 60)

    data_dir = Path(__file__).parent.parent / "data"
    input_file = data_dir / "delhi_historical_floods.json"
    output_file = data_dir / "delhi_historical_floods.json"

    print(f"\n1. Loading data from {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data["features"]
    print(f"   Loaded {len(features)} flood events")

    print("\n2. Geocoding districts to coordinates...")

    # Track statistics
    stats = {
        "geocoded": 0,
        "fallback_center": 0,
        "by_district": {}
    }

    for feature in features:
        props = feature["properties"]
        districts_str = props.get("districts", "")

        # Try to extract a Delhi district
        district = extract_delhi_district(districts_str)

        if district and district in DELHI_DISTRICT_COORDS:
            coords = DELHI_DISTRICT_COORDS[district]
            lat, lng = add_jitter(coords["lat"], coords["lng"], jitter_km=1.0)
            stats["geocoded"] += 1
            stats["by_district"][district] = stats["by_district"].get(district, 0) + 1
        else:
            # Fallback to Delhi center with larger jitter
            lat, lng = add_jitter(28.6139, 77.2090, jitter_km=5.0)
            stats["fallback_center"] += 1

        # Update coordinates
        feature["geometry"]["coordinates"] = [round(lng, 4), round(lat, 4)]

    print(f"   Geocoded: {stats['geocoded']}")
    print(f"   Fallback (Delhi center with jitter): {stats['fallback_center']}")
    print("\n   By district:")
    for district, count in sorted(stats["by_district"].items(), key=lambda x: -x[1]):
        print(f"     {district}: {count}")

    # Update metadata
    data["metadata"]["coordinates_source"] = "District centroids with random jitter"
    data["metadata"]["coordinates_updated"] = datetime.now().isoformat()
    data["metadata"]["coordinate_accuracy"] = "Approximate district-level (±1-5km)"

    print(f"\n3. Saving updated data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    # Verify coordinates are now different
    coords_set = set()
    for f in features:
        coord = tuple(f["geometry"]["coordinates"])
        coords_set.add(coord)

    print(f"\n4. Verification:")
    print(f"   Total events: {len(features)}")
    print(f"   Unique coordinates: {len(coords_set)}")
    print(f"   All different: {'YES' if len(coords_set) == len(features) else 'NO'}")

    print("\n" + "=" * 60)
    print("DONE! Historical floods now have distinct coordinates.")
    print("=" * 60)


if __name__ == "__main__":
    main()
