"""
Example Usage: DEM and Surface Water Fetchers

Demonstrates how to use the DEMFetcher and SurfaceWaterFetcher
for flood risk analysis in Delhi NCR.
"""

import sys
from pathlib import Path

# Add parent src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.dem_fetcher import dem_fetcher
from data.surface_water import surface_water_fetcher
from core.config import REGIONS

# Delhi NCR bounds
delhi_bounds = REGIONS["delhi"]["bounds"]
delhi_center = REGIONS["delhi"]["center"]

print("FloodSafe ML Service - DEM & Surface Water Demo")
print("=" * 60)

# ============================================================================
# Example 1: Get terrain features for Delhi NCR
# ============================================================================
print("\n1. Fetching terrain features for Delhi NCR...")
print(f"   Bounds: {delhi_bounds}")

try:
    terrain_features = dem_fetcher.get_terrain_features(
        bounds=delhi_bounds,
        scale=100,  # 100m resolution for faster processing
    )

    print("\n   Terrain Features:")
    print(f"   - Mean Elevation: {terrain_features['elevation_mean']:.2f} m")
    print(f"   - Min Elevation: {terrain_features['elevation_min']:.2f} m")
    print(f"   - Max Elevation: {terrain_features['elevation_max']:.2f} m")
    print(f"   - Elevation Range: {terrain_features['elevation_range']:.2f} m")
    print(f"   - Mean Slope: {terrain_features['slope_mean']:.2f}°")
    print(f"   - Mean Aspect: {terrain_features['aspect_mean']:.2f}°")

except Exception as e:
    print(f"   Error: {e}")

# ============================================================================
# Example 2: Get elevation at a specific point (India Gate)
# ============================================================================
print("\n2. Fetching elevation at India Gate...")
india_gate_lat, india_gate_lng = 28.6129, 77.2295

try:
    elevation = dem_fetcher.get_elevation_at_point(
        lat=india_gate_lat,
        lng=india_gate_lng,
        buffer_radius_km=0.5,
    )

    print(f"   Location: ({india_gate_lat}, {india_gate_lng})")
    print(f"   Elevation: {elevation:.2f} m above sea level")

except Exception as e:
    print(f"   Error: {e}")

# ============================================================================
# Example 3: Get surface water features for Delhi NCR
# ============================================================================
print("\n3. Fetching surface water features for Delhi NCR...")

try:
    water_features = surface_water_fetcher.get_water_features(
        bounds=delhi_bounds,
        scale=100,
    )

    print("\n   Surface Water Features:")
    print(f"   - Mean Water Occurrence: {water_features['water_occurrence']:.2f}%")
    print(f"   - Max Water Occurrence: {water_features['water_occurrence_max']:.2f}%")
    print(f"   - Water Recurrence: {water_features['water_recurrence']:.2f}%")
    print(f"   - Water Seasonality: {water_features['water_seasonality']:.2f} months")
    print(f"\n   Water Classification:")
    print(f"   - Permanent Water: {water_features['permanent_water_pct']:.2f}%")
    print(f"   - Seasonal Water: {water_features['seasonal_water_pct']:.2f}%")
    print(f"   - Occasional Water: {water_features['occasional_water_pct']:.2f}%")
    print(f"   - No Water: {water_features['no_water_pct']:.2f}%")

except Exception as e:
    print(f"   Error: {e}")

# ============================================================================
# Example 4: Get water info at Yamuna River location
# ============================================================================
print("\n4. Fetching water info at Yamuna River location...")
yamuna_lat, yamuna_lng = 28.6562, 77.2410

try:
    water_info = surface_water_fetcher.get_water_at_point(
        lat=yamuna_lat,
        lng=yamuna_lng,
        buffer_radius_km=0.5,
    )

    print(f"   Location: ({yamuna_lat}, {yamuna_lng})")
    print(f"   Water Occurrence: {water_info['occurrence']:.2f}%")
    print(f"   Water Recurrence: {water_info['recurrence']:.2f}%")
    print(f"   Water Seasonality: {water_info['seasonality']:.2f} months")
    print(f"   Water Type: {water_info['water_type']}")

except Exception as e:
    print(f"   Error: {e}")

# ============================================================================
# Example 5: Combined Analysis - Flood Risk Indicators
# ============================================================================
print("\n5. Combined Analysis - Flood Risk Indicators...")
print("   (Low elevation + high water occurrence = higher flood risk)")

# Sample location: Near Yamuna floodplain
analysis_lat, analysis_lng = 28.6700, 77.2400

try:
    # Get elevation
    elevation = dem_fetcher.get_elevation_at_point(
        lat=analysis_lat,
        lng=analysis_lng,
        buffer_radius_km=0.3,
    )

    # Get water info
    water_info = surface_water_fetcher.get_water_at_point(
        lat=analysis_lat,
        lng=analysis_lng,
        buffer_radius_km=0.3,
    )

    print(f"\n   Analysis Point: ({analysis_lat}, {analysis_lng})")
    print(f"   Elevation: {elevation:.2f} m")
    print(f"   Water Occurrence: {water_info['occurrence']:.2f}%")
    print(f"   Water Type: {water_info['water_type']}")

    # Simple risk assessment
    risk_score = 0
    if elevation < 220:  # Below typical Delhi elevation
        risk_score += 2
        print(f"   ⚠ Low elevation (flood-prone)")
    if water_info['occurrence'] > 10:
        risk_score += 2
        print(f"   ⚠ Historical water presence detected")
    if water_info['water_type'] == 'seasonal':
        risk_score += 1
        print(f"   ⚠ Seasonal water area")

    if risk_score >= 3:
        print(f"\n   → HIGH FLOOD RISK (Score: {risk_score}/5)")
    elif risk_score >= 1:
        print(f"\n   → MODERATE FLOOD RISK (Score: {risk_score}/5)")
    else:
        print(f"\n   → LOW FLOOD RISK (Score: {risk_score}/5)")

except Exception as e:
    print(f"   Error: {e}")

# ============================================================================
# Notes
# ============================================================================
print("\n" + "=" * 60)
print("Notes:")
print("- First run requires GEE authentication (ee.Authenticate())")
print("- Data is cached locally for faster subsequent access")
print("- DEM cache TTL: 365 days (terrain rarely changes)")
print("- Surface Water cache TTL: 30 days")
print("- Use scale parameter to balance speed vs. resolution")
print("=" * 60)
