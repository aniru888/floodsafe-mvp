#!/usr/bin/env python3
"""
Dataset Split Script.

Splits processed images into train/val/test sets with:
- Stratified sampling (maintains class balance)
- Configurable ratios (default: 80/10/10)
- Reproducible random seed

Usage:
    python -m apps.ml-service.scripts.data_processing.split_dataset
"""

import json
import logging
import random
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from tqdm import tqdm

# Add scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from data_collection.config import (
    SPLIT_CONFIG,
    PROCESSED_DIR,
    PROCESSED_FLOOD_DIR,
    PROCESSED_NORMAL_DIR,
    DATASET_DIR,
    METADATA_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def split_list(
    items: List,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int = 42,
) -> Tuple[List, List, List]:
    """
    Split a list into train/val/test sets.

    Args:
        items: List to split
        train_ratio: Proportion for training
        val_ratio: Proportion for validation
        test_ratio: Proportion for test
        seed: Random seed for reproducibility

    Returns:
        (train_items, val_items, test_items)
    """
    # Validate ratios
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 0.001:
        raise ValueError(f"Ratios must sum to 1.0, got {total}")

    # Shuffle with seed
    random.seed(seed)
    items_copy = items.copy()
    random.shuffle(items_copy)

    # Calculate split points
    n = len(items_copy)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    train_items = items_copy[:n_train]
    val_items = items_copy[n_train:n_train + n_val]
    test_items = items_copy[n_train + n_val:]

    return train_items, val_items, test_items


def split_dataset(
    processed_flood_dir: Path = PROCESSED_FLOOD_DIR,
    processed_normal_dir: Path = PROCESSED_NORMAL_DIR,
    output_dir: Path = DATASET_DIR,
    config: dict = SPLIT_CONFIG,
) -> dict:
    """
    Split processed images into train/val/test.

    Maintains class balance and creates proper directory structure:
    output_dir/
    ├── train/{flood,no_flood}/
    ├── val/{flood,no_flood}/
    └── test/{flood,no_flood}/

    Returns:
        Stats dict with counts per split and class
    """
    train_ratio = config["train_ratio"]
    val_ratio = config["val_ratio"]
    test_ratio = config["test_ratio"]
    seed = config["random_seed"]

    stats = {
        "flood": {"train": 0, "val": 0, "test": 0, "total": 0},
        "no_flood": {"train": 0, "val": 0, "test": 0, "total": 0},
    }

    # Process each class
    class_mappings = [
        ("flood", processed_flood_dir),
        ("no_flood", processed_normal_dir),
    ]

    for class_name, source_dir in class_mappings:
        logger.info(f"\nProcessing class: {class_name}")

        # Find all images
        images = list(source_dir.rglob("*.jpg"))
        stats[class_name]["total"] = len(images)
        logger.info(f"  Found {len(images)} images")

        if not images:
            logger.warning(f"  No images found in {source_dir}")
            continue

        # Split images
        train_imgs, val_imgs, test_imgs = split_list(
            images, train_ratio, val_ratio, test_ratio, seed
        )

        # Copy to output directories
        for split_name, split_imgs in [
            ("train", train_imgs),
            ("val", val_imgs),
            ("test", test_imgs),
        ]:
            dest_dir = output_dir / split_name / class_name
            dest_dir.mkdir(parents=True, exist_ok=True)

            for img_path in tqdm(split_imgs, desc=f"  {split_name}"):
                dest_path = dest_dir / img_path.name

                # Handle filename collisions
                counter = 1
                while dest_path.exists():
                    stem = img_path.stem
                    suffix = img_path.suffix
                    dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

                shutil.copy2(img_path, dest_path)

            stats[class_name][split_name] = len(split_imgs)

    # Calculate totals
    stats["totals"] = {
        "train": stats["flood"]["train"] + stats["no_flood"]["train"],
        "val": stats["flood"]["val"] + stats["no_flood"]["val"],
        "test": stats["flood"]["test"] + stats["no_flood"]["test"],
        "total": stats["flood"]["total"] + stats["no_flood"]["total"],
    }

    # Save stats
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    stats_file = METADATA_DIR / "stats.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)

    logger.info(f"Saved stats to {stats_file}")

    return stats


def main():
    print("\n" + "="*60)
    print("DATASET SPLIT")
    print("="*60)
    print(f"Train ratio: {SPLIT_CONFIG['train_ratio']}")
    print(f"Val ratio: {SPLIT_CONFIG['val_ratio']}")
    print(f"Test ratio: {SPLIT_CONFIG['test_ratio']}")
    print(f"Random seed: {SPLIT_CONFIG['random_seed']}")
    print(f"Output: {DATASET_DIR}")
    print("="*60 + "\n")

    stats = split_dataset()

    print("\n" + "="*60)
    print("SPLIT COMPLETE")
    print("="*60)

    print("\nFlood images:")
    print(f"  Train: {stats['flood']['train']}")
    print(f"  Val: {stats['flood']['val']}")
    print(f"  Test: {stats['flood']['test']}")

    print("\nNo-flood images:")
    print(f"  Train: {stats['no_flood']['train']}")
    print(f"  Val: {stats['no_flood']['val']}")
    print(f"  Test: {stats['no_flood']['test']}")

    print("\nTotals:")
    print(f"  Train: {stats['totals']['train']}")
    print(f"  Val: {stats['totals']['val']}")
    print(f"  Test: {stats['totals']['test']}")
    print(f"  Total: {stats['totals']['total']}")

    # Class balance
    if stats['no_flood']['total'] > 0:
        ratio = stats['flood']['total'] / stats['no_flood']['total']
        print(f"\nClass ratio (flood:no_flood): {ratio:.2f}")

    print("="*60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
