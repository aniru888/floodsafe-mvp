"""
Export Sensor Time-Series Data for LSTM Training
=================================================

Exports sensor readings in LSTM-ready sequence format.

Output NPZ format:
- X: shape (n_sequences, sequence_length, n_features)
    Features: [water_height_mm, water_percent_distance, is_warning, is_flood]
- y: shape (n_sequences,) - next water_height_mm (prediction target)
- timestamps: shape (n_sequences,) - timestamp of prediction target
- sensor_ids: shape (n_sequences,) - sensor ID for grouping

Usage:
    python -m apps.ml-service.scripts.export_sensor_timeseries --sensor-id <UUID>
    python -m apps.ml-service.scripts.export_sensor_timeseries --all
    python -m apps.ml-service.scripts.export_sensor_timeseries --stats
"""

import sys
from pathlib import Path
import argparse
from datetime import datetime
from typing import Optional, List
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/floodsafe")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# Configuration
SEQUENCE_LENGTH = 10  # Number of timesteps for LSTM input
MIN_READINGS_PER_SENSOR = 50  # Minimum readings to include sensor
FEATURES = ['water_height_mm', 'water_percent_distance', 'is_warning', 'is_flood']


def fetch_sensor_readings(sensor_id: str) -> List[dict]:
    """Fetch all readings for a sensor, ordered by timestamp."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT
                timestamp,
                water_level,
                water_segments,
                distance_mm,
                water_height_mm,
                water_percent_strips,
                water_percent_distance,
                is_warning,
                is_flood
            FROM readings
            WHERE sensor_id = :sensor_id
            ORDER BY timestamp ASC
        """), {"sensor_id": sensor_id})

        readings = []
        for row in result:
            readings.append({
                'timestamp': row[0],
                'water_level': row[1],
                'water_segments': row[2],
                'distance_mm': row[3],
                'water_height_mm': row[4],
                'water_percent_strips': row[5],
                'water_percent_distance': row[6],
                'is_warning': row[7],
                'is_flood': row[8],
            })
        return readings
    finally:
        db.close()


def fetch_all_sensors() -> List[dict]:
    """Fetch all sensors with their reading counts."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT
                s.id,
                s.name,
                COUNT(r.id) as reading_count,
                MIN(r.timestamp) as first_reading,
                MAX(r.timestamp) as last_reading
            FROM sensors s
            LEFT JOIN readings r ON s.id = r.sensor_id
            GROUP BY s.id, s.name
            ORDER BY reading_count DESC
        """))

        sensors = []
        for row in result:
            sensors.append({
                'id': str(row[0]),
                'name': row[1],
                'reading_count': row[2],
                'first_reading': row[3],
                'last_reading': row[4],
            })
        return sensors
    finally:
        db.close()


def create_sequences(readings: List[dict], sequence_length: int = SEQUENCE_LENGTH) -> tuple:
    """
    Create LSTM-ready sequences from sensor readings.

    Args:
        readings: List of reading dictionaries
        sequence_length: Number of timesteps per sequence

    Returns:
        X: np.array of shape (n_sequences, sequence_length, n_features)
        y: np.array of shape (n_sequences,) - prediction targets
        timestamps: np.array of timestamps for each prediction target
    """
    if len(readings) < sequence_length + 1:
        print(f"    Skipping: only {len(readings)} readings (need {sequence_length + 1}+)")
        return None, None, None

    sequences = []
    targets = []
    timestamps = []

    for i in range(sequence_length, len(readings)):
        # Get sequence of past readings
        sequence = readings[i - sequence_length:i]
        target = readings[i]

        # Extract features
        seq_features = []
        for r in sequence:
            features = [
                r.get('water_height_mm') or 0.0,
                r.get('water_percent_distance') or 0.0,
                1.0 if r.get('is_warning') else 0.0,
                1.0 if r.get('is_flood') else 0.0,
            ]
            seq_features.append(features)

        sequences.append(seq_features)
        targets.append(target.get('water_height_mm') or 0.0)
        timestamps.append(target['timestamp'])

    X = np.array(sequences, dtype=np.float32)
    y = np.array(targets, dtype=np.float32)

    return X, y, timestamps


def export_sensor(sensor_id: str, output_dir: str = None) -> Optional[str]:
    """
    Export time-series data for a single sensor.

    Returns:
        Path to output file, or None if insufficient data
    """
    print(f"\nExporting sensor: {sensor_id}")

    readings = fetch_sensor_readings(sensor_id)
    print(f"  Found {len(readings)} readings")

    if len(readings) < MIN_READINGS_PER_SENSOR:
        print(f"  Skipping: insufficient data (need {MIN_READINGS_PER_SENSOR}+)")
        return None

    X, y, timestamps = create_sequences(readings)

    if X is None:
        return None

    print(f"  Created {X.shape[0]} sequences")
    print(f"  Shape: X={X.shape}, y={y.shape}")

    # Output directory
    if output_dir is None:
        output_dir = project_root / "apps" / "ml-service" / "data" / "sensor_timeseries"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Output filename
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"sensor_{sensor_id[:8]}_{timestamp_str}.npz"

    # Save to NPZ
    np.savez(
        output_file,
        X=X,
        y=y,
        timestamps=np.array([t.isoformat() for t in timestamps]),
        sensor_id=sensor_id,
        sequence_length=SEQUENCE_LENGTH,
        features=FEATURES,
    )

    print(f"  Saved to: {output_file}")
    return str(output_file)


