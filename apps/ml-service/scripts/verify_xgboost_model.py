"""
XGBoost Hotspot Model Verification Script.

Comprehensive verification testing:
1. Location-Aware CV - Tests spatial generalization
2. Temporal Split - Tests year-over-year consistency
3. Fold 1 Leakage Investigation - Explains perfect AUC
4. Feature Duplicate Detection - Checks for data issues

Usage:
    cd apps/ml-service
    python scripts/verify_xgboost_model.py

Output:
    - Console: Detailed analysis with metrics
    - xgboost_verification_results.json: All results for documentation
"""

import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sklearn.model_selection import StratifiedKFold, GroupKFold
from sklearn.metrics import (
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    confusion_matrix
)
from xgboost import XGBClassifier

# XGBoost hyperparameters (same as training)
XGBOOST_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "max_depth": 5,
    "learning_rate": 0.1,
    "n_estimators": 100,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "use_label_encoder": False,
    "verbosity": 0,
}


def load_training_data() -> Tuple[np.ndarray, np.ndarray, List[Dict], np.ndarray, np.ndarray]:
    """
    Load training data and extract location/date information.

    Returns:
        X: Features (486, 18)
        y: Labels (486,)
        metadata: List of sample info dicts
        location_ids: Array of location identifiers (for GroupKFold)
        date_indices: Array of date indices (0=2023-07-15, 1=2023-08-10, 2=2022-07-20)
    """
    data_file = project_root / "data" / "hotspot_training_data.npz"
    metadata_file = project_root / "data" / "hotspot_training_metadata.json"

    # Load NPZ data
    data = np.load(data_file, allow_pickle=True)
    X = data["features"]
    y = data["labels"]

    # Load metadata
    with open(metadata_file) as f:
        meta = json.load(f)

    samples = meta["samples"]
    dates_sampled = meta["dates_sampled"]  # ["2023-07-15", "2023-08-10", "2022-07-20"]

    # Extract location IDs (unique per physical location)
    # Hotspots: sample_id 1-62
    # Negatives: sample_id "neg_1" through "neg_100"
    location_ids = []
    date_indices = []

    # Create location ID mapping
    location_map = {}
    current_loc_id = 0

    for sample in samples:
        sample_id = sample["sample_id"]
        if sample_id not in location_map:
            location_map[sample_id] = current_loc_id
            current_loc_id += 1

        location_ids.append(location_map[sample_id])

        # Map date to index
        date_str = sample["date"]
        if date_str in dates_sampled:
            date_indices.append(dates_sampled.index(date_str))
        else:
            date_indices.append(-1)

    location_ids = np.array(location_ids)
    date_indices = np.array(date_indices)

    return X, y, samples, location_ids, date_indices


