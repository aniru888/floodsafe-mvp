"""
Phase 2: Full Static Feature Extraction for All Cities.

For each city:
  1. Load ALL hotspots from apps/backend/data/{city}_waterlogging_hotspots.json
  2. Generate 500 quadrant-stratified background points within city bounds
     (min 500m from any hotspot)
  3. Extract whitelisted GEE features for all hotspot + background points
  4. Save to .npz files with metadata

Batched extraction: Uses GEE reduceRegions() to process ~100 points per API
call (2 calls per batch: terrain at 30m, land cover at 10m). This gives
~650x fewer API calls vs per-point extraction.

Fallback: If a batch fails (GEE timeout/memory), it splits in half
recursively until reaching single-point extraction with retries. This
ensures per-point error tracking while maximizing throughput.

Estimated runtime: ~15-30 minutes for all 5 cities (vs ~8 hours per-point).

Usage:
    python scripts/02_static_profiling.py                    # All cities
    python scripts/02_static_profiling.py --city bangalore   # Single city
    python scripts/02_static_profiling.py --city bangalore --resume
    python scripts/02_static_profiling.py --bg-only          # Only generate background points (no GEE)

Output:
    output/profiles/{city}_hotspot_features.npz
    output/profiles/{city}_background_features.npz
"""

import argparse
import json
import logging
import math
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

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
CONFIG_DIR = SCRIPT_DIR.parent / "config"
OUTPUT_DIR = SCRIPT_DIR.parent / "output" / "profiles"
CHECKPOINT_DIR = SCRIPT_DIR.parent / "output" / "profiles" / "checkpoints"
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
BACKEND_DATA = PROJECT_ROOT / "apps" / "backend" / "data"
CREDENTIALS = PROJECT_ROOT / "apps" / "ml-service" / "credentials" / "gee-service-account.json"

# GEE datasets
SRTM = "USGS/SRTMGL1_003"
WORLDCOVER = "ESA/WorldCover/v200"

# WorldCover class values
WC_TREE = 10
WC_GRASS = 30
WC_CROP = 40
WC_BUILT = 50
WC_BARE = 60
WC_WATER = 80
WC_WETLAND = 90

# Extraction parameters
BUFFER_M = 250  # Buffer radius for feature extraction (meters)
BATCH_SIZE = 100  # Points per GEE reduceRegions call
MAX_RETRIES = 3
RETRY_BACKOFF_S = 5.0  # Multiplied by retry number
BACKGROUND_POINTS_PER_CITY = 500
MIN_DISTANCE_FROM_HOTSPOT_KM = 0.5  # 500 meters
MAX_ATTEMPTS_PER_POINT = 1000  # Max random samples before giving up

ALL_CITIES = ["delhi", "bangalore", "yogyakarta", "singapore", "indore"]

# Feature group membership (for routing to correct image stack)
TERRAIN_FEATURES = {"elevation", "slope", "aspect", "tpi", "twi"}
LANDCOVER_FEATURES = {
    "built_up_pct", "vegetation_pct", "cropland_pct",
    "water_pct", "bare_pct", "grass_pct", "wetland_pct",
}


# ---------------------------------------------------------------------------
# GEE Authentication
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
# GEE Image Stacks (built once, reused across batches)
# ---------------------------------------------------------------------------

def build_terrain_stack() -> ee.Image:
    """
    Build a 5-band terrain image stack from SRTM.

    Bands: elevation, slope, aspect, tpi, twi
    All at native 30m resolution.
    """
    srtm = ee.Image(SRTM)
    elevation = srtm.select("elevation")
    terrain = ee.Terrain.products(srtm)

    # TPI: elevation minus focal mean (300m radius neighborhood)
    focal_mean = elevation.focalMean(radius=300, units="meters")
    tpi = elevation.subtract(focal_mean).rename("tpi")

    # TWI: ln(contributing_area / tan(slope))
    # Using pixel area (900 m^2) as proxy for contributing area
    slope_rad = ee.Terrain.slope(srtm).multiply(math.pi).divide(180)
    tan_slope = slope_rad.tan().max(0.001)  # Clamp to avoid div-by-zero
    twi = ee.Image.constant(900).divide(tan_slope).log().rename("twi")

    return ee.Image.cat([
        elevation,                        # band: 'elevation'
        terrain.select("slope"),          # band: 'slope'
        terrain.select("aspect"),         # band: 'aspect'
        tpi,                              # band: 'tpi'
        twi,                              # band: 'twi'
    ])


