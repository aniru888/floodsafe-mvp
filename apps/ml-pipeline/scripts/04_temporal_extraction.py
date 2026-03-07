"""
Phase 5: SAR Temporal Feature Extraction (Bangalore + Yogyakarta).

For each city with curated flood/dry event dates:
  1. Load event dates JSON (flood dates with storm clusters + dry dates)
  2. Load hotspot coordinates from backend data
  3. For each date, extract Sentinel-1 SAR features at all hotspots:
     - Flood dates: forward-looking window (ref-2d to ref+7d)
     - Dry dates: backward lookback window (ref-7d to ref)
  4. Track SAR default rates (silent extraction failures)
  5. Save to .npz with labels, metadata, and effective-n counts

SAR features per point per date:
  - vv_mean: VV backscatter (dB) — water appears dark (<-15 dB)
  - vh_mean: VH backscatter (dB) — water appears dark (<-22 dB)
  - vv_vh_ratio: VV - VH (dB) — water indicator
  - change_magnitude: flood - baseline change (negative = flooding)

The script reuses GEE patterns from 02_static_profiling.py (auth,
checkpointing, retries) and SAR collection building from
apps/ml-service/src/data/sentinel1_sar.py (Refined Lee filter,
baseline compositing, change detection).

Usage:
    python scripts/04_temporal_extraction.py                     # Both cities
    python scripts/04_temporal_extraction.py --city bangalore    # Single city
    python scripts/04_temporal_extraction.py --city bangalore --resume

Output:
    output/temporal/{city}_temporal_features.npz

Estimated runtime:
    Bangalore: 200 hotspots x 22 dates x ~2s = ~2.4 hours
    Yogyakarta: 76 hotspots x 19 dates x ~0.8 hours
"""

import argparse
import json
import logging
import math
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ee
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "output" / "temporal"
CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
BACKEND_DATA = PROJECT_ROOT / "apps" / "backend" / "data"
CREDENTIALS = PROJECT_ROOT / "apps" / "ml-service" / "credentials" / "gee-service-account.json"

# SAR extraction parameters
BUFFER_M = 500          # Buffer radius around each hotspot (meters)
BATCH_SIZE = 50         # Hotspots per reduceRegions call (smaller than static due to temporal complexity)
MAX_RETRIES = 3
RETRY_BACKOFF_S = 5.0
CHECKPOINT_EVERY = 25   # Save checkpoint every N hotspots

# SAR default values (from Sentinel1SARFetcher.get_sar_features)
SAR_DEFAULTS = {
    "vv_mean": -10.0,
    "vh_mean": -17.0,
    "vv_vh_ratio": 7.0,
    "change_magnitude": 0.0,
}
SAR_DEFAULT_RATE_THRESHOLD = 0.30  # >30% defaults = unreliable

# Speckle filter parameters (matching Sentinel1SARFetcher)
SPECKLE_KERNEL_SIZE = 7
EQUIVALENT_NUMBER_OF_LOOKS = 4.4

# Cities with temporal event dates
TEMPORAL_CITIES = ["bangalore", "yogyakarta"]

# Dry season baseline months per city
BASELINE_MONTHS = {
    "bangalore": [1, 2, 3, 4, 5],  # Jan-May (pre-monsoon)
    "yogyakarta": [6, 7, 8],       # Jun-Aug (dry season)
}

SAR_FEATURE_NAMES = ["vv_mean", "vh_mean", "vv_vh_ratio", "change_magnitude"]


# ---------------------------------------------------------------------------
# GEE Authentication (reused from 02_static_profiling.py)
# ---------------------------------------------------------------------------

