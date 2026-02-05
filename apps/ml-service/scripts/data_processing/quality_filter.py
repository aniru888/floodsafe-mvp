#!/usr/bin/env python3
"""
Image Quality Filter Script.

Filters images based on quality criteria:
- Minimum resolution
- Maximum aspect ratio
- Blur detection (Laplacian variance)
- Not mostly black/white

Usage:
    python -m apps.ml-service.scripts.data_processing.quality_filter
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from tqdm import tqdm

# Add scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    import cv2
    import numpy as np
except ImportError:
    print("ERROR: opencv-python not installed. Run: pip install opencv-python")
    sys.exit(1)

from data_collection.config import (
    QUALITY_CONFIG,
    PROCESSED_DIR,
    METADATA_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_resolution(img: np.ndarray, min_res: Tuple[int, int]) -> Tuple[bool, str]:
    """Check if image meets minimum resolution."""
    h, w = img.shape[:2]
    if w < min_res[0] or h < min_res[1]:
        return False, f"too_small_{w}x{h}"
    return True, "ok"


def check_aspect_ratio(img: np.ndarray, max_ratio: float) -> Tuple[bool, str]:
    """Check if aspect ratio is within acceptable range."""
    h, w = img.shape[:2]
    ratio = max(w/h, h/w)
    if ratio > max_ratio:
        return False, f"bad_aspect_{ratio:.2f}"
    return True, "ok"


def check_blur(img: np.ndarray, threshold: float) -> Tuple[bool, str]:
    """
    Check if image is blurry using Laplacian variance.

    Lower variance = more blurry.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    if laplacian_var < threshold:
        return False, f"blurry_{laplacian_var:.1f}"
    return True, "ok"


def check_brightness(
    img: np.ndarray,
    min_brightness: float,
    max_brightness: float,
) -> Tuple[bool, str]:
    """Check if image is not mostly black or white."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_val = gray.mean()

    if mean_val < min_brightness:
        return False, f"too_dark_{mean_val:.1f}"
    if mean_val > max_brightness:
        return False, f"too_bright_{mean_val:.1f}"
    return True, "ok"


def filter_image(image_path: Path, config: dict = QUALITY_CONFIG) -> Tuple[bool, str]:
    """
    Apply all quality filters to an image.

    Args:
        image_path: Path to image file
        config: Quality configuration dict

    Returns:
        (passed, reason) tuple
    """
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return False, "corrupt"

        # Check resolution
        passed, reason = check_resolution(img, config["min_resolution"])
        if not passed:
            return False, reason

        # Check aspect ratio
        passed, reason = check_aspect_ratio(img, config["max_aspect_ratio"])
        if not passed:
            return False, reason

        # Check blur
        passed, reason = check_blur(img, config["blur_threshold"])
        if not passed:
            return False, reason

        # Check brightness
        passed, reason = check_brightness(
            img,
            config["min_brightness"],
            config["max_brightness"]
        )
        if not passed:
            return False, reason

        return True, "ok"

    except Exception as e:
        return False, f"error_{str(e)[:20]}"


def filter_directory(
    input_dir: Path,
    config: dict = QUALITY_CONFIG,
) -> dict:
    """
    Filter all images in directory.

    Returns:
        Report dict with pass/fail counts and rejection reasons
    """
    images = list(input_dir.rglob("*.jpg"))
    logger.info(f"Checking quality of {len(images)} images in {input_dir}")

    passed_images: List[str] = []
    rejected_images: Dict[str, str] = {}  # path -> reason
    reason_counts: Dict[str, int] = {}

    for img_path in tqdm(images, desc="Filtering"):
        passed, reason = filter_image(img_path, config)

        if passed:
            passed_images.append(str(img_path))
        else:
            rejected_images[str(img_path)] = reason
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return {
        "total": len(images),
        "passed": len(passed_images),
        "rejected": len(rejected_images),
        "pass_rate": len(passed_images) / len(images) if images else 0,
        "reason_counts": dict(sorted(reason_counts.items(), key=lambda x: -x[1])),
        "passed_images": passed_images,
        "rejected_images": rejected_images,
    }


def filter_all(
    input_dir: Path = PROCESSED_DIR,
    output_report: Path = None,
) -> dict:
    """
    Filter all images and generate report.

    Args:
        input_dir: Directory to filter
        output_report: Path to save report

    Returns:
        Combined report dict
    """
    if output_report is None:
        output_report = METADATA_DIR / "rejected.json"

    report = filter_directory(input_dir)

    # Save report
    output_report.parent.mkdir(parents=True, exist_ok=True)
    with open(output_report, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"Saved quality report to {output_report}")

    return report


def remove_rejected(report: dict, dry_run: bool = True) -> int:
    """
    Remove rejected images from disk.

    Args:
        report: Quality filter report
        dry_run: If True, only log what would be removed

    Returns:
        Number of files removed
    """
    removed = 0

    for path_str in report["rejected_images"]:
        path = Path(path_str)
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

    parser = argparse.ArgumentParser(description="Filter images by quality")
    parser.add_argument(
        "--remove", action="store_true",
        help="Actually remove rejected images (default: dry run)"
    )
    parser.add_argument(
        "--input-dir", type=Path, default=PROCESSED_DIR,
        help="Input directory to filter"
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("IMAGE QUALITY FILTER")
    print("="*60)
    print(f"Input: {args.input_dir}")
    print(f"Min resolution: {QUALITY_CONFIG['min_resolution']}")
    print(f"Max aspect ratio: {QUALITY_CONFIG['max_aspect_ratio']}")
    print(f"Blur threshold: {QUALITY_CONFIG['blur_threshold']}")
    print(f"Brightness range: {QUALITY_CONFIG['min_brightness']}-{QUALITY_CONFIG['max_brightness']}")
    print(f"Mode: {'REMOVE' if args.remove else 'DRY RUN'}")
    print("="*60 + "\n")

    # Run quality filter
    report = filter_all(args.input_dir)

    print("\n" + "="*60)
    print("QUALITY FILTER RESULTS")
    print("="*60)
    print(f"Total images: {report['total']}")
    print(f"Passed: {report['passed']}")
    print(f"Rejected: {report['rejected']}")
    print(f"Pass rate: {report['pass_rate']*100:.2f}%")

    if report['reason_counts']:
        print("\nRejection reasons:")
        for reason, count in report['reason_counts'].items():
            print(f"  {reason}: {count}")

    if args.remove:
        print("\nRemoving rejected images...")
        removed = remove_rejected(report, dry_run=False)
        print(f"Removed {removed} files")
    else:
        print("\nDry run - no files removed. Use --remove to delete rejected images.")

    print("="*60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