def build_landcover_stack() -> ee.Image:
    """
    Build a 7-band land cover binary mask stack from ESA WorldCover.

    Each band is a binary mask (0 or 1) for one land cover class.
    When reduced with mean(), the result IS the fraction (0.0-1.0).
    Multiply by 100 to get percentage.

    Bands: built_up_pct, vegetation_pct, cropland_pct, water_pct,
           bare_pct, grass_pct, wetland_pct
    All at native 10m resolution.
    """
    wc = ee.ImageCollection(WORLDCOVER).mosaic().select("Map")

    return ee.Image.cat([
        wc.eq(WC_BUILT).rename("built_up_pct"),
        wc.eq(WC_TREE).rename("vegetation_pct"),
        wc.eq(WC_CROP).rename("cropland_pct"),
        wc.eq(WC_WATER).rename("water_pct"),
        wc.eq(WC_BARE).rename("bare_pct"),
        wc.eq(WC_GRASS).rename("grass_pct"),
        wc.eq(WC_WETLAND).rename("wetland_pct"),
    ])


# ---------------------------------------------------------------------------
# Batched GEE Extraction
# ---------------------------------------------------------------------------

def _extract_batch_gee(
    points: List[Dict],
    terrain_stack: ee.Image,
    lc_stack: ee.Image,
    whitelist: List[str],
) -> List[Dict]:
    """
    Extract features for a batch of points using 2 reduceRegions calls.

    Args:
        points: List of dicts with 'lat', 'lng' keys
        terrain_stack: 5-band terrain image (from build_terrain_stack)
        lc_stack: 7-band land cover image (from build_landcover_stack)
        whitelist: Feature names to include in results

    Returns:
        List of per-point feature dicts (whitelisted only).
        Each dict maps feature_name -> value (or None if missing).

    Raises:
        Exception on GEE error (caller handles fallback).
    """
    # Build FeatureCollection with 250m buffer geometries
    ee_features = []
    for i, p in enumerate(points):
        pt = ee.Geometry.Point([p["lng"], p["lat"]])
        buf = pt.buffer(BUFFER_M)
        ee_features.append(ee.Feature(buf, {"_idx": i}))
    fc = ee.FeatureCollection(ee_features)

    # Determine which image groups this whitelist needs
    need_terrain = bool(TERRAIN_FEATURES & set(whitelist))
    need_lc = bool(LANDCOVER_FEATURES & set(whitelist))

    # Extract terrain features (scale=30m, SRTM native resolution)
    terrain_by_idx: Dict[int, Dict] = {}
    if need_terrain:
        result = terrain_stack.reduceRegions(
            collection=fc,
            reducer=ee.Reducer.mean(),
            scale=30,
        ).getInfo()
        for f in result["features"]:
            idx = f["properties"]["_idx"]
            terrain_by_idx[idx] = f["properties"]

    # Extract land cover features (scale=10m, WorldCover native resolution)
    lc_by_idx: Dict[int, Dict] = {}
    if need_lc:
        result = lc_stack.reduceRegions(
            collection=fc,
            reducer=ee.Reducer.mean(),
            scale=10,
        ).getInfo()
        for f in result["features"]:
            idx = f["properties"]["_idx"]
            lc_by_idx[idx] = f["properties"]

    # Assemble per-point results in input order
    results = []
    for i in range(len(points)):
        t_props = terrain_by_idx.get(i, {})
        l_props = lc_by_idx.get(i, {})
        features: Dict[str, Optional[float]] = {}

        for key in whitelist:
            if key in TERRAIN_FEATURES:
                features[key] = t_props.get(key)
            elif key in LANDCOVER_FEATURES:
                val = l_props.get(key)
                # mean of binary mask gives fraction (0-1), convert to %
                features[key] = round(val * 100, 2) if val is not None else None
            else:
                features[key] = None

        results.append(features)

    return results


