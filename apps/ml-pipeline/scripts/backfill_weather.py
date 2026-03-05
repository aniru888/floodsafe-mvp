"""
Backfill weather snapshots for existing reports that lack them.

Uses Open-Meteo historical archive API to fetch weather conditions
at the time and location of each report.

Usage:
    python scripts/backfill_weather.py
    python scripts/backfill_weather.py --limit 50
    python scripts/backfill_weather.py --dry-run

Prerequisites:
    - DATABASE_URL in .env
    - Reports exist in the database
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
RATE_LIMIT_DELAY = 1.0  # seconds between requests (Open-Meteo free tier)


def get_engine():
    """Create SQLAlchemy engine from DATABASE_URL."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        for parent in [Path(__file__).parent.parent.parent / "backend",
                       Path(__file__).parent.parent.parent.parent]:
            env_path = parent / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                database_url = os.getenv("DATABASE_URL")
                if database_url:
                    break

    if not database_url:
        logger.error("DATABASE_URL not found. Set it in .env or environment.")
        sys.exit(1)

    return create_engine(database_url)


def get_reports_without_weather(engine, limit: int = 0):
    """Get reports that don't have weather_snapshot populated."""
    query = """
        SELECT id, ST_Y(location::geometry) as lat, ST_X(location::geometry) as lng, timestamp
        FROM reports
        WHERE weather_snapshot IS NULL
          AND location IS NOT NULL
        ORDER BY timestamp DESC
    """
    if limit > 0:
        query += f" LIMIT {limit}"

    with engine.connect() as conn:
        result = conn.execute(text(query))
        reports = result.fetchall()

    return reports


def fetch_historical_weather(lat: float, lng: float, date: datetime) -> dict:
    """
    Fetch historical weather from Open-Meteo archive API.

    The archive API uses different parameters than the forecast API:
    - start_date and end_date instead of past_days/forecast_days
    - Only hourly data available (no daily aggregation)
    """
    date_str = date.strftime("%Y-%m-%d")

    # Fetch 7 days before the report date for rainfall accumulation
    from datetime import timedelta
    start_date = (date - timedelta(days=7)).strftime("%Y-%m-%d")

    params = {
        "latitude": lat,
        "longitude": lng,
        "start_date": start_date,
        "end_date": date_str,
        "hourly": "precipitation,temperature_2m,relative_humidity_2m,surface_pressure",
        "timezone": "auto",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(OPEN_METEO_ARCHIVE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        return extract_snapshot(data, date)

    except httpx.TimeoutException:
        logger.error(f"Archive API timeout for ({lat}, {lng}) on {date_str}")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"Archive API HTTP {e.response.status_code} for ({lat}, {lng}) on {date_str}")
        return None
    except Exception as e:
        logger.error(f"Archive API failed for ({lat}, {lng}) on {date_str}: {e}")
        return None


def extract_snapshot(data: dict, report_date: datetime) -> dict:
    """Extract weather snapshot from archive API response."""
    hourly = data.get("hourly", {})

    precip_hourly = hourly.get("precipitation", [])
    temp_hourly = hourly.get("temperature_2m", [])
    humidity_hourly = hourly.get("relative_humidity_2m", [])
    pressure_hourly = hourly.get("surface_pressure", [])
    time_hourly = hourly.get("time", [])

    # Find the hour closest to the report time
    target_hour = report_date.strftime("%Y-%m-%dT%H:00")
    hour_idx = -1
    for i, t in enumerate(time_hourly):
        if t >= target_hour:
            hour_idx = i
            break
    if hour_idx < 0:
        hour_idx = len(time_hourly) - 1

    # Current conditions at report time
    current_precip = precip_hourly[hour_idx] if hour_idx < len(precip_hourly) else 0.0
    current_temp = temp_hourly[hour_idx] if hour_idx < len(temp_hourly) else None
    current_humidity = humidity_hourly[hour_idx] if hour_idx < len(humidity_hourly) else None
    current_pressure = pressure_hourly[hour_idx] if hour_idx < len(pressure_hourly) else None

    # Max hourly intensity in last 24 hours
    start_24h = max(0, hour_idx - 24)
    last_24h = precip_hourly[start_24h:hour_idx + 1]
    hourly_intensity_max = max(last_24h) if last_24h else 0.0

    # Rainfall accumulation: compute daily sums then sum last 3 and 7 days
    daily_precip = []
    for day_start in range(0, len(precip_hourly), 24):
        day_end = min(day_start + 24, len(precip_hourly))
        daily_total = sum(p for p in precip_hourly[day_start:day_end] if p is not None)
        daily_precip.append(daily_total)

    rainfall_3d = sum(daily_precip[-3:]) if len(daily_precip) >= 3 else sum(daily_precip)
    rainfall_7d = sum(daily_precip[-7:]) if len(daily_precip) >= 7 else sum(daily_precip)

    return {
        "precipitation_mm": float(current_precip) if current_precip is not None else 0.0,
        "precipitation_probability": 0,  # Not available in archive API
        "hourly_intensity_max": float(hourly_intensity_max) if hourly_intensity_max is not None else 0.0,
        "surface_pressure_hpa": float(current_pressure) if current_pressure is not None else None,
        "temperature_c": float(current_temp) if current_temp is not None else None,
        "relative_humidity": int(current_humidity) if current_humidity is not None else None,
        "rainfall_3d_mm": round(float(rainfall_3d), 2),
        "rainfall_7d_mm": round(float(rainfall_7d), 2),
        "captured_at": report_date.isoformat(),
        "source": "archive_backfill",
    }


def update_report_weather(engine, report_id, weather_snapshot):
    """Update a report's weather_snapshot field."""
    import json

    with engine.connect() as conn:
        conn.execute(
            text("UPDATE reports SET weather_snapshot = :weather::jsonb WHERE id = :id"),
            {"id": str(report_id), "weather": json.dumps(weather_snapshot)}
        )
        conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Backfill weather snapshots for reports")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max reports to backfill (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be backfilled without making changes")
    args = parser.parse_args()

    engine = get_engine()

    # Find reports needing backfill
    reports = get_reports_without_weather(engine, args.limit)
    logger.info(f"Found {len(reports)} reports without weather snapshots")

    if not reports:
        print("No reports need weather backfill.")
        return

    if args.dry_run:
        print(f"\n[DRY RUN] Would backfill {len(reports)} reports")
        for r in reports[:5]:
            print(f"  Report {r[0]}: ({r[1]:.4f}, {r[2]:.4f}) at {r[3]}")
        if len(reports) > 5:
            print(f"  ... and {len(reports) - 5} more")
        return

    # Backfill
    success = 0
    failed = 0

    for i, report in enumerate(reports):
        report_id, lat, lng, timestamp = report

        logger.info(f"Backfilling {i+1}/{len(reports)}: report {report_id}")

        weather = fetch_historical_weather(lat, lng, timestamp)
        if weather:
            update_report_weather(engine, report_id, weather)
            success += 1
        else:
            failed += 1

        # Rate limit
        if i < len(reports) - 1:
            time.sleep(RATE_LIMIT_DELAY)

    print(f"\nBackfill complete: {success} success, {failed} failed out of {len(reports)} total")


if __name__ == "__main__":
    main()
