"""
Explore flood-related datasets available in Google Earth Engine.

These can be used as labels for training without external data!
"""

import sys
sys.path.insert(0, '../')

from src.data.gee_client import gee_client
import ee

def explore_flood_datasets():
    """Find and test flood datasets in GEE."""
    print("=" * 60)
    print("Exploring GEE Flood Datasets")
    print("=" * 60)

    gee_client.initialize()

    # 1. Global Flood Database (NASA)
    print("\n1. NASA Global Flood Database")
    print("-" * 60)
    try:
        # Note: This is a hypothetical - need to check actual collection name
        # Common flood datasets in GEE:
        # - MODIS/006/MOD09GA (can detect water bodies)
        # - JRC/GSW1_4/GlobalSurfaceWater (historical water occurrence)
        # - COPERNICUS/S1_GRD (Sentinel-1 SAR - can detect floods)

        # Let's use JRC Surface Water as a proxy
        water = ee.Image('JRC/GSW1_4/GlobalSurfaceWater')
        print("[OK] JRC Global Surface Water available")
        print("  Bands:", water.bandNames().getInfo())
        print("  Can use 'occurrence' band as flood proxy")
        print("  High occurrence (>80) = flood-prone area")
    except Exception as e:
        print(f"[INFO] {e}")

    # 2. Sentinel-1 SAR for Flood Detection
    print("\n2. Sentinel-1 SAR (Flood Detection)")
    print("-" * 60)
    try:
        s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
        count = s1.filterDate('2023-07-01', '2023-07-31').size().getInfo()
        print(f"[OK] Sentinel-1 available: {count} images in July 2023")
        print("  Can compare pre/post flood SAR backscatter")
        print("  Sudden decrease in VV polarization = water/flood")
    except Exception as e:
        print(f"[FAIL] {e}")

    # 3. MODIS for Water Detection
    print("\n3. MODIS Water Detection")
    print("-" * 60)
    try:
        modis = ee.ImageCollection('MODIS/006/MOD09GA')
        count = modis.filterDate('2023-07-01', '2023-07-31').size().getInfo()
        print(f"[OK] MODIS available: {count} images in July 2023")
        print("  Can use NDWI (Normalized Difference Water Index)")
        print("  High NDWI = water presence")
    except Exception as e:
        print(f"[FAIL] {e}")

    # 4. Create Labels from Precipitation Extremes
    print("\n4. Precipitation-Based Flood Proxy")
    print("-" * 60)
    try:
        chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
        delhi_bounds = ee.Geometry.Rectangle([76.8, 28.4, 77.4, 28.9])

        # Get extreme rainfall events
        july_2023 = chirps.filterDate('2023-07-01', '2023-07-31') \
                          .filterBounds(delhi_bounds)

        # Calculate daily stats
        def get_daily_rain(image):
            mean = image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=delhi_bounds,
                scale=5000
            ).get('precipitation')
            return image.set('daily_rain', mean)

        with_stats = july_2023.map(get_daily_rain)
        rain_list = with_stats.aggregate_array('daily_rain').getInfo()

        print(f"[OK] Got {len(rain_list)} days of rainfall data")
        print(f"  Max rainfall: {max(rain_list):.1f}mm")
        print(f"  Mean rainfall: {sum(rain_list)/len(rain_list):.1f}mm")
        print("\n  Flood label strategy:")
        print("  - Rainfall > 100mm = HIGH flood risk (label=1)")
        print("  - Rainfall 50-100mm = MEDIUM risk (label=0.5)")
        print("  - Rainfall < 50mm = LOW risk (label=0)")
    except Exception as e:
        print(f"[FAIL] {e}")

    print("\n" + "=" * 60)
    print("Flood Dataset Strategy Recommendations:")
    print("=" * 60)
    print("""
1. EASY - Use Precipitation Threshold:
   - Get CHIRPS rainfall data from GEE
   - Label: rainfall > 100mm = flood (1), else no flood (0)
   - Pro: Simple, all data from GEE
   - Con: Indirect proxy, not actual flood extent

2. MEDIUM - Use JRC Surface Water Change:
   - Compare historical water occurrence vs current
   - Sudden increase in water = flood event
   - Pro: Actual water detection
   - Con: Monthly data, not daily

3. ADVANCED - Use Sentinel-1 SAR:
   - Compare pre/post event radar backscatter
   - Water reflects radar differently than land
   - Pro: All-weather, detects actual floods
   - Con: Requires SAR processing knowledge

RECOMMENDATION: Start with #1 (precipitation threshold) for quick MVP,
then add #3 (SAR) for production accuracy.
    """)


if __name__ == "__main__":
    explore_flood_datasets()
