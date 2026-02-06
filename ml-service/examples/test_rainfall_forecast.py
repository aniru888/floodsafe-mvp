"""
Example: Fetch Real Rainfall Forecasts

Demonstrates using RainfallForecastFetcher to get live forecast data
from Open-Meteo API for major Indian cities.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.rainfall_forecast import RainfallForecastFetcher, RainfallForecastError
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Fetch rainfall forecasts for major Indian cities."""

    cities = {
        'Delhi': (28.6139, 77.2090),
        'Mumbai': (19.0760, 72.8777),
        'Bangalore': (12.9716, 77.5946),
        'Chennai': (13.0827, 80.2707),
        'Kolkata': (22.5726, 88.3639),
    }

    fetcher = RainfallForecastFetcher(timeout_seconds=30.0)

    print("\n" + "="*80)
    print("RAINFALL FORECAST FOR MAJOR INDIAN CITIES")
    print("="*80 + "\n")

    for city_name, (lat, lon) in cities.items():
        try:
            logger.info(f"Fetching forecast for {city_name}...")

            # Get 3-day forecast
            forecast = fetcher.get_forecast(lat, lon, forecast_days=3)

            # Display results
            print(f"\n{city_name} ({lat:.4f}, {lon:.4f})")
            print("-" * 60)
            print(f"  Next 24h:     {forecast.rain_forecast_24h:6.1f} mm")
            print(f"  24-48h:       {forecast.rain_forecast_48h:6.1f} mm")
            print(f"  48-72h:       {forecast.rain_forecast_72h:6.1f} mm")
            print(f"  3-day total:  {forecast.rain_forecast_total_3d:6.1f} mm")
            print(f"  Peak intensity: {forecast.hourly_max:6.2f} mm/h")
            print(f"  Max probability: {forecast.probability_max_3d:5.0f}%")
            print(f"  Category:     {forecast.get_intensity_category().upper().replace('_', ' ')}")
            print(f"  Source:       {forecast.source}")
            print(f"  Fetched:      {forecast.fetched_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")

            # Alert if heavy rainfall expected
            category = forecast.get_intensity_category()
            if category in ['heavy', 'very_heavy', 'extremely_heavy']:
                print(f"\n  ⚠️  ALERT: {category.upper().replace('_', ' ')} rainfall expected!")

        except RainfallForecastError as e:
            logger.error(f"Failed to fetch forecast for {city_name}: {e}")
            print(f"\n{city_name}: ERROR - {e}")

        except Exception as e:
            logger.error(f"Unexpected error for {city_name}: {e}")
            print(f"\n{city_name}: UNEXPECTED ERROR - {e}")

    # Show cache statistics
    print("\n" + "="*80)
    print("CACHE STATISTICS")
    print("="*80)
    stats = fetcher.get_cache_stats()
    print(f"  Total entries:   {stats['total_entries']}")
    print(f"  Valid entries:   {stats['valid_entries']}")
    print(f"  Expired entries: {stats['expired_entries']}")
    print(f"  TTL:             {stats['ttl_seconds']} seconds ({stats['ttl_seconds']/3600:.1f} hours)")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
