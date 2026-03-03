"""
Compute monthly precipitation percentiles from 10 years of Open-Meteo historical data.

Usage:
    python apps/backend/scripts/compute_climate_percentiles.py

Output:
    apps/backend/data/{city}_climate_percentiles.json

Each JSON file contains monthly percentiles (P50, P75, P90, P95, P99) of daily
precipitation sum in mm. These are used by the FHI calculator for ceiling-only
threshold adjustments during peak wet months.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

try:
    import numpy as np
except ImportError:
    print("numpy required: pip install numpy")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("httpx required: pip install httpx")
    sys.exit(1)


# City centroids (representative point for climate data)
CITY_CENTROIDS = {
    "delhi": {"lat": 28.6139, "lng": 77.2090},
    "bangalore": {"lat": 12.9716, "lng": 77.5946},
    "yogyakarta": {"lat": -7.7956, "lng": 110.3695},
    "singapore": {"lat": 1.3521, "lng": 103.8198},
    "indore": {"lat": 22.7196, "lng": 75.8577},
}

# Open-Meteo Historical Weather API (free, no key needed)
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# 10-year period for stable percentiles
START_DATE = "2014-01-01"
END_DATE = "2023-12-31"

OUTPUT_DIR = Path(__file__).parent.parent / "data"


def fetch_historical_precip(city: str, lat: float, lng: float) -> list[dict]:
    """Fetch 10 years of daily precipitation from Open-Meteo Archive API."""
    print(f"  Fetching {city} ({lat}, {lng}) from {START_DATE} to {END_DATE}...")

    params = {
        "latitude": lat,
        "longitude": lng,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": "precipitation_sum",
        "timezone": "auto",
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.get(ARCHIVE_URL, params=params)
        response.raise_for_status()
        data = response.json()

    dates = data.get("daily", {}).get("time", [])
    precip = data.get("daily", {}).get("precipitation_sum", [])

    print(f"  Got {len(dates)} days of data")
    return [{"date": d, "precip": p} for d, p in zip(dates, precip)]


def compute_percentiles(daily_data: list[dict]) -> dict:
    """Compute monthly percentiles from daily precipitation data.

    Returns dict with keys "1" through "12" (month numbers), each containing:
    - P50, P75, P90, P95, P99: precipitation percentiles in mm
    - n_days: number of days used for computation
    - mean: mean daily precipitation
    """
    # Group by month
    monthly: dict[int, list[float]] = {m: [] for m in range(1, 13)}

    for entry in daily_data:
        if entry["precip"] is None:
            continue
        month = int(entry["date"].split("-")[1])
        monthly[month].append(entry["precip"])

    result = {}
    for month in range(1, 13):
        values = np.array(monthly[month])
        if len(values) == 0:
            result[str(month)] = {
                "P50": 0.0, "P75": 0.0, "P90": 0.0, "P95": 0.0, "P99": 0.0,
                "n_days": 0, "mean": 0.0,
            }
            continue

        # Include ALL days (including dry days with 0mm) for accurate percentiles.
        # This is correct: P95 = "95% of ALL days have less rain than this"
        result[str(month)] = {
            "P50": round(float(np.percentile(values, 50)), 2),
            "P75": round(float(np.percentile(values, 75)), 2),
            "P90": round(float(np.percentile(values, 90)), 2),
            "P95": round(float(np.percentile(values, 95)), 2),
            "P99": round(float(np.percentile(values, 99)), 2),
            "n_days": len(values),
            "mean": round(float(np.mean(values)), 2),
        }

    return result


def main():
    print("Computing climate percentiles from Open-Meteo Historical API")
    print(f"Period: {START_DATE} to {END_DATE}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for city, coords in CITY_CENTROIDS.items():
        print(f"\n{'='*50}")
        print(f"Processing {city.upper()}")
        print(f"{'='*50}")

        daily_data = fetch_historical_precip(city, coords["lat"], coords["lng"])
        percentiles = compute_percentiles(daily_data)

        # Add metadata
        output = {
            "city": city,
            "centroid": coords,
            "period": f"{START_DATE} to {END_DATE}",
            "source": "Open-Meteo Archive API (ERA5 reanalysis)",
            "generated_at": datetime.now().isoformat(),
            "description": "Monthly daily precipitation percentiles (mm). Includes all days (wet+dry).",
            "monthly": percentiles,
        }

        output_path = OUTPUT_DIR / f"{city}_climate_percentiles.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        print(f"\nSaved to {output_path}")

        # Print summary table
        print(f"\n{'Month':>6} | {'P50':>6} | {'P75':>6} | {'P90':>6} | {'P95':>6} | {'P99':>6} | {'Mean':>6} | {'N':>5}")
        print("-" * 65)
        for month in range(1, 13):
            m = percentiles[str(month)]
            month_name = datetime(2024, month, 1).strftime("%b")
            print(f"{month_name:>6} | {m['P50']:>6.1f} | {m['P75']:>6.1f} | {m['P90']:>6.1f} | {m['P95']:>6.1f} | {m['P99']:>6.1f} | {m['mean']:>6.1f} | {m['n_days']:>5}")


if __name__ == "__main__":
    main()