def test_standard_cv(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    """
    Run standard 5-fold stratified CV (original methodology).
    This is what was used during training - expected AUC ~0.984.
    """
    print("\n" + "=" * 60)
    print("TEST 1: STANDARD STRATIFIED CV (ORIGINAL METHOD)")
    print("=" * 60)

    kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    fold_results = []
    fold_test_indices = []

    for fold, (train_idx, test_idx) in enumerate(kf.split(X, y)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Auto-adjust class weight
        n_neg = np.sum(y_train == 0)
        n_pos = np.sum(y_train == 1)
        scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

        params = XGBOOST_PARAMS.copy()
        params["scale_pos_weight"] = scale_pos_weight

        model = XGBClassifier(**params)
        model.fit(X_train, y_train)

        y_proba = model.predict_proba(X_test)[:, 1]
        y_pred = (y_proba >= 0.5).astype(int)

        auc = roc_auc_score(y_test, y_proba)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        fold_results.append({
            "fold": fold + 1,
            "auc": auc,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "n_train": len(train_idx),
            "n_test": len(test_idx),
            "n_positive_test": int(y_test.sum()),
        })
        fold_test_indices.append(test_idx.tolist())

        print(f"  Fold {fold + 1}: AUC={auc:.4f}, Precision={precision:.4f}, Recall={recall:.4f}, F1={f1:.4f}")

    # Aggregate
    auc_mean = np.mean([r["auc"] for r in fold_results])
    auc_std = np.std([r["auc"] for r in fold_results])

    print(f"\n  MEAN: AUC={auc_mean:.4f} ± {auc_std:.4f}")

    return {
        "method": "standard_stratified_cv",
        "n_folds": 5,
        "fold_results": fold_results,
        "fold_test_indices": fold_test_indices,
        "auc_mean": auc_mean,
        "auc_std": auc_std,
        "precision_mean": np.mean([r["precision"] for r in fold_results]),
        "recall_mean": np.mean([r["recall"] for r in fold_results]),
        "f1_mean": np.mean([r["f1"] for r in fold_results]),
    }


def test_location_aware_cv(X: np.ndarray, y: np.ndarray, location_ids: np.ndarray) -> Dict[str, Any]:
    """
    Run location-aware CV using GroupKFold.
    Same location never appears in both train and test.
    This tests TRUE spatial generalization.
    """
    print("\n" + "=" * 60)
    print("TEST 2: LOCATION-AWARE CV (GroupKFold)")
    print("=" * 60)
    print("  Same hotspot location NEVER in both train and test")

    # Count unique locations
    n_locations = len(np.unique(location_ids))
    print(f"  Unique locations: {n_locations}")

    gkf = GroupKFold(n_splits=5)

    fold_results = []
    location_overlap_check = []

    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups=location_ids)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Verify no location overlap
        train_locs = set(location_ids[train_idx])
        test_locs = set(location_ids[test_idx])
        overlap = train_locs & test_locs
        location_overlap_check.append(len(overlap) == 0)

        if len(overlap) > 0:
            print(f"  WARNING: Fold {fold + 1} has {len(overlap)} overlapping locations!")

        # Auto-adjust class weight
        n_neg = np.sum(y_train == 0)
        n_pos = np.sum(y_train == 1)
        scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

        params = XGBOOST_PARAMS.copy()
        params["scale_pos_weight"] = scale_pos_weight

        model = XGBClassifier(**params)
        model.fit(X_train, y_train)

        y_proba = model.predict_proba(X_test)[:, 1]
        y_pred = (y_proba >= 0.5).astype(int)

        # Handle case where only one class in test set
        if len(np.unique(y_test)) < 2:
            auc = 0.5  # Can't compute AUC with single class
            print(f"  WARNING: Fold {fold + 1} test set has only one class")
        else:
            auc = roc_auc_score(y_test, y_proba)

        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        fold_results.append({
            "fold": fold + 1,
            "auc": auc,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "n_train": len(train_idx),
            "n_test": len(test_idx),
            "n_positive_test": int(y_test.sum()),
            "n_train_locations": len(train_locs),
            "n_test_locations": len(test_locs),
            "no_overlap": len(overlap) == 0,
        })

        print(f"  Fold {fold + 1}: AUC={auc:.4f}, Precision={precision:.4f}, Recall={recall:.4f}, "
              f"(train_locs={len(train_locs)}, test_locs={len(test_locs)})")

    # Aggregate
    auc_mean = np.mean([r["auc"] for r in fold_results])
    auc_std = np.std([r["auc"] for r in fold_results])

    print(f"\n  MEAN: AUC={auc_mean:.4f} ± {auc_std:.4f}")
    print(f"  Location overlap check: {'PASS' if all(location_overlap_check) else 'FAIL'}")

    return {
        "method": "location_aware_cv",
        "n_folds": 5,
        "fold_results": fold_results,
        "auc_mean": auc_mean,
        "auc_std": auc_std,
        "precision_mean": np.mean([r["precision"] for r in fold_results]),
        "recall_mean": np.mean([r["recall"] for r in fold_results]),
        "f1_mean": np.mean([r["f1"] for r in fold_results]),
        "all_no_overlap": all(location_overlap_check),
    }


def test_temporal_split(X: np.ndarray, y: np.ndarray, date_indices: np.ndarray) -> Dict[str, Any]:
    """
    Test temporal generalization: Train on one year, test on another.

    date_indices: 0 = 2023-07-15, 1 = 2023-08-10, 2 = 2022-07-20
    """
    print("\n" + "=" * 60)
    print("TEST 3: TEMPORAL SPLIT VALIDATION")
    print("=" * 60)

    results = {}

    # Test 1: Train 2022, Test 2023
    train_mask_2022 = date_indices == 2  # 2022-07-20
    test_mask_2023 = (date_indices == 0) | (date_indices == 1)  # 2023 dates

    X_train = X[train_mask_2022]
    y_train = y[train_mask_2022]
    X_test = X[test_mask_2023]
    y_test = y[test_mask_2023]

    print(f"\n  Direction 1: Train 2022 ({len(X_train)} samples) -> Test 2023 ({len(X_test)} samples)")

    n_neg = np.sum(y_train == 0)
    n_pos = np.sum(y_train == 1)
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    params = XGBOOST_PARAMS.copy()
    params["scale_pos_weight"] = scale_pos_weight

    model = XGBClassifier(**params)
    model.fit(X_train, y_train)

    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)

    auc_2022_to_2023 = roc_auc_score(y_test, y_proba)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    print(f"    AUC={auc_2022_to_2023:.4f}, Precision={precision:.4f}, Recall={recall:.4f}, F1={f1:.4f}")

    results["2022_to_2023"] = {
        "auc": auc_2022_to_2023,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "n_train": len(X_train),
        "n_test": len(X_test),
    }

    # Test 2: Train 2023, Test 2022
    train_mask_2023 = (date_indices == 0) | (date_indices == 1)
    test_mask_2022 = date_indices == 2

    X_train = X[train_mask_2023]
    y_train = y[train_mask_2023]
    X_test = X[test_mask_2022]
    y_test = y[test_mask_2022]

    print(f"\n  Direction 2: Train 2023 ({len(X_train)} samples) -> Test 2022 ({len(X_test)} samples)")

    n_neg = np.sum(y_train == 0)
    n_pos = np.sum(y_train == 1)
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    params = XGBOOST_PARAMS.copy()
    params["scale_pos_weight"] = scale_pos_weight

    model = XGBClassifier(**params)
    model.fit(X_train, y_train)

    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)

    auc_2023_to_2022 = roc_auc_score(y_test, y_proba)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    print(f"    AUC={auc_2023_to_2022:.4f}, Precision={precision:.4f}, Recall={recall:.4f}, F1={f1:.4f}")

    results["2023_to_2022"] = {
        "auc": auc_2023_to_2022,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "n_train": len(X_train),
        "n_test": len(X_test),
    }

    # Calculate consistency gap
    auc_gap = abs(auc_2022_to_2023 - auc_2023_to_2022)
    print(f"\n  Temporal consistency gap: {auc_gap:.4f}")
    print(f"  {'PASS' if auc_gap < 0.10 else 'WARNING'}: Gap < 0.10 threshold")

    results["auc_gap"] = auc_gap
    results["consistent"] = auc_gap < 0.10

    return results