def _extract_with_fallback(
    points: List[Dict],
    terrain_stack: ee.Image,
    lc_stack: ee.Image,
    whitelist: List[str],
    depth: int = 0,
) -> List[Dict]:
    """
    Adaptive batched extraction with binary split fallback.

    Strategy:
      1. Try extracting all points in one batch
      2. On failure: split in half, recurse on each half
      3. At single-point level: retry up to MAX_RETRIES times
      4. If single point still fails: record null features

    This guarantees per-point results regardless of batch failures.
    Max recursion depth for batch of 100: log2(100) ~ 7 levels.

    Args:
        points: Points to extract (subset being processed)
        terrain_stack: Pre-built terrain image stack
        lc_stack: Pre-built land cover image stack
        whitelist: Feature names to extract
        depth: Current recursion depth (for logging indentation)

    Returns:
        List of per-point feature dicts, same length as points.
    """
    indent = "  " * (depth + 1)
    n = len(points)

    if n == 0:
        return []

    # --- Single point: final fallback with retries ---
    if n == 1:
        point_name = points[0].get("name", f"({points[0]['lat']:.4f}, {points[0]['lng']:.4f})")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = _extract_batch_gee(points, terrain_stack, lc_stack, whitelist)
                return result
            except Exception as e:
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF_S * attempt
                    logger.warning(
                        f"{indent}Point {point_name} attempt {attempt}/{MAX_RETRIES} "
                        f"failed: {e}. Retrying in {wait:.0f}s..."
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        f"{indent}FAILED: {point_name} after {MAX_RETRIES} attempts. "
                        f"Recording nulls."
                    )
                    return [{k: None for k in whitelist}]

    # --- Batch extraction with split-on-failure ---
    try:
        result = _extract_batch_gee(points, terrain_stack, lc_stack, whitelist)
        return result
    except Exception as e:
        logger.warning(
            f"{indent}Batch of {n} failed: {e}. Splitting into two halves..."
        )
        mid = n // 2
        left = _extract_with_fallback(
            points[:mid], terrain_stack, lc_stack, whitelist, depth + 1
        )
        right = _extract_with_fallback(
            points[mid:], terrain_stack, lc_stack, whitelist, depth + 1
        )
        return left + right

    # Unreachable, but makes the return type explicit
    return []  # type: ignore[unreachable]