def export_all_sensors(output_dir: str = None) -> List[str]:
    """Export time-series data for all sensors with sufficient data."""
    print("\nFetching all sensors...")
    sensors = fetch_all_sensors()

    eligible = [s for s in sensors if s['reading_count'] >= MIN_READINGS_PER_SENSOR]
    print(f"Found {len(sensors)} sensors, {len(eligible)} eligible (>={MIN_READINGS_PER_SENSOR} readings)")

    output_files = []
    for sensor in eligible:
        output_file = export_sensor(sensor['id'], output_dir)
        if output_file:
            output_files.append(output_file)

    # Create combined dataset if multiple sensors
    if len(output_files) > 1:
        print("\nCreating combined dataset...")
        combined_file = combine_exports(output_files, output_dir)
        if combined_file:
            output_files.append(combined_file)

    return output_files


def combine_exports(npz_files: List[str], output_dir: str = None) -> Optional[str]:
    """Combine multiple sensor exports into a single dataset."""
    all_X = []
    all_y = []
    all_timestamps = []
    all_sensor_ids = []

    for npz_file in npz_files:
        data = np.load(npz_file, allow_pickle=True)
        X = data['X']
        y = data['y']
        timestamps = data['timestamps']
        sensor_id = str(data['sensor_id'])

        all_X.append(X)
        all_y.append(y)
        all_timestamps.extend(timestamps)
        all_sensor_ids.extend([sensor_id] * len(y))

    # Concatenate
    X_combined = np.concatenate(all_X, axis=0)
    y_combined = np.concatenate(all_y, axis=0)

    print(f"Combined: {X_combined.shape[0]} sequences from {len(npz_files)} sensors")

    # Output
    if output_dir is None:
        output_dir = project_root / "apps" / "ml-service" / "data" / "sensor_timeseries"
    else:
        output_dir = Path(output_dir)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"combined_sensors_{timestamp_str}.npz"

    np.savez(
        output_file,
        X=X_combined,
        y=y_combined,
        timestamps=np.array(all_timestamps),
        sensor_ids=np.array(all_sensor_ids),
        sequence_length=SEQUENCE_LENGTH,
        features=FEATURES,
        source_files=npz_files,
    )

    print(f"Saved combined dataset to: {output_file}")
    return str(output_file)


def show_stats():
    """Show statistics about available sensor data."""
    print("\n" + "=" * 60)
    print("SENSOR DATA STATISTICS")
    print("=" * 60)

    sensors = fetch_all_sensors()

    print(f"\nTotal sensors: {len(sensors)}")

    if not sensors:
        print("No sensors found in database.")
        return

    # Summary stats
    total_readings = sum(s['reading_count'] for s in sensors)
    eligible = [s for s in sensors if s['reading_count'] >= MIN_READINGS_PER_SENSOR]

    print(f"Total readings: {total_readings:,}")
    print(f"Sensors with >={MIN_READINGS_PER_SENSOR} readings: {len(eligible)}")

    print("\n" + "-" * 60)
    print(f"{'Sensor ID':<40} {'Name':<20} {'Readings':>10}")
    print("-" * 60)

    for sensor in sensors[:10]:  # Show top 10
        name = sensor['name'] or "(unnamed)"
        if len(name) > 17:
            name = name[:17] + "..."
        print(f"{sensor['id']:<40} {name:<20} {sensor['reading_count']:>10}")

    if len(sensors) > 10:
        print(f"... and {len(sensors) - 10} more sensors")

    # LSTM readiness
    print("\n" + "=" * 60)
    print("LSTM TRAINING READINESS")
    print("=" * 60)

    if len(eligible) == 0:
        print("\n[NOT READY] No sensors have sufficient data for LSTM training.")
        print(f"Need at least {MIN_READINGS_PER_SENSOR} readings per sensor.")
        print(f"Current max: {sensors[0]['reading_count'] if sensors else 0} readings")
    else:
        potential_sequences = sum(
            max(0, s['reading_count'] - SEQUENCE_LENGTH)
            for s in eligible
        )
        print(f"\n[PARTIAL] {len(eligible)} sensor(s) have sufficient data")
        print(f"Potential training sequences: ~{potential_sequences:,}")

        if potential_sequences < 1000:
            print("\n[RECOMMENDATION] Need more data collection:")
            print(f"  - Target: 1,000+ sequences minimum")
            print(f"  - Current: {potential_sequences} sequences")
            print(f"  - At 30s intervals, need ~8 hours continuous data per sensor")
        elif potential_sequences < 10000:
            print("\n[RECOMMENDATION] Moderate dataset - can train basic LSTM:")
            print(f"  - Current: {potential_sequences} sequences")
            print(f"  - May have high variance in predictions")
            print(f"  - Continue collecting for better generalization")
        else:
            print("\n[READY] Sufficient data for LSTM training!")
            print(f"  - Current: {potential_sequences:,} sequences")
            print(f"  - Run: python -m apps.ml-service.scripts.export_sensor_timeseries --all")


def main():
    parser = argparse.ArgumentParser(
        description="Export sensor time-series data for LSTM training"
    )
    parser.add_argument(
        '--sensor-id',
        type=str,
        help='Export data for specific sensor UUID'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Export data for all sensors with sufficient readings'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics about available sensor data'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Output directory for NPZ files'
    )

    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.all:
        export_all_sensors(args.output_dir)
    elif args.sensor_id:
        export_sensor(args.sensor_id, args.output_dir)
    else:
        # Default: show stats
        show_stats()
        print("\nUsage:")
        print("  --stats        Show data statistics")
        print("  --all          Export all eligible sensors")
        print("  --sensor-id X  Export specific sensor")


if __name__ == "__main__":
    main()
