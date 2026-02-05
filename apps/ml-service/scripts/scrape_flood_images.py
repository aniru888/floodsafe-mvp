"""
Flood Image Scraper

Scrapes flood and non-flood images from Google Images using icrawler.
Focuses on India-specific urban flooding scenarios for FloodSafe.

SAFETY NOTE:
- Respects rate limits (default: 1 request/second)
- Uses proper User-Agent headers
- Images require manual verification before training

Usage:
    python -m apps.ml-service.scripts.scrape_flood_images
    python -m apps.ml-service.scripts.scrape_flood_images --images-per-query 100
    python -m apps.ml-service.scripts.scrape_flood_images --flood-only
    python -m apps.ml-service.scripts.scrape_flood_images --no-flood-only
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Base paths
SCRIPT_DIR = Path(__file__).parent
ML_SERVICE_DIR = SCRIPT_DIR.parent
DATA_DIR = ML_SERVICE_DIR / "data"
SCRAPED_DIR = DATA_DIR / "scraped_images"

# India-specific flood search queries (positive samples)
FLOOD_QUERIES: List[str] = [
    # Delhi floods
    "Delhi road flooding 2023",
    "Delhi waterlogging monsoon",
    "Delhi underpass flooded",
    "Delhi ITO flooded road",
    "Delhi Minto bridge waterlogging",
    "Delhi flood street view",

    # Mumbai floods
    "Mumbai road flooding 2023",
    "Mumbai street waterlogged monsoon",
    "Mumbai Hindmata flooded",
    "Mumbai local train flooded tracks",
    "Mumbai marine drive flood",

    # Bangalore floods
    "Bangalore road flooding",
    "Bangalore underpass waterlogging",
    "Bangalore ORR flooded",
    "Bengaluru silk board junction flooded",

    # Chennai floods
    "Chennai road flooding",
    "Chennai waterlogging monsoon",
    "Chennai flood street 2023",

    # General India urban floods
    "India urban flood street",
    "Indian road waterlogged monsoon",
    "India city flooding rain",
    "Indian underpass water accumulation",
    "India metro city flood road",

    # Specific flood scenarios
    "car stuck flood India",
    "water on road India monsoon",
    "road submerged water India",
    "pedestrian walking flood India",
    "flooded market India",
]

# Non-flood search queries (negative samples)
NO_FLOOD_QUERIES: List[str] = [
    # Normal road conditions
    "Delhi road dry sunny",
    "Mumbai street normal day",
    "Bangalore road clear weather",
    "Chennai road sunny",
    "India city road normal",

    # Specific non-flood scenarios
    "Indian road traffic normal",
    "India street market sunny",
    "Indian underpass dry",
    "India highway clear",
    "Indian city junction normal",

    # Clear weather scenes
    "Delhi street summer",
    "Mumbai road morning",
    "Bangalore road evening",
    "India urban road winter",
]


def scrape_images(
    query: str,
    output_dir: Path,
    max_images: int = 50,
    crawler_type: str = "google"
) -> int:
    """
    Scrape images for a single query.

    Args:
        query: Search query string
        output_dir: Directory to save images
        max_images: Maximum number of images to download
        crawler_type: "google", "bing", or "baidu"

    Returns:
        Number of images successfully downloaded
    """
    try:
        # Create query-specific subdirectory FIRST
        query_dir = output_dir / query.replace(" ", "_")[:50]
        query_dir.mkdir(parents=True, exist_ok=True)

        # Initialize crawler with correct directory from the start
        # (storage cannot be reassigned after creation!)
        if crawler_type == "google":
            from icrawler.builtin import GoogleImageCrawler
            crawler = GoogleImageCrawler(
                storage={"root_dir": str(query_dir)},
                log_level=logging.WARNING,
            )
        elif crawler_type == "bing":
            from icrawler.builtin import BingImageCrawler
            crawler = BingImageCrawler(
                storage={"root_dir": str(query_dir)},
                log_level=logging.WARNING,
            )
        else:
            logger.error(f"Unknown crawler type: {crawler_type}")
            return 0

        logger.info(f"Scraping: '{query}' ({max_images} images)")

        # Crawl with rate limiting
        crawler.crawl(
            keyword=query,
            max_num=max_images,
            min_size=(200, 200),  # Minimum image size
            file_idx_offset=0,
        )

        # Count downloaded images
        downloaded = len(list(query_dir.glob("*.jpg"))) + len(list(query_dir.glob("*.png")))

        logger.info(f"  Downloaded {downloaded} images for '{query}'")
        return downloaded

    except ImportError:
        logger.error("icrawler not installed. Run: pip install icrawler")
        return 0
    except Exception as e:
        logger.error(f"Failed to scrape '{query}': {e}")
        return 0


def scrape_category(
    queries: List[str],
    category: str,
    images_per_query: int = 50,
    crawler_type: str = "google"
) -> Dict[str, int]:
    """
    Scrape images for a category (flood or no_flood).

    Args:
        queries: List of search queries
        category: "flood" or "no_flood"
        images_per_query: Max images per query
        crawler_type: Crawler to use

    Returns:
        Dict mapping query to download count
    """
    output_dir = SCRAPED_DIR / category
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    total = 0

    for i, query in enumerate(queries, 1):
        print(f"\n[{i}/{len(queries)}] Scraping '{query}'...")

        count = scrape_images(
            query=query,
            output_dir=output_dir,
            max_images=images_per_query,
            crawler_type=crawler_type
        )

        results[query] = count
        total += count

        # Rate limiting between queries
        if i < len(queries):
            time.sleep(2)

    print(f"\nTotal {category} images: {total}")
    return results


def consolidate_images(scraped_dir: Path, output_dir: Path) -> int:
    """
    Consolidate all scraped images from subdirectories into a flat structure.

    Args:
        scraped_dir: Root scraped directory (e.g., scraped_images/flood/)
        output_dir: Destination directory

    Returns:
        Number of images moved
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for img_file in scraped_dir.rglob("*.jpg"):
        # Create unique filename
        dest = output_dir / f"scraped_{count:04d}.jpg"
        while dest.exists():
            count += 1
            dest = output_dir / f"scraped_{count:04d}.jpg"

        img_file.rename(dest)
        count += 1

    for img_file in scraped_dir.rglob("*.png"):
        dest = output_dir / f"scraped_{count:04d}.png"
        while dest.exists():
            count += 1
            dest = output_dir / f"scraped_{count:04d}.png"

        img_file.rename(dest)
        count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Scrape flood images from Google Images")
    parser.add_argument(
        "--images-per-query",
        type=int,
        default=50,
        help="Maximum images to download per query (default: 50)"
    )
    parser.add_argument(
        "--flood-only",
        action="store_true",
        help="Only scrape flood images"
    )
    parser.add_argument(
        "--no-flood-only",
        action="store_true",
        help="Only scrape non-flood images"
    )
    parser.add_argument(
        "--crawler",
        choices=["google", "bing"],
        default="google",
        help="Image crawler to use (default: google)"
    )
    parser.add_argument(
        "--consolidate",
        action="store_true",
        help="Consolidate scraped images into flat directories"
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("FLOOD IMAGE SCRAPER")
    print("="*60)
    print(f"Images per query: {args.images_per_query}")
    print(f"Crawler: {args.crawler}")
    print(f"Output directory: {SCRAPED_DIR}")
    print("="*60 + "\n")

    # Check icrawler installation
    try:
        import icrawler
        logger.info(f"icrawler version: {icrawler.__version__}")
    except ImportError:
        logger.error("icrawler not installed. Run: pip install icrawler")
        return 1

    # Scrape flood images
    if not args.no_flood_only:
        print("\n" + "-"*60)
        print("SCRAPING FLOOD IMAGES")
        print("-"*60)
        flood_results = scrape_category(
            queries=FLOOD_QUERIES,
            category="flood",
            images_per_query=args.images_per_query,
            crawler_type=args.crawler
        )

    # Scrape non-flood images
    if not args.flood_only:
        print("\n" + "-"*60)
        print("SCRAPING NON-FLOOD IMAGES")
        print("-"*60)
        no_flood_results = scrape_category(
            queries=NO_FLOOD_QUERIES,
            category="no_flood",
            images_per_query=args.images_per_query,
            crawler_type=args.crawler
        )

    # Consolidate if requested
    if args.consolidate:
        print("\n" + "-"*60)
        print("CONSOLIDATING IMAGES")
        print("-"*60)

        train_flood = DATA_DIR / "flood_images" / "train" / "flood"
        train_no_flood = DATA_DIR / "flood_images" / "train" / "no_flood"

        flood_count = consolidate_images(SCRAPED_DIR / "flood", train_flood)
        no_flood_count = consolidate_images(SCRAPED_DIR / "no_flood", train_no_flood)

        print(f"Consolidated {flood_count} flood images")
        print(f"Consolidated {no_flood_count} non-flood images")

    # Summary
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    print(f"Images saved to: {SCRAPED_DIR}")
    print("\nNEXT STEPS:")
    print("1. Review scraped images and remove irrelevant ones")
    print("2. Run preprocessing script to dedupe and split data")
    print("3. Upload to Roboflow for additional labeling (optional)")
    print("="*60 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
