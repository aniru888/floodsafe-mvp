"""
Groundsource Data Exploration
==============================
Explores the 667MB Parquet file to understand structure, filter to 5 cities,
and verify column mapping before committing to the import pipeline.

Run: python apps/ml-pipeline/notebooks/groundsource_exploration.py
"""
import pandas as pd
import sys

PARQUET_PATH = "path/to/groundsource_flood_events.parquet"  # UPDATE THIS

# City bounding boxes (same as fhi_calculator.py CITY_BOUNDS)
CITY_BOUNDS = {
    "delhi": {"lat_min": 28.40, "lat_max": 28.88, "lng_min": 76.84, "lng_max": 77.35},
    "bangalore": {"lat_min": 12.85, "lat_max": 13.15, "lng_min": 77.45, "lng_max": 77.75},
    "yogyakarta": {"lat_min": -7.95, "lat_max": -7.70, "lng_min": 110.30, "lng_max": 110.50},
    "singapore": {"lat_min": 1.20, "lat_max": 1.47, "lng_min": 103.60, "lng_max": 104.00},
    "indore": {"lat_min": 22.62, "lat_max": 22.82, "lng_min": 75.78, "lng_max": 75.95},
}

print("Loading Parquet file (this may take 30-60 seconds)...")
df = pd.read_parquet(PARQUET_PATH)

print(f"\n=== DATASET OVERVIEW ===")
print(f"Total rows: {len(df):,}")
print(f"Columns: {list(df.columns)}")
print(f"Dtypes:\n{df.dtypes}")
print(f"\nFirst 3 rows:\n{df.head(3)}")
print(f"\nNull counts:\n{df.isnull().sum()}")

# Identify lat/lng columns
lat_col = None
lng_col = None
for col in df.columns:
    col_lower = col.lower()
    if 'lat' in col_lower:
        lat_col = col
    if 'lon' in col_lower or 'lng' in col_lower:
        lng_col = col

if not lat_col or not lng_col:
    print(f"\nWARNING: Could not auto-detect lat/lng columns from: {list(df.columns)}")
    print("Please manually specify lat_col and lng_col")
    sys.exit(1)

print(f"\nUsing lat_col='{lat_col}', lng_col='{lng_col}'")

# Filter to 5 cities
print(f"\n=== CITY FILTERING ===")
for city, bounds in CITY_BOUNDS.items():
    mask = (
        (df[lat_col] >= bounds["lat_min"]) & (df[lat_col] <= bounds["lat_max"]) &
        (df[lng_col] >= bounds["lng_min"]) & (df[lng_col] <= bounds["lng_max"])
    )
    count = mask.sum()
    print(f"{city:>12}: {count:>6,} events")

total = sum(
    ((df[lat_col] >= b["lat_min"]) & (df[lat_col] <= b["lat_max"]) &
     (df[lng_col] >= b["lng_min"]) & (df[lng_col] <= b["lng_max"])).sum()
    for b in CITY_BOUNDS.values()
)
print(f"{'TOTAL':>12}: {total:>6,} events (from {len(df):,} global)")

# Date range
date_col = None
for col in df.columns:
    if 'date' in col.lower() or 'time' in col.lower() or 'start' in col.lower():
        date_col = col
        break

if date_col:
    print(f"\n=== DATE RANGE (column: {date_col}) ===")
    print(f"Min: {df[date_col].min()}")
    print(f"Max: {df[date_col].max()}")

# Area column
area_col = None
for col in df.columns:
    if 'area' in col.lower():
        area_col = col
        break

if area_col:
    print(f"\n=== AREA DISTRIBUTION (column: {area_col}) ===")
    print(f"Mean: {df[area_col].mean():.2f}")
    print(f"Median: {df[area_col].median():.2f}")
    print(f"Max: {df[area_col].max():.2f}")
    print(f"Events > 10 km²: {(df[area_col] > 10).sum():,} (will be filtered)")

print(f"\n=== COLUMN MAPPING FOR IMPORT ===")
print(f"lat_col = '{lat_col}'")
print(f"lng_col = '{lng_col}'")
print(f"date_col = '{date_col}'")
print(f"area_col = '{area_col}'")
print("\nUpdate import_groundsource.py with these column names.")
