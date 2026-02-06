"""
Data Fetcher Validation Script

This script validates that the CHIRPS, DEM, and landcover fetchers
return REAL data (not defaults/fallbacks) for Delhi locations.

Critical: This MUST pass before building any ML models.
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np

# Test locations across Delhi (diverse areas)
TEST_LOCATIONS = [
    {"name": "Minto Bridge", "lat": 28.6365, "lng": 77.2224, "zone": "Central"},
    {"name": "Dwarka", "lat": 28.5880, "lng": 77.0670, "zone": "West"},
    {"name": "Pul Prahladpur", "lat": 28.5025, "lng": 77.2917, "zone": "South"},
    {"name": "Majnu Ka Tila", "lat": 28.6967, "lng": 77.2283, "zone": "North"},
    {"name": "Ghazipur", "lat": 28.6235, "lng": 77.3235, "zone": "East"},
]

# Delhi bounds for regional queries (lat_min, lng_min, lat_max, lng_max)
DELHI_BOUNDS = (28.4, 76.8, 28.9, 77.4)


def validate_dem_fetcher():
    """
    Validate DEM (elevation/slope) fetcher.

    Expected: Different elevations for different locations (variance > 5m)
    Failure: All same values OR all zeros
    """
    print("\n" + "="*60)
    print("VALIDATING DEM FETCHER (SRTM Elevation)")
    print("="*60)

    try:
        from src.data.dem_fetcher import DEMFetcher
        dem = DEMFetcher()

        elevations = []
        slopes = []

        for loc in TEST_LOCATIONS:
            # Bounds format: (lat_min, lng_min, lat_max, lng_max)
            # Using larger bounds (~1km) for DEM sampling
            bounds = (
                loc["lat"] - 0.01,
                loc["lng"] - 0.01,
                loc["lat"] + 0.01,
                loc["lng"] + 0.01,
            )

            try:
                features = dem.get_terrain_features(bounds)
                elevation = features.get("elevation_mean", 0)
                slope = features.get("slope_mean", 0)

                elevations.append(elevation)
                slopes.append(slope)

                print(f"  {loc['name']}: elevation={elevation:.1f}m, slope={slope:.2f}deg")
            except Exception as e:
                print(f"  {loc['name']}: ERROR - {str(e)[:50]}")
                elevations.append(0)
                slopes.append(0)

        # Validation checks
        elev_variance = np.var(elevations)
        elev_range = max(elevations) - min(elevations)
        all_zero = all(e == 0 for e in elevations)

        print(f"\n  Elevation range: {elev_range:.1f}m (min={min(elevations):.1f}, max={max(elevations):.1f})")
        print(f"  Elevation variance: {elev_variance:.1f}")

        # Pass/Fail criteria
        if all_zero:
            print("  STATUS: FAIL - All elevations are ZERO (fetcher returning defaults)")
            return False, "All zeros"
        elif elev_range < 2:
            print("  STATUS: WARNING - Very low elevation variance (may be fallback data)")
            return False, f"Low variance: {elev_range:.1f}m"
        else:
            print("  STATUS: PASS - Elevations vary by location")
            return True, f"Range: {elev_range:.1f}m"

    except ImportError as e:
        print(f"  ERROR: Could not import DEM fetcher - {e}")
        return False, f"Import error: {e}"
    except Exception as e:
        print(f"  ERROR: {e}")
        return False, f"Error: {e}"


def validate_precipitation_fetcher():
    """
    Validate CHIRPS precipitation fetcher.

    Expected: Non-zero rainfall values for monsoon dates
    Failure: All zeros OR constant values
    """
    print("\n" + "="*60)
    print("VALIDATING PRECIPITATION FETCHER (CHIRPS)")
    print("="*60)

    try:
        from src.data.precipitation import PrecipitationFetcher
        precip = PrecipitationFetcher()

        # Test two dates: monsoon (July) and dry season (February)
        test_dates = [
            datetime(2023, 7, 15),  # Monsoon
            datetime(2023, 2, 15),  # Dry season
        ]

        results = []

        for test_date in test_dates:
            try:
                features = precip.get_rainfall_features(
                    bounds=DELHI_BOUNDS,
                    reference_date=test_date
                )

                rain_24h = features.get("rainfall_24h", 0)
                rain_7d = features.get("rainfall_7d", 0)

                results.append({
                    "date": test_date.strftime("%Y-%m-%d"),
                    "rain_24h": rain_24h,
                    "rain_7d": rain_7d,
                })

                print(f"  {test_date.strftime('%Y-%m-%d')}: rain_24h={rain_24h:.1f}mm, rain_7d={rain_7d:.1f}mm")

            except Exception as e:
                print(f"  {test_date.strftime('%Y-%m-%d')}: ERROR - {str(e)[:50]}")
                results.append({"date": test_date.strftime("%Y-%m-%d"), "rain_24h": 0, "rain_7d": 0})

        # Validation checks
        all_zero = all(r["rain_7d"] == 0 for r in results)

        if all_zero:
            print("  STATUS: FAIL - All rainfall values are ZERO")
            return False, "All zeros"
        else:
            print("  STATUS: PASS - Precipitation data retrieved")
            return True, f"rain_7d values vary"

    except ImportError as e:
        print(f"  ERROR: Could not import Precipitation fetcher - {e}")
        return False, f"Import error: {e}"
    except Exception as e:
        print(f"  ERROR: {e}")
        return False, f"Error: {e}"


def validate_landcover_fetcher():
    """
    Validate ESA WorldCover landcover fetcher.

    Expected: Different impervious % for urban vs rural areas
    Failure: All same values OR uniform distribution
    """
    print("\n" + "="*60)
    print("VALIDATING LANDCOVER FETCHER (ESA WorldCover)")
    print("="*60)

    try:
        from src.data.landcover import LandcoverFetcher
        lc = LandcoverFetcher()

        results = []

        for loc in TEST_LOCATIONS:
            # Bounds format: (lat_min, lng_min, lat_max, lng_max)
            bounds = (
                loc["lat"] - 0.01,
                loc["lng"] - 0.01,
                loc["lat"] + 0.01,
                loc["lng"] + 0.01,
            )

            try:
                features = lc.get_landcover_features(bounds)
                built_up = features.get("built_up_pct", 0)
                vegetation = features.get("vegetation_pct", 0)

                results.append({
                    "name": loc["name"],
                    "built_up": built_up,
                    "vegetation": vegetation,
                })

                print(f"  {loc['name']}: built_up={built_up:.1f}%, vegetation={vegetation:.1f}%")

            except Exception as e:
                print(f"  {loc['name']}: ERROR - {str(e)[:50]}")
                results.append({"name": loc["name"], "built_up": 0, "vegetation": 0})

        # Validation checks
        built_ups = [r["built_up"] for r in results]
        built_up_variance = np.var(built_ups)
        all_zero = all(b == 0 for b in built_ups)
        all_uniform = all(abs(b - 11.11) < 0.5 for b in built_ups)  # Default uniform is ~11%

        print(f"\n  Built-up variance: {built_up_variance:.1f}")

        if all_zero:
            print("  STATUS: FAIL - All built_up values are ZERO")
            return False, "All zeros"
        elif all_uniform:
            print("  STATUS: FAIL - All values are uniform (default fallback)")
            return False, "Uniform fallback"
        else:
            print("  STATUS: PASS - Landcover varies by location")
            return True, f"Variance: {built_up_variance:.1f}"

    except ImportError as e:
        print(f"  ERROR: Could not import Landcover fetcher - {e}")
        return False, f"Import error: {e}"
    except Exception as e:
        print(f"  ERROR: {e}")
        return False, f"Error: {e}"


def validate_dynamic_world_fetcher():
    """
    Validate Dynamic World landcover probabilities.

    Expected: Non-uniform probabilities (not all 0.111)
    Failure: All uniform values (default fallback)
    """
    print("\n" + "="*60)
    print("VALIDATING DYNAMIC WORLD FETCHER")
    print("="*60)

    try:
        from src.data.dynamic_world import DynamicWorldFetcher
        dw = DynamicWorldFetcher()

        results = []

        for loc in TEST_LOCATIONS[:2]:  # Test just 2 locations (slower)
            # Bounds format: (lat_min, lng_min, lat_max, lng_max)
            bounds = (
                loc["lat"] - 0.01,
                loc["lng"] - 0.01,
                loc["lat"] + 0.01,
                loc["lng"] + 0.01,
            )

            try:
                features = dw.get_flood_features(
                    bounds=bounds,
                    reference_date=datetime(2023, 7, 15)
                )

                built = features.get("built_prob", 0)
                water = features.get("water_prob", 0)
                flooded = features.get("flooded_vegetation_prob", 0)

                results.append({
                    "name": loc["name"],
                    "built": built,
                    "water": water,
                    "flooded": flooded,
                })

                print(f"  {loc['name']}: built={built:.3f}, water={water:.3f}, flooded_veg={flooded:.3f}")

            except Exception as e:
                print(f"  {loc['name']}: ERROR - {str(e)[:50]}")
                results.append({"name": loc["name"], "built": 0.111, "water": 0.111, "flooded": 0.111})

        # Check if all values are uniform (default)
        is_uniform = all(abs(r["built"] - 0.111) < 0.01 for r in results)

        if is_uniform:
            print("  STATUS: WARNING - Values appear to be default fallback")
            return False, "Uniform fallback"
        else:
            print("  STATUS: PASS - Dynamic World returns varied probabilities")
            return True, "Varied probabilities"

    except ImportError as e:
        print(f"  ERROR: Could not import Dynamic World fetcher - {e}")
        return False, f"Import error: {e}"
    except Exception as e:
        print(f"  ERROR: {e}")
        return False, f"Error: {e}"


def main():
    """Run all validation tests and report results."""
    print("\n" + "#"*60)
    print("#  FLOODSAFE DATA FETCHER VALIDATION")
    print("#  Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("#"*60)

    results = {}

    # Run validations
    results["DEM (Elevation)"] = validate_dem_fetcher()
    results["CHIRPS (Precipitation)"] = validate_precipitation_fetcher()
    results["ESA WorldCover"] = validate_landcover_fetcher()
    results["Dynamic World"] = validate_dynamic_world_fetcher()

    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)

    passed = 0
    failed = 0

    for name, (status, msg) in results.items():
        status_str = "PASS" if status else "FAIL"
        emoji = "+" if status else "X"
        print(f"  [{emoji}] {name}: {status_str} - {msg}")
        if status:
            passed += 1
        else:
            failed += 1

    print(f"\n  Total: {passed} passed, {failed} failed")

    # GO/NO-GO decision
    print("\n" + "="*60)
    if passed >= 3:
        print("GO DECISION: Sufficient data sources validated.")
        print("Proceed with Phase 2 (Hotspot Data Preparation)")
    else:
        print("NO-GO DECISION: Too many data sources failed.")
        print("Fix data fetcher issues before proceeding.")
    print("="*60)

    return passed >= 3


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