def investigate_fold1_leakage(
    X: np.ndarray,
    y: np.ndarray,
    samples: List[Dict],
    location_ids: np.ndarray
) -> Dict[str, Any]:
    """
    Investigate why Fold 1 achieved perfect 1.0 AUC.
    """
    print("\n" + "=" * 60)
    print("TEST 4: FOLD 1 LEAKAGE INVESTIGATION")
    print("=" * 60)

    kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    fold_idx = 0
    for train_idx, test_idx in kf.split(X, y):
        if fold_idx == 0:
            break
        fold_idx += 1

    # Fold 1 composition
    test_samples = [samples[i] for i in test_idx]
    test_locations = location_ids[test_idx]
    train_locations = location_ids[train_idx]

    # Location overlap analysis
    overlap_locs = set(test_locations) & set(train_locations)

    print(f"\n  Fold 1 Test Set:")
    print(f"    Samples: {len(test_idx)}")
    print(f"    Positive (flood): {int(y[test_idx].sum())}")
    print(f"    Negative: {len(test_idx) - int(y[test_idx].sum())}")
    print(f"    Unique locations: {len(set(test_locations))}")
    print(f"    Overlapping locations with train: {len(overlap_locs)}")

    # Check for duplicate feature rows
    X_test = X[test_idx]
    X_train = X[train_idx]

    exact_duplicates = 0
    near_duplicates = 0

    for i, test_row in enumerate(X_test):
        found_exact = False
        for train_row in X_train:
            if np.allclose(test_row, train_row, rtol=1e-5):
                exact_duplicates += 1
                found_exact = True
                break
        if not found_exact:
            for train_row in X_train:
                if np.allclose(test_row, train_row, rtol=0.1):
                    near_duplicates += 1
                    break

    print(f"\n  Feature Similarity Analysis:")
    print(f"    Exact duplicates (train <-> test): {exact_duplicates}")
    print(f"    Near duplicates (within 10%): {near_duplicates}")

    # Explanation
    print(f"\n  EXPLANATION:")
    if len(overlap_locs) > 0:
        print(f"    {len(overlap_locs)} locations appear in BOTH train and test!")
        print(f"    Features for same location are nearly identical (terrain doesn't change)")
        print(f"    Model memorizes location-specific patterns -> inflated AUC")

    if exact_duplicates > 0:
        print(f"    {exact_duplicates} test samples have EXACT feature matches in training!")
        print(f"    This is likely from same location on different dates")

    return {
        "fold_1_test_size": len(test_idx),
        "fold_1_positive": int(y[test_idx].sum()),
        "fold_1_unique_locations": len(set(test_locations)),
        "overlapping_locations": len(overlap_locs),
        "exact_duplicates": exact_duplicates,
        "near_duplicates": near_duplicates,
        "explanation": "Location overlap causes spatial leakage" if len(overlap_locs) > 0 else "Unknown"
    }


