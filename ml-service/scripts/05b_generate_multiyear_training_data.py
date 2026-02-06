"""
Generate multi-year training dataset using Google Earth Engine data.

This creates a comprehensive dataset across multiple monsoon seasons
with CONTINUOUS risk scores (not binary) for better model training.

Strategy:
- Features (X): Dynamic World + WorldCover + Sentinel-2 + DEM + CHIRPS + Temporal + GloFAS (37 dims)
- Labels (y): Continuous risk score (0-1) based on precipitation intensity
"""

import sys
sys.path.insert(0, '../')

from src.features.extractor import FeatureExtractor
from src.data.precipitation import PrecipitationFetcher
from datetime import datetime, timedelta
import numpy as np
import json
import os
import time


def retry_with_backoff(func, max_retries=3, initial_delay=2.0):
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to call
        max_retries: Maximum number of retries
        initial_delay: Initial delay in seconds

    Returns:
        Result of function call, or raises last exception
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                print(f"  [RETRY] Attempt {attempt + 1} failed: {str(e)[:50]}... waiting {delay:.1f}s")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise last_exception


def calculate_flood_risk_score(rainfall_mm: float, max_rainfall: float = 100.0) -> float:
    """
    Calculate continuous flood risk score from rainfall.

    Uses a nonlinear scaling to capture the exponential increase in risk:
    - 0-20mm: Low risk (0.0-0.2)
    - 20-50mm: Moderate risk (0.2-0.5)
    - 50-100mm: High risk (0.5-0.9)
    - >100mm: Very high risk (0.9-1.0)

    Args:
        rainfall_mm: Daily rainfall in millimeters
        max_rainfall: Rainfall considered as maximum risk (default 100mm)

    Returns:
        Float between 0.0 and 1.0
    """
    if rainfall_mm <= 0:
        return 0.0

    # Sigmoid-like transformation for more realistic risk curve
    # Low rainfall has minimal impact, high rainfall has exponential impact
    normalized = rainfall_mm / max_rainfall

    # Apply sigmoid transformation: 1 / (1 + exp(-k*(x-0.5)))
    # Adjusted to give reasonable scores
    if normalized < 0.2:
        return normalized * 0.5  # 0-10% for <20mm
    elif normalized < 0.5:
        return 0.1 + (normalized - 0.2) * 1.33  # 10-50% for 20-50mm
    elif normalized < 1.0:
        return 0.5 + (normalized - 0.5) * 0.8  # 50-90% for 50-100mm
    else:
        return min(0.9 + (normalized - 1.0) * 0.1, 1.0)  # 90-100% for >100mm


