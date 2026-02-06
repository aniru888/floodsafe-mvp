"""
Test Sentinel-1 SAR Fetcher on Delhi Monsoon 2023.

Validates SAR flood detection by comparing:
1. Dry season (March 2023) - should show normal backscatter
2. Monsoon flood event (July 2023 Delhi floods) - should show reduced backscatter

Expected Results:
- VV backscatter decreases by 3+ dB over flooded areas
- Flood fraction > 0 during monsoon events
- Clear difference between baseline and flood imagery
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
import logging
from src.data.sentinel1_sar import Sentinel1SARFetcher, get_sar_features_at_point
from src.data.gee_client import gee_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Delhi test locations from hotspots
DELHI_TEST_LOCATIONS = [
    {
        "name": "Minto Bridge",
        "lat": 28.6365,
        "lng": 77.2224,
        "description": "Historic flood-prone underpass, Central Delhi",
    },
    {
        "name": "Pul Prahladpur",
        "lat": 28.5025,
        "lng": 77.2917,
        "description": "Major waterlogging hotspot, South Delhi",
    },
    {
        "name": "ITO",
        "lat": 28.6289,
        "lng": 77.2403,
        "description": "Central Delhi near Yamuna",
    },
    {
        "name": "Dwarka Underpass",
        "lat": 28.5826,
        "lng": 77.0533,
        "description": "West Delhi, frequent waterlogging",
    },
    {
        "name": "Azadpur",
        "lat": 28.7135,
        "lng": 77.1732,
        "description": "North Delhi, low-lying area",
    },
]

# Test periods
DRY_PERIOD = {
    "start": datetime(2023, 3, 1),
    "end": datetime(2023, 3, 31),
    "name": "March 2023 (Dry Season)",
}

MONSOON_FLOOD_PERIOD = {
    "start": datetime(2023, 7, 8),
    "end": datetime(2023, 7, 15),
    "name": "July 2023 Delhi Floods",
}


def test_sar_at_location(location: dict) -> dict:
    """Test SAR data for a single location during dry and flood periods."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing: {location['name']}")
    logger.info(f"Coordinates: ({location['lat']}, {location['lng']})")
    logger.info(f"Description: {location['description']}")
    logger.info("="*60)

    # Create bounds (500m buffer)
    buffer_deg = 0.005  # ~500m
    bounds = (
        location["lat"] - buffer_deg,
        location["lng"] - buffer_deg,
        location["lat"] + buffer_deg,
        location["lng"] + buffer_deg,
    )

    fetcher = Sentinel1SARFetcher()
    results = {"location": location["name"]}

    # Test dry period
    logger.info(f"\n--- {DRY_PERIOD['name']} ---")
    try:
        dry_data = fetcher.fetch(
            bounds,
            DRY_PERIOD["start"],
            DRY_PERIOD["end"],
        )
        results["dry"] = dry_data
        logger.info(f"  VV mean: {dry_data.get('vv_mean', 'N/A'):.2f} dB" if dry_data.get('vv_mean') else "  VV mean: N/A")
        logger.info(f"  VH mean: {dry_data.get('vh_mean', 'N/A'):.2f} dB" if dry_data.get('vh_mean') else "  VH mean: N/A")
        logger.info(f"  Images: {dry_data.get('image_count', 0)}")
    except Exception as e:
        logger.error(f"  Dry period fetch failed: {e}")
        results["dry"] = None

    # Test monsoon flood period
    logger.info(f"\n--- {MONSOON_FLOOD_PERIOD['name']} ---")
    try:
        flood_data = fetcher.fetch(
            bounds,
            MONSOON_FLOOD_PERIOD["start"],
            MONSOON_FLOOD_PERIOD["end"],
        )
        results["flood"] = flood_data
        logger.info(f"  VV mean: {flood_data.get('vv_mean', 'N/A'):.2f} dB" if flood_data.get('vv_mean') else "  VV mean: N/A")
        logger.info(f"  VH mean: {flood_data.get('vh_mean', 'N/A'):.2f} dB" if flood_data.get('vh_mean') else "  VH mean: N/A")
        logger.info(f"  VV change: {flood_data.get('change_vv_mean', 'N/A'):.2f} dB" if flood_data.get('change_vv_mean') else "  VV change: N/A")
        logger.info(f"  Flood fraction: {flood_data.get('flood_fraction', 0):.2%}")
        logger.info(f"  Images: {flood_data.get('image_count', 0)}")
    except Exception as e:
        logger.error(f"  Flood period fetch failed: {e}")
        results["flood"] = None

    # Compare dry vs flood
    if results.get("dry") and results.get("flood"):
        dry_vv = results["dry"].get("vv_mean")
        flood_vv = results["flood"].get("vv_mean")
        if dry_vv and flood_vv:
            vv_change = flood_vv - dry_vv
            logger.info(f"\n--- COMPARISON ---")
            logger.info(f"  VV change (flood - dry): {vv_change:.2f} dB")
            if vv_change < -3:
                logger.info(f"  FLOOD DETECTED (>3 dB decrease)")
                results["flood_detected"] = True
            else:
                logger.info(f"  No significant flood signal")
                results["flood_detected"] = False

    return results


