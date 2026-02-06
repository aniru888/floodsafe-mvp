"""
Generate Training Data for Waterlogging Hotspot Prediction.

This script generates training data by:
1. Loading 62 known waterlogging hotspots (positive class)
2. Generating ~200 random non-hotspot points (negative class)
3. Extracting 10-dimensional features for each location
4. Creating balanced training dataset with multiple temporal samples

Usage:
    python scripts/generate_hotspot_training_data.py

Output:
    data/hotspot_training_data.npz - Training data with features and labels
"""

import sys
import json
import random
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.features.hotspot_features import HotspotFeatureExtractor, FEATURE_NAMES, FEATURE_DIM

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Delhi bounds for generating negative samples
DELHI_BOUNDS = {
    "lat_min": 28.45,
    "lat_max": 28.85,
    "lng_min": 76.85,
    "lng_max": 77.35,
}

# Buffer distance from hotspots for negative samples (in km)
NEGATIVE_BUFFER_KM = 0.5

# Number of negative samples per zone
NEGATIVE_SAMPLES_PER_ZONE = 20  # 100 random negatives (5 zones × 20)

# Path to explicit LOW risk underpasses (used as high-quality negatives)
LOW_UNDERPASSES_FILE = Path(__file__).parent.parent / "data" / "low_risk_underpasses.json"

# Sample dates for feature extraction
# Using confirmed-working monsoon dates with SAR data available
SAMPLE_DATES = [
    # Monsoon 2023 (SAR verified available)
    datetime(2023, 7, 15),
    datetime(2023, 8, 10),
    # Monsoon 2022
    datetime(2022, 7, 20),
]

# Zones for stratified negative sampling
ZONES = ["ring_road", "rohtak_road_west", "central_north", "south_east", "rural_outlying"]