def extract_features_batched(
    points: List[Dict],
    whitelist: List[str],
    city: str,
    point_type: str,
    terrain_stack: ee.Image,
    lc_stack: ee.Image,
    resume: bool = False,
) -> List[Dict]:
    """
    Main extraction entry point. Processes points in batches with checkpointing.

    Splits points into BATCH_SIZE chunks, extracts each chunk via GEE
    reduceRegions, and saves checkpoints after each batch completes.

    Args:
        points: All points to extract (hotspots or background)
        whitelist: Feature names to extract
        city: City name (for checkpoint filenames)
        point_type: 'hotspot' or 'background'
        terrain_stack: Pre-built terrain GEE image
        lc_stack: Pre-built land cover GEE image
        resume: Whether to resume from checkpoint

    Returns:
        List of dicts with 'name', 'lat', 'lng', 'features' keys.
    """
    results: List[Dict] = []
    start_idx = 0

    # Resume from checkpoint if requested
    if resume:
        ckpt = load_checkpoint(city, point_type)
        if ckpt and ckpt["whitelist"] == whitelist:
            results = ckpt["results"]
            start_idx = ckpt["completed"]
            logger.info(f"  Resuming from point {start_idx}/{len(points)}")
        elif ckpt:
            logger.warning(
                "  Checkpoint exists but whitelist changed. Starting fresh."
            )

    total = len(points)
    remaining_points = points[start_idx:]

    # Process in batches
    for batch_start in range(0, len(remaining_points), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(remaining_points))
        batch = remaining_points[batch_start:batch_end]
        absolute_start = start_idx + batch_start
        absolute_end = start_idx + batch_end

        logger.info(
            f"  Batch [{absolute_start + 1}-{absolute_end}/{total}] "
            f"({len(batch)} {point_type} points)"
        )

        t0 = time.time()
        batch_features = _extract_with_fallback(
            batch, terrain_stack, lc_stack, whitelist
        )
        elapsed = time.time() - t0

        # Combine batch results with point metadata
        for i, features in enumerate(batch_features):
            point = batch[i]
            results.append({
                "name": point.get("name", f"point_{absolute_start + i}"),
                "lat": point["lat"],
                "lng": point["lng"],
                "features": features,
            })

        # Per-batch quality report
        n_null = sum(
            1 for f in batch_features
            for v in f.values()
            if v is None
        )
        n_total_vals = sum(len(f) for f in batch_features)
        pct_valid = (1 - n_null / n_total_vals) * 100 if n_total_vals > 0 else 0

        logger.info(
            f"    Completed in {elapsed:.1f}s "
            f"({elapsed/len(batch):.1f}s/point avg). "
            f"{pct_valid:.0f}% valid values."
        )

        # Checkpoint after each batch
        save_checkpoint(city, point_type, whitelist, results, total)
        logger.info(f"    Checkpoint: {len(results)}/{total} complete")

    return results


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Great-circle distance between two points on Earth (km).

    Uses the haversine formula. Accurate to ~0.1% for distances relevant
    to our 500m exclusion buffer.
    """
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Background point generation
# ---------------------------------------------------------------------------

def generate_background_points(
    city: str,
    hotspots: List[Dict],
    n: int = BACKGROUND_POINTS_PER_CITY,
    min_dist_km: float = MIN_DISTANCE_FROM_HOTSPOT_KM,
) -> List[Dict]:
    """
    Generate n stratified random background points within city bounds.

    Strategy:
      1. Divide bounding box into 4 quadrants (NW, NE, SW, SE)
      2. Generate n/4 points per quadrant
      3. Each candidate must be >= min_dist_km from ALL hotspots

    This prevents accidental clustering and ensures geographic coverage.
    The 500m buffer prevents "contaminating" the background class with
    locations that are actually flood-prone.

    Returns list of dicts with 'lat', 'lng', 'name', 'quadrant' keys.
    """
    # Load city bounds
    with open(CONFIG_DIR / "city_bounds.json") as f:
        bounds = json.load(f)[city]

    min_lat, max_lat = bounds["min_lat"], bounds["max_lat"]
    min_lng, max_lng = bounds["min_lng"], bounds["max_lng"]
    mid_lat = (min_lat + max_lat) / 2
    mid_lng = (min_lng + max_lng) / 2

    # Hotspot coords for distance checking
    hotspot_coords = [(h["lat"], h["lng"]) for h in hotspots]

    # Define quadrants: (name, lat_min, lat_max, lng_min, lng_max)
    quadrants = [
        ("NW", mid_lat, max_lat, min_lng, mid_lng),
        ("NE", mid_lat, max_lat, mid_lng, max_lng),
        ("SW", min_lat, mid_lat, min_lng, mid_lng),
        ("SE", min_lat, mid_lat, mid_lng, max_lng),
    ]

    points_per_quadrant = n // 4
    remainder = n % 4  # Distribute leftover to first quadrants

    all_points = []
    rng = random.Random(42)  # Reproducible seed

    for q_idx, (q_name, lat_lo, lat_hi, lng_lo, lng_hi) in enumerate(quadrants):
        target = points_per_quadrant + (1 if q_idx < remainder else 0)
        generated = 0
        attempts = 0

        while generated < target and attempts < target * MAX_ATTEMPTS_PER_POINT:
            attempts += 1
            lat = rng.uniform(lat_lo, lat_hi)
            lng = rng.uniform(lng_lo, lng_hi)

            # Check distance from all hotspots
            too_close = False
            for h_lat, h_lng in hotspot_coords:
                if haversine_km(lat, lng, h_lat, h_lng) < min_dist_km:
                    too_close = True
                    break

            if not too_close:
                generated += 1
                all_points.append({
                    "lat": round(lat, 6),
                    "lng": round(lng, 6),
                    "name": f"bg_{city}_{q_name}_{generated:03d}",
                    "quadrant": q_name,
                })

        if generated < target:
            logger.warning(
                f"  {city} quadrant {q_name}: only generated {generated}/{target} "
                f"points after {attempts} attempts. Hotspot density may be too high."
            )

    logger.info(
        f"  Generated {len(all_points)} background points for {city} "
        f"({points_per_quadrant}+ per quadrant, seed=42)"
    )
    return all_points


# ---------------------------------------------------------------------------
# Feature whitelist
# ---------------------------------------------------------------------------

def load_feature_whitelist(city: str) -> List[str]:
    """Load the list of features that passed Phase 1 trial for this city."""
    trial_path = CONFIG_DIR / f"{city}_feature_trial.json"
    if not trial_path.exists():
        logger.error(f"Feature trial results not found: {trial_path}")
        sys.exit(1)

    with open(trial_path) as f:
        trial = json.load(f)

    whitelist = trial["passed_features"]
    logger.info(f"  {city} whitelist ({len(whitelist)} features): {', '.join(whitelist)}")
    return whitelist


# ---------------------------------------------------------------------------
# Hotspot loading
# ---------------------------------------------------------------------------

def load_all_hotspots(city: str) -> List[Dict]:
    """Load all hotspots for a city from backend data."""
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
# Checkpointing
# ---------------------------------------------------------------------------

def checkpoint_path(city: str, point_type: str) -> Path:
    """Get checkpoint file path for a city/type combination."""
    return CHECKPOINT_DIR / f"{city}_{point_type}_checkpoint.json"


def load_checkpoint(city: str, point_type: str) -> Optional[Dict]:
    """Load checkpoint if it exists. Returns None if no checkpoint."""
    path = checkpoint_path(city, point_type)
    if not path.exists():
        return None

    with open(path) as f:
        data = json.load(f)

    logger.info(
        f"  Loaded checkpoint: {data['completed']}/{data['total']} "
        f"{point_type} points for {city}"
    )
    return data


def save_checkpoint(
    city: str,
    point_type: str,
    whitelist: List[str],
    results: List[Dict],
    total: int,
) -> None:
    """Save extraction progress to checkpoint file."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "city": city,
        "point_type": point_type,
        "whitelist": whitelist,
        "completed": len(results),
        "total": total,
        "results": results,
    }
    path = checkpoint_path(city, point_type)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Save to NPZ