def generate_training_data_multiyear(
    bounds,
    years: list,
    monsoon_start_month: int = 6,
    monsoon_end_month: int = 9,
    save_path: str = '../data/training_data_multiyear.npz'
):
    """
    Generate multi-year training dataset from GEE with continuous risk scores.

    Args:
        bounds: Geographic bounds tuple (lat_min, lng_min, lat_max, lng_max)
        years: List of years to include (e.g., [2019, 2020, 2021, 2022, 2023])
        monsoon_start_month: Start of monsoon season (default: June)
        monsoon_end_month: End of monsoon season (default: September)
        save_path: Where to save the dataset

    Returns:
        Dictionary with X_train, y_train, dates
    """
    print("=" * 70)
    print("Generating Multi-Year Training Data from Google Earth Engine")
    print("=" * 70)
    print(f"\nRegion: {bounds}")
    print(f"Years: {years}")
    print(f"Monsoon period: Month {monsoon_start_month} to {monsoon_end_month}")
    print(f"Label type: CONTINUOUS risk score (0.0 - 1.0)")

    extractor = FeatureExtractor()
    precip_fetcher = PrecipitationFetcher()

    all_features = []
    all_labels = []
    all_dates = []
    all_rainfall = []
    year_stats = {}

    for year in years:
        print(f"\n{'='*70}")
        print(f"Processing year {year}...")
        print("=" * 70)

        start_date = datetime(year, monsoon_start_month, 1)
        # End on the last day of monsoon_end_month
        if monsoon_end_month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, monsoon_end_month + 1, 1) - timedelta(days=1)

        print(f"Period: {start_date.date()} to {end_date.date()}")

        # Step 1: Get precipitation data
        print(f"\n[1/2] Fetching precipitation data for {year}...")
        try:
            precip_df = precip_fetcher.fetch(bounds, start_date, end_date)
            print(f"[OK] Got {len(precip_df)} days of data")

            # Statistics for this year
            year_stats[year] = {
                'days': len(precip_df),
                'mean_rainfall': float(precip_df['precipitation_mm'].mean()),
                'max_rainfall': float(precip_df['precipitation_mm'].max()),
                'days_above_20mm': int((precip_df['precipitation_mm'] > 20).sum()),
                'days_above_50mm': int((precip_df['precipitation_mm'] > 50).sum()),
                'days_above_100mm': int((precip_df['precipitation_mm'] > 100).sum()),
            }

            print(f"  Mean rainfall: {year_stats[year]['mean_rainfall']:.1f}mm")
            print(f"  Max rainfall: {year_stats[year]['max_rainfall']:.1f}mm")
            print(f"  Days >20mm: {year_stats[year]['days_above_20mm']}")
            print(f"  Days >50mm: {year_stats[year]['days_above_50mm']}")
            print(f"  Days >100mm: {year_stats[year]['days_above_100mm']}")

        except Exception as e:
            print(f"[FAIL] Precipitation fetch failed for {year}: {e}")
            continue

        # Step 2: Extract features for each day
        print(f"\n[2/2] Extracting features for {len(precip_df)} days...")

        year_features = []
        year_labels = []
        year_dates = []
        year_rainfall_values = []
        failed_count = 0

        for idx, row in precip_df.iterrows():
            date = row['date'].to_pydatetime()
            rainfall = row['precipitation_mm']

            try:
                # Extract 37-dimensional features with retry logic
                def extract_fn():
                    return extractor.extract_features(bounds, date)

                features = retry_with_backoff(extract_fn, max_retries=3, initial_delay=2.0)
                year_features.append(features['combined'])

                # Calculate continuous risk score
                risk_score = calculate_flood_risk_score(rainfall)
                year_labels.append(risk_score)
                year_dates.append(date.isoformat())
                year_rainfall_values.append(rainfall)

                if (idx + 1) % 20 == 0:
                    print(f"  Progress: {idx + 1}/{len(precip_df)} days")

                # Small delay between requests to avoid rate limiting
                time.sleep(0.5)

            except Exception as e:
                failed_count += 1
                if failed_count <= 3:
                    print(f"  [WARN] Failed for {date.date()}: {str(e)[:50]}")

        print(f"\n[OK] Year {year}: {len(year_features)} samples extracted")
        if failed_count > 0:
            print(f"[WARN] {failed_count} days failed (skipped)")

        # Accumulate
        all_features.extend(year_features)
        all_labels.extend(year_labels)
        all_dates.extend(year_dates)
        all_rainfall.extend(year_rainfall_values)

        # Delay between years to help with GEE rate limits
        if year != years[-1]:  # Don't delay after last year
            print(f"\n  [PAUSE] Waiting 10 seconds before next year...")
            time.sleep(10)

    # Convert to arrays
    print(f"\n{'='*70}")
    print("Finalizing dataset...")
    print("=" * 70)

    X = np.array(all_features)
    y = np.array(all_labels)
    rainfall = np.array(all_rainfall)

    print(f"\nDataset shape:")
    print(f"  Features (X): {X.shape}")
    print(f"  Labels (y): {y.shape}")

    # Risk distribution analysis
    print(f"\nRisk score distribution:")
    print(f"  Low risk (0.0-0.2): {(y < 0.2).sum()} samples ({(y < 0.2).mean()*100:.1f}%)")
    print(f"  Moderate risk (0.2-0.5): {((y >= 0.2) & (y < 0.5)).sum()} samples ({((y >= 0.2) & (y < 0.5)).mean()*100:.1f}%)")
    print(f"  High risk (0.5-0.9): {((y >= 0.5) & (y < 0.9)).sum()} samples ({((y >= 0.5) & (y < 0.9)).mean()*100:.1f}%)")
    print(f"  Very high risk (0.9-1.0): {(y >= 0.9).sum()} samples ({(y >= 0.9).mean()*100:.1f}%)")

    print(f"\nRainfall distribution:")
    print(f"  Mean: {rainfall.mean():.1f}mm")
    print(f"  Max: {rainfall.max():.1f}mm")
    print(f"  Std: {rainfall.std():.1f}mm")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # Save dataset
    np.savez(
        save_path,
        X=X,
        y=y,
        rainfall=rainfall,
        dates=all_dates,
    )
    print(f"\n[OK] Dataset saved to: {save_path}")

    # Save detailed metadata
    metadata = {
        'bounds': bounds,
        'years': years,
        'monsoon_months': [monsoon_start_month, monsoon_end_month],
        'label_type': 'continuous_risk_score',
        'feature_dim': 37,  # Updated: Dynamic World (9) + WorldCover (6) + Sentinel-2 (5) + DEM (6) + CHIRPS (5) + Temporal (4) + GloFAS (2)
        'n_samples': len(X),
        'year_stats': year_stats,
        'risk_distribution': {
            'low_0_to_0.2': int((y < 0.2).sum()),
            'moderate_0.2_to_0.5': int(((y >= 0.2) & (y < 0.5)).sum()),
            'high_0.5_to_0.9': int(((y >= 0.5) & (y < 0.9)).sum()),
            'very_high_0.9_to_1.0': int((y >= 0.9).sum()),
        },
        'rainfall_stats': {
            'mean_mm': float(rainfall.mean()),
            'max_mm': float(rainfall.max()),
            'std_mm': float(rainfall.std()),
        },
        'high_risk_dates': [all_dates[i] for i in range(len(y)) if y[i] >= 0.5],
    }

    metadata_path = save_path.replace('.npz', '_metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"[OK] Metadata saved to: {metadata_path}")

    return {'X': X, 'y': y, 'dates': all_dates, 'rainfall': rainfall}


if __name__ == "__main__":
    # Delhi NCR bounds
    delhi_bounds = (28.4, 76.8, 28.9, 77.4)

    # Multi-year monsoon data (2019-2023 = 5 seasons)
    years = [2019, 2020, 2021, 2022, 2023]

    print("\n" + "="*70)
    print("MULTI-YEAR TRAINING DATA GENERATION (5 YEARS)")
    print("="*70)
    print(f"\nThis will collect {len(years)} monsoon seasons of data (~{len(years)*120} days)")
    print("Estimated time: 30-60 minutes (depending on GEE quota)")
    print("\nUsing CONTINUOUS risk scores (0.0-1.0) instead of binary labels")
    print("This provides better gradient signal for training.")
    print("\nFeature dimension: 37 (Dynamic World + WorldCover + Sentinel-2 + DEM + CHIRPS + Temporal + GloFAS)\n")

    dataset = generate_training_data_multiyear(
        bounds=delhi_bounds,
        years=years,
        monsoon_start_month=6,  # June
        monsoon_end_month=9,    # September
        save_path='../data/delhi_monsoon_5years.npz'  # Updated filename
    )

    if dataset:
        print("\n" + "=" * 70)
        print("[SUCCESS] Multi-year training dataset created!")
        print("=" * 70)
        print(f"\nTotal samples: {len(dataset['y'])}")
        print(f"High-risk samples (>0.5): {(dataset['y'] >= 0.5).sum()}")
        print("\nNext steps:")
        print("1. Train models: python 06_train_ensemble.py")
        print("2. The ensemble will use continuous targets for regression")
        print("3. Or threshold at 0.5 for classification")
