"""
Fetch sample data from all sources for Delhi.

This demonstrates how to use all the data fetchers.
"""

import sys
sys.path.insert(0, '../')

from src.data.alphaearth import AlphaEarthFetcher
from src.data.dem_fetcher import DEMFetcher
from src.data.precipitation import PrecipitationFetcher
from src.data.surface_water import SurfaceWaterFetcher
from src.data.landcover import LandcoverFetcher
from datetime import datetime
import numpy as np

def fetch_sample_data():
    """Fetch sample data from all sources for Delhi."""
    print("=" * 60)
    print("Fetching Sample Data for Delhi NCR")
    print("=" * 60)

    delhi_bounds = (28.4, 76.8, 28.9, 77.4)
    delhi_point = (28.6139, 77.2090)  # Connaught Place

    # 1. AlphaEarth Embeddings
    print("\n1. Fetching AlphaEarth embeddings...")
    try:
        alphaearth = AlphaEarthFetcher()
        embedding = alphaearth.get_embedding_at_point(
            delhi_point[0], delhi_point[1], year=2023
        )
        print(f"✓ AlphaEarth embeddings: shape {embedding.shape}")
        print(f"  Sample values: {embedding[:5]}")
    except Exception as e:
        print(f"✗ AlphaEarth failed: {e}")

    # 2. DEM/Terrain
    print("\n2. Fetching terrain features...")
    try:
        dem = DEMFetcher()
        terrain = dem.get_terrain_features(delhi_bounds)
        print(f"✓ Terrain features:")
        for key, value in terrain.items():
            print(f"  {key}: {value:.2f}")
    except Exception as e:
        print(f"✗ DEM failed: {e}")

    # 3. Surface Water
    print("\n3. Fetching surface water data...")
    try:
        water = SurfaceWaterFetcher()
        water_features = water.get_water_features(delhi_bounds)
        print(f"✓ Surface water features:")
        print(f"  Water occurrence: {water_features['water_occurrence']:.2f}%")
        print(f"  Permanent water: {water_features['permanent_water_pct']:.2f}%")
        print(f"  Seasonal water: {water_features['seasonal_water_pct']:.2f}%")
    except Exception as e:
        print(f"✗ Surface water failed: {e}")

    # 4. Precipitation
    print("\n4. Fetching precipitation data...")
    try:
        precip = PrecipitationFetcher()
        reference_date = datetime(2023, 7, 15)  # Mid-monsoon
        rainfall = precip.get_rainfall_features(delhi_bounds, reference_date)
        print(f"✓ Rainfall features (July 15, 2023):")
        print(f"  Last 24h: {rainfall['rainfall_24h']:.1f}mm")
        print(f"  Last 7d: {rainfall['rainfall_7d']:.1f}mm")
        print(f"  Wet days: {rainfall['wet_days_7d']}")
    except Exception as e:
        print(f"✗ Precipitation failed: {e}")

    # 5. Landcover
    print("\n5. Fetching landcover data...")
    try:
        landcover = LandcoverFetcher()
        land_features = landcover.get_landcover_features(delhi_bounds)
        print(f"✓ Landcover features:")
        print(f"  Built-up: {land_features['built_up_pct']:.1f}%")
        print(f"  Vegetation: {land_features['vegetation_pct']:.1f}%")
        print(f"  Water: {land_features['water_pct']:.1f}%")
    except Exception as e:
        print(f"✗ Landcover failed: {e}")

    print("\n" + "=" * 60)
    print("Data fetching complete!")
    print("=" * 60)


if __name__ == "__main__":
    fetch_sample_data()
