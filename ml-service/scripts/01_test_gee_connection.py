"""
Test Google Earth Engine connection.

Run this first to verify GEE authentication is working.
"""

import sys
sys.path.insert(0, '../')

from src.data.gee_client import gee_client
from src.core.config import settings

def test_gee_connection():
    """Test GEE initialization and basic query."""
    print("=" * 60)
    print("Testing Google Earth Engine Connection")
    print("=" * 60)

    # Initialize GEE
    print("\n1. Initializing GEE client...")
    try:
        gee_client.initialize()
        print("[OK] GEE initialized successfully!")
        print(f"  Project: {settings.GCP_PROJECT_ID}")
    except Exception as e:
        print(f"[FAIL] GEE initialization failed: {e}")
        print("\nTo authenticate, run:")
        print("  earthengine authenticate")
        return False

    # Test basic query - get AlphaEarth info
    print("\n2. Testing dataset access...")
    try:
        import ee
        collection = ee.ImageCollection(settings.GEE_ALPHAEARTH)
        count = collection.size().getInfo()
        print(f"[OK] AlphaEarth dataset accessible!")
        print(f"  Images available: {count}")
    except Exception as e:
        print(f"[FAIL] Dataset access failed: {e}")
        return False

    # Test data fetching for Delhi
    print("\n3. Testing data fetch for Delhi...")
    try:
        delhi_bounds = (28.4, 76.8, 28.9, 77.4)  # Delhi NCR
        geometry = gee_client.bounds_to_geometry(delhi_bounds)

        # Get a single image
        image = collection.filterDate('2023-01-01', '2023-12-31').first()

        # Sample a point
        point = gee_client.point_to_geometry(28.6139, 77.2090)  # Connaught Place
        sample = image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point.buffer(100),
            scale=10,
            maxPixels=1e6
        ).getInfo()

        print(f"[OK] Successfully fetched data!")
        print(f"  Location: Connaught Place, Delhi")
        print(f"  Sample bands: {list(sample.keys())[:3]}...")

    except Exception as e:
        print(f"[FAIL] Data fetch failed: {e}")
        return False

    print("\n" + "=" * 60)
    print("[SUCCESS] All GEE tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_gee_connection()
    sys.exit(0 if success else 1)
