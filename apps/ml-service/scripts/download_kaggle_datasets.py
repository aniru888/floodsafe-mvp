"""
Kaggle Flood Dataset Downloader

Downloads flood image datasets from Kaggle for training YOLOv8 classifier.

PREREQUISITES:
1. Install kaggle CLI: pip install kaggle
2. Create Kaggle API token:
   - Go to https://www.kaggle.com/account
   - Click "Create New Token"
   - Save kaggle.json to:
     - Windows: C:\\Users\\<username>\\.kaggle\\kaggle.json
     - Linux/Mac: ~/.kaggle/kaggle.json

DATASETS:
1. saurabhshahane/roadway-flooding-image-dataset (441 images, 17MB)
2. dhawalsrivastava2583/flood-classification-dataset (balanced)
3. armaanoajay/flooded-images (general flood images)

Usage:
    python -m apps.ml-service.scripts.download_kaggle_datasets
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path
from typing import List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Base paths
SCRIPT_DIR = Path(__file__).parent
ML_SERVICE_DIR = SCRIPT_DIR.parent
DATA_DIR = ML_SERVICE_DIR / "data"
KAGGLE_DOWNLOAD_DIR = DATA_DIR / "kaggle_downloads"
FLOOD_IMAGES_DIR = DATA_DIR / "flood_images"

# Kaggle datasets to download
KAGGLE_DATASETS: List[Tuple[str, str, str]] = [
    # (dataset_slug, download_name, description)
    ("saurabhshahane/roadway-flooding-image-dataset", "roadway-flooding", "Roadway Flooding (441 images)"),
    ("dhawalsrivastava2583/flood-classification-dataset", "flood-classification", "Flood Classification (balanced)"),
    ("armaanoajay/flooded-images", "flooded-images", "Flooded Images (general)"),
]


def check_kaggle_setup() -> bool:
    """Check if Kaggle API is properly configured."""
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_json = kaggle_dir / "kaggle.json"

    if not kaggle_json.exists():
        logger.error(f"Kaggle API token not found at {kaggle_json}")
        logger.error("Please follow these steps:")
        logger.error("1. Go to https://www.kaggle.com/account")
        logger.error("2. Click 'Create New Token'")
        logger.error(f"3. Save kaggle.json to {kaggle_dir}")
        return False

    # Check permissions (should be 600 on Unix)
    if os.name != 'nt':  # Not Windows
        import stat
        mode = os.stat(kaggle_json).st_mode
        if mode & stat.S_IRWXG or mode & stat.S_IRWXO:
            logger.warning(f"Fixing permissions on {kaggle_json}")
            os.chmod(kaggle_json, 0o600)

    return True


def download_dataset(dataset_slug: str, output_dir: Path) -> bool:
    """
    Download a Kaggle dataset.

    Args:
        dataset_slug: Kaggle dataset identifier (e.g., "user/dataset-name")
        output_dir: Directory to save the downloaded files

    Returns:
        True if successful, False otherwise
    """
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi()
        api.authenticate()

        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading {dataset_slug}...")
        api.dataset_download_files(dataset_slug, path=str(output_dir), unzip=True)

        logger.info(f"Successfully downloaded to {output_dir}")
        return True

    except Exception as e:
        logger.error(f"Failed to download {dataset_slug}: {e}")
        return False


def organize_images(source_dir: Path, flood_dir: Path, no_flood_dir: Path) -> Tuple[int, int]:
    """
    Organize downloaded images into flood/no_flood directories.

    Uses directory names and common patterns to classify images.

    Returns:
        Tuple of (flood_count, no_flood_count)
    """
    flood_count = 0
    no_flood_count = 0

    # Common flood-related keywords
    flood_keywords = ['flood', 'water', 'inund', 'submerge', 'waterlog']
    no_flood_keywords = ['dry', 'normal', 'clear', 'sunny', 'no_flood', 'non_flood', 'not_flood']

    for root, dirs, files in os.walk(source_dir):
        root_path = Path(root)
        root_lower = str(root_path).lower()

        # Determine category based on directory name
        is_flood_dir = any(kw in root_lower for kw in flood_keywords)
        is_no_flood_dir = any(kw in root_lower for kw in no_flood_keywords)

        # Process image files
        for file in files:
            if not file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')):
                continue

            src_path = root_path / file
            file_lower = file.lower()

            # Determine destination
            if is_no_flood_dir or any(kw in file_lower for kw in no_flood_keywords):
                dest_dir = no_flood_dir
                no_flood_count += 1
            elif is_flood_dir or any(kw in file_lower for kw in flood_keywords):
                dest_dir = flood_dir
                flood_count += 1
            else:
                # Default to flood (safer assumption for this training purpose)
                dest_dir = flood_dir
                flood_count += 1

            # Copy file with unique name to avoid overwrites
            dest_path = dest_dir / f"{root_path.name}_{file}"

            # Handle duplicates
            counter = 1
            while dest_path.exists():
                stem = dest_path.stem
                suffix = dest_path.suffix
                dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            shutil.copy2(src_path, dest_path)

    return flood_count, no_flood_count


def main():
    """Main function to download and organize Kaggle datasets."""
    print("\n" + "="*60)
    print("KAGGLE FLOOD DATASET DOWNLOADER")
    print("="*60 + "\n")

    # Check Kaggle setup
    if not check_kaggle_setup():
        sys.exit(1)

    # Create directories
    KAGGLE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    flood_dest = FLOOD_IMAGES_DIR / "train" / "flood"
    no_flood_dest = FLOOD_IMAGES_DIR / "train" / "no_flood"
    flood_dest.mkdir(parents=True, exist_ok=True)
    no_flood_dest.mkdir(parents=True, exist_ok=True)

    total_flood = 0
    total_no_flood = 0

    # Download each dataset
    for dataset_slug, download_name, description in KAGGLE_DATASETS:
        print(f"\n{'-'*60}")
        print(f"Dataset: {description}")
        print(f"Slug: {dataset_slug}")
        print(f"{'-'*60}")

        output_dir = KAGGLE_DOWNLOAD_DIR / download_name

        if output_dir.exists():
            logger.info(f"Dataset already exists at {output_dir}, skipping download...")
        else:
            if not download_dataset(dataset_slug, output_dir):
                logger.warning(f"Skipping {description} due to download failure")
                continue

        # Organize images
        logger.info("Organizing images...")
        flood_count, no_flood_count = organize_images(output_dir, flood_dest, no_flood_dest)

        print(f"  Flood images: {flood_count}")
        print(f"  No-flood images: {no_flood_count}")

        total_flood += flood_count
        total_no_flood += no_flood_count

    # Summary
    print("\n" + "="*60)
    print("DOWNLOAD SUMMARY")
    print("="*60)
    print(f"Total flood images: {total_flood}")
    print(f"Total no-flood images: {total_no_flood}")
    print(f"\nImages saved to:")
    print(f"  Flood: {flood_dest}")
    print(f"  No-flood: {no_flood_dest}")
    print("="*60 + "\n")

    if total_flood == 0 and total_no_flood == 0:
        logger.warning("No images were downloaded. Check Kaggle authentication.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
