#!/usr/bin/env python3
"""
Image Standardization Script.

Normalizes all images to consistent format:
- Size: 640x480 (landscape)
- Format: JPEG with quality 85
- Color: RGB (no alpha)

Usage:
    python -m apps.ml-service.scripts.data_processing.standardize
"""

import logging
import sys
from pathlib import Path
from typing import Tuple, Optional
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

from data_collection.config import (
    IMAGE_CONFIG,
    RAW_DIR,
    PROCESSED_DIR,
    PROCESSED_FLOOD_DIR,
    PROCESSED_NORMAL_DIR,
    KAGGLE_FLOOD_DIR,
    KAGGLE_NORMAL_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def standardize_image(
    input_path: Path,
    output_path: Path,
    target_size: Tuple[int, int] = (640, 480),
    jpeg_quality: int = 85,
) -> bool:
    """
    Standardize a single image.

    Args:
        input_path: Source image path
        output_path: Destination path
        target_size: (width, height) tuple
        jpeg_quality: JPEG compression quality

    Returns:
        True if successful, False otherwise
    """
    try:
        img = Image.open(input_path)

        # Convert to RGB if needed (handles RGBA, grayscale, etc.)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Resize to target size (may distort aspect ratio, but consistent)
        img = img.resize(target_size, Image.Resampling.LANCZOS)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save as JPEG
        img.save(output_path, 'JPEG', quality=jpeg_quality)
        return True

    except Exception as e:
        logger.warning(f"Failed to process {input_path}: {e}")
        return False


def process_directory(
    input_dir: Path,
    output_dir: Path,
    extensions: Tuple[str, ...] = ('.jpg', '.jpeg', '.png', '.bmp', '.webp'),
) -> dict:
    """
    Process all images in a directory.

    Args:
        input_dir: Source directory
        output_dir: Destination directory
        extensions: Tuple of valid image extensions

    Returns:
        Stats dict with success/failure counts
    """
    stats = {"processed": 0, "failed": 0, "skipped": 0}

    # Find all images
    images = []
    for ext in extensions:
        images.extend(input_dir.rglob(f"*{ext}"))
        images.extend(input_dir.rglob(f"*{ext.upper()}"))

    if not images:
        logger.info(f"No images found in {input_dir}")
        return stats

    logger.info(f"Found {len(images)} images in {input_dir}")

    target_size = (IMAGE_CONFIG["target_width"], IMAGE_CONFIG["target_height"])
    jpeg_quality = IMAGE_CONFIG["jpeg_quality"]

    for img_path in tqdm(images, desc=f"Standardizing {input_dir.name}"):
        # Maintain relative path structure
        rel_path = img_path.relative_to(input_dir)
        output_path = output_dir / rel_path.with_suffix('.jpg')

        # Skip if already processed
        if output_path.exists():
            stats["skipped"] += 1
            continue

        if standardize_image(img_path, output_path, target_size, jpeg_quality):
            stats["processed"] += 1
        else:
            stats["failed"] += 1

    return stats


def process_all() -> dict:
    """
    Process all raw images to processed directory.

    Returns:
        Combined stats dict
    """
    total_stats = {"processed": 0, "failed": 0, "skipped": 0}

    # Define source -> destination mappings
    # Includes YouTube, DuckDuckGo scraped data AND existing Kaggle datasets
    mappings = [
        (RAW_DIR / "youtube" / "flood", PROCESSED_FLOOD_DIR),
        (RAW_DIR / "youtube" / "normal", PROCESSED_NORMAL_DIR),
        (RAW_DIR / "ddg" / "flood", PROCESSED_FLOOD_DIR),
        (RAW_DIR / "ddg" / "normal", PROCESSED_NORMAL_DIR),
        # Existing Kaggle datasets (already downloaded)
        (KAGGLE_FLOOD_DIR, PROCESSED_FLOOD_DIR),
        (KAGGLE_NORMAL_DIR, PROCESSED_NORMAL_DIR),
    ]

    for input_dir, output_dir in mappings:
        if input_dir.exists():
            logger.info(f"\nProcessing: {input_dir}")
            stats = process_directory(input_dir, output_dir)

            for key in total_stats:
                total_stats[key] += stats[key]

            logger.info(f"  Processed: {stats['processed']}, Failed: {stats['failed']}, Skipped: {stats['skipped']}")

    return total_stats


def main():
    print("\n" + "="*60)
    print("IMAGE STANDARDIZATION")
    print("="*60)
    print(f"Target size: {IMAGE_CONFIG['target_width']}x{IMAGE_CONFIG['target_height']}")
    print(f"JPEG quality: {IMAGE_CONFIG['jpeg_quality']}")
    print("="*60 + "\n")

    stats = process_all()

    print("\n" + "="*60)
    print("STANDARDIZATION COMPLETE")
    print("="*60)
    print(f"Total processed: {stats['processed']}")
    print(f"Total failed: {stats['failed']}")
    print(f"Total skipped: {stats['skipped']}")
    print(f"\nOutput directories:")
    print(f"  Flood: {PROCESSED_FLOOD_DIR}")
    print(f"  Normal: {PROCESSED_NORMAL_DIR}")
    print("="*60 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
