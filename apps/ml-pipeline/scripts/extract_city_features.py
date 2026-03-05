"""
Extract GEE features for a city's waterlogging hotspots.

Runs the same 18-feature extraction pipeline used for Delhi on any supported city.
Generates training data (positive hotspots + negative random points) for XGBoost.

Usage:
    python scripts/extract_city_features.py --city bangalore
    python scripts/extract_city_features.py --city delhi --dry-run

Prerequisites:
    - earthengine authenticate
    - pip install earthengine-api numpy
"""
import argparse
import json
import logging
import random
import sys
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
ML_SERVICE_ROOT = PROJECT_ROOT / "apps" / "ml-service"
BACKEND_DATA = PROJECT_ROOT / "apps" / "backend" / "data"

# City bounding boxes (matches FHICalculator.CITY_BOUNDS)
CITY_BOUNDS = {
    "delhi": {"min_lat": 28.40, "max_lat": 28.88, "min_lng": 76.84, "max_lng": 77.35},
    "bangalore": {"min_lat": 12.75, "max_lat": 13.20, "min_lng": 77.35, "max_lng": 77.80},
    "yogyakarta": {"min_lat": -7.95, "max_lat": -7.65, "min_lng": 110.30, "max_lng": 110.50},
    "singapore": {"min_lat": 1.15, "max_lat": 1.47, "min_lng": 103.60, "max_lng": 104.05},
    "indore": {"min_lat": 22.52, "max_lat": 22.85, "min_lng": 75.72, "max_lng": 75.97},
}

# 18 features (must match ml-service/models/xgboost_hotspot/metadata.json)
FEATURE_NAMES = [
    "elevation", "slope", "tpi", "tri", "twi", "spi",
    "rainfall_24h", "rainfall_3d", "rainfall_7d", "max_daily_7d", "wet_days_7d",
    "impervious_pct", "built_up_pct",
    "sar_vv_mean", "sar_vh_mean", "sar_vv_vh_ratio", "sar_change_mag",
    "is_monsoon",
]

# Buffer distance from hotspots for negative samples (degrees, ~500m)
NEGATIVE_BUFFER_DEG = 0.005


def load_hotspots(city: str) -> List[Dict]:
    """Load hotspot data from backend JSON file."""
    filename = f"{city}_waterlogging_hotspots.json"
    path = BACKEND_DATA / filename

    if not path.exists():
        logger.error(f"Hotspot file not found: {path}")
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    # Handle both list format and dict-with-features format
    if isinstance(data, list):
        hotspots = data
    elif isinstance(data, dict) and "features" in data:
        hotspots = data["features"]
    else:
        hotspots = list(data.values()) if isinstance(data, dict) else []

    logger.info(f"Loaded {len(hotspots)} hotspots for {city} from {path}")
    return hotspots


def extract_hotspot_coords(hotspots: List[Dict]) -> List[Tuple[float, float]]:
    """Extract (lat, lng) from hotspot data (handles various formats)."""
    coords = []
    for h in hotspots:
        if isinstance(h, dict):
            # GeoJSON feature format
            if "geometry" in h:
                c = h["geometry"].get("coordinates", [])
                if len(c) >= 2:
                    coords.append((c[1], c[0]))  # GeoJSON is [lng, lat]
                    continue
            # Direct lat/lng format
            lat = h.get("lat") or h.get("latitude")
            lng = h.get("lng") or h.get("longitude")
            if lat and lng:
                coords.append((float(lat), float(lng)))
    return coords


def generate_negative_points(
    bounds: Dict[str, float],
    positive_coords: List[Tuple[float, float]],
    n_negatives: int,
) -> List[Tuple[float, float]]:
    """Generate random negative points within bounds, filtered away from hotspots."""
    negatives = []
    max_attempts = n_negatives * 10

    for _ in range(max_attempts):
        if len(negatives) >= n_negatives:
            break

        lat = random.uniform(bounds["min_lat"], bounds["max_lat"])
        lng = random.uniform(bounds["min_lng"], bounds["max_lng"])

        # Ensure minimum distance from all hotspots
        too_close = False
        for plat, plng in positive_coords:
            if abs(lat - plat) < NEGATIVE_BUFFER_DEG and abs(lng - plng) < NEGATIVE_BUFFER_DEG:
                too_close = True
                break

        if not too_close:
            negatives.append((lat, lng))

    logger.info(f"Generated {len(negatives)} negative points (target: {n_negatives})")
    return negatives


