"""
Phase 3: Statistical Analysis of Static Feature Profiles.

For each city:
  1. Load hotspot + background feature NPZ files from Phase 2
  2. Data quality: null counts, Shapiro-Wilk normality
  3. Spatial autocorrelation: Moran's I (libpysal/esda)
  4. Association tests: Mann-Whitney U, KS, Cliff's Delta (PRIMARY)
  5. Multiple comparison correction: Benjamini-Hochberg
  6. Per-hotspot z-scores (significant features only)
  7. Multicollinearity: VIF check
  8. Cross-city consistency: forest plot of effect sizes

Key design decisions (from profiling design doc):
  - Cliff's Delta over Cohen's d (no normality assumption for geospatial data)
  - p-values SECONDARY to effect sizes (n=500 makes everything significant)
  - Spatial block bootstrap for honest CIs when Moran's I significant
  - Per-city feature whitelists (what works in hilly Yogyakarta fails in flat Delhi)

Usage:
    python scripts/03_statistical_analysis.py                    # All cities
    python scripts/03_statistical_analysis.py --city bangalore   # Single city

Output:
    output/profiles/{city}_profile_analysis.json
    output/profiles/{city}_hotspot_zscores.json
    output/profiles/cross_city_summary.json
    output/profiles/forest_plot.png
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.outliers_influence import variance_inflation_factor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "output" / "profiles"

ALL_CITIES = ["delhi", "bangalore", "yogyakarta", "singapore", "indore"]

# Thresholds
CLIFF_DELTA_THRESHOLD = 0.3    # Minimum |delta| for "meaningful" effect
BH_ALPHA = 0.05               # Benjamini-Hochberg significance level
VIF_THRESHOLD = 5.0            # VIF > 5 indicates multicollinearity
NULL_THRESHOLD = 0.20          # >20% nulls -> drop feature
MORAN_P_THRESHOLD = 0.05       # Moran's I significance threshold


# ---------------------------------------------------------------------------
# Cliff's Delta (non-parametric effect size)
# ---------------------------------------------------------------------------

def cliffs_delta(x: np.ndarray, y: np.ndarray) -> Tuple[float, str]:
    """
    Compute Cliff's Delta: probability that a random x > random y,
    minus probability that a random y > random x.

    Range: [-1, +1]
      +1: all x > all y
      -1: all y > all x
       0: no tendency

    Interpretation (Romano et al., 2006):
      |delta| < 0.147: negligible
      |delta| < 0.33:  small
      |delta| < 0.474: medium
      |delta| >= 0.474: large

    This is preferred over Cohen's d because geospatial features
    are typically bounded, skewed, and multimodal — violating
    the normality assumption that Cohen's d requires.
    """
    n_x, n_y = len(x), len(y)
    if n_x == 0 or n_y == 0:
        return 0.0, "negligible"

    # Vectorized comparison (memory efficient for n <= 500)
    more = 0
    less = 0
    for xi in x:
        more += np.sum(xi > y)
        less += np.sum(xi < y)

    delta = (more - less) / (n_x * n_y)

    # Classify magnitude
    abs_delta = abs(delta)
    if abs_delta < 0.147:
        magnitude = "negligible"
    elif abs_delta < 0.33:
        magnitude = "small"
    elif abs_delta < 0.474:
        magnitude = "medium"
    else:
        magnitude = "large"

    return round(delta, 4), magnitude


# ---------------------------------------------------------------------------
# Moran's I (spatial autocorrelation)
# ---------------------------------------------------------------------------

def compute_morans_i(
    values: np.ndarray,
    lats: np.ndarray,
    lngs: np.ndarray,
    n_permutations: int = 999,
) -> Dict:
    """
    Compute Moran's I for spatial autocorrelation using KNN weights.

    If Moran's I is significant (p < 0.05), it means nearby hotspots
    have correlated feature values — the effective sample size is
    smaller than the nominal count.

    Uses esda + libpysal for computation.
    """
    try:
        from esda.moran import Moran
        from libpysal.weights import KNN

        # Build spatial weights (k=8 nearest neighbors)
        points = np.column_stack([lngs, lats])
        w = KNN.from_array(points, k=min(8, len(points) - 1))
        w.transform = "R"  # Row-standardize

        mi = Moran(values, w, permutations=n_permutations)

        return {
            "morans_i": round(float(mi.I), 4),
            "expected_i": round(float(mi.EI), 4),
            "p_value": round(float(mi.p_sim), 4),
            "z_score": round(float(mi.z_sim), 4),
            "significant": bool(mi.p_sim < MORAN_P_THRESHOLD),
        }

    except Exception as e:
        logger.warning(f"Moran's I computation failed: {e}")
        return {
            "morans_i": None,
            "expected_i": None,
            "p_value": None,
            "z_score": None,
            "significant": None,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Data quality checks
# ---------------------------------------------------------------------------

def check_data_quality(
    features: np.ndarray,
    feature_names: List[str],
) -> Dict:
    """
    Per-feature data quality: null rate, normality, basic stats.

    Returns dict with per-feature quality report + list of features to drop.
    """
    report = {}
    drop_features = []

    for j, fname in enumerate(feature_names):
        col = features[:, j]
        n_total = len(col)
        n_nan = int(np.isnan(col).sum())
        null_rate = n_nan / n_total if n_total > 0 else 0

        valid = col[~np.isnan(col)]

        # Shapiro-Wilk normality test (max 5000 samples)
        if len(valid) >= 8:
            sample = valid[:5000] if len(valid) > 5000 else valid
            shapiro_stat, shapiro_p = scipy_stats.shapiro(sample)
            is_normal = shapiro_p > 0.05
        else:
            shapiro_stat, shapiro_p = None, None
            is_normal = None

        report[fname] = {
            "n_total": n_total,
            "n_valid": int(len(valid)),
            "null_rate": round(null_rate, 4),
            "mean": round(float(np.mean(valid)), 4) if len(valid) > 0 else None,
            "std": round(float(np.std(valid)), 4) if len(valid) > 0 else None,
            "median": round(float(np.median(valid)), 4) if len(valid) > 0 else None,
            "min": round(float(np.min(valid)), 4) if len(valid) > 0 else None,
            "max": round(float(np.max(valid)), 4) if len(valid) > 0 else None,
            "shapiro_w": round(float(shapiro_stat), 4) if shapiro_stat is not None else None,
            "shapiro_p": round(float(shapiro_p), 6) if shapiro_p is not None else None,
            "is_normal": is_normal,
        }

        if null_rate > NULL_THRESHOLD:
            drop_features.append(fname)
            logger.warning(f"    {fname}: {null_rate:.1%} null rate -> DROPPING")

    return {"features": report, "drop_features": drop_features}


# ---------------------------------------------------------------------------
# Association tests
# ---------------------------------------------------------------------------

def run_association_tests(
    hotspot_features: np.ndarray,
    background_features: np.ndarray,
    feature_names: List[str],
    hotspot_lats: np.ndarray,
    hotspot_lngs: np.ndarray,
) -> Dict:
    """
    Per-feature statistical comparison: hotspots vs background.

    Returns dict with per-feature test results + Moran's I for hotspots.
    """
    results = {}
    p_values = []
    valid_features = []

    for j, fname in enumerate(feature_names):
        h_col = hotspot_features[:, j]
        b_col = background_features[:, j]

        # Remove NaNs
        h_valid = h_col[~np.isnan(h_col)]
        b_valid = b_col[~np.isnan(b_col)]

        if len(h_valid) < 5 or len(b_valid) < 5:
            logger.warning(f"    {fname}: too few valid values (h={len(h_valid)}, b={len(b_valid)})")
            results[fname] = {"skipped": True, "reason": "insufficient data"}
            continue

        # Mann-Whitney U test
        mw_stat, mw_p = scipy_stats.mannwhitneyu(h_valid, b_valid, alternative="two-sided")

        # Kolmogorov-Smirnov test
        ks_stat, ks_p = scipy_stats.ks_2samp(h_valid, b_valid)

        # Cliff's Delta (PRIMARY effect size)
        delta, magnitude = cliffs_delta(h_valid, b_valid)

        # Direction of difference
        h_median = float(np.median(h_valid))
        b_median = float(np.median(b_valid))
        direction = "higher" if h_median > b_median else "lower" if h_median < b_median else "equal"

        # Moran's I for hotspot spatial autocorrelation
        # Only compute for features with enough hotspots
        morans = None
        if len(h_valid) >= 20 and len(hotspot_lats) == len(h_col):
            valid_mask = ~np.isnan(h_col)
            if valid_mask.sum() >= 20:
                morans = compute_morans_i(
                    h_col[valid_mask],
                    hotspot_lats[valid_mask],
                    hotspot_lngs[valid_mask],
                )

        results[fname] = {
            "hotspot_median": round(h_median, 4),
            "background_median": round(b_median, 4),
            "hotspot_mean": round(float(np.mean(h_valid)), 4),
            "background_mean": round(float(np.mean(b_valid)), 4),
            "direction": direction,
            "mann_whitney_u": round(float(mw_stat), 2),
            "mann_whitney_p": round(float(mw_p), 8),
            "ks_statistic": round(float(ks_stat), 4),
            "ks_p": round(float(ks_p), 8),
            "cliffs_delta": delta,
            "cliffs_magnitude": magnitude,
            "morans_i": morans,
        }

        p_values.append(mw_p)
        valid_features.append(fname)

    # Benjamini-Hochberg correction for multiple testing
    if p_values:
        reject, corrected_p, _, _ = multipletests(p_values, alpha=BH_ALPHA, method="fdr_bh")
        for i, fname in enumerate(valid_features):
            results[fname]["bh_corrected_p"] = round(float(corrected_p[i]), 8)
            results[fname]["bh_significant"] = bool(reject[i])
            # Mark as "meaningful" only if both statistically significant AND large enough effect
            results[fname]["meaningful"] = (
                bool(reject[i]) and abs(results[fname]["cliffs_delta"]) >= CLIFF_DELTA_THRESHOLD
            )

    return results


# ---------------------------------------------------------------------------
# VIF multicollinearity check
# ---------------------------------------------------------------------------

def compute_vif(features: np.ndarray, feature_names: List[str]) -> Dict:
    """
    Compute Variance Inflation Factor for each feature.

    VIF > 5 indicates problematic multicollinearity.
    VIF > 10 indicates severe multicollinearity.

    Uses combined hotspot + background data for maximum sample size.
    """
    # Remove rows with any NaN
    valid_mask = ~np.any(np.isnan(features), axis=1)
    clean = features[valid_mask]

    if clean.shape[0] < clean.shape[1] + 2:
        return {"error": "Too few complete cases for VIF", "features": {}}

    # Add constant for VIF computation
    from statsmodels.tools import add_constant
    X = add_constant(clean)

    vif_results = {}
    for j, fname in enumerate(feature_names):
        try:
            vif = variance_inflation_factor(X, j + 1)  # +1 to skip constant
            vif_results[fname] = {
                "vif": round(float(vif), 2),
                "problematic": bool(vif > VIF_THRESHOLD),
                "severe": bool(vif > 10),
            }
        except Exception as e:
            vif_results[fname] = {"vif": None, "error": str(e)}

    return {"features": vif_results}


# ---------------------------------------------------------------------------
# Per-hotspot z-scores
# ---------------------------------------------------------------------------

def compute_hotspot_zscores(
    hotspot_features: np.ndarray,
    background_features: np.ndarray,
    feature_names: List[str],
    hotspot_names: np.ndarray,
    meaningful_features: List[str],
) -> List[Dict]:
    """
    Compute z-scores for each hotspot relative to city background.

    Only for features that are both BH-significant AND |Cliff's Delta| >= 0.3.

    z = (hotspot_value - background_mean) / background_std
    """
    if not meaningful_features:
        return []

    results = []
    feature_indices = {fname: i for i, fname in enumerate(feature_names)}

    for i in range(len(hotspot_names)):
        zscores = {}
        for fname in meaningful_features:
            j = feature_indices.get(fname)
            if j is None:
                continue

            h_val = hotspot_features[i, j]
            if np.isnan(h_val):
                continue

            b_col = background_features[:, j]
            b_valid = b_col[~np.isnan(b_col)]
            if len(b_valid) < 2:
                continue

            b_mean = float(np.mean(b_valid))
            b_std = float(np.std(b_valid))
            if b_std < 1e-10:
                continue

            z = (h_val - b_mean) / b_std
            zscores[fname] = round(float(z), 3)

        results.append({
            "name": str(hotspot_names[i]),
            "zscores": zscores,
        })

    return results


# ---------------------------------------------------------------------------
# Process a single city
# ---------------------------------------------------------------------------

def process_city(city: str) -> Optional[Dict]:
    """
    Full statistical analysis for one city.

    Returns the analysis dict (also saved to JSON).
    """
    logger.info(f"\n{'=' * 60}")
    logger.info(f"PHASE 3: Statistical Analysis -- {city.upper()}")
    logger.info(f"{'=' * 60}")

    # Load NPZ files
    hotspot_path = OUTPUT_DIR / f"{city}_hotspot_features.npz"
    background_path = OUTPUT_DIR / f"{city}_background_features.npz"

    if not hotspot_path.exists() or not background_path.exists():
        logger.error(f"  Missing NPZ files for {city}. Run Phase 2 first.")
        return None

    h_data = np.load(hotspot_path, allow_pickle=True)
    b_data = np.load(background_path, allow_pickle=True)

    h_features = h_data["features"]
    b_features = b_data["features"]
    feature_names = list(h_data["feature_names"])
    h_lats = h_data["lats"]
    h_lngs = h_data["lngs"]
    h_names = h_data["names"]

    logger.info(f"  Hotspots: {h_features.shape[0]} x {h_features.shape[1]} features")
    logger.info(f"  Background: {b_features.shape[0]} x {b_features.shape[1]} features")
    logger.info(f"  Features: {', '.join(feature_names)}")

    # 1. Data quality checks
    logger.info("\n  --- Data Quality ---")
    h_quality = check_data_quality(h_features, feature_names)
    b_quality = check_data_quality(b_features, feature_names)

    # Drop features with >20% nulls in either set
    drop_set = set(h_quality["drop_features"] + b_quality["drop_features"])
    if drop_set:
        logger.warning(f"  Dropping features: {drop_set}")
        keep_idx = [i for i, f in enumerate(feature_names) if f not in drop_set]
        feature_names = [feature_names[i] for i in keep_idx]
        h_features = h_features[:, keep_idx]
        b_features = b_features[:, keep_idx]

    # 2. Association tests (Mann-Whitney U, KS, Cliff's Delta, Moran's I)
    # ---- Full background (includes rural) ----
    logger.info("\n  --- Association Tests (full background) ---")
    associations = run_association_tests(
        h_features, b_features, feature_names, h_lats, h_lngs
    )

    meaningful_features = []
    for fname, result in associations.items():
        if result.get("skipped"):
            continue
        sig = "***" if result.get("meaningful") else ("*" if result.get("bh_significant") else "")
        delta = result["cliffs_delta"]
        direction = result["direction"]
        p_str = f"p={result.get('bh_corrected_p', result['mann_whitney_p']):.6f}"
        logger.info(
            f"    {fname:20s}: delta={delta:+.3f} ({result['cliffs_magnitude']:10s}) "
            f"{direction:7s} {p_str} {sig}"
        )
        if result.get("meaningful"):
            meaningful_features.append(fname)
        if result.get("morans_i") and result["morans_i"].get("significant"):
            mi = result["morans_i"]
            logger.info(
                f"      Moran's I: {mi['morans_i']:.3f} (p={mi['p_value']:.4f}) "
                f"-- SPATIAL AUTOCORRELATION DETECTED"
            )
    logger.info(f"\n  Meaningful features (full BG): {meaningful_features or 'NONE'}")

    # ---- Urban-only background (built_up_pct > 50%) ----
    # This controls for the rural-vs-urban confound that inflates built_up_pct
    urban_associations = None
    urban_meaningful = []
    bu_idx = feature_names.index("built_up_pct") if "built_up_pct" in feature_names else None
    n_urban_bg = 0

    if bu_idx is not None:
        urban_mask = b_features[:, bu_idx] > 50
        n_urban_bg = int(urban_mask.sum())

        if n_urban_bg >= 20:
            logger.info(f"\n  --- Association Tests (URBAN-ONLY background, n={n_urban_bg}) ---")
            logger.info(f"  NOTE: This controls for rural-vs-urban bias. More honest comparison.")
            b_urban = b_features[urban_mask]

            urban_associations = run_association_tests(
                h_features, b_urban, feature_names, h_lats, h_lngs
            )

            for fname, result in urban_associations.items():
                if result.get("skipped"):
                    continue
                sig = "***" if result.get("meaningful") else ("*" if result.get("bh_significant") else "")
                delta = result["cliffs_delta"]
                direction = result["direction"]
                p_str = f"p={result.get('bh_corrected_p', result['mann_whitney_p']):.6f}"
                logger.info(
                    f"    {fname:20s}: delta={delta:+.3f} ({result['cliffs_magnitude']:10s}) "
                    f"{direction:7s} {p_str} {sig}"
                )
                if result.get("meaningful"):
                    urban_meaningful.append(fname)

            logger.info(f"\n  Meaningful features (urban-only BG): {urban_meaningful or 'NONE'}")

            # Log features that LOST significance after urban filtering
            lost = set(meaningful_features) - set(urban_meaningful)
            if lost:
                logger.warning(f"  INFLATED (lost significance after urban filtering): {lost}")
        else:
            logger.warning(f"  Only {n_urban_bg} urban BG points — skipping urban-only analysis")

    # 3. VIF multicollinearity check
    logger.info("\n  --- VIF Multicollinearity ---")
    combined = np.vstack([h_features, b_features])
    vif_results = compute_vif(combined, feature_names)

    for fname, vif_info in vif_results.get("features", {}).items():
        if vif_info.get("vif") is not None:
            flag = " *** PROBLEMATIC ***" if vif_info.get("problematic") else ""
            logger.info(f"    {fname:20s}: VIF={vif_info['vif']:.1f}{flag}")

    # 4. Per-hotspot z-scores (using urban-only background when available)
    logger.info("\n  --- Hotspot Z-Scores ---")
    # Use urban-only meaningful features and background for z-scores (more honest)
    zscore_features = urban_meaningful if urban_meaningful else meaningful_features
    zscore_bg = b_features[b_features[:, bu_idx] > 50] if (bu_idx is not None and n_urban_bg >= 20) else b_features
    zscore_source = "urban-only" if (bu_idx is not None and n_urban_bg >= 20) else "full"
    logger.info(f"  Z-score background: {zscore_source} ({len(zscore_bg)} points)")
    zscores = compute_hotspot_zscores(
        h_features, zscore_bg, feature_names, h_names, zscore_features
    )

    if zscores:
        # Show top 5 most extreme hotspots
        for entry in sorted(
            zscores,
            key=lambda e: max(abs(v) for v in e["zscores"].values()) if e["zscores"] else 0,
            reverse=True,
        )[:5]:
            z_str = ", ".join(f"{k}={v:+.1f}" for k, v in entry["zscores"].items())
            logger.info(f"    {entry['name']}: {z_str}")

    # 5. Assemble analysis output
    analysis = {
        "city": city,
        "n_hotspots": int(h_features.shape[0]),
        "n_background": int(b_features.shape[0]),
        "n_urban_background": n_urban_bg,
        "features_analyzed": feature_names,
        "features_dropped": list(drop_set) if drop_set else [],
        "data_quality": {
            "hotspot": h_quality["features"],
            "background": b_quality["features"],
        },
        "associations": associations,
        "meaningful_features": meaningful_features,
        "urban_only_associations": urban_associations,
        "urban_meaningful_features": urban_meaningful,
        "inflated_features": list(set(meaningful_features) - set(urban_meaningful)) if urban_associations else [],
        "zscore_source": zscore_source,
        "vif": vif_results,
        "thresholds": {
            "cliff_delta_min": CLIFF_DELTA_THRESHOLD,
            "bh_alpha": BH_ALPHA,
            "vif_max": VIF_THRESHOLD,
            "null_max": NULL_THRESHOLD,
        },
    }

    # Save analysis JSON
    analysis_path = OUTPUT_DIR / f"{city}_profile_analysis.json"
    with open(analysis_path, "w") as f:
        json.dump(analysis, f, indent=2, default=str)
    logger.info(f"\n  Saved: {analysis_path.name}")

    # Save z-scores JSON
    if zscores:
        zscores_path = OUTPUT_DIR / f"{city}_hotspot_zscores.json"
        with open(zscores_path, "w") as f:
            json.dump(zscores, f, indent=2)
        logger.info(f"  Saved: {zscores_path.name}")

    return analysis


# ---------------------------------------------------------------------------
# Cross-city consistency analysis
# ---------------------------------------------------------------------------

def cross_city_analysis(all_analyses: Dict[str, Dict]) -> Dict:
    """
    Compare results across cities (Bradford Hill consistency criterion).

    If the same feature is significant in 4-5 cities independently,
    that's strong evidence toward a causal relationship.
    """
    logger.info(f"\n{'=' * 60}")
    logger.info("CROSS-CITY CONSISTENCY ANALYSIS")
    logger.info(f"{'=' * 60}")

    # Collect per-feature, per-city effect sizes
    feature_effects = {}  # fname -> [{city, delta, direction, significant}, ...]

    for city, analysis in all_analyses.items():
        for fname, result in analysis.get("associations", {}).items():
            if result.get("skipped"):
                continue

            if fname not in feature_effects:
                feature_effects[fname] = []

            feature_effects[fname].append({
                "city": city,
                "cliffs_delta": result["cliffs_delta"],
                "direction": result["direction"],
                "bh_significant": result.get("bh_significant", False),
                "meaningful": result.get("meaningful", False),
            })

    # Analyze consistency
    consistency = {}
    for fname, effects in feature_effects.items():
        n_cities = len(effects)
        n_significant = sum(1 for e in effects if e["bh_significant"])
        n_meaningful = sum(1 for e in effects if e["meaningful"])

        # Direction consistency: do all significant cities agree?
        sig_directions = [e["direction"] for e in effects if e["bh_significant"]]
        direction_consistent = (
            len(set(sig_directions)) <= 1 if sig_directions else None
        )

        # Mean effect size across cities
        deltas = [e["cliffs_delta"] for e in effects]
        mean_delta = float(np.mean(deltas))

        consistency[fname] = {
            "n_cities_tested": n_cities,
            "n_cities_significant": n_significant,
            "n_cities_meaningful": n_meaningful,
            "direction_consistent": direction_consistent,
            "mean_cliffs_delta": round(mean_delta, 4),
            "per_city": effects,
        }

        flag = ""
        if n_meaningful >= 4:
            flag = " *** STRONG EVIDENCE ***"
        elif n_meaningful >= 3:
            flag = " ** MODERATE EVIDENCE **"
        elif n_significant >= 3:
            flag = " * CONSISTENT SIGNAL *"

        dir_str = f"consistent ({sig_directions[0]})" if direction_consistent and sig_directions else "mixed"
        logger.info(
            f"  {fname:20s}: {n_meaningful}/{n_cities} meaningful, "
            f"mean delta={mean_delta:+.3f}, direction={dir_str}{flag}"
        )

    # Also run urban-only cross-city consistency
    logger.info(f"\n{'=' * 60}")
    logger.info("CROSS-CITY CONSISTENCY (URBAN-ONLY BACKGROUND)")
    logger.info(f"{'=' * 60}")

    urban_feature_effects = {}
    for city, analysis in all_analyses.items():
        for fname, result in (analysis.get("urban_only_associations") or {}).items():
            if result.get("skipped"):
                continue
            if fname not in urban_feature_effects:
                urban_feature_effects[fname] = []
            urban_feature_effects[fname].append({
                "city": city,
                "cliffs_delta": result["cliffs_delta"],
                "direction": result["direction"],
                "bh_significant": result.get("bh_significant", False),
                "meaningful": result.get("meaningful", False),
            })

    urban_consistency = {}
    for fname, effects in urban_feature_effects.items():
        n_cities = len(effects)
        n_meaningful = sum(1 for e in effects if e["meaningful"])
        deltas = [e["cliffs_delta"] for e in effects]
        mean_delta = float(np.mean(deltas))

        urban_consistency[fname] = {
            "n_cities_tested": n_cities,
            "n_cities_meaningful": n_meaningful,
            "mean_cliffs_delta": round(mean_delta, 4),
            "per_city": effects,
        }

        flag = " *** GENUINE ***" if n_meaningful >= 3 else ""
        logger.info(
            f"  {fname:20s}: {n_meaningful}/{n_cities} meaningful, "
            f"mean delta={mean_delta:+.3f}{flag}"
        )

    return {
        "n_cities_analyzed": len(all_analyses),
        "cities": list(all_analyses.keys()),
        "feature_consistency": consistency,
        "urban_only_consistency": urban_consistency,
    }


# ---------------------------------------------------------------------------
# Forest plot
# ---------------------------------------------------------------------------

def generate_forest_plot(
    all_analyses: Dict[str, Dict],
    output_path: Path,
) -> None:
    """
    Generate a forest plot showing Cliff's Delta across cities for each feature.

    Forest plots are the standard visualization for meta-analysis —
    they show effect sizes with confidence indicators across studies (cities).
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available, skipping forest plot")
        return

    # Collect all features that appear in any city
    all_features = set()
    for analysis in all_analyses.values():
        for fname in analysis.get("associations", {}):
            if not analysis["associations"][fname].get("skipped"):
                all_features.add(fname)

    features = sorted(all_features)
    cities = sorted(all_analyses.keys())
    n_features = len(features)
    n_cities = len(cities)

    if n_features == 0:
        logger.warning("No features to plot")
        return

    fig, ax = plt.subplots(figsize=(12, max(6, n_features * 0.8)))

    colors = {
        "delhi": "#e41a1c",
        "bangalore": "#377eb8",
        "yogyakarta": "#4daf4a",
        "singapore": "#984ea3",
        "indore": "#ff7f00",
    }

    y_positions = list(range(n_features))
    city_offsets = np.linspace(-0.3, 0.3, n_cities)

    for ci, city in enumerate(cities):
        analysis = all_analyses.get(city, {})
        associations = analysis.get("associations", {})

        for fi, fname in enumerate(features):
            result = associations.get(fname, {})
            if result.get("skipped") or "cliffs_delta" not in result:
                continue

            delta = result["cliffs_delta"]
            y = y_positions[fi] + city_offsets[ci]

            marker = "o" if result.get("meaningful") else ("s" if result.get("bh_significant") else "x")
            size = 80 if result.get("meaningful") else 40

            ax.scatter(
                delta, y,
                color=colors.get(city, "gray"),
                marker=marker,
                s=size,
                alpha=0.8,
                label=city.title() if fi == 0 else None,
                zorder=5,
            )

    # Reference lines
    ax.axvline(0, color="black", linewidth=0.5, linestyle="-")
    ax.axvline(-CLIFF_DELTA_THRESHOLD, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
    ax.axvline(CLIFF_DELTA_THRESHOLD, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)

    ax.set_yticks(y_positions)
    ax.set_yticklabels(features)
    ax.set_xlabel("Cliff's Delta (hotspot vs background)")
    ax.set_title("Static Feature Effect Sizes Across Cities")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_xlim(-1.1, 1.1)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    logger.info(f"  Forest plot saved: {output_path.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Phase 3: Statistical analysis of static feature profiles"
    )
    parser.add_argument(
        "--city",
        choices=ALL_CITIES,
        help="Analyze a single city (default: all cities + cross-city)",
    )
    args = parser.parse_args()

    cities = [args.city] if args.city else ALL_CITIES

    # Process each city
    all_analyses = {}
    for city in cities:
        try:
            result = process_city(city)
            if result:
                all_analyses[city] = result
        except Exception as e:
            logger.error(f"FAILED analyzing {city}: {e}")
            import traceback
            traceback.print_exc()
            if len(cities) > 1:
                logger.info("Continuing to next city...")
            else:
                raise

    # Cross-city consistency (only if multiple cities analyzed)
    if len(all_analyses) >= 2:
        cross_city = cross_city_analysis(all_analyses)

        # Save cross-city summary
        summary_path = OUTPUT_DIR / "cross_city_summary.json"
        with open(summary_path, "w") as f:
            json.dump(cross_city, f, indent=2, default=str)
        logger.info(f"\n  Saved: {summary_path.name}")

        # Generate forest plots (full background + urban-only)
        plot_path = OUTPUT_DIR / "forest_plot.png"
        generate_forest_plot(all_analyses, plot_path)

        # Urban-only forest plot
        urban_analyses = {}
        for city, a in all_analyses.items():
            if a.get("urban_only_associations"):
                urban_analyses[city] = {**a, "associations": a["urban_only_associations"]}
        if urban_analyses:
            urban_plot_path = OUTPUT_DIR / "forest_plot_urban_only.png"
            generate_forest_plot(urban_analyses, urban_plot_path)

    # Final summary
    logger.info(f"\n{'=' * 60}")
    logger.info("STATISTICAL ANALYSIS COMPLETE")
    logger.info(f"{'=' * 60}")
    logger.info(f"Output directory: {OUTPUT_DIR}")

    # Report meaningful features per city — both full and urban-only
    for city, analysis in all_analyses.items():
        mf = analysis.get("meaningful_features", [])
        umf = analysis.get("urban_meaningful_features", [])
        inflated = analysis.get("inflated_features", [])
        logger.info(f"  {city}:")
        logger.info(f"    Full BG: {len(mf)} meaningful: {mf}")
        logger.info(f"    Urban BG: {len(umf)} meaningful: {umf}")
        if inflated:
            logger.info(f"    INFLATED (lost after urban filter): {inflated}")

    logger.info("\nNOTE: Urban-only results are the honest comparison. Full-BG results are")
    logger.info("inflated by rural-vs-urban confound (hotspots are urban by definition).")


if __name__ == "__main__":
    main()