# ---------------------------------------------------------------------------

def results_to_npz(
    results: List[Dict],
    whitelist: List[str],
    output_path: Path,
) -> None:
    """
    Convert extraction results to a .npz file.

    Saves:
      - features: np.float64 array of shape (n_points, n_features)
        NaN for missing values (not None, which isn't NumPy-compatible)
      - feature_names: list of feature names (order matches columns)
      - lats: np.float64 array of latitudes
      - lngs: np.float64 array of longitudes
      - names: list of point names
    """
    n = len(results)
    n_features = len(whitelist)

    features = np.full((n, n_features), np.nan, dtype=np.float64)
    lats = np.zeros(n, dtype=np.float64)
    lngs = np.zeros(n, dtype=np.float64)
    names = []

    for i, r in enumerate(results):
        lats[i] = r["lat"]
        lngs[i] = r["lng"]
        names.append(r["name"])
        for j, fname in enumerate(whitelist):
            val = r["features"].get(fname)
            if val is not None:
                features[i, j] = float(val)
            # else: stays NaN

    np.savez(
        output_path,
        features=features,
        feature_names=np.array(whitelist),
        lats=lats,
        lngs=lngs,
        names=np.array(names),
    )

    # Summary stats
    n_nan = np.isnan(features).sum()
    n_total = features.size
    pct_valid = (1 - n_nan / n_total) * 100 if n_total > 0 else 0

    logger.info(
        f"  Saved {output_path.name}: {n} points x {n_features} features, "
        f"{pct_valid:.1f}% valid values"
    )


# ---------------------------------------------------------------------------
# Process a single city
# ---------------------------------------------------------------------------

