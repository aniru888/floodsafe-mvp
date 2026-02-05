#!/usr/bin/env python3
"""
3-Level Image Deduplication Script.

Removes duplicate images using:
1. Level 1: MD5 hash (exact duplicates)
2. Level 2: Perceptual hash (near-duplicates)
3. Level 3: Cross-query deduplication

Usage:
    python -m apps.ml-service.scripts.data_processing.deduplicate
"""

import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
from tqdm import tqdm

# Add scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

try:
    import imagehash
except ImportError:
    print("ERROR: imagehash not installed. Run: pip install imagehash")
    sys.exit(1)

from data_collection.config import (
    DEDUP_CONFIG,
    PROCESSED_DIR,
    METADATA_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def compute_md5(file_path: Path) -> str:
    """Compute MD5 hash of file."""
    md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5.update(chunk)
    return md5.hexdigest()


def compute_phash(file_path: Path) -> str:
    """Compute perceptual hash of image."""
    try:
        img = Image.open(file_path)
        return str(imagehash.phash(img))
    except Exception as e:
        logger.warning(f"Failed to compute phash for {file_path}: {e}")
        return None


def level1_md5_dedup(images: List[Path]) -> Tuple[List[Path], Dict]:
    """
    Level 1: Remove exact duplicates using MD5 hash.

    Returns:
        (kept_images, duplicate_groups)
    """
    logger.info("Level 1: MD5 deduplication...")

    md5_to_images: Dict[str, List[Path]] = defaultdict(list)

    for img_path in tqdm(images, desc="Computing MD5"):
        md5 = compute_md5(img_path)
        md5_to_images[md5].append(img_path)

    kept = []
    duplicate_groups = {}

    for md5, paths in md5_to_images.items():
        # Keep first, mark rest as duplicates
        kept.append(paths[0])
        if len(paths) > 1:
            duplicate_groups[md5] = {
                "kept": str(paths[0]),
                "removed": [str(p) for p in paths[1:]],
                "method": "md5",
            }

    duplicates_removed = len(images) - len(kept)
    logger.info(f"  Removed {duplicates_removed} exact duplicates")

    return kept, duplicate_groups


def level2_phash_dedup(
    images: List[Path],
    threshold: int = 5,
) -> Tuple[List[Path], Dict]:
    """
    Level 2: Remove near-duplicates using perceptual hash.

    Args:
        images: List of image paths
        threshold: Hash difference threshold (lower = stricter)

    Returns:
        (kept_images, duplicate_groups)
    """
    logger.info(f"Level 2: Perceptual hash deduplication (threshold={threshold})...")

    # Compute all perceptual hashes
    phashes: Dict[Path, str] = {}
    for img_path in tqdm(images, desc="Computing pHash"):
        phash = compute_phash(img_path)
        if phash:
            phashes[img_path] = phash

    # Find near-duplicates
    kept: List[Path] = []
    kept_hashes: Dict[str, Path] = {}  # hash -> kept image path
    duplicate_groups: Dict[str, dict] = {}

    for img_path, phash in tqdm(phashes.items(), desc="Comparing hashes"):
        is_duplicate = False

        for existing_hash, existing_path in kept_hashes.items():
            # Compare hashes
            try:
                diff = imagehash.hex_to_hash(phash) - imagehash.hex_to_hash(existing_hash)
                if diff < threshold:
                    # Found a near-duplicate
                    group_key = existing_hash

                    if group_key not in duplicate_groups:
                        duplicate_groups[group_key] = {
                            "kept": str(existing_path),
                            "removed": [],
                            "method": "phash",
                            "threshold": threshold,
                        }

                    duplicate_groups[group_key]["removed"].append(str(img_path))
                    is_duplicate = True
                    break
            except Exception:
                continue

        if not is_duplicate:
            kept.append(img_path)
            kept_hashes[phash] = img_path

    duplicates_removed = len(images) - len(kept)
    logger.info(f"  Removed {duplicates_removed} near-duplicates")

    return kept, duplicate_groups


def level3_cross_query_dedup(
    images: List[Path],
    threshold: int = 5,
) -> Tuple[List[Path], Dict]:
    """
    Level 3: Cross-query deduplication.

    Ensures same image from different queries is only kept once.
    Uses stricter comparison (phash diff = 0-2).

    Returns:
        (kept_images, duplicate_groups)
    """
    logger.info("Level 3: Cross-query deduplication...")

    # This is essentially the same as Level 2 but with a stricter threshold
    # and specifically designed to catch images that appeared in multiple queries

    return level2_phash_dedup(images, threshold=min(threshold, 3))


def deduplicate_dataset(
    input_dir: Path = PROCESSED_DIR,
    output_report: Path = None,
) -> dict:
    """
    Run full 3-level deduplication on dataset.

    Args:
        input_dir: Directory containing images
        output_report: Path to save deduplication report

    Returns:
        Report dict with statistics and duplicate groups
    """
    if output_report is None:
        output_report = METADATA_DIR / "duplicates.json"

    # Find all images
    images = list(input_dir.rglob("*.jpg"))
    initial_count = len(images)
    logger.info(f"Found {initial_count} images in {input_dir}")

    all_duplicate_groups: Dict[str, dict] = {}
    current_images = images

    # Level 1: MD5
    if DEDUP_CONFIG["use_md5"]:
        current_images, groups = level1_md5_dedup(current_images)
        all_duplicate_groups.update(groups)

    # Level 2: Perceptual hash
    if DEDUP_CONFIG["use_phash"]:
        current_images, groups = level2_phash_dedup(
            current_images,
            threshold=DEDUP_CONFIG["phash_threshold"],
        )
        all_duplicate_groups.update(groups)

    # Level 3: Cross-query
    if DEDUP_CONFIG["use_cross_query"]:
        current_images, groups = level3_cross_query_dedup(
            current_images,
            threshold=DEDUP_CONFIG["phash_threshold"],
        )
        all_duplicate_groups.update(groups)

    # Calculate statistics
    final_count = len(current_images)
    removed_count = initial_count - final_count

    # Build report
    report = {
        "initial_count": initial_count,
        "final_count": final_count,
        "removed_count": removed_count,
        "duplicate_rate": round(removed_count / initial_count, 4) if initial_count > 0 else 0,
        "levels_used": {
            "md5": DEDUP_CONFIG["use_md5"],
            "phash": DEDUP_CONFIG["use_phash"],
            "cross_query": DEDUP_CONFIG["use_cross_query"],
        },
        "phash_threshold": DEDUP_CONFIG["phash_threshold"],
        "duplicate_groups": list(all_duplicate_groups.values()),
        "kept_images": [str(p) for p in current_images],
    }

    # Save report
    output_report.parent.mkdir(parents=True, exist_ok=True)
    with open(output_report, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"Saved deduplication report to {output_report}")

    return report


def remove_duplicates(report: dict, dry_run: bool = True) -> int:
    """
    Actually remove duplicate files from disk.

    Args:
        report: Deduplication report from deduplicate_dataset()
        dry_run: If True, only log what would be removed

    Returns:
        Number of files removed
    """
    removed = 0

    for group in report["duplicate_groups"]:
        for removed_path in group["removed"]:
            path = Path(removed_path)
            if path.exists():
                if dry_run:
                    logger.info(f"Would remove: {path}")
                else:
                    path.unlink()
                    logger.debug(f"Removed: {path}")
                removed += 1

    return removed


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Remove duplicate images")
    parser.add_argument(
        "--remove", action="store_true",
        help="Actually remove duplicates (default: dry run)"
    )
    parser.add_argument(
        "--input-dir", type=Path, default=PROCESSED_DIR,
        help="Input directory to deduplicate"
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("IMAGE DEDUPLICATION")
    print("="*60)
    print(f"Input: {args.input_dir}")
    print(f"pHash threshold: {DEDUP_CONFIG['phash_threshold']}")
    print(f"Mode: {'REMOVE' if args.remove else 'DRY RUN'}")
    print("="*60 + "\n")

    # Run deduplication analysis
    report = deduplicate_dataset(args.input_dir)

    print("\n" + "="*60)
    print("DEDUPLICATION RESULTS")
    print("="*60)
    print(f"Initial images: {report['initial_count']}")
    print(f"Final images: {report['final_count']}")
    print(f"Duplicates found: {report['removed_count']}")
    print(f"Duplicate rate: {report['duplicate_rate']*100:.2f}%")
    print(f"Duplicate groups: {len(report['duplicate_groups'])}")

    if args.remove:
        print("\nRemoving duplicates...")
        removed = remove_duplicates(report, dry_run=False)
        print(f"Removed {removed} files")
    else:
        print("\nDry run - no files removed. Use --remove to delete duplicates.")

    print("="*60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
