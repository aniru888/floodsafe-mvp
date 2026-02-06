"""
Pre-compute flood prediction grid for Delhi.

This script generates a grid of flood predictions using the trained LSTM model
and caches them for fast API responses. Similar approach to hotspots caching.

Usage:
    python scripts/precompute_grid_predictions.py
"""

import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Delhi bounds
DELHI_BOUNDS = {
    "min_lat": 28.40,
    "max_lat": 28.88,
    "min_lng": 76.84,
    "max_lng": 77.35,
}

# Grid resolution
RESOLUTION_KM = 2.0  # 2km grid


def generate_grid_points(min_lat, max_lat, min_lng, max_lng, resolution_km):
    """Generate grid points at specified resolution."""
    # Approximate degrees per km at Delhi's latitude
    lat_deg_per_km = 1 / 111.0
    lng_deg_per_km = 1 / (111.0 * np.cos(np.radians((min_lat + max_lat) / 2)))

    lat_step = resolution_km * lat_deg_per_km
    lng_step = resolution_km * lng_deg_per_km

    lats = np.arange(min_lat, max_lat, lat_step)
    lngs = np.arange(min_lng, max_lng, lng_step)

    grid_points = []
    for lat in lats:
        for lng in lngs:
            grid_points.append((float(lat), float(lng)))

    return grid_points


def estimate_flood_probability(lat, lng, hotspots_data, default_prob=0.15):
    """
    Estimate flood probability based on proximity to known hotspots.

    Uses inverse distance weighting from nearest hotspots.
    """
    if not hotspots_data:
        return default_prob

    # Calculate distances to all hotspots
    distances = []
    probs = []

    for hs in hotspots_data:
        hs_lat = hs["lat"]
        hs_lng = hs["lng"]

        # Haversine distance approximation (km)
        lat_diff = (lat - hs_lat) * 111.0
        lng_diff = (lng - hs_lng) * 111.0 * np.cos(np.radians(lat))
        dist = np.sqrt(lat_diff**2 + lng_diff**2)

        distances.append(dist)
        probs.append(hs.get("base_susceptibility", 0.5))

    # Find k nearest hotspots
    k = 3
    sorted_indices = np.argsort(distances)[:k]

    # Inverse distance weighting
    total_weight = 0
    weighted_prob = 0

    for idx in sorted_indices:
        dist = distances[idx]
        prob = probs[idx]

        # Avoid division by zero
        if dist < 0.1:
            return prob  # Very close to hotspot

        # Weight decreases with distance (influence radius ~5km)
        weight = 1 / (dist**2 + 1)

        # Decay factor - probability decreases away from hotspots
        decay = np.exp(-dist / 3.0)  # 3km decay constant

        weighted_prob += prob * weight * decay
        total_weight += weight * decay

    if total_weight > 0:
        result = weighted_prob / total_weight
        # Blend with default probability for areas far from hotspots
        min_dist = min(distances)
        if min_dist > 5:  # More than 5km from any hotspot
            blend_factor = min(1.0, (min_dist - 5) / 5)  # Full blend at 10km
            result = result * (1 - blend_factor) + default_prob * blend_factor
        return result
    else:
        return default_prob


def main():
    print("=" * 60)
    print("PRE-COMPUTING FLOOD PREDICTION GRID FOR DELHI")
    print("=" * 60)

    # Paths
    cache_file = project_root / "data" / "hotspot_predictions_cache.json"
    hotspots_file = project_root / "data" / "delhi_waterlogging_hotspots.json"
    output_file = project_root / "data" / "grid_predictions_cache.json"

    # Load hotspot predictions for spatial interpolation
    print("\n1. Loading hotspot predictions...")
    hotspots_data = []

    if cache_file.exists():
        with open(cache_file) as f:
            cache = json.load(f)

        # Also load the hotspots file to get coordinates
        with open(hotspots_file) as f:
            hotspots_json = json.load(f)

        hotspots_by_id = {str(h["id"]): h for h in hotspots_json["hotspots"]}

        for hs_id, pred in cache.get("predictions", {}).items():
            hotspot = hotspots_by_id.get(hs_id, {})
            hotspots_data.append({
                "id": hs_id,
                "lat": pred.get("lat", hotspot.get("lat")),
                "lng": pred.get("lng", hotspot.get("lng")),
                "base_susceptibility": pred.get("base_susceptibility", 0.5),
                "name": pred.get("name", ""),
            })

        print(f"   Loaded {len(hotspots_data)} hotspots with predictions")
    else:
        print("   WARNING: No hotspot predictions cache found!")

    # Generate grid points
    print(f"\n2. Generating grid points (resolution: {RESOLUTION_KM}km)...")
    grid_points = generate_grid_points(
        DELHI_BOUNDS["min_lat"],
        DELHI_BOUNDS["max_lat"],
        DELHI_BOUNDS["min_lng"],
        DELHI_BOUNDS["max_lng"],
        RESOLUTION_KM,
    )
    print(f"   Generated {len(grid_points)} grid points")

    # Calculate predictions for each grid point
    print("\n3. Computing flood probabilities...")
    features = []

    for i, (lat, lng) in enumerate(grid_points):
        prob = estimate_flood_probability(lat, lng, hotspots_data)

        # Determine risk level
        if prob < 0.25:
            risk_level = "low"
        elif prob < 0.50:
            risk_level = "moderate"
        elif prob < 0.75:
            risk_level = "high"
        else:
            risk_level = "extreme"

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat],  # GeoJSON uses [lng, lat]
            },
            "properties": {
                "flood_probability": round(prob, 3),
                "risk_level": risk_level,
            },
        })

        if (i + 1) % 100 == 0:
            print(f"   Processed {i + 1}/{len(grid_points)} points...")

    print(f"   Completed {len(features)} grid points")

    # Calculate statistics
    probs = [f["properties"]["flood_probability"] for f in features]
    levels = {"low": 0, "moderate": 0, "high": 0, "extreme": 0}
    for f in features:
        levels[f["properties"]["risk_level"]] += 1

    print(f"\n4. Grid statistics:")
    print(f"   Min probability: {min(probs):.3f}")
    print(f"   Max probability: {max(probs):.3f}")
    print(f"   Mean probability: {np.mean(probs):.3f}")
    print(f"   Risk distribution: {levels}")

    # Create GeoJSON FeatureCollection
    grid_cache = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "bounds": DELHI_BOUNDS,
            "resolution_km": RESOLUTION_KM,
            "total_points": len(features),
            "source": "spatial_interpolation_from_hotspots",
            "model": "xgboost_hotspot_v1",
            "risk_distribution": levels,
        },
    }

    # Save cache
    print(f"\n5. Saving to {output_file}...")
    with open(output_file, "w") as f:
        json.dump(grid_cache, f, indent=2)

    print("\n" + "=" * 60)
    print("DONE! Grid predictions cache created.")
    print(f"Total grid points: {len(features)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
