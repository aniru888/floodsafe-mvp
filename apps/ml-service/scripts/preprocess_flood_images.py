"""
Flood Image Preprocessing Script

Prepares downloaded/scraped images for YOLOv8 training:
1. Resize to 640x640 (YOLOv8 default)
2. Remove duplicates using perceptual hashing
3. Filter low quality images (blur detection)
4. Split into train/val/test (70/20/10)
5. Generate dataset.yaml for YOLOv8 classification

Usage:
    python -m apps.ml-service.scripts.preprocess_flood_images
    python -m apps.ml-service.scripts.preprocess_flood_images --size 224
    python -m apps.ml-service.scripts.preprocess_flood_images --no-dedupe
"""

import argparse
import hashlib
import logging
import shutil
import sys
import random
from pathlib import Path
from typing import List, Set, Tuple, Dict
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Base paths
SCRIPT_DIR = Path(__file__).parent
ML_SERVICE_DIR = SCRIPT_DIR.parent
DATA_DIR = ML_SERVICE_DIR / "data"
FLOOD_IMAGES_DIR = DATA_DIR / "flood_images"

# Default settings
DEFAULT_SIZE = 640  # YOLOv8 default
TRAIN_RATIO = 0.70
VAL_RATIO = 0.20
TEST_RATIO = 0.10
BLUR_THRESHOLD = 100.0  # Laplacian variance threshold


