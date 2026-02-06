"""
Generate complete training dataset using ONLY Google Earth Engine data.

This creates both features (X) and labels (y) from GEE without external data!

Strategy:
- Features (X): AlphaEarth + DEM + precipitation + temporal
- Labels (y): Derived from extreme precipitation events
"""

import sys
sys.path.insert(0, '../')

from src.features.extractor import FeatureExtractor
from src.data.precipitation import PrecipitationFetcher
from datetime import datetime, timedelta
import numpy as np
import json

def generate_training_data(
    bounds,
    start_date,
    end_date,
    flood_threshold_mm=100,
    save_path='../data/training_data.npz'
):
    """
    Generate training dataset from GEE.

    Args:
        bounds: Geographic bounds tuple
        start_date: Start date for data collection
        end_date: End date for data collection
        flood_threshold_mm: Rainfall threshold to label as flood (default 100mm)
        save_path: Where to save the dataset

    Returns:
        Dictionary with X_train, y_train
    """
    print("=" * 60)
    print("Generating Training Data from Google Earth Engine")
    print("=" * 60)
    print(f"\nRegion: {bounds}")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print(f"Flood threshold: {flood_threshold_mm}mm rainfall")

    extractor = FeatureExtractor()
    precip_fetcher = PrecipitationFetcher()

    # Step 1: Get precipitation time series to create labels
    print("\n[1/3] Fetching precipitation data for label generation...")
    try:
        precip_df = precip_fetcher.fetch(bounds, start_date, end_date)
        print(f"[OK] Got {len(precip_df)} days of data")

        # Show rainfall statistics
        print(f"\nRainfall statistics:")
        print(f"  Mean: {precip_df['precipitation_mm'].mean():.1f}mm")
        print(f"  Max: {precip_df['precipitation_mm'].max():.1f}mm")
        print(f"  Std: {precip_df['precipitation_mm'].std():.1f}mm")

        # Count flood events
        flood_days = (precip_df['precipitation_mm'] > flood_threshold_mm).sum()
        print(f"\nFlood events: {flood_days} days (>{flood_threshold_mm}mm)")
        print(f"Normal days: {len(precip_df) - flood_days}")

    except Exception as e:
        print(f"[FAIL] Precipitation fetch failed: {e}")
        return None

    # Step 2: Extract features for each day
    print(f"\n[2/3] Extracting 79-dim features for {len(precip_df)} days...")

    features_list = []
    labels_list = []
    dates_list = []
    failed_count = 0

    for idx, row in precip_df.iterrows():
        date = row['date'].to_pydatetime()
        rainfall = row['precipitation_mm']

        try:
            # Extract features
            features = extractor.extract_features(bounds, date)
            features_list.append(features['combined'])

            # Create label based on rainfall
            # Binary: 1 if flood, 0 if not
            label = 1.0 if rainfall > flood_threshold_mm else 0.0

            # Alternative: Continuous risk score (0-1)
            # risk_score = min(rainfall / 200.0, 1.0)

            labels_list.append(label)
            dates_list.append(date.isoformat())

            if (idx + 1) % 10 == 0:
                print(f"  Progress: {idx + 1}/{len(precip_df)} days")

        except Exception as e:
            failed_count += 1
            if failed_count < 5:
                print(f"  [WARN] Failed for {date.date()}: {e}")

    print(f"\n[OK] Extracted features for {len(features_list)} days")
    if failed_count > 0:
        print(f"[WARN] {failed_count} days failed (skipped)")

    # Step 3: Convert to arrays and save
    print(f"\n[3/3] Converting to numpy arrays and saving...")

    X = np.array(features_list)  # Shape: (n_days, 79)
    y = np.array(labels_list)    # Shape: (n_days,)

    print(f"\nDataset shape:")
    print(f"  Features (X): {X.shape}")
    print(f"  Labels (y): {y.shape}")
    print(f"\nClass distribution:")
    print(f"  Flood (1): {(y == 1).sum()} samples ({(y == 1).mean()*100:.1f}%)")
    print(f"  Normal (0): {(y == 0).sum()} samples ({(y == 0).mean()*100:.1f}%)")

    # Check for class imbalance
    if (y == 1).sum() < 5:
        print("\n[WARN] Very few flood samples! Consider:")
        print("  1. Lower flood threshold (try 50mm)")
        print("  2. Extend date range to include more monsoon seasons")
        print("  3. Use continuous risk scores instead of binary labels")

    # Save dataset
    np.savez(
        save_path,
        X=X,
        y=y,
        dates=dates_list,
        metadata={
            'bounds': bounds,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'flood_threshold_mm': flood_threshold_mm,
            'feature_dim': 79,
            'n_samples': len(X),
            'n_flood': int((y == 1).sum()),
            'n_normal': int((y == 0).sum()),
        }
    )

    print(f"\n[OK] Dataset saved to: {save_path}")

    # Save metadata as JSON for easy reading
    metadata_path = save_path.replace('.npz', '_metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump({
            'bounds': bounds,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'flood_threshold_mm': flood_threshold_mm,
            'feature_dim': 79,
            'n_samples': len(X),
            'n_flood': int((y == 1).sum()),
            'n_normal': int((y == 0).sum()),
            'dates_with_floods': [dates_list[i] for i in range(len(y)) if y[i] == 1],
        }, f, indent=2)

    print(f"[OK] Metadata saved to: {metadata_path}")

    return {'X': X, 'y': y, 'dates': dates_list}


if __name__ == "__main__":
    # Delhi NCR bounds
    delhi_bounds = (28.4, 76.8, 28.9, 77.4)

    # Monsoon season 2023 (most recent complete season)
    start_date = datetime(2023, 6, 1)   # June 1
    end_date = datetime(2023, 9, 30)    # September 30

    print("\nGenerating training data for Delhi monsoon season 2023...")
    print("This will take 5-10 minutes (fetching from GEE)...\n")

    dataset = generate_training_data(
        bounds=delhi_bounds,
        start_date=start_date,
        end_date=end_date,
        flood_threshold_mm=50,  # 50mm+ = flood risk (adjusted for Delhi 2023 data)
        save_path='../data/delhi_monsoon_2023.npz'
    )

    if dataset:
        print("\n" + "=" * 60)
        print("[SUCCESS] Training dataset created!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Train models: python 06_train_models.py")
        print("2. Evaluate: python 07_evaluate_models.py")
        print("3. Deploy: Copy trained models to ../models/ensemble/")