def extract_features_gee(coords: List[Tuple[float, float]], is_monsoon: bool = True) -> np.ndarray:
    """
    Extract 18 features for each coordinate using Google Earth Engine.

    This imports the existing HotspotFeatureExtractor from ml-service.
    Falls back to a simplified extraction if the full extractor isn't available.
    """
    try:
        sys.path.insert(0, str(ML_SERVICE_ROOT))
        from src.features.hotspot_features import HotspotFeatureExtractor
        extractor = HotspotFeatureExtractor()

        features = []
        for i, (lat, lng) in enumerate(coords):
            if (i + 1) % 10 == 0:
                logger.info(f"  Extracting features: {i+1}/{len(coords)}")
            try:
                feat = extractor.extract(lat, lng, is_monsoon=is_monsoon)
                features.append(feat)
            except Exception as e:
                logger.warning(f"  Failed for ({lat:.4f}, {lng:.4f}): {e}")
                features.append(np.zeros(len(FEATURE_NAMES)))

        return np.array(features)

    except ImportError:
        logger.error(
            "HotspotFeatureExtractor not available. "
            "Ensure apps/ml-service is set up with GEE authentication."
        )
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Extract GEE features for city hotspots")
    parser.add_argument("--city", required=True, choices=list(CITY_BOUNDS.keys()))
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing GEE calls")
    parser.add_argument("--monsoon", action="store_true", default=True, help="Extract monsoon features")
    parser.add_argument("--negative-ratio", type=float, default=2.0,
                        help="Ratio of negative to positive samples (default 2.0)")
    args = parser.parse_args()

    city = args.city
    bounds = CITY_BOUNDS[city]

    # Load hotspots
    hotspots = load_hotspots(city)
    positive_coords = extract_hotspot_coords(hotspots)

    if not positive_coords:
        logger.error(f"No valid coordinates found in hotspot data for {city}")
        sys.exit(1)

    # Generate negatives
    n_negatives = int(len(positive_coords) * args.negative_ratio)
    negative_coords = generate_negative_points(bounds, positive_coords, n_negatives)

    # Combined coordinates and labels
    all_coords = positive_coords + negative_coords
    labels = np.array([1] * len(positive_coords) + [0] * len(negative_coords))

    logger.info(f"\nTraining data plan for {city}:")
    logger.info(f"  Positive (hotspot): {len(positive_coords)}")
    logger.info(f"  Negative (random):  {len(negative_coords)}")
    logger.info(f"  Total:              {len(all_coords)}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would extract {len(FEATURE_NAMES)} features for {len(all_coords)} points")
        print(f"Sample positive: {positive_coords[0]}")
        print(f"Sample negative: {negative_coords[0] if negative_coords else 'N/A'}")
        return

    # Extract features via GEE
    logger.info(f"\nExtracting {len(FEATURE_NAMES)} GEE features for {len(all_coords)} points...")
    features = extract_features_gee(all_coords, is_monsoon=args.monsoon)

    # Save training data
    output_dir = ML_SERVICE_ROOT / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{city}_hotspot_training_data.npz"

    np.savez(
        output_path,
        features=features,
        labels=labels,
        feature_names=np.array(FEATURE_NAMES),
        coords=np.array(all_coords),
        metadata=json.dumps({
            "city": city,
            "n_positive": len(positive_coords),
            "n_negative": len(negative_coords),
            "is_monsoon": args.monsoon,
            "bounds": bounds,
        }),
    )

    logger.info(f"\nTraining data saved to: {output_path}")
    logger.info(f"  Features shape: {features.shape}")
    logger.info(f"  Labels shape: {labels.shape}")


if __name__ == "__main__":
    main()