def check_feature_duplicates(X: np.ndarray, samples: List[Dict]) -> Dict[str, Any]:
    """
    Check for duplicate or near-duplicate feature rows.
    """
    print("\n" + "=" * 60)
    print("TEST 5: FEATURE DUPLICATE DETECTION")
    print("=" * 60)

    n_samples = len(X)

    # Group samples by location
    location_groups = defaultdict(list)
    for i, sample in enumerate(samples):
        loc_key = (round(sample["lat"], 4), round(sample["lng"], 4))
        location_groups[loc_key].append(i)

    print(f"  Unique locations: {len(location_groups)}")

    # Check feature similarity within locations
    within_location_identical = 0
    within_location_similar = 0

    for loc_key, indices in location_groups.items():
        if len(indices) > 1:
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    row_i = X[indices[i]]
                    row_j = X[indices[j]]

                    if np.allclose(row_i, row_j, rtol=1e-5):
                        within_location_identical += 1
                    elif np.allclose(row_i, row_j, rtol=0.2):
                        within_location_similar += 1

    print(f"  Within-location identical pairs: {within_location_identical}")
    print(f"  Within-location similar pairs (20% tolerance): {within_location_similar}")

    # Feature variance analysis
    variances = np.var(X, axis=0)
    zero_var_features = np.sum(variances < 1e-10)

    print(f"\n  Zero-variance features: {zero_var_features}")

    # Terrain features should be near-identical for same location
    # Only rainfall/SAR should vary
    terrain_features = [0, 1, 2, 3, 4, 5]  # elevation, slope, tpi, tri, twi, spi
    rainfall_features = [6, 7, 8, 9, 10]  # rainfall_24h/3d/7d, max_daily, wet_days

    terrain_avg_var = np.mean(variances[terrain_features])
    rainfall_avg_var = np.mean(variances[rainfall_features])

    print(f"\n  Feature Variance Analysis:")
    print(f"    Terrain features avg variance: {terrain_avg_var:.4f}")
    print(f"    Rainfall features avg variance: {rainfall_avg_var:.4f}")
    print(f"    Rainfall/Terrain variance ratio: {rainfall_avg_var/terrain_avg_var:.2f}x")

    return {
        "unique_locations": len(location_groups),
        "within_location_identical": within_location_identical,
        "within_location_similar": within_location_similar,
        "zero_variance_features": zero_var_features,
        "terrain_avg_variance": terrain_avg_var,
        "rainfall_avg_variance": rainfall_avg_var,
    }


