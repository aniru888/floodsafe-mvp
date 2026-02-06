"""
Test script for precipitation and ERA5 data fetchers.

Usage:
    python examples/test_data_fetchers.py
"""

from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.precipitation import PrecipitationFetcher
from src.data.era5_fetcher import ERA5Fetcher
from src.core.config import REGIONS


def test_precipitation():
    """Test precipitation fetcher."""
    print("=" * 60)
    print("Testing Precipitation Fetcher (CHIRPS)")
    print("=" * 60)

    fetcher = PrecipitationFetcher()

    # Delhi bounds
    delhi_bounds = REGIONS["delhi"]["bounds"]

    # Get data for last 10 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=10)

    print(f"\nFetching data for Delhi NCR")
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print(f"Bounds: {delhi_bounds}")

    try:
        # Test raw data fetch
        df = fetcher.fetch(delhi_bounds, start_date, end_date)
        print(f"\n✓ Fetched {len(df)} days of data")
        print(f"\nFirst 5 rows:")
        print(df.head())

        # Test rainfall features
        print("\n" + "-" * 60)
        print("Testing rainfall features...")
        features = fetcher.get_rainfall_features(
            bounds=delhi_bounds,
            reference_date=end_date,
            lookback_days=7,
        )

        print("\nRainfall Features:")
        for key, value in features.items():
            print(f"  {key}: {value}")

        print("\n✓ Precipitation fetcher working correctly!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_era5():
    """Test ERA5 fetcher."""
    print("\n" + "=" * 60)
    print("Testing ERA5 Land Fetcher")
    print("=" * 60)

    fetcher = ERA5Fetcher()

    # Delhi bounds
    delhi_bounds = REGIONS["delhi"]["bounds"]

    # ERA5 has ~5 day lag, so test older data
    end_date = datetime.now() - timedelta(days=6)
    start_date = end_date - timedelta(days=10)

    print(f"\nFetching data for Delhi NCR")
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print(f"Bounds: {delhi_bounds}")
    print("Note: ERA5-Land has ~5 day lag")

    try:
        # Test raw data fetch
        df = fetcher.fetch(delhi_bounds, start_date, end_date)
        print(f"\n✓ Fetched {len(df)} days of data")
        print(f"\nFirst 5 rows:")
        print(df.head())

        # Test weather features
        print("\n" + "-" * 60)
        print("Testing weather features...")
        features = fetcher.get_weather_features(
            bounds=delhi_bounds,
            reference_date=end_date,
            lookback_days=7,
        )

        print("\nWeather Features:")
        for key, value in features.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")

        # Test latest conditions
        print("\n" + "-" * 60)
        print("Testing latest conditions...")
        latest = fetcher.get_latest_conditions(delhi_bounds)

        print("\nLatest Conditions:")
        for key, value in latest.items():
            print(f"  {key}: {value:.2f}")

        print("\n✓ ERA5 fetcher working correctly!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all tests."""
    print("\nFloodSafe ML Service - Data Fetcher Tests")
    print("=" * 60)
    print("\nNOTE: These tests require:")
    print("  1. Google Earth Engine authentication (ee.Authenticate())")
    print("  2. Active internet connection")
    print("  3. GCP Project: gen-lang-client-0669818939")
    print("=" * 60)

    # Test precipitation
    test_precipitation()

    # Test ERA5
    test_era5()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