def authenticate_gee() -> bool:
    """Authenticate with GEE using service account credentials."""
    if not CREDENTIALS.exists():
        logger.error(f"Service account key not found: {CREDENTIALS}")
        return False

    try:
        credentials = ee.ServiceAccountCredentials(
            email=None,
            key_file=str(CREDENTIALS),
        )
        ee.Initialize(credentials=credentials, project="gen-lang-client-0669818939")
        logger.info("GEE authenticated successfully")
        return True
    except Exception as e:
        logger.error(f"GEE authentication failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Refined Lee Speckle Filter (adapted from Sentinel1SARFetcher)
# ---------------------------------------------------------------------------

def _refined_lee_band(band: ee.Image, kernel: ee.Kernel) -> ee.Image:
    """
    Apply Refined Lee MMSE filter to a single band.

    filtered = local_mean + k * (original - local_mean)
    where k = (local_variance - noise_variance) / local_variance
    """
    local_mean = band.reduceNeighborhood(
        reducer=ee.Reducer.mean(), kernel=kernel
    )
    local_variance = band.reduceNeighborhood(
        reducer=ee.Reducer.variance(), kernel=kernel
    )
    noise_variance = local_mean.pow(2).divide(EQUIVALENT_NUMBER_OF_LOOKS)
    signal_variance = local_variance.subtract(noise_variance).max(0)
    weight = signal_variance.divide(local_variance.add(1e-10))
    return local_mean.add(weight.multiply(band.subtract(local_mean)))


def apply_refined_lee(image: ee.Image) -> ee.Image:
    """Apply Refined Lee speckle filter to VV and VH bands."""
    kernel = ee.Kernel.square(
        radius=SPECKLE_KERNEL_SIZE // 2, units="pixels"
    )

    # Convert dB to linear, filter, convert back
    vv_linear = ee.Image(10).pow(image.select("VV").divide(10))
    vh_linear = ee.Image(10).pow(image.select("VH").divide(10))

    vv_filtered = _refined_lee_band(vv_linear, kernel)
    vh_filtered = _refined_lee_band(vh_linear, kernel)

    vv_db = ee.Image(10).multiply(vv_filtered.log10()).rename("VV")
    vh_db = ee.Image(10).multiply(vh_filtered.log10()).rename("VH")

    return vv_db.addBands(vh_db).copyProperties(image, image.propertyNames())


# ---------------------------------------------------------------------------
# SAR Collection and Extraction
# ---------------------------------------------------------------------------

def get_s1_collection(geometry: ee.Geometry) -> ee.ImageCollection:
    """
    Get filtered Sentinel-1 GRD collection with speckle filtering.

    Filters: IW mode, VV+VH polarization, descending orbit.
    """
    return (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
        .filterBounds(geometry)
        .select(["VV", "VH"])
        .map(apply_refined_lee)
    )


def build_date_window(date_str: str, is_flood: bool) -> Tuple[str, str]:
    """
    Build SAR search window for a given event date.

    Flood dates: forward-looking (ref-2d to ref+7d)
      - SAR captures standing water that persists days after rainfall
      - Start 2 days before to catch pre-event baseline shift

    Dry dates: backward lookback (ref-7d to ref)
      - Capture stable dry conditions before the reference date
    """
    ref = datetime.strptime(date_str, "%Y-%m-%d")

    if is_flood:
        start = ref - timedelta(days=2)
        end = ref + timedelta(days=7)
    else:
        start = ref - timedelta(days=7)
        end = ref

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def get_baseline_year(date_str: str) -> int:
    """Determine baseline year for change detection."""
    ref = datetime.strptime(date_str, "%Y-%m-%d")
    return ref.year - 1 if ref.month >= 6 else ref.year


def extract_sar_for_date(
    hotspots: List[Dict],
    date_str: str,
    is_flood: bool,
    city: str,
    s1_collection: ee.ImageCollection,
) -> List[Dict]:
    """
    Extract SAR features for all hotspots on a single date.

    Uses reduceRegions for batch efficiency — all hotspots share the
    same date window, so we composite once and extract at all points.

    Returns list of feature dicts (one per hotspot), same order as input.
    """
    window_start, window_end = build_date_window(date_str, is_flood)

    # Filter collection to date window
    flood_collection = s1_collection.filterDate(window_start, window_end)

    # Check image availability
    n_images = flood_collection.size().getInfo()
    if n_images == 0:
        logger.warning(
            f"  No SAR images for {date_str} ({window_start} to {window_end}). "
            f"Returning defaults for all {len(hotspots)} hotspots."
        )
        return [dict(SAR_DEFAULTS) for _ in hotspots]

    # Create flood composite (median for robustness)
    flood_image = flood_collection.median()

    # Create dry-season baseline for change detection
    baseline_year = get_baseline_year(date_str)
    baseline_months = BASELINE_MONTHS.get(city, [1, 2, 3, 4, 5])
    baseline_collection = s1_collection.filter(
        ee.Filter.calendarRange(baseline_year, baseline_year, "year")
    ).filter(
        ee.Filter.calendarRange(min(baseline_months), max(baseline_months), "month")
    )

    baseline_count = baseline_collection.size().getInfo()
    if baseline_count == 0:
        # Fallback: any available dry season data
        baseline_collection = s1_collection.filter(
            ee.Filter.calendarRange(min(baseline_months), max(baseline_months), "month")
        ).limit(50)

    baseline_image = baseline_collection.median()

    # Compute change: flood - baseline (negative = flooding)
    change_image = flood_image.subtract(baseline_image)

    # Build a combined image with all 4 features
    vv_vh_ratio = flood_image.select("VV").subtract(flood_image.select("VH")).rename("vv_vh_ratio")
    change_vv = change_image.select("VV").rename("change_magnitude")

    combined = ee.Image.cat([
        flood_image.select("VV").rename("vv_mean"),
        flood_image.select("VH").rename("vh_mean"),
        vv_vh_ratio,
        change_vv,
    ])

    # Extract at all hotspot locations using batched reduceRegions
    all_results = []
    for batch_start in range(0, len(hotspots), BATCH_SIZE):
        batch = hotspots[batch_start:batch_start + BATCH_SIZE]
        batch_results = _extract_batch_sar(batch, combined)
        all_results.extend(batch_results)

    return all_results


def _extract_batch_sar(
    points: List[Dict],
    combined_image: ee.Image,
) -> List[Dict]:
    """
    Extract SAR features for a batch of points using reduceRegions.

    Falls back to single-point extraction on batch failure.
    """
    try:
        return _extract_batch_sar_gee(points, combined_image)
    except Exception as e:
        if len(points) <= 1:
            logger.warning(f"  Single point SAR extraction failed: {e}. Using defaults.")
            return [dict(SAR_DEFAULTS)]

        logger.warning(
            f"  Batch of {len(points)} failed: {e}. Splitting..."
        )
        mid = len(points) // 2
        left = _extract_batch_sar(points[:mid], combined_image)
        right = _extract_batch_sar(points[mid:], combined_image)
        return left + right


def _extract_batch_sar_gee(
    points: List[Dict],
    combined_image: ee.Image,
) -> List[Dict]:
    """
    GEE reduceRegions call for SAR features at multiple points.
    """
    # Build FeatureCollection with buffer geometries
    ee_features = []
    for i, p in enumerate(points):
        pt = ee.Geometry.Point([p["lng"], p["lat"]])
        buf = pt.buffer(BUFFER_M)
        ee_features.append(ee.Feature(buf, {"_idx": i}))
    fc = ee.FeatureCollection(ee_features)

    # reduceRegions at 100m scale (efficiency vs 10m native)
    result = combined_image.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=100,
    ).getInfo()

    # Parse results in order
    by_idx = {}
    for f in result["features"]:
        idx = f["properties"]["_idx"]
        by_idx[idx] = f["properties"]

    results = []
    for i in range(len(points)):
        props = by_idx.get(i, {})
        results.append({
            "vv_mean": props.get("vv_mean") if props.get("vv_mean") is not None else SAR_DEFAULTS["vv_mean"],
            "vh_mean": props.get("vh_mean") if props.get("vh_mean") is not None else SAR_DEFAULTS["vh_mean"],
            "vv_vh_ratio": props.get("vv_vh_ratio") if props.get("vv_vh_ratio") is not None else SAR_DEFAULTS["vv_vh_ratio"],
            "change_magnitude": props.get("change_magnitude") if props.get("change_magnitude") is not None else SAR_DEFAULTS["change_magnitude"],
        })

    return results