def main():
    """Run all verification tests."""
    print("\n" + "#" * 60)
    print("#  XGBOOST HOTSPOT MODEL VERIFICATION")
    print("#  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("#" * 60)

    # Load data
    print("\nLoading training data...")
    X, y, samples, location_ids, date_indices = load_training_data()

    print(f"  Features shape: {X.shape}")
    print(f"  Labels: {int(y.sum())} positive, {len(y) - int(y.sum())} negative")
    print(f"  Unique locations: {len(np.unique(location_ids))}")
    print(f"  Date distribution: {dict(zip(*np.unique(date_indices, return_counts=True)))}")

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "data_info": {
            "n_samples": len(y),
            "n_positive": int(y.sum()),
            "n_negative": len(y) - int(y.sum()),
            "n_features": X.shape[1],
            "n_unique_locations": len(np.unique(location_ids)),
        }
    }

    # Test 1: Standard CV
    all_results["standard_cv"] = test_standard_cv(X, y)

    # Test 2: Location-Aware CV
    all_results["location_aware_cv"] = test_location_aware_cv(X, y, location_ids)

    # Test 3: Temporal Split
    all_results["temporal_split"] = test_temporal_split(X, y, date_indices)

    # Test 4: Fold 1 Leakage
    all_results["fold1_investigation"] = investigate_fold1_leakage(X, y, samples, location_ids)

    # Test 5: Feature Duplicates
    all_results["feature_duplicates"] = check_feature_duplicates(X, samples)

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    std_auc = all_results["standard_cv"]["auc_mean"]
    loc_auc = all_results["location_aware_cv"]["auc_mean"]
    auc_drop = std_auc - loc_auc

    print(f"\n  Standard CV AUC:        {std_auc:.4f}")
    print(f"  Location-Aware CV AUC:  {loc_auc:.4f}")
    print(f"  AUC DROP (spatial leak): {auc_drop:.4f} ({auc_drop/std_auc*100:.1f}%)")

    temporal_gap = all_results["temporal_split"]["auc_gap"]
    print(f"\n  Temporal consistency gap: {temporal_gap:.4f}")

    overlap_locs = all_results["fold1_investigation"]["overlapping_locations"]
    print(f"\n  Fold 1 location overlap: {overlap_locs} locations")

    # Verdicts
    print("\n" + "-" * 60)
    print("VERDICTS:")

    if loc_auc >= 0.85:
        print(f"  [PASS] Location-aware AUC >= 0.85: PASS ({loc_auc:.4f})")
    else:
        print(f"  [FAIL] Location-aware AUC >= 0.85: FAIL ({loc_auc:.4f})")

    if temporal_gap < 0.10:
        print(f"  [PASS] Temporal consistency < 0.10: PASS ({temporal_gap:.4f})")
    else:
        print(f"  [WARN] Temporal consistency < 0.10: WARNING ({temporal_gap:.4f})")

    if overlap_locs > 0:
        print(f"  [WARN] Fold 1 leakage explained: {overlap_locs} overlapping locations")

    # RF Recommendation
    print("\n" + "-" * 60)
    print("RANDOM FOREST RECOMMENDATION:")

    if loc_auc >= 0.92:
        print("  -> XGBoost is excellent. RF optional for robustness.")
        all_results["rf_recommendation"] = "optional"
    elif loc_auc >= 0.85:
        print("  -> XGBoost is good. RF ensemble (60/40) recommended for robustness.")
        all_results["rf_recommendation"] = "recommended"
    elif loc_auc >= 0.80:
        print("  -> XGBoost is marginal. RF comparison strongly recommended.")
        all_results["rf_recommendation"] = "strongly_recommended"
    else:
        print("  -> Both models may struggle. Need more training data.")
        all_results["rf_recommendation"] = "need_more_data"

    all_results["verdicts"] = {
        "location_aware_auc_pass": loc_auc >= 0.85,
        "temporal_consistency_pass": temporal_gap < 0.10,
        "standard_auc": std_auc,
        "location_aware_auc": loc_auc,
        "auc_drop_from_leakage": auc_drop,
        "temporal_gap": temporal_gap,
    }

    # Save results
    output_file = project_root / "xgboost_verification_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\n  Results saved to: {output_file}")
    print("=" * 60)

    return all_results


if __name__ == "__main__":
    results = main()
