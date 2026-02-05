"""
Configuration for Indian Flood Image Data Collection.

Defines search queries, collection rules, and anti-bias/anti-overfitting thresholds.
"""

from pathlib import Path
from typing import List, Dict

# Base paths
SCRIPT_DIR = Path(__file__).parent
ML_SERVICE_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = ML_SERVICE_DIR / "data"

# Raw download directories
RAW_DIR = DATA_DIR / "raw"
YOUTUBE_FLOOD_DIR = RAW_DIR / "youtube" / "flood"
YOUTUBE_NORMAL_DIR = RAW_DIR / "youtube" / "normal"
DDG_FLOOD_DIR = RAW_DIR / "ddg" / "flood"
DDG_NORMAL_DIR = RAW_DIR / "ddg" / "normal"

# Existing Kaggle datasets (already downloaded)
KAGGLE_DIR = DATA_DIR / "kaggle_downloads"
KAGGLE_FLOOD_CLASSIFICATION = KAGGLE_DIR / "flood-classification" / "Dataset"
KAGGLE_FLOOD_DIR = KAGGLE_FLOOD_CLASSIFICATION / "Flood Images"
KAGGLE_NORMAL_DIR = KAGGLE_FLOOD_CLASSIFICATION / "Non Flood Images"

# Processed and final directories
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_FLOOD_DIR = PROCESSED_DIR / "flood"
PROCESSED_NORMAL_DIR = PROCESSED_DIR / "normal"
DATASET_DIR = DATA_DIR / "india_flood_dataset"
METADATA_DIR = DATA_DIR / "metadata"

# ============================================================================
# SEARCH QUERIES - India-specific flood and normal road images
# ============================================================================

# Flood queries by city (for bias tracking)
FLOOD_QUERIES: Dict[str, List[str]] = {
    "delhi": [
        "Delhi flood road 2023",
        "Delhi waterlogging monsoon",
        "Delhi underpass flooded",
        "Delhi ITO waterlogged road",
        "Delhi Minto bridge flood",
        "DTC bus flooded road Delhi",
    ],
    "mumbai": [
        "Mumbai road flooding 2023",
        "Mumbai street waterlogged monsoon",
        "Mumbai Hindmata flooded",
        "Mumbai local train flooded tracks",
        "Mumbai marine drive flood road",
    ],
    "bangalore": [
        "Bangalore road flooding",
        "Bangalore underpass waterlogging",
        "Bangalore ORR flooded road",
        "Bengaluru silk board junction flooded",
    ],
    "chennai": [
        "Chennai road flooding",
        "Chennai waterlogging monsoon 2023",
        "Chennai flood street",
    ],
    "general": [
        "India urban flood street",
        "Indian road waterlogged monsoon",
        "auto rickshaw flood India",
        "Indian underpass water accumulation",
        "car stuck flood India road",
        "pedestrian walking flood India street",
    ],
}

# Normal (non-flood) queries by city
NORMAL_QUERIES: Dict[str, List[str]] = {
    "delhi": [
        "Delhi road drive dashcam",
        "Delhi road dry sunny day",
        "Delhi traffic normal road",
    ],
    "mumbai": [
        "Mumbai street view driving",
        "Mumbai road normal day traffic",
    ],
    "bangalore": [
        "Bangalore road traffic dashcam",
        "Bangalore road clear weather",
    ],
    "chennai": [
        "Chennai road sunny day",
    ],
    "general": [
        "India city road normal traffic",
        "Indian road auto rickshaw sunny",
        "India highway clear day",
        "Indian city junction traffic",
        "India street market sunny",
    ],
}

# Flatten queries for simple iteration
ALL_FLOOD_QUERIES = [q for queries in FLOOD_QUERIES.values() for q in queries]
ALL_NORMAL_QUERIES = [q for queries in NORMAL_QUERIES.values() for q in queries]

# ============================================================================
# YOUTUBE COLLECTION CONFIG - Anti-overfitting rules
# ============================================================================