def test_sar_feature_extraction():
    """Test the ML feature extraction convenience function."""
    logger.info("\n" + "="*60)
    logger.info("Testing SAR Feature Extraction for ML")
    logger.info("="*60)

    location = DELHI_TEST_LOCATIONS[0]  # Minto Bridge
    logger.info(f"Location: {location['name']}")

    # Test during flood period
    try:
        features = get_sar_features_at_point(
            lat=location["lat"],
            lng=location["lng"],
            reference_date=MONSOON_FLOOD_PERIOD["end"],
        )
        logger.info("\nExtracted SAR features for ML:")
        for key, value in features.items():
            logger.info(f"  {key}: {value:.4f}")
        return features
    except Exception as e:
        logger.error(f"Feature extraction failed: {e}")
        return None


def main():
    """Run all SAR tests."""
    logger.info("="*60)
    logger.info("SENTINEL-1 SAR FETCHER TEST")
    logger.info("Testing flood detection on Delhi monsoon 2023")
    logger.info("="*60)

    # Initialize GEE
    logger.info("\nInitializing Google Earth Engine...")
    try:
        gee_client.initialize()
        logger.info("GEE initialized successfully")
    except Exception as e:
        logger.error(f"GEE initialization failed: {e}")
        logger.error("Make sure you have valid GEE credentials configured.")
        return

    # Test each location
    all_results = []
    for location in DELHI_TEST_LOCATIONS:
        result = test_sar_at_location(location)
        all_results.append(result)

    # Test feature extraction
    features = test_sar_feature_extraction()

    # Summary
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)

    flood_detected_count = sum(1 for r in all_results if r.get("flood_detected"))
    logger.info(f"Locations tested: {len(all_results)}")
    logger.info(f"Flood signals detected: {flood_detected_count}/{len(all_results)}")

    if features:
        logger.info(f"\nML Feature Vector (4 SAR features):")
        logger.info(f"  sar_vv_mean:        {features.get('sar_vv_mean', 0):.2f} dB")
        logger.info(f"  sar_vh_mean:        {features.get('sar_vh_mean', 0):.2f} dB")
        logger.info(f"  sar_vv_vh_ratio:    {features.get('sar_vv_vh_ratio', 0):.2f}")
        logger.info(f"  sar_change_mag:     {features.get('sar_change_magnitude', 0):.2f} dB")

    # Validation check
    logger.info("\n" + "-"*60)
    if flood_detected_count > 0:
        logger.info("SAR FLOOD DETECTION: WORKING")
        logger.info("The SAR fetcher successfully detected flood signals")
        logger.info("during the July 2023 Delhi monsoon event.")
    else:
        logger.info("SAR FLOOD DETECTION: CHECK REQUIRED")
        logger.info("No flood signals detected. This could mean:")
        logger.info("1. The specific locations didn't flood significantly")
        logger.info("2. SAR thresholds need adjustment")
        logger.info("3. Data availability issues")

    logger.info("-"*60)


if __name__ == "__main__":
    main()