def load_low_underpasses() -> List[Dict]:
    """
    Load LOW risk underpasses as explicit negative samples.

    These are underpasses with infrastructure similar to hotspots but LOW flood risk,
    providing high-quality negative examples that help the model learn decision boundaries.
    """
    if not LOW_UNDERPASSES_FILE.exists():
        logger.warning(f"LOW underpasses file not found: {LOW_UNDERPASSES_FILE}")
        return []

    with open(LOW_UNDERPASSES_FILE) as f:
        data = json.load(f)

    negatives = []
    for up in data["negatives"]:
        negatives.append({
            "id": up["id"],
            "name": up["name"],
            "lat": up["lat"],
            "lng": up["lng"],
            "zone": up["zone"],
            "label": 0,  # Negative class
            "source": "low_risk_underpass",  # Track source for analysis
        })

    logger.info(f"Loaded {len(negatives)} LOW risk underpasses as explicit negatives")
    return negatives


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate haversine distance between two points in km."""
    R = 6371  # Earth radius in km

    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlng = np.radians(lng2 - lng1)

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlng / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    return R * c


def is_far_from_hotspots(lat: float, lng: float, hotspots: List[Dict], min_distance_km: float) -> bool:
    """Check if a point is at least min_distance_km away from all hotspots."""
    for hotspot in hotspots:
        dist = haversine_distance(lat, lng, hotspot["lat"], hotspot["lng"])
        if dist < min_distance_km:
            return False
    return True


def generate_negative_samples(hotspots: List[Dict], n_samples: int) -> List[Dict]:
    """
    Generate random negative sample locations.

    Negative samples are:
    - Random points within Delhi bounds
    - At least NEGATIVE_BUFFER_KM away from all hotspots
    - Stratified by zone (rough geographic quadrants)
    """
    negative_samples = []
    attempts = 0
    max_attempts = n_samples * 100

    # Define zone bounds for stratification
    lat_mid = (DELHI_BOUNDS["lat_min"] + DELHI_BOUNDS["lat_max"]) / 2
    lng_mid = (DELHI_BOUNDS["lng_min"] + DELHI_BOUNDS["lng_max"]) / 2

    zone_bounds = {
        "ring_road": (lat_mid - 0.05, lat_mid + 0.05, lng_mid - 0.1, lng_mid + 0.1),
        "rohtak_road_west": (lat_mid, DELHI_BOUNDS["lat_max"], DELHI_BOUNDS["lng_min"], lng_mid),
        "central_north": (lat_mid, DELHI_BOUNDS["lat_max"], lng_mid, DELHI_BOUNDS["lng_max"]),
        "south_east": (DELHI_BOUNDS["lat_min"], lat_mid, lng_mid, DELHI_BOUNDS["lng_max"]),
        "rural_outlying": (DELHI_BOUNDS["lat_min"], lat_mid, DELHI_BOUNDS["lng_min"], lng_mid),
    }

    samples_per_zone = n_samples // len(zone_bounds)

    for zone_name, (lat_min, lat_max, lng_min, lng_max) in zone_bounds.items():
        zone_samples = 0

        while zone_samples < samples_per_zone and attempts < max_attempts:
            attempts += 1

            # Generate random point in zone
            lat = random.uniform(lat_min, lat_max)
            lng = random.uniform(lng_min, lng_max)

            # Check if far enough from hotspots
            if is_far_from_hotspots(lat, lng, hotspots, NEGATIVE_BUFFER_KM):
                negative_samples.append({
                    "id": f"neg_{len(negative_samples) + 1}",
                    "name": f"Non-hotspot {zone_name} #{zone_samples + 1}",
                    "lat": lat,
                    "lng": lng,
                    "zone": zone_name,
                    "label": 0,  # Negative class
                })
                zone_samples += 1

    logger.info(f"Generated {len(negative_samples)} negative samples in {attempts} attempts")
    return negative_samples


def extract_features_for_samples(
    samples: List[Dict],
    dates: List[datetime],
    extractor: HotspotFeatureExtractor,
) -> Tuple[np.ndarray, np.ndarray, List[Dict]]:
    """
    Extract features for all samples across multiple dates.

    Returns:
        features: numpy array of shape (n_samples * n_dates, 10)
        labels: numpy array of shape (n_samples * n_dates,)
        metadata: list of dicts with sample info
    """
    n_samples = len(samples)
    n_dates = len(dates)
    total = n_samples * n_dates

    features = np.zeros((total, FEATURE_DIM))
    labels = np.zeros(total)
    metadata = []

    idx = 0
    for sample in samples:
        for date in dates:
            logger.info(f"Extracting [{idx + 1}/{total}] {sample['name'][:30]} @ {date.strftime('%Y-%m-%d')}")

            try:
                feat = extractor.extract_features_for_hotspot(
                    lat=sample["lat"],
                    lng=sample["lng"],
                    reference_date=date,
                )
                features[idx] = feat
                labels[idx] = sample.get("label", 1)  # Default to positive for hotspots
                metadata.append({
                    "sample_id": sample["id"] if "id" in sample else idx,
                    "name": sample["name"],
                    "lat": sample["lat"],
                    "lng": sample["lng"],
                    "zone": sample.get("zone", "unknown"),
                    "date": date.strftime("%Y-%m-%d"),
                    "label": int(labels[idx]),
                })
            except Exception as e:
                logger.warning(f"Failed to extract features for {sample['name']}: {e}")
                # Keep zeros for failed extractions
                labels[idx] = sample.get("label", 1)
                metadata.append({
                    "sample_id": sample.get("id", idx),
                    "name": sample["name"],
                    "lat": sample["lat"],
                    "lng": sample["lng"],
                    "zone": sample.get("zone", "unknown"),
                    "date": date.strftime("%Y-%m-%d"),
                    "label": int(labels[idx]),
                    "error": str(e),
                })

            idx += 1

    return features, labels, metadata


def main():
    """Generate training data."""
    print("\n" + "#" * 60)
    print("#  FLOODSAFE HOTSPOT TRAINING DATA GENERATOR")
    print("#  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("#" * 60)

    # Load hotspots
    hotspots_file = project_root / "data" / "delhi_waterlogging_hotspots.json"

    if not hotspots_file.exists():
        print(f"ERROR: Hotspots file not found: {hotspots_file}")
        sys.exit(1)

    with open(hotspots_file) as f:
        data = json.load(f)
        hotspots = data["hotspots"]

    print(f"\nLoaded {len(hotspots)} waterlogging hotspots")

    # Add label to hotspots (positive class)
    for h in hotspots:
        h["label"] = 1

    # LOW underpasses DISABLED: Caused AUC drop from 0.82 to 0.71
    # Using model predictions to generate labels introduced label noise
    low_underpasses = []  # load_low_underpasses() - DISABLED
    print(f"LOW underpasses disabled (AUC regression fix)")

    # Generate random negative samples (reduced count since we have explicit negatives)
    n_random_negative = NEGATIVE_SAMPLES_PER_ZONE * len(ZONES)
    print(f"Generating {n_random_negative} random negative samples...")
    random_negative_samples = generate_negative_samples(hotspots, n_random_negative)

    # Combine all negative samples
    all_negative_samples = low_underpasses + random_negative_samples
    print(f"Total negatives: {len(all_negative_samples)} ({len(low_underpasses)} explicit + {len(random_negative_samples)} random)")

    # Combine all samples
    all_samples = hotspots + all_negative_samples
    print(f"\nTotal unique locations: {len(all_samples)} ({len(hotspots)} positive, {len(all_negative_samples)} negative)")

    # Initialize feature extractor
    print("\nInitializing feature extractor...")
    extractor = HotspotFeatureExtractor()

    # Extract features
    print(f"\nExtracting features across {len(SAMPLE_DATES)} dates...")
    print("This may take a while due to GEE API calls...")

    features, labels, metadata = extract_features_for_samples(
        all_samples, SAMPLE_DATES, extractor
    )

    # Calculate statistics
    n_positive = int(labels.sum())
    n_negative = len(labels) - n_positive
    class_ratio = n_positive / n_negative if n_negative > 0 else 0

    print(f"\n" + "=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)
    print(f"  Total samples:     {len(labels)}")
    print(f"  Positive (flood):  {n_positive} ({n_positive/len(labels)*100:.1f}%)")
    print(f"  Negative:          {n_negative} ({n_negative/len(labels)*100:.1f}%)")
    print(f"  Class ratio:       1:{1/class_ratio:.1f}" if class_ratio > 0 else "  Class ratio: N/A")
    print(f"  Feature dimension: {features.shape[1]}")
    print(f"  Dates sampled:     {len(SAMPLE_DATES)}")

    # Feature statistics
    print(f"\nFEATURE STATISTICS:")
    for i, name in enumerate(FEATURE_NAMES):
        col = features[:, i]
        non_zero = np.sum(col != 0)
        print(f"  {name:15}: min={col.min():8.2f}, max={col.max():8.2f}, mean={col.mean():8.2f}, non-zero={non_zero}/{len(col)}")

    # Check for zero-variance features
    variances = np.var(features, axis=0)
    zero_var = np.sum(variances < 1e-10)
    if zero_var > 0:
        print(f"\n  WARNING: {zero_var} features have zero variance!")
        for i, (name, var) in enumerate(zip(FEATURE_NAMES, variances)):
            if var < 1e-10:
                print(f"    - {name}")

    # Save training data
    output_file = project_root / "data" / "hotspot_training_data.npz"

    np.savez(
        output_file,
        features=features,
        labels=labels,
        feature_names=FEATURE_NAMES,
        metadata=json.dumps(metadata),
    )

    print(f"\nTraining data saved to: {output_file}")
    print(f"  features shape: {features.shape}")
    print(f"  labels shape:   {labels.shape}")

    # Save metadata separately as JSON for easier inspection
    metadata_file = project_root / "data" / "hotspot_training_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump({
            "created": datetime.now().isoformat(),
            "n_samples": len(labels),
            "n_positive": n_positive,
            "n_negative": n_negative,
            "n_unique_locations": len(all_samples),
            "n_hotspots": len(hotspots),
            "n_low_underpasses": len(low_underpasses),
            "n_random_negatives": len(random_negative_samples),
            "feature_names": FEATURE_NAMES,
            "dates_sampled": [d.strftime("%Y-%m-%d") for d in SAMPLE_DATES],
            "samples": metadata,
        }, f, indent=2)

    print(f"  Metadata saved to: {metadata_file}")

    # Validation gate
    print("\n" + "=" * 60)
    if zero_var == 0 and n_positive > 50 and n_negative > 100:
        print("VALIDATION: PASS")
        print("Training data ready for model training.")
    else:
        print("VALIDATION: WARNING")
        if zero_var > 0:
            print(f"  - {zero_var} zero-variance features detected")
        if n_positive < 50:
            print(f"  - Only {n_positive} positive samples (need 50+)")
        if n_negative < 100:
            print(f"  - Only {n_negative} negative samples (need 100+)")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
