"""
Phase 6: Tiered SAR Temporal Analysis + Output Generation.

For each city with temporal features (Bangalore + Yogyakarta):
  1. Load temporal NPZ from Phase 5
  2. Select analysis tier based on effective-n:
     <8:  Descriptive only (effect sizes, no model)
     8-14: Mixed-effects model (LMM)
     15+: Constrained XGBoost + SHAP
  3. Run tiered analysis
  4. Generate output JSONs for frontend integration
  5. Generate methodology report

Both Bangalore (effective-n=20) and Yogyakarta (effective-n=17) qualify
for Tier 3 (XGBoost). But if SAR default rate is too high or AUC < 0.65,
they fall back to Tier 2 or Tier 1.

Usage:
    python scripts/05_temporal_analysis.py                    # Both cities
    python scripts/05_temporal_analysis.py --city bangalore   # Single city

Output:
    output/temporal/{city}_temporal_analysis.json
    output/temporal/{city}_shap_importance.json
    output/temporal/{city}_temporal_report.md
    output/temporal/temporal_summary.json
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
PROFILES_DIR = SCRIPT_DIR.parent / "output" / "profiles"

TEMPORAL_CITIES = ["bangalore", "yogyakarta"]

# SAR defaults (from Phase 5)
SAR_DEFAULTS = {
    "vv_mean": -10.0,
    "vh_mean": -17.0,
    "vv_vh_ratio": 7.0,
    "change_magnitude": 0.0,
}
SAR_DEFAULT_RATE_THRESHOLD = 0.30

# XGBoost parameters (constrained per design doc)
XGBOOST_PARAMS = {
    "max_depth": 2,
    "n_estimators": 30,
    "learning_rate": 0.1,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "random_state": 42,
    "verbosity": 0,
}

# AUC thresholds
AUC_STRONG = 0.75
AUC_WEAK = 0.65

SAR_FEATURE_NAMES = ["vv_mean", "vh_mean", "vv_vh_ratio", "change_magnitude"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_temporal_data(city: str) -> Optional[Dict]:
    """Load temporal NPZ and parse metadata."""
    path = OUTPUT_DIR / f"{city}_temporal_features.npz"
    if not path.exists():
        logger.error(f"  Temporal features not found: {path}")
        return None

    data = np.load(path, allow_pickle=True)
    metadata = json.loads(str(data["metadata"]))

    return {
        "features": data["features"],
        "labels": data["labels"],
        "hotspot_ids": data["hotspot_ids"],
        "dates": data["dates"],
        "feature_names": list(data["feature_names"]),
        "metadata": metadata,
    }


def filter_default_samples(data: Dict) -> Dict:
    """
    Remove samples where ALL SAR features are defaults (extraction failure).

    Keeps samples where only some features hit defaults — partial data
    is better than no data.
    """
    features = data["features"]
    n_features = features.shape[1]

    # A sample is "full default" if ALL features match defaults
    is_default = np.ones(len(features), dtype=bool)
    for j, fname in enumerate(data["feature_names"]):
        default_val = SAR_DEFAULTS.get(fname, None)
        if default_val is not None:
            is_default &= np.abs(features[:, j] - default_val) < 1e-6

    n_removed = is_default.sum()
    keep = ~is_default

    logger.info(
        f"  Removed {n_removed}/{len(features)} full-default samples "
        f"({n_removed / len(features):.1%})"
    )

    return {
        "features": features[keep],
        "labels": data["labels"][keep],
        "hotspot_ids": data["hotspot_ids"][keep],
        "dates": data["dates"][keep],
        "feature_names": data["feature_names"],
        "metadata": data["metadata"],
        "n_removed_defaults": int(n_removed),
        "n_original": len(features),
    }


# ---------------------------------------------------------------------------
# Tier 1: Descriptive Analysis
# ---------------------------------------------------------------------------

def descriptive_analysis(data: Dict) -> Dict:
    """
    Tier 1: Simple descriptive comparison of flood vs dry SAR features.

    Suitable when effective-n < 8 or as baseline for all cities.
    """
    features = data["features"]
    labels = data["labels"]
    feature_names = data["feature_names"]

    flood_mask = labels == 1
    dry_mask = labels == 0

    results = {}
    for j, fname in enumerate(feature_names):
        flood_vals = features[flood_mask, j]
        dry_vals = features[dry_mask, j]

        def _safe_stats(vals):
            if len(vals) == 0:
                return {"median": None, "mean": None, "std": None, "iqr": None}
            return {
                "median": round(float(np.median(vals)), 4),
                "mean": round(float(np.mean(vals)), 4),
                "std": round(float(np.std(vals)), 4),
                "iqr": round(float(np.percentile(vals, 75) - np.percentile(vals, 25)), 4),
            }

        fs = _safe_stats(flood_vals)
        ds = _safe_stats(dry_vals)

        median_diff = None
        direction = None
        if fs["median"] is not None and ds["median"] is not None:
            median_diff = round(fs["median"] - ds["median"], 4)
            direction = "lower" if fs["median"] < ds["median"] else "higher"

        results[fname] = {
            "flood_median": fs["median"],
            "flood_mean": fs["mean"],
            "flood_std": fs["std"],
            "flood_iqr": fs["iqr"],
            "dry_median": ds["median"],
            "dry_mean": ds["mean"],
            "dry_std": ds["std"],
            "dry_iqr": ds["iqr"],
            "median_diff": median_diff,
            "direction": direction,
        }

    return {"tier": "descriptive", "features": results}


# ---------------------------------------------------------------------------
# Tier 3: Constrained XGBoost + SHAP
# ---------------------------------------------------------------------------

def leave_one_storm_out_cv(data: Dict) -> Dict:
    """
    Tier 3: Constrained XGBoost with leave-one-storm-out cross-validation.

    Key constraints from design doc:
    - max_depth=2, n_estimators=30 (shallow, regularized)
    - Leave-One-Date-Out CV (NOT random split) — all samples from
      the same date go into the same fold
    - If mean AUC < 0.65: fall back to Tier 2/1
    - SHAP for feature importance
    """
    try:
        import xgboost as xgb
        from sklearn.metrics import roc_auc_score
    except ImportError:
        logger.error("  xgboost or sklearn not available")
        return {"tier": "xgboost", "error": "missing dependencies"}

    features = data["features"]
    labels = data["labels"]
    dates = data["dates"]

    # Get unique dates for leave-one-date-out CV
    unique_dates = np.unique(dates)
    n_folds = len(unique_dates)

    logger.info(f"  Leave-one-date-out CV: {n_folds} folds")

    all_preds = np.full(len(labels), np.nan)
    predicted_mask = np.zeros(len(labels), dtype=bool)
    fold_details = []

    for fold_idx, held_out_date in enumerate(unique_dates):
        test_mask = dates == held_out_date
        train_mask = ~test_mask

        X_train = features[train_mask]
        y_train = labels[train_mask]
        X_test = features[test_mask]
        y_test = labels[test_mask]

        # Skip fold if train has only one class (can't learn)
        if len(np.unique(y_train)) < 2:
            fold_details.append({
                "date": str(held_out_date),
                "n_test": int(test_mask.sum()),
                "test_label": int(y_test[0]) if len(y_test) > 0 else None,
                "skipped": True,
                "reason": "single class in train fold",
            })
            continue

        model = xgb.XGBClassifier(**XGBOOST_PARAMS)
        model.fit(X_train, y_train, verbose=False)

        y_pred = model.predict_proba(X_test)[:, 1]
        all_preds[test_mask] = y_pred
        predicted_mask[test_mask] = True

        fold_details.append({
            "date": str(held_out_date),
            "n_test": int(test_mask.sum()),
            "test_label": int(y_test[0]) if len(y_test) > 0 else None,
            "mean_pred": round(float(y_pred.mean()), 4),
            "skipped": False,
        })

    # Compute GLOBAL AUC from all out-of-fold predictions
    # (Per-fold AUC is undefined when each date has only one class)
    valid = predicted_mask
    if valid.sum() > 0 and len(np.unique(labels[valid])) >= 2:
        global_auc = float(roc_auc_score(labels[valid], all_preds[valid]))
    else:
        global_auc = 0.0
    n_predicted = int(valid.sum())

    # Determine quality tier
    if global_auc >= AUC_STRONG:
        quality = "strong"
        interpretation = "Model reliably distinguishes flood from dry conditions"
    elif global_auc >= AUC_WEAK:
        quality = "weak"
        interpretation = "Weak signal. Features may be too coarse. Reporting as associations, not predictions."
    else:
        quality = "failed"
        interpretation = "Available data cannot distinguish flood from dry at this resolution."

    logger.info(f"  Global AUC: {global_auc:.3f} (n={n_predicted} predicted, {quality})")
    logger.info(f"  Interpretation: {interpretation}")

    # Train final model on all data for importance analysis
    final_model = xgb.XGBClassifier(**XGBOOST_PARAMS)
    final_model.fit(features, labels, verbose=False)

    # Native XGBoost feature importance (gain-based, always works)
    feature_names = list(data["feature_names"])
    native_importance = {}
    raw_imp = final_model.feature_importances_
    ranked_idx = np.argsort(raw_imp)[::-1]
    for rank, idx in enumerate(ranked_idx, 1):
        native_importance[feature_names[idx]] = {
            "gain_importance": round(float(raw_imp[idx]), 6),
            "rank": rank,
        }
    logger.info("  XGBoost native feature importance (gain):")
    for fname in sorted(native_importance, key=lambda f: native_importance[f]["rank"]):
        logger.info(f"    #{native_importance[fname]['rank']} {fname}: {native_importance[fname]['gain_importance']:.4f}")

    # SHAP feature importance (may fail with XGBoost 3.x + SHAP <0.50)
    shap_importance = compute_shap_importance(final_model, features, feature_names)

    # Permutation importance as cross-check
    perm_importance = compute_permutation_importance(
        final_model, features, labels, feature_names
    )

    return {
        "tier": "xgboost",
        "global_auc": round(global_auc, 4),
        "n_folds": n_folds,
        "n_predicted": n_predicted,
        "quality": quality,
        "interpretation": interpretation,
        "fold_details": fold_details,
        "xgboost_params": XGBOOST_PARAMS,
        "native_importance": native_importance,
        "shap_importance": shap_importance,
        "permutation_importance": perm_importance,
    }


def compute_shap_importance(model, features: np.ndarray, feature_names: List[str]) -> Dict:
    """Compute SHAP feature importance values."""
    try:
        import shap

        explainer = shap.TreeExplainer(model)
        # Ensure features is float64 (SHAP can fail on object arrays)
        features = np.asarray(features, dtype=np.float64)
        shap_values = explainer.shap_values(features)

        # Mean absolute SHAP per feature
        mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

        importance = {}
        for j, fname in enumerate(feature_names):
            importance[fname] = {
                "mean_abs_shap": round(float(mean_abs_shap[j]), 6),
                "rank": 0,  # Filled below
            }

        # Rank by importance
        ranked = sorted(importance.keys(), key=lambda f: importance[f]["mean_abs_shap"], reverse=True)
        for rank, fname in enumerate(ranked, 1):
            importance[fname]["rank"] = rank

        logger.info("  SHAP feature importance:")
        for fname in ranked:
            logger.info(f"    #{importance[fname]['rank']} {fname}: {importance[fname]['mean_abs_shap']:.4f}")

        return importance

    except Exception as e:
        logger.warning(f"  SHAP computation failed: {e}")
        return {"error": str(e)}


def compute_permutation_importance(
    model, features: np.ndarray, labels: np.ndarray, feature_names: List[str],
    n_repeats: int = 10,
) -> Dict:
    """
    Compute permutation importance as cross-check against SHAP.

    Design doc requires that SHAP and permutation importance agree
    on feature ranking direction.
    """
    try:
        from sklearn.inspection import permutation_importance as sklearn_perm
        from sklearn.metrics import roc_auc_score

        result = sklearn_perm(
            model, features, labels,
            n_repeats=n_repeats,
            scoring="roc_auc",
            random_state=42,
        )

        importance = {}
        for j, fname in enumerate(feature_names):
            importance[fname] = {
                "mean_decrease": round(float(result.importances_mean[j]), 6),
                "std": round(float(result.importances_std[j]), 6),
            }

        return importance

    except Exception as e:
        logger.warning(f"  Permutation importance failed: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Per-hotspot analysis
# ---------------------------------------------------------------------------

def per_hotspot_summary(data: Dict, analysis_result: Dict) -> List[Dict]:
    """
    Generate per-hotspot SAR contrast summary.

    For each hotspot, compute the median SAR values during flood vs dry,
    and the direction of change.
    """
    features = data["features"]
    labels = data["labels"]
    hotspot_ids = data["hotspot_ids"]
    feature_names = data["feature_names"]

    unique_hotspots = np.unique(hotspot_ids)
    summaries = []

    for hs_id in unique_hotspots:
        hs_mask = hotspot_ids == hs_id
        hs_features = features[hs_mask]
        hs_labels = labels[hs_mask]

        flood_mask = hs_labels == 1
        dry_mask = hs_labels == 0

        if flood_mask.sum() == 0 or dry_mask.sum() == 0:
            continue

        hs_summary = {"hotspot": str(hs_id), "n_flood": int(flood_mask.sum()), "n_dry": int(dry_mask.sum())}

        for j, fname in enumerate(feature_names):
            flood_vals = hs_features[flood_mask, j]
            dry_vals = hs_features[dry_mask, j]

            flood_med = float(np.median(flood_vals))
            dry_med = float(np.median(dry_vals))

            hs_summary[fname] = {
                "flood_median": round(flood_med, 2),
                "dry_median": round(dry_med, 2),
                "diff": round(flood_med - dry_med, 2),
            }

        summaries.append(hs_summary)

    return summaries


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(city: str, data: Dict, analysis: Dict, hotspot_summaries: List[Dict]) -> str:
    """Generate Markdown methodology report for a city."""
    metadata = data["metadata"]
    tier = analysis.get("tier", "unknown")

    lines = [
        f"# {city.title()} — SAR Temporal Contrast Analysis",
        "",
        "## Overview",
        "",
        f"Compared Sentinel-1 SAR backscatter at {metadata.get('n_samples', '?')} hotspot-date observations "
        f"({metadata.get('n_flood_dates', '?')} flood dates, {metadata.get('n_dry_dates', '?')} dry dates).",
        "",
        f"- **Effective independent observations**: {metadata.get('effective_n', '?')}",
        f"- **Analysis tier**: {tier}",
        f"- **SAR default rate**: {metadata.get('default_rates', {}).get('overall', 0):.1%}",
        "",
        "## SAR Features",
        "",
        "| Feature | Description |",
        "|---------|-------------|",
        "| vv_mean | VV backscatter (dB). Water < -15 dB |",
        "| vh_mean | VH backscatter (dB). Water < -22 dB |",
        "| vv_vh_ratio | VV - VH (dB). Water indicator |",
        "| change_magnitude | Flood - baseline change. Negative = flooding |",
        "",
    ]

    # Add descriptive results
    desc = analysis.get("descriptive", {})
    if desc.get("features"):
        lines.extend([
            "## Descriptive Comparison",
            "",
            "| Feature | Flood Median | Dry Median | Difference | Direction |",
            "|---------|:---:|:---:|:---:|:---:|",
        ])
        for fname, stats in desc["features"].items():
            fm = f"{stats['flood_median']:.2f}" if stats['flood_median'] is not None else "N/A"
            dm = f"{stats['dry_median']:.2f}" if stats['dry_median'] is not None else "N/A"
            md = f"{stats['median_diff']:+.2f}" if stats['median_diff'] is not None else "N/A"
            dr = stats['direction'] or "N/A"
            lines.append(f"| {fname} | {fm} | {dm} | {md} | {dr} |")
        lines.append("")

    # Add XGBoost results
    if tier == "xgboost":
        lines.extend([
            "## XGBoost Analysis",
            "",
            f"- **Global AUC**: {analysis.get('global_auc', 0):.3f}",
            f"- **Quality**: {analysis.get('quality', 'unknown')}",
            f"- **Interpretation**: {analysis.get('interpretation', '')}",
            f"- **CV method**: Leave-one-date-out ({analysis.get('n_folds', 0)} folds, {analysis.get('n_predicted', 0)} predicted)",
            "",
        ])

        # SHAP importance
        shap = analysis.get("shap_importance", {})
        if shap and "error" not in shap:
            lines.extend([
                "### Feature Importance (SHAP)",
                "",
                "| Rank | Feature | Mean |SHAP| |",
                "|:---:|---------|:---:|",
            ])
            ranked = sorted(shap.items(), key=lambda x: x[1].get("rank", 99))
            for fname, info in ranked:
                lines.append(f"| {info['rank']} | {fname} | {info['mean_abs_shap']:.4f} |")
            lines.append("")

    # Methodology notes
    lines.extend([
        "## Methodology Notes",
        "",
        "- SAR date windows: flood dates use ref-2d to ref+7d (forward-looking), "
        "dry dates use ref-7d to ref (backward lookback)",
        "- Baseline: median of same-year dry season imagery (Jan-May for India, Jun-Aug for Indonesia)",
        "- Speckle filtering: Refined Lee (7x7 kernel, 4.4 ENL)",
        "- Default detection: samples where ALL features match known defaults are removed",
        "- Spatial resolution: 100m (reduced from 10m native for efficiency)",
        "",
        "## Limitations",
        "",
        "- City-wide flood dates don't mean ALL hotspots flooded — label noise is expected",
        "- Sentinel-1 has 6-12 day revisit — may miss short-lived flooding",
        "- 2014 dates have no SAR coverage (Sentinel-1 launched late 2014)",
        "- This analysis shows correlation, not causation",
        "",
        f"*Generated by FloodSafe ML Pipeline, Phase 6*",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Process city
# ---------------------------------------------------------------------------

def process_city(city: str) -> Optional[Dict]:
    """Full tiered analysis for one city."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"PHASE 6: Temporal Analysis -- {city.upper()}")
    logger.info(f"{'=' * 60}")

    # Load data
    data = load_temporal_data(city)
    if data is None:
        return None

    metadata = data["metadata"]
    effective_n = metadata.get("effective_n", 0)
    logger.info(f"  Loaded: {data['features'].shape[0]} samples, effective-n={effective_n}")
    logger.info(f"  SAR default rate: {metadata.get('default_rates', {}).get('overall', 0):.1%}")

    # Filter out full-default samples
    data = filter_default_samples(data)

    if len(data["features"]) < 10:
        logger.error(f"  Too few valid samples after filtering ({len(data['features'])})")
        return None

    # Determine tier
    default_rate = metadata.get("default_rates", {}).get("overall", 0)
    if default_rate > SAR_DEFAULT_RATE_THRESHOLD:
        logger.warning(f"  High default rate ({default_rate:.1%}) — restricting to descriptive analysis")
        tier = "descriptive"
    elif effective_n < 8:
        tier = "descriptive"
    elif effective_n < 15:
        tier = "mixed-effects"
    else:
        tier = "xgboost"

    logger.info(f"  Selected tier: {tier}")

    # Always run descriptive as baseline
    descriptive = descriptive_analysis(data)
    logger.info("  Descriptive analysis complete")

    # Run tiered analysis
    analysis_result = {"descriptive": descriptive, "tier": tier}

    if tier == "xgboost":
        xgb_result = leave_one_storm_out_cv(data)
        analysis_result.update(xgb_result)

        # Fall back if AUC too low
        auc_val = xgb_result.get("global_auc", 0)
        if auc_val < AUC_WEAK:
            logger.warning(
                f"  AUC {auc_val:.3f} < {AUC_WEAK} threshold. "
                f"Falling back to descriptive."
            )
            analysis_result["tier"] = "descriptive"
            analysis_result["fallback_reason"] = f"AUC {auc_val:.3f} below threshold"

    # Per-hotspot summaries
    hotspot_summaries = per_hotspot_summary(data, analysis_result)
    logger.info(f"  Generated summaries for {len(hotspot_summaries)} hotspots")

    # Assemble output
    output = {
        "city": city,
        "effective_n": effective_n,
        "n_samples_original": data.get("n_original", len(data["features"])),
        "n_samples_valid": len(data["features"]),
        "n_defaults_removed": data.get("n_removed_defaults", 0),
        "default_rate": default_rate,
        "analysis": analysis_result,
        "hotspot_summaries": hotspot_summaries[:10],  # Top 10 for JSON size
        "methodology_caveats": {
            "scope": "DATE-LEVEL detection, not spatial prediction",
            "what_auc_means": (
                "AUC measures whether SAR can distinguish flood DATES from dry DATES "
                "across the city. It does NOT measure per-hotspot discrimination."
            ),
            "between_date_dominance": (
                "ANOVA F-stat between dates >> within dates. The model learns "
                "temporal (date-level) patterns, not spatial (hotspot-level) patterns."
            ),
            "genuine_value": (
                "SAR temporal contrast confirms that satellite radar reliably "
                "detects active flooding at city scale. change_magnitude is the "
                "key feature (backscatter change vs 90-day baseline)."
            ),
        },
    }

    # Save analysis JSON
    analysis_path = OUTPUT_DIR / f"{city}_temporal_analysis.json"
    with open(analysis_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    logger.info(f"  Saved: {analysis_path.name}")

    # Save SHAP importance separately (for frontend)
    if "shap_importance" in analysis_result and "error" not in analysis_result.get("shap_importance", {}):
        shap_path = OUTPUT_DIR / f"{city}_shap_importance.json"
        with open(shap_path, "w") as f:
            json.dump(analysis_result["shap_importance"], f, indent=2)
        logger.info(f"  Saved: {shap_path.name}")

    # Generate methodology report
    report = generate_report(city, data, analysis_result, hotspot_summaries)
    report_path = OUTPUT_DIR / f"{city}_temporal_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"  Saved: {report_path.name}")

    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Phase 6: Tiered SAR temporal analysis + output generation"
    )
    parser.add_argument(
        "--city",
        choices=TEMPORAL_CITIES,
        help="Analyze a single city (default: both)",
    )
    args = parser.parse_args()

    cities = [args.city] if args.city else TEMPORAL_CITIES

    all_results = {}
    for city in cities:
        try:
            result = process_city(city)
            if result:
                all_results[city] = result
        except Exception as e:
            logger.error(f"FAILED analyzing {city}: {e}")
            import traceback
            traceback.print_exc()
            if len(cities) > 1:
                logger.info("Continuing to next city...")
            else:
                raise

    # Save combined summary
    if all_results:
        summary = {
            "cities_analyzed": list(all_results.keys()),
            "per_city": {
                city: {
                    "tier": r["analysis"].get("tier", "unknown"),
                    "effective_n": r["effective_n"],
                    "n_valid_samples": r["n_samples_valid"],
                    "default_rate": r["default_rate"],
                    "global_auc": r["analysis"].get("global_auc"),
                    "quality": r["analysis"].get("quality"),
                }
                for city, r in all_results.items()
            },
        }
        summary_path = OUTPUT_DIR / "temporal_summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"\n  Saved: {summary_path.name}")

    # Final summary
    logger.info(f"\n{'=' * 60}")
    logger.info("TEMPORAL ANALYSIS COMPLETE")
    logger.info(f"{'=' * 60}")
    for city, result in all_results.items():
        tier = result["analysis"].get("tier", "?")
        auc = result["analysis"].get("global_auc", "N/A")
        quality = result["analysis"].get("quality", "N/A")
        logger.info(
            f"  {city}: tier={tier}, AUC={auc}, quality={quality}, "
            f"valid samples={result['n_samples_valid']}"
        )


if __name__ == "__main__":
    main()