def calculate_image_hash(image_path: Path) -> str:
    """
    Calculate perceptual hash for duplicate detection.

    Uses imagehash library for robust duplicate detection.
    Falls back to MD5 if imagehash is not available.
    """
    try:
        import imagehash
        from PIL import Image

        img = Image.open(image_path)
        # Use difference hash - fast and effective for duplicates
        return str(imagehash.dhash(img, hash_size=16))

    except ImportError:
        # Fallback to MD5 hash
        with open(image_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    except Exception as e:
        logger.warning(f"Could not hash {image_path}: {e}")
        return None


def detect_blur(image_path: Path, threshold: float = BLUR_THRESHOLD) -> bool:
    """
    Detect if an image is blurry using Laplacian variance.

    Args:
        image_path: Path to image
        threshold: Variance threshold (lower = blurrier)

    Returns:
        True if image is blurry (should be filtered)
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(str(image_path))
        if img is None:
            return True  # Can't read = filter out

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()

        return variance < threshold

    except ImportError:
        # cv2 not available, skip blur detection
        return False

    except Exception as e:
        logger.warning(f"Blur detection failed for {image_path}: {e}")
        return False


def resize_image(
    src_path: Path,
    dest_path: Path,
    size: int = DEFAULT_SIZE,
    preserve_aspect: bool = True
) -> bool:
    """
    Resize image to target size.

    Args:
        src_path: Source image path
        dest_path: Destination path
        size: Target size (square)
        preserve_aspect: If True, resize maintaining aspect ratio with padding

    Returns:
        True if successful
    """
    try:
        from PIL import Image

        img = Image.open(src_path)

        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')

        if preserve_aspect:
            # Calculate resize dimensions
            width, height = img.size
            ratio = min(size / width, size / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)

            # Resize
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Create padded image (center the resized image)
            padded = Image.new('RGB', (size, size), (128, 128, 128))  # Gray padding
            x = (size - new_width) // 2
            y = (size - new_height) // 2
            padded.paste(img, (x, y))
            img = padded
        else:
            # Simple resize to exact dimensions
            img = img.resize((size, size), Image.Resampling.LANCZOS)

        # Save as JPEG for consistent format
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest_path, 'JPEG', quality=95)
        return True

    except Exception as e:
        logger.warning(f"Failed to resize {src_path}: {e}")
        return False


def deduplicate_images(
    image_paths: List[Path],
    similarity_threshold: int = 5
) -> List[Path]:
    """
    Remove duplicate images using perceptual hashing.

    Args:
        image_paths: List of image paths
        similarity_threshold: Max hash distance for duplicates (0 = exact)

    Returns:
        List of unique image paths
    """
    logger.info(f"Deduplicating {len(image_paths)} images...")

    hash_to_path: Dict[str, Path] = {}
    duplicates = 0

    for img_path in image_paths:
        img_hash = calculate_image_hash(img_path)
        if img_hash is None:
            continue

        if img_hash in hash_to_path:
            duplicates += 1
            logger.debug(f"Duplicate: {img_path.name} matches {hash_to_path[img_hash].name}")
        else:
            hash_to_path[img_hash] = img_path

    logger.info(f"Found {duplicates} duplicates, keeping {len(hash_to_path)} unique images")
    return list(hash_to_path.values())


def split_dataset(
    images: List[Path],
    train_ratio: float = TRAIN_RATIO,
    val_ratio: float = VAL_RATIO,
    test_ratio: float = TEST_RATIO,
    seed: int = 42
) -> Tuple[List[Path], List[Path], List[Path]]:
    """
    Split images into train/val/test sets.

    Args:
        images: List of image paths
        train_ratio: Training set ratio
        val_ratio: Validation set ratio
        test_ratio: Test set ratio
        seed: Random seed for reproducibility

    Returns:
        Tuple of (train, val, test) image lists
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 0.01, "Ratios must sum to 1"

    random.seed(seed)
    shuffled = images.copy()
    random.shuffle(shuffled)

    n = len(shuffled)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    train = shuffled[:train_end]
    val = shuffled[train_end:val_end]
    test = shuffled[val_end:]

    return train, val, test


def process_category(
    category: str,
    source_dirs: List[Path],
    output_dir: Path,
    size: int = DEFAULT_SIZE,
    dedupe: bool = True,
    filter_blur: bool = True
) -> Dict[str, int]:
    """
    Process all images for a category (flood or no_flood).

    Args:
        category: "flood" or "no_flood"
        source_dirs: List of source directories to search
        output_dir: Base output directory (flood_images)
        size: Target image size
        dedupe: Whether to remove duplicates
        filter_blur: Whether to filter blurry images

    Returns:
        Dict with counts for each split
    """
    logger.info(f"\nProcessing '{category}' images...")

    # Collect all images from source directories
    all_images: List[Path] = []
    for src_dir in source_dirs:
        if not src_dir.exists():
            continue
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.bmp']:
            all_images.extend(src_dir.rglob(ext))

    if not all_images:
        logger.warning(f"No images found for {category}")
        return {"train": 0, "val": 0, "test": 0}

    logger.info(f"Found {len(all_images)} images for {category}")

    # Deduplicate
    if dedupe:
        all_images = deduplicate_images(all_images)

    # Filter blurry images
    if filter_blur:
        logger.info("Filtering blurry images...")
        original_count = len(all_images)
        all_images = [img for img in all_images if not detect_blur(img)]
        filtered = original_count - len(all_images)
        logger.info(f"Filtered {filtered} blurry images")

    # Split dataset
    train, val, test = split_dataset(all_images)

    # Process and save each split
    counts = {"train": 0, "val": 0, "test": 0}

    for split_name, split_images in [("train", train), ("val", val), ("test", test)]:
        dest_dir = output_dir / split_name / category
        dest_dir.mkdir(parents=True, exist_ok=True)

        for idx, src_path in enumerate(split_images):
            dest_path = dest_dir / f"{category}_{idx:04d}.jpg"

            if resize_image(src_path, dest_path, size):
                counts[split_name] += 1

    return counts


def generate_dataset_yaml(output_dir: Path) -> Path:
    """
    Generate dataset.yaml for YOLOv8 classification training.

    Args:
        output_dir: Base output directory (flood_images)

    Returns:
        Path to generated YAML file
    """
    yaml_content = f"""# YOLOv8 Flood Classification Dataset
# Generated by preprocess_flood_images.py

path: {output_dir.absolute()}
train: train
val: val
test: test

# Class names
names:
  0: no_flood
  1: flood

# Safety threshold (used in inference)
# CRITICAL: Low threshold to minimize false negatives (<2% FNR target)
flood_threshold: 0.3
"""

    yaml_path = output_dir / "dataset.yaml"
    yaml_path.write_text(yaml_content)
    logger.info(f"Generated dataset.yaml at {yaml_path}")
    return yaml_path


def main():
    parser = argparse.ArgumentParser(description="Preprocess flood images for YOLOv8")
    parser.add_argument(
        "--size",
        type=int,
        default=DEFAULT_SIZE,
        help=f"Target image size (default: {DEFAULT_SIZE})"
    )
    parser.add_argument(
        "--no-dedupe",
        action="store_true",
        help="Skip duplicate removal"
    )
    parser.add_argument(
        "--no-blur-filter",
        action="store_true",
        help="Skip blur filtering"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for train/val/test split"
    )

    args = parser.parse_args()
    random.seed(args.seed)

    print("\n" + "="*60)
    print("FLOOD IMAGE PREPROCESSING")
    print("="*60)
    print(f"Target size: {args.size}x{args.size}")
    print(f"Deduplicate: {not args.no_dedupe}")
    print(f"Filter blur: {not args.no_blur_filter}")
    print(f"Train/Val/Test: {TRAIN_RATIO*100:.0f}%/{VAL_RATIO*100:.0f}%/{TEST_RATIO*100:.0f}%")
    print("="*60 + "\n")

    # Check for required libraries
    missing_libs = []
    try:
        from PIL import Image
    except ImportError:
        missing_libs.append("Pillow")

    if not args.no_dedupe:
        try:
            import imagehash
        except ImportError:
            logger.warning("imagehash not installed, using MD5 for deduplication")

    if not args.no_blur_filter:
        try:
            import cv2
        except ImportError:
            logger.warning("opencv-python not installed, skipping blur filter")
            args.no_blur_filter = True

    if missing_libs:
        logger.error(f"Missing required libraries: {missing_libs}")
        return 1

    # Define source directories
    scraped_dir = DATA_DIR / "scraped_images"
    kaggle_dir = DATA_DIR / "kaggle_downloads"

    # Source directories for each category
    flood_sources = [
        scraped_dir / "flood",
        kaggle_dir,  # Will search recursively
        FLOOD_IMAGES_DIR / "train" / "flood",  # Include existing
    ]

    no_flood_sources = [
        scraped_dir / "no_flood",
        FLOOD_IMAGES_DIR / "train" / "no_flood",
    ]

    # Create output directory
    output_dir = FLOOD_IMAGES_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process flood images
    flood_counts = process_category(
        category="flood",
        source_dirs=flood_sources,
        output_dir=output_dir,
        size=args.size,
        dedupe=not args.no_dedupe,
        filter_blur=not args.no_blur_filter
    )

    # Process non-flood images
    no_flood_counts = process_category(
        category="no_flood",
        source_dirs=no_flood_sources,
        output_dir=output_dir,
        size=args.size,
        dedupe=not args.no_dedupe,
        filter_blur=not args.no_blur_filter
    )

    # Generate dataset.yaml
    generate_dataset_yaml(output_dir)

    # Summary
    print("\n" + "="*60)
    print("PREPROCESSING COMPLETE")
    print("="*60)
    print("\nFlood images:")
    print(f"  Train: {flood_counts['train']}")
    print(f"  Val:   {flood_counts['val']}")
    print(f"  Test:  {flood_counts['test']}")

    print("\nNo-flood images:")
    print(f"  Train: {no_flood_counts['train']}")
    print(f"  Val:   {no_flood_counts['val']}")
    print(f"  Test:  {no_flood_counts['test']}")

    total_train = flood_counts['train'] + no_flood_counts['train']
    total_val = flood_counts['val'] + no_flood_counts['val']
    total_test = flood_counts['test'] + no_flood_counts['test']

    print(f"\nTotal: {total_train + total_val + total_test} images")
    print(f"  Train: {total_train}")
    print(f"  Val:   {total_val}")
    print(f"  Test:  {total_test}")

    print(f"\nDataset saved to: {output_dir}")
    print(f"Dataset config: {output_dir / 'dataset.yaml'}")

    # Check for imbalanced dataset
    if total_train > 0:
        flood_ratio = flood_counts['train'] / total_train
        if flood_ratio < 0.3 or flood_ratio > 0.7:
            logger.warning(f"Dataset is imbalanced ({flood_ratio:.1%} flood). Consider collecting more images.")

    print("="*60 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