# ---------------------------------------------------------------------------
# Default rate analysis
# ---------------------------------------------------------------------------

def is_default_value(feature_name: str, value: float) -> bool:
    """Check if a SAR feature value matches the known default."""
    default = SAR_DEFAULTS.get(feature_name, None)
    if default is None:
        return False
    return abs(value - default) < 1e-6


def compute_default_rate(all_features: List[Dict]) -> Dict[str, float]:
    """
    Compute per-feature and overall default rates.

    Returns dict with per-feature rates and 'overall' rate.
    """
    rates = {}
    total_defaults = 0
    total_values = 0

    for fname in SAR_FEATURE_NAMES:
        values = [f[fname] for f in all_features if fname in f]
        n_default = sum(1 for v in values if is_default_value(fname, v))
        rates[fname] = n_default / len(values) if values else 0.0
        total_defaults += n_default
        total_values += len(values)

    rates["overall"] = total_defaults / total_values if total_values else 0.0
    return rates


# ---------------------------------------------------------------------------
# Checkpointing
# ---------------------------------------------------------------------------

def checkpoint_path(city: str) -> Path:
    return CHECKPOINT_DIR / f"{city}_temporal_checkpoint.json"


def load_checkpoint(city: str) -> Optional[Dict]:
    path = checkpoint_path(city)
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    logger.info(
        f"  Loaded checkpoint: {data['completed_hotspots']}/{data['total_hotspots']} "
        f"hotspots, {data['completed_dates']}/{data['total_dates']} dates"
    )
    return data