def process_city(
    city: str,
    terrain_stack: ee.Image,
    lc_stack: ee.Image,
    resume: bool = False,
    bg_only: bool = False,
) -> None:
    """
    Full extraction pipeline for one city.

    Steps:
      1. Load hotspots and feature whitelist
      2. Generate (or load cached) background points
      3. Extract features for hotspots using batched GEE
      4. Extract features for background points
      5. Save .npz files
    """
    logger.info(f"\n{'=' * 60}")
    logger.info(f"PHASE 2: Static Profiling -- {city.upper()}")
    logger.info(f"{'=' * 60}")

    # Load data
    hotspots = load_all_hotspots(city)
    whitelist = load_feature_whitelist(city)

    # Generate background points
    bg_points_path = OUTPUT_DIR / f"{city}_background_points.json"
    if resume and bg_points_path.exists():
        with open(bg_points_path) as f:
            bg_points = json.load(f)
        logger.info(f"  Loaded {len(bg_points)} cached background points")
    else:
        bg_points = generate_background_points(city, hotspots)
        # Cache the background points for reproducibility
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(bg_points_path, "w") as f:
            json.dump(bg_points, f, indent=2)
        logger.info(f"  Cached background points to {bg_points_path.name}")

    if bg_only:
        logger.info("  --bg-only: Skipping GEE extraction.")
        logger.info(f"  Background points saved to {bg_points_path}")
        return

    # Extract hotspot features
    logger.info(f"\n--- Extracting features for {len(hotspots)} hotspots ---")
    city_t0 = time.time()

    hotspot_results = extract_features_batched(
        points=hotspots,
        whitelist=whitelist,
        city=city,
        point_type="hotspot",
        terrain_stack=terrain_stack,
        lc_stack=lc_stack,
        resume=resume,
    )

    hotspot_npz = OUTPUT_DIR / f"{city}_hotspot_features.npz"
    results_to_npz(hotspot_results, whitelist, hotspot_npz)

    # Extract background features
    logger.info(f"\n--- Extracting features for {len(bg_points)} background points ---")
    bg_results = extract_features_batched(
        points=bg_points,
        whitelist=whitelist,
        city=city,
        point_type="background",
        terrain_stack=terrain_stack,
        lc_stack=lc_stack,
        resume=resume,
    )

    bg_npz = OUTPUT_DIR / f"{city}_background_features.npz"
    results_to_npz(bg_results, whitelist, bg_npz)

    city_elapsed = time.time() - city_t0
    logger.info(f"\n  {city.upper()} COMPLETE in {city_elapsed:.0f}s")
    logger.info(f"    Hotspots:   {hotspot_npz}")
    logger.info(f"    Background: {bg_npz}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Phase 2: Full static feature extraction for all cities"
    )
    parser.add_argument(
        "--city",
        choices=ALL_CITIES,
        help="Process a single city (default: all cities sequentially)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint (skips already-extracted points)",
    )
    parser.add_argument(
        "--bg-only",
        action="store_true",
        help="Only generate background points (no GEE extraction)",
    )
    args = parser.parse_args()

    # Authenticate GEE and build image stacks (unless bg-only mode)
    terrain_stack = None
    lc_stack = None

    if not args.bg_only:
        logger.info("Authenticating with Google Earth Engine...")
        if not authenticate_gee():
            logger.error("FATAL: GEE authentication failed. Cannot proceed.")
            sys.exit(1)

        logger.info("Building GEE image stacks (reused across all batches)...")
        terrain_stack = build_terrain_stack()
        lc_stack = build_landcover_stack()
        logger.info("  Terrain stack: 5 bands (elevation, slope, aspect, tpi, twi)")
        logger.info("  Land cover stack: 7 bands (built_up, vegetation, cropland, water, bare, grass, wetland)")

    # Process cities
    cities = [args.city] if args.city else ALL_CITIES

    for city in cities:
        try:
            process_city(
                city,
                terrain_stack=terrain_stack,
                lc_stack=lc_stack,
                resume=args.resume,
                bg_only=args.bg_only,
            )
        except Exception as e:
            logger.error(f"FAILED processing {city}: {e}")
            if len(cities) > 1:
                logger.info("Continuing to next city...")
            else:
                raise

    # Final summary
    logger.info(f"\n{'=' * 60}")
    logger.info("ALL CITIES PROCESSED")
    logger.info(f"{'=' * 60}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info("Next step: Phase 3 (statistical_tests.py)")


if __name__ == "__main__":
    main()
