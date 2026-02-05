"""
Terrain Heuristic Validation Script.

Tests whether the terrain susceptibility formula can identify known flood hotspots.

Purpose: Validate the terrain-based approach BEFORE scaling to full grid discovery.

Success Criteria:
    - >=80% of known hotspots score > 0.5 -> PASS (proceed to Phase 2)
    - <80% -> FAIL (adjust formula weights or approach)

Usage:
    cd apps/ml-service
    python scripts/validate_terrain_heuristic.py
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np

# Import GEE data fetchers
import ee
from src.data.gee_client import gee_client
from src.data.landcover import LandcoverFetcher
from src.features.terrain_indices import TerrainIndicesCalculator
from src.core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Delhi-specific normalization ranges (from analysis of 62 hotspots)
NORMALIZATION_RANGES = {
    "tpi": (-15, 15),          # meters; negative = valley
    "twi": (5, 20),            # unitless; high = water accumulation
    "elevation": (190, 320),   # meters; Delhi plateau
    "slope": (0, 15),          # degrees; most of Delhi is <5
    "impervious_pct": (0, 100), # percent
}


def normalize(value: float, min_val: float, max_val: float, invert: bool = False) -> float:
    """
    Normalize value to 0-1 range.

    Args:
        value: Raw value
        min_val: Minimum expected value
        max_val: Maximum expected value
        invert: If True, high values become low risk (e.g., elevation)

    Returns:
        Normalized value in [0, 1]
    """
    if max_val == min_val:
        return 0.5

    normalized = (value - min_val) / (max_val - min_val)
    normalized = max(0.0, min(1.0, normalized))  # Clamp to [0,1]

    return 1.0 - normalized if invert else normalized


def calculate_terrain_susceptibility(features: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
    """
    Calculate terrain-based flood susceptibility score.

    Formula (physics-based heuristic):
        susceptibility = (
            0.35 * normalize(TPI, invert=True) +   # Negative TPI = valley = HIGH risk
            0.30 * normalize(TWI) +                 # High TWI = water accumulation = HIGH
            0.20 * normalize(elevation, invert=True) +  # Low elevation = HIGH risk
            0.10 * normalize(impervious_pct) +      # Paved surfaces = no drainage = HIGH
            0.05 * normalize(slope, invert=True)    # Flat areas = pooling = HIGH
        )

    Args:
        features: Dict with tpi, twi, elevation, slope, impervious_pct

    Returns:
        (susceptibility_score, component_scores)
    """
    tpi = features.get("tpi", 0)
    twi = features.get("twi", 10)
    elevation = features.get("elevation", 250)
    slope = features.get("slope", 2)
    impervious_pct = features.get("impervious_pct", 50)

    # Calculate normalized components
    components = {
        "tpi_risk": normalize(tpi, *NORMALIZATION_RANGES["tpi"], invert=True),
        "twi_risk": normalize(twi, *NORMALIZATION_RANGES["twi"], invert=False),
        "elevation_risk": normalize(elevation, *NORMALIZATION_RANGES["elevation"], invert=True),
        "impervious_risk": normalize(impervious_pct, *NORMALIZATION_RANGES["impervious_pct"], invert=False),
        "slope_risk": normalize(slope, *NORMALIZATION_RANGES["slope"], invert=True),
    }

    # Weighted sum
    susceptibility = (
        0.35 * components["tpi_risk"] +
        0.30 * components["twi_risk"] +
        0.20 * components["elevation_risk"] +
        0.10 * components["impervious_risk"] +
        0.05 * components["slope_risk"]
    )

    return susceptibility, components


def extract_elevation_slope(lat: float, lng: float, buffer_m: int = 500) -> Dict[str, float]:
    """
    Extract elevation and slope at a point using direct GEE query.

    This bypasses the DEM fetcher's sample() method which fails for small regions.
    """
    try:
        gee_client.initialize()

        # Get DEM
        dem = ee.Image(settings.GEE_DEM)

        # Create buffer geometry
        point = ee.Geometry.Point([lng, lat])
        buffer = point.buffer(buffer_m)

        # Get terrain products (includes slope)
        terrain = ee.Terrain.products(dem)

        # Reduce to mean values
        result = terrain.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffer,
            scale=30,
            maxPixels=10000
        ).getInfo()

        return {
            "elevation": result.get("elevation", 250),
            "slope": result.get("slope", 2),
        }
    except Exception as e:
        logger.warning(f"Direct DEM fetch failed for ({lat}, {lng}): {e}")
        return {"elevation": 250, "slope": 2}


def extract_terrain_features(
    lat: float,
    lng: float,
    landcover_fetcher: LandcoverFetcher,
    terrain_calc: TerrainIndicesCalculator,
) -> Dict[str, float]:
    """
    Extract terrain features for a single point.

    Args:
        lat, lng: Coordinates
        landcover_fetcher: Land cover fetcher
        terrain_calc: Terrain indices calculator

    Returns:
        Dict with elevation, slope, tpi, twi, impervious_pct
    """
    features = {}

    # Get elevation and slope using direct GEE query (reliable method)
    try:
        elev_slope = extract_elevation_slope(lat, lng, buffer_m=300)
        features["elevation"] = elev_slope.get("elevation", 250)
        features["slope"] = elev_slope.get("slope", 2)
    except Exception as e:
        logger.warning(f"Elevation/slope fetch failed for ({lat}, {lng}): {e}")
        features["elevation"] = 250
        features["slope"] = 2

    # Get terrain indices (TPI, TRI, TWI, SPI)
    try:
        terrain = terrain_calc.get_terrain_indices_at_point(lat, lng, buffer_km=0.3)
        features["tpi"] = terrain.get("tpi", 0)
        features["tri"] = terrain.get("tri", 0)
        features["twi"] = terrain.get("twi", 10)
        features["spi"] = terrain.get("spi", 0)
    except Exception as e:
        logger.warning(f"Terrain indices fetch failed for ({lat}, {lng}): {e}")
        features.update({"tpi": 0, "tri": 0, "twi": 10, "spi": 0})

    # Get land cover (impervious percentage)
    try:
        landcover = landcover_fetcher.get_landcover_at_point(lat, lng, buffer_m=300)
        built_up = landcover.get("built_up", 0)
        bare = landcover.get("bare_sparse", 0)
        features["impervious_pct"] = built_up + bare
        features["built_up_pct"] = built_up
    except Exception as e:
        logger.warning(f"Landcover fetch failed for ({lat}, {lng}): {e}")
        features["impervious_pct"] = 50
        features["built_up_pct"] = 50

    return features


def load_hotspots() -> List[Dict]:
    """Load 62 Delhi waterlogging hotspots."""
    hotspots_file = project_root / "data" / "delhi_waterlogging_hotspots.json"

    with open(hotspots_file) as f:
        data = json.load(f)

    return data["hotspots"]


def run_validation():
    """Main validation function."""
    print("\n" + "=" * 70)
    print("TERRAIN HEURISTIC VALIDATION")
    print("Testing flood susceptibility formula on 62 known Delhi hotspots")
    print("=" * 70)

    # Load hotspots
    hotspots = load_hotspots()
    print(f"\nLoaded {len(hotspots)} hotspots from delhi_waterlogging_hotspots.json")

    # Initialize fetchers
    print("\nInitializing GEE data fetchers...")
    gee_client.initialize()
    landcover_fetcher = LandcoverFetcher()
    terrain_calc = TerrainIndicesCalculator()

    # Process each hotspot
    results = []
    high_score_count = 0
    total_processed = 0

    print("\n" + "-" * 70)
    print("Processing hotspots (this may take ~8 minutes for 62 locations)...")
    print("-" * 70)

    for i, hotspot in enumerate(hotspots):
        name = hotspot["name"]
        lat = hotspot["lat"]
        lng = hotspot["lng"]
        zone = hotspot.get("zone", "unknown")

        print(f"\n[{i+1}/{len(hotspots)}] {name}")
        print(f"  Location: ({lat:.4f}, {lng:.4f}) - Zone: {zone}")

        try:
            # Extract terrain features
            features = extract_terrain_features(
                lat, lng,
                landcover_fetcher, terrain_calc
            )

            # Calculate susceptibility
            susceptibility, components = calculate_terrain_susceptibility(features)

            # Record result
            result = {
                "id": hotspot["id"],
                "name": name,
                "lat": lat,
                "lng": lng,
                "zone": zone,
                "features": features,
                "components": components,
                "susceptibility": susceptibility,
                "passes_threshold": susceptibility > 0.5,
            }
            results.append(result)

            if susceptibility > 0.5:
                high_score_count += 1
                status = "PASS"
            else:
                status = "FAIL"

            total_processed += 1

            print(f"  Elevation: {features.get('elevation', 'N/A'):.1f}m")
            print(f"  TPI: {features.get('tpi', 'N/A'):.2f} (risk: {components['tpi_risk']:.2f})")
            print(f"  TWI: {features.get('twi', 'N/A'):.2f} (risk: {components['twi_risk']:.2f})")
            print(f"  Impervious: {features.get('impervious_pct', 'N/A'):.1f}%")
            print(f"  -> Susceptibility: {susceptibility:.3f} [{status}]")

        except Exception as e:
            logger.error(f"Failed to process {name}: {e}")
            results.append({
                "id": hotspot["id"],
                "name": name,
                "lat": lat,
                "lng": lng,
                "error": str(e),
            })

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)

    pass_rate = (high_score_count / total_processed * 100) if total_processed > 0 else 0

    print(f"\nProcessed: {total_processed}/{len(hotspots)} hotspots")
    print(f"Scoring > 0.5: {high_score_count}/{total_processed} ({pass_rate:.1f}%)")

    # Score distribution
    scores = [r["susceptibility"] for r in results if "susceptibility" in r]
    if scores:
        print(f"\nScore Distribution:")
        print(f"  Min: {min(scores):.3f}")
        print(f"  Max: {max(scores):.3f}")
        print(f"  Mean: {np.mean(scores):.3f}")
        print(f"  Median: {np.median(scores):.3f}")
        print(f"  Std Dev: {np.std(scores):.3f}")

    # By zone analysis
    print(f"\nBy Zone:")
    zones = {}
    for r in results:
        if "susceptibility" in r:
            zone = r.get("zone", "unknown")
            if zone not in zones:
                zones[zone] = {"scores": [], "passes": 0, "total": 0}
            zones[zone]["scores"].append(r["susceptibility"])
            zones[zone]["total"] += 1
            if r["passes_threshold"]:
                zones[zone]["passes"] += 1

    for zone, data in sorted(zones.items()):
        avg_score = np.mean(data["scores"])
        pass_pct = data["passes"] / data["total"] * 100 if data["total"] > 0 else 0
        print(f"  {zone}: {data['passes']}/{data['total']} pass ({pass_pct:.0f}%), avg score: {avg_score:.3f}")

    # Failed hotspots (for debugging)
    failed = [r for r in results if "susceptibility" in r and not r["passes_threshold"]]
    if failed:
        print(f"\nLow-Scoring Hotspots (< 0.5):")
        for r in sorted(failed, key=lambda x: x["susceptibility"]):
            print(f"  {r['name']}: {r['susceptibility']:.3f}")
            print(f"    TPI: {r['features'].get('tpi', 'N/A'):.2f}, TWI: {r['features'].get('twi', 'N/A'):.2f}")

    # VERDICT
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    if pass_rate >= 80:
        print(f"\n  [PASS] Terrain heuristic validates on {pass_rate:.1f}% of known hotspots")
        print("  -> Proceed to Phase 2: Pilot Grid in ring_road zone")
    elif pass_rate >= 60:
        print(f"\n  [PARTIAL] Terrain heuristic validates on {pass_rate:.1f}% of hotspots")
        print("  -> Consider adjusting formula weights")
        print("  -> May proceed with caution to Phase 2")
    else:
        print(f"\n  [FAIL] Terrain heuristic only validates on {pass_rate:.1f}% of hotspots")
        print("  -> Terrain alone is NOT sufficient for discovery")
        print("  -> Consider alternative approaches (crowdsourcing, more training data)")

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_hotspots": len(hotspots),
        "processed": total_processed,
        "passing_threshold": high_score_count,
        "pass_rate_pct": pass_rate,
        "threshold": 0.5,
        "success_criteria": ">=80% pass rate",
        "verdict": "PASS" if pass_rate >= 80 else ("PARTIAL" if pass_rate >= 60 else "FAIL"),
        "score_stats": {
            "min": float(min(scores)) if scores else None,
            "max": float(max(scores)) if scores else None,
            "mean": float(np.mean(scores)) if scores else None,
            "median": float(np.median(scores)) if scores else None,
            "std": float(np.std(scores)) if scores else None,
        },
        "by_zone": {
            zone: {
                "count": data["total"],
                "passes": data["passes"],
                "pass_rate_pct": data["passes"] / data["total"] * 100 if data["total"] > 0 else 0,
                "avg_score": float(np.mean(data["scores"])),
            }
            for zone, data in zones.items()
        },
        "hotspot_results": results,
        "normalization_ranges": NORMALIZATION_RANGES,
        "formula_weights": {
            "tpi": 0.35,
            "twi": 0.30,
            "elevation": 0.20,
            "impervious_pct": 0.10,
            "slope": 0.05,
        },
    }

    output_file = project_root / "terrain_validation_results.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {output_file}")
    print("=" * 70)

    return output


if __name__ == "__main__":
    results = run_validation()