YOUTUBE_CONFIG = {
    # Frame extraction rules
    "frame_interval_seconds": 10,      # Min 10s between frames (prevent correlation)
    "max_frames_per_video": 30,        # Cap frames per video (prevent dominance)
    "skip_first_seconds": 30,          # Skip intro/ads
    "skip_last_seconds": 15,           # Skip outros
    "min_video_duration": 60,          # Ignore clips <1min

    # Download settings
    "max_videos_per_query": 5,         # Videos per search query
    "video_quality": "best[height<=480]",  # Cap quality for bandwidth
    "max_total_videos": 100,           # Session limit

    # Rate limiting
    "delay_between_downloads": 3,      # Seconds between video downloads
}

# ============================================================================
# DUCKDUCKGO COLLECTION CONFIG
# ============================================================================

DDG_CONFIG = {
    "max_images_per_query": 50,        # Images per search query
    "timeout_seconds": 10,             # Download timeout
    "delay_between_queries": 2,        # Seconds between queries
    "delay_between_downloads": 0.5,    # Seconds between image downloads
}

# ============================================================================
# IMAGE STANDARDIZATION CONFIG
# ============================================================================

IMAGE_CONFIG = {
    "target_width": 640,
    "target_height": 480,
    "jpeg_quality": 85,
    "min_source_width": 200,
    "min_source_height": 200,
    "max_aspect_ratio": 3.0,
}

# ============================================================================
# DEDUPLICATION CONFIG
# ============================================================================

DEDUP_CONFIG = {
    "phash_threshold": 5,              # Perceptual hash difference threshold
    "use_md5": True,                   # Level 1: Exact duplicate removal
    "use_phash": True,                 # Level 2: Near-duplicate removal
    "use_cross_query": True,           # Level 3: Cross-query duplicate removal
}

# ============================================================================
# QUALITY FILTER CONFIG
# ============================================================================

QUALITY_CONFIG = {
    "min_resolution": (200, 200),
    "max_aspect_ratio": 3.0,
    "blur_threshold": 100,             # Laplacian variance threshold
    "min_brightness": 20,              # Reject mostly black
    "max_brightness": 235,             # Reject mostly white
}

# ============================================================================
# DATASET SPLIT CONFIG
# ============================================================================

SPLIT_CONFIG = {
    "train_ratio": 0.80,
    "val_ratio": 0.10,
    "test_ratio": 0.10,
    "random_seed": 42,
}

# ============================================================================
# VALIDATION RULES - All must pass before training
# ============================================================================

VALIDATION_RULES = {
    # Size requirements
    "min_total_images": 1000,
    "min_per_class": 400,

    # Balance requirements
    "max_class_imbalance_ratio": 2.0,  # flood:no_flood
    "max_source_dominance": 0.40,      # No source >40%
    "min_city_representation": 0.15,   # Each major city >=15%

    # Quality requirements
    "max_blur_percentage": 0.10,       # <=10% blurry images
    "max_duplicate_percentage": 0.05,  # <=5% duplicates after dedup

    # Leakage prevention
    "cross_split_hash_threshold": 5,   # Perceptual hash difference for leakage
    "same_video_min_frame_gap": 10,    # Seconds between frames from same video
}

# ============================================================================
# NAMING CONVENTION
# ============================================================================

def generate_image_name(source: str, query: str, index: int, ext: str = "jpg") -> str:
    """
    Generate standardized image filename.

    Format: {source}_{query_slug}_{index:05d}.{ext}
    Example: yt_delhi_flood_2023_00001.jpg
    """
    # Slugify query: lowercase, replace spaces with underscore, limit length
    query_slug = query.lower().replace(" ", "_")[:30]
    return f"{source}_{query_slug}_{index:05d}.{ext}"


def get_city_from_query(query: str) -> str:
    """Extract city from query string."""
    query_lower = query.lower()
    for city in ["delhi", "mumbai", "bangalore", "bengaluru", "chennai"]:
        if city in query_lower:
            return "bangalore" if city == "bengaluru" else city
    return "other"
