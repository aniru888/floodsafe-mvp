"""
Quick syntax check for DEM and Surface Water fetchers.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from data.dem_fetcher import DEMFetcher, dem_fetcher
    print("✓ dem_fetcher.py imports successfully")

    from data.surface_water import SurfaceWaterFetcher, surface_water_fetcher
    print("✓ surface_water.py imports successfully")

    # Check class structure
    assert hasattr(dem_fetcher, 'source_name')
    assert hasattr(dem_fetcher, 'cache_ttl_days')
    assert hasattr(dem_fetcher, 'get_terrain_features')
    assert hasattr(dem_fetcher, 'get_elevation_at_point')
    print("✓ DEMFetcher has all required methods")

    assert hasattr(surface_water_fetcher, 'source_name')
    assert hasattr(surface_water_fetcher, 'cache_ttl_days')
    assert hasattr(surface_water_fetcher, 'get_water_features')
    assert hasattr(surface_water_fetcher, 'get_water_at_point')
    print("✓ SurfaceWaterFetcher has all required methods")

    print("\n✓ All syntax checks passed!")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