def save_checkpoint(
    city: str,
    results: List[Dict],
    completed_hotspots: int,
    total_hotspots: int,
    completed_dates: int,
    total_dates: int,
    current_date_idx: int,
) -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "city": city,
        "completed_hotspots": completed_hotspots,
        "total_hotspots": total_hotspots,
        "completed_dates": completed_dates,
        "total_dates": total_dates,
        "current_date_idx": current_date_idx,
        "results": results,
    }
    with open(checkpoint_path(city), "w") as f:
        json.dump(data, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Storm cluster / effective-n counting
# ---------------------------------------------------------------------------

def count_effective_n(event_dates: Dict) -> Tuple[int, int]:
    """
    Count effective independent observations.

    Storm clusters (multi-day events from same system) count as 1
    independent observation, not multiple.

    Returns (total_dates, effective_independent_storms).
    """
    flood_dates = event_dates.get("flood_dates", [])
    dry_dates = event_dates.get("dry_dates", [])

    # Flood: count independent storms
    storm_clusters = event_dates.get("notes", {}).get("storm_clusters", {})
    independent_storms = event_dates.get("notes", {}).get("independent_storms", len(flood_dates))

    total_dates = len(flood_dates) + len(dry_dates)
    effective_n = independent_storms + len(dry_dates)

    return total_dates, effective_n


def determine_analysis_tier(effective_n: int) -> str:
    """
    Determine analysis tier based on effective date count.

    <8:  Descriptive only (effect sizes, no p-values)
    8-14: Mixed-effects model
    15+: Constrained XGBoost
    """
    if effective_n < 8:
        return "descriptive"
    elif effective_n <= 14:
        return "mixed-effects"
    else:
        return "xgboost"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_event_dates(city: str) -> Dict:
    """Load curated flood/dry event dates for a city."""
    path = OUTPUT_DIR / f"{city}_event_dates.json"
    if not path.exists():
        logger.error(f"Event dates not found: {path}")
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    n_flood = len(data.get("flood_dates", []))
    n_dry = len(data.get("dry_dates", []))
    logger.info(f"  Loaded {n_flood} flood + {n_dry} dry dates for {city}")
    return data


def load_hotspots(city: str) -> List[Dict]:
    """Load hotspot coordinates from backend data."""
    path = BACKEND_DATA / f"{city}_waterlogging_hotspots.json"
    if not path.exists():
        logger.error(f"Hotspot file not found: {path}")
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    hotspots = data.get("hotspots", [])
    logger.info(f"  Loaded {len(hotspots)} hotspots for {city}")
    return hotspots


# ---------------------------------------------------------------------------
# Save to NPZ
# ---------------------------------------------------------------------------

def results_to_npz(
    results: List[Dict],
    city: str,
    event_dates: Dict,
    default_rates: Dict,
    effective_n: int,
    analysis_tier: str,
) -> Path:
    """
    Save temporal extraction results to NPZ.

    Structure:
      features: (n_samples, 4) float64 — [vv_mean, vh_mean, vv_vh_ratio, change_magnitude]
      labels: (n_samples,) int32 — 1=flood, 0=dry
      hotspot_ids: (n_samples,) — hotspot name for each sample
      dates: (n_samples,) — date string for each sample
      feature_names: (4,) — SAR feature names
      metadata: JSON string with default_rates, effective_n, analysis_tier, storm_clusters
    """
    n = len(results)
    features = np.zeros((n, len(SAR_FEATURE_NAMES)), dtype=np.float64)
    labels = np.zeros(n, dtype=np.int32)
    hotspot_ids = []
    dates = []

    for i, r in enumerate(results):
        for j, fname in enumerate(SAR_FEATURE_NAMES):
            features[i, j] = r["features"].get(fname, SAR_DEFAULTS[fname])
        labels[i] = r["label"]
        hotspot_ids.append(r["hotspot_name"])
        dates.append(r["date"])

    metadata = {
        "city": city,
        "n_samples": n,
        "n_flood_dates": len(event_dates.get("flood_dates", [])),
        "n_dry_dates": len(event_dates.get("dry_dates", [])),
        "effective_n": effective_n,
        "analysis_tier": analysis_tier,
        "default_rates": default_rates,
        "storm_clusters": event_dates.get("notes", {}).get("storm_clusters", {}),
    }

    output_path = OUTPUT_DIR / f"{city}_temporal_features.npz"
    np.savez(
        output_path,
        features=features,
        labels=labels,
        hotspot_ids=np.array(hotspot_ids),
        dates=np.array(dates),
        feature_names=np.array(SAR_FEATURE_NAMES),
        metadata=json.dumps(metadata),
    )

    n_flood = int(labels.sum())
    n_dry = n - n_flood
    logger.info(
        f"  Saved {output_path.name}: {n} samples "
        f"({n_flood} flood, {n_dry} dry), "
        f"analysis tier: {analysis_tier}"
    )

    return output_path


# ---------------------------------------------------------------------------
# Main extraction loop
# ---------------------------------------------------------------------------

def process_city(city: str, resume: bool = False) -> None:
    """
    Full SAR temporal extraction pipeline for one city.

    Iterates date-first (not hotspot-first) because:
    1. Each date needs its own SAR composite — expensive to rebuild
    2. All hotspots share the same date window — batch via reduceRegions
    3. Checkpointing is per-date (coarser but simpler)
    """
    logger.info(f"\n{'=' * 60}")
    logger.info(f"PHASE 5: SAR Temporal Extraction -- {city.upper()}")
    logger.info(f"{'=' * 60}")

    # Load data
    event_dates = load_event_dates(city)
    hotspots = load_hotspots(city)
    total_dates, effective_n = count_effective_n(event_dates)
    analysis_tier = determine_analysis_tier(effective_n)

    logger.info(f"  Total dates: {total_dates}, Effective-n: {effective_n}")
    logger.info(f"  Analysis tier: {analysis_tier}")

    # Build date list with labels
    all_dates = []
    for fd in event_dates["flood_dates"]:
        all_dates.append({"date": fd["date"], "is_flood": True, "label": 1})
    for dd in event_dates["dry_dates"]:
        all_dates.append({"date": dd["date"], "is_flood": False, "label": 0})

    logger.info(f"  Processing {len(all_dates)} dates x {len(hotspots)} hotspots")

    # Build bounding geometry for SAR collection (city-wide)
    lats = [h["lat"] for h in hotspots]
    lngs = [h["lng"] for h in hotspots]
    margin = 0.05  # ~5km margin
    city_geometry = ee.Geometry.Rectangle([
        min(lngs) - margin, min(lats) - margin,
        max(lngs) + margin, max(lats) + margin,
    ])

    # Build SAR collection once (filtered to city bounds, with speckle filter)
    logger.info("  Building Sentinel-1 collection (with Refined Lee filter)...")
    s1_collection = get_s1_collection(city_geometry)
    total_images = s1_collection.size().getInfo()
    logger.info(f"  Total S1 images over {city}: {total_images}")

    # Resume from checkpoint
    results = []
    start_date_idx = 0

    if resume:
        ckpt = load_checkpoint(city)
        if ckpt:
            results = ckpt["results"]
            start_date_idx = ckpt["current_date_idx"]
            logger.info(f"  Resuming from date index {start_date_idx}")

    # Process each date
    city_t0 = time.time()

    for date_idx in range(start_date_idx, len(all_dates)):
        date_info = all_dates[date_idx]
        date_str = date_info["date"]
        is_flood = date_info["is_flood"]
        label = date_info["label"]
        label_str = "FLOOD" if is_flood else "DRY"

        window_start, window_end = build_date_window(date_str, is_flood)
        logger.info(
            f"\n  [{date_idx + 1}/{len(all_dates)}] {date_str} ({label_str}) "
            f"window: {window_start} to {window_end}"
        )

        t0 = time.time()

        # Extract SAR for all hotspots on this date
        date_features = extract_sar_for_date(
            hotspots=hotspots,
            date_str=date_str,
            is_flood=is_flood,
            city=city,
            s1_collection=s1_collection,
        )

        elapsed = time.time() - t0

        # Record results
        for i, features in enumerate(date_features):
            results.append({
                "hotspot_name": hotspots[i].get("name", f"hotspot_{i}"),
                "lat": hotspots[i]["lat"],
                "lng": hotspots[i]["lng"],
                "date": date_str,
                "label": label,
                "features": features,
            })

        # Per-date quality report
        n_defaults = sum(
            1 for f in date_features
            if all(is_default_value(k, v) for k, v in f.items())
        )
        logger.info(
            f"    {len(hotspots)} hotspots in {elapsed:.1f}s "
            f"({elapsed / len(hotspots):.2f}s/point). "
            f"{n_defaults} full-default points."
        )

        # Checkpoint after each date
        save_checkpoint(
            city=city,
            results=results,
            completed_hotspots=len(hotspots),
            total_hotspots=len(hotspots),
            completed_dates=date_idx + 1,
            total_dates=len(all_dates),
            current_date_idx=date_idx + 1,
        )

        # Rate limiting: 2s pause between dates to avoid GEE throttling
        if date_idx < len(all_dates) - 1:
            time.sleep(2)

    city_elapsed = time.time() - city_t0

    # Default rate analysis
    all_features = [r["features"] for r in results]
    default_rates = compute_default_rate(all_features)

    logger.info(f"\n  {'=' * 40}")
    logger.info(f"  {city.upper()} EXTRACTION COMPLETE in {city_elapsed:.0f}s")
    logger.info(f"  Total samples: {len(results)}")
    logger.info(f"  Default rates:")
    for fname, rate in default_rates.items():
        flag = " *** UNRELIABLE ***" if rate > SAR_DEFAULT_RATE_THRESHOLD and fname != "overall" else ""
        logger.info(f"    {fname}: {rate:.1%}{flag}")

    if default_rates["overall"] > SAR_DEFAULT_RATE_THRESHOLD:
        logger.warning(
            f"  WARNING: Overall default rate {default_rates['overall']:.1%} "
            f"exceeds {SAR_DEFAULT_RATE_THRESHOLD:.0%} threshold. "
            f"SAR data may be unreliable for {city}."
        )

    # Save NPZ
    output_path = results_to_npz(
        results=results,
        city=city,
        event_dates=event_dates,
        default_rates=default_rates,
        effective_n=effective_n,
        analysis_tier=analysis_tier,
    )

    logger.info(f"  Output: {output_path}")
    logger.info(f"  Analysis tier: {analysis_tier} (effective-n={effective_n})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Phase 5: SAR temporal feature extraction (Bangalore + Yogyakarta)"
    )
    parser.add_argument(
        "--city",
        choices=TEMPORAL_CITIES,
        help="Process a single city (default: both cities sequentially)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint",
    )
    args = parser.parse_args()

    # Authenticate GEE
    logger.info("Authenticating with Google Earth Engine...")
    if not authenticate_gee():
        logger.error("FATAL: GEE authentication failed. Cannot proceed.")
        sys.exit(1)

    # Process cities
    cities = [args.city] if args.city else TEMPORAL_CITIES

    for city in cities:
        try:
            process_city(city, resume=args.resume)
        except Exception as e:
            logger.error(f"FAILED processing {city}: {e}")
            import traceback
            traceback.print_exc()
            if len(cities) > 1:
                logger.info("Continuing to next city...")
            else:
                raise

    # Final summary
    logger.info(f"\n{'=' * 60}")
    logger.info("SAR TEMPORAL EXTRACTION COMPLETE")
    logger.info(f"{'=' * 60}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info("Next step: Phase 6 (05_temporal_analysis.py)")


if __name__ == "__main__":
    main()
