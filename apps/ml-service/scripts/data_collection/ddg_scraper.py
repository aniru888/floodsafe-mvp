#!/usr/bin/env python3
"""
DuckDuckGo Image Scraper for Indian Flood Images.

Downloads flood/normal road images from DuckDuckGo image search.

ZERO REGISTRATION REQUIRED - No API key needed.

Usage:
    python -m apps.ml-service.scripts.data_collection.ddg_scraper --flood
    python -m apps.ml-service.scripts.data_collection.ddg_scraper --normal
    python -m apps.ml-service.scripts.data_collection.ddg_scraper --both
"""

import json
import logging
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import argparse
import hashlib

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    from duckduckgo_search import DDGS
except ImportError:
    print("ERROR: duckduckgo-search not installed. Run: pip install duckduckgo-search")
    sys.exit(1)

try:
    from PIL import Image
    import io
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

from .config import (
    DDG_CONFIG,
    DDG_FLOOD_DIR,
    DDG_NORMAL_DIR,
    PROCESSED_FLOOD_DIR,
    PROCESSED_NORMAL_DIR,
    METADATA_DIR,
    FLOOD_QUERIES,
    NORMAL_QUERIES,
    IMAGE_CONFIG,
    generate_image_name,
    get_city_from_query,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DDGScraper:
    """
    Download images from DuckDuckGo image search.
    """

    def __init__(self):
        self.config = DDG_CONFIG
        self.image_config = IMAGE_CONFIG
        self.sources: Dict[str, dict] = {}
        self.total_downloaded = 0
        self.total_failed = 0
        self.seen_hashes: set = set()  # For in-session dedup

    def download_image(self, url: str, timeout: int = 10) -> Optional[bytes]:
        """
        Download image from URL.

        Returns image bytes or None if failed.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(url, timeout=timeout, headers=headers)

            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'image' in content_type:
                    return response.content

            return None

        except Exception as e:
            logger.debug(f"Download failed: {e}")
            return None

    def validate_and_process_image(
        self,
        image_bytes: bytes,
        output_path: Path,
    ) -> bool:
        """
        Validate image quality and save to disk.

        Checks:
        - Minimum resolution
        - Valid image format
        - Not a duplicate (MD5 hash)

        Returns True if saved successfully.
        """
        try:
            # Check hash for duplicates
            md5_hash = hashlib.md5(image_bytes).hexdigest()
            if md5_hash in self.seen_hashes:
                logger.debug("Duplicate image (same hash)")
                return False
            self.seen_hashes.add(md5_hash)

            # Load and validate image
            img = Image.open(io.BytesIO(image_bytes))

            # Check minimum size
            if img.width < self.image_config["min_source_width"]:
                logger.debug(f"Image too small: {img.width}x{img.height}")
                return False
            if img.height < self.image_config["min_source_height"]:
                logger.debug(f"Image too small: {img.width}x{img.height}")
                return False

            # Check aspect ratio
            aspect = max(img.width / img.height, img.height / img.width)
            if aspect > self.image_config["max_aspect_ratio"]:
                logger.debug(f"Bad aspect ratio: {aspect:.2f}")
                return False

            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Resize to target size
            img = img.resize(
                (self.image_config["target_width"], self.image_config["target_height"]),
                Image.Resampling.LANCZOS
            )

            # Save as JPEG
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(
                output_path,
                'JPEG',
                quality=self.image_config["jpeg_quality"]
            )

            return True

        except Exception as e:
            logger.debug(f"Image processing failed: {e}")
            return False

    def search_images(self, query: str, max_results: int = 50) -> List[Dict]:
        """
        Search DuckDuckGo for images.

        Returns list of image info dicts.
        """
        try:
            with DDGS() as ddgs:
                results = list(ddgs.images(
                    query,
                    max_results=max_results,
                    safesearch="moderate",
                ))
                return results
        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return []

    def scrape_query(
        self,
        query: str,
        output_dir: Path,
        class_label: str,
        start_index: int = 0,
    ) -> int:
        """
        Scrape images for a single query.

        Returns number of images successfully downloaded.
        """
        logger.info(f"Searching: {query}")

        results = self.search_images(query, self.config["max_images_per_query"])
        logger.info(f"  Found {len(results)} results")

        downloaded = 0
        city = get_city_from_query(query)

        for i, result in enumerate(results):
            img_url = result.get('image')
            if not img_url:
                continue

            # Generate filename
            filename = generate_image_name("ddg", query, start_index + downloaded)
            output_path = output_dir / filename

            # Avoid overwriting
            while output_path.exists():
                start_index += 1
                filename = generate_image_name("ddg", query, start_index + downloaded)
                output_path = output_dir / filename

            # Download image
            img_bytes = self.download_image(img_url, self.config["timeout_seconds"])
            if not img_bytes:
                self.total_failed += 1
                continue

            # Validate and save
            if self.validate_and_process_image(img_bytes, output_path):
                # Track provenance
                self.sources[filename] = {
                    "source": "duckduckgo",
                    "url": img_url,
                    "query": query,
                    "download_date": datetime.now().isoformat()[:10],
                    "city": city,
                    "class": class_label,
                    "estimated_severity": "unknown",
                }

                downloaded += 1
                self.total_downloaded += 1
            else:
                self.total_failed += 1

            # Rate limiting
            time.sleep(self.config["delay_between_downloads"])

        logger.info(f"  Downloaded {downloaded} images")
        return downloaded

    def scrape_category(
        self,
        queries: Dict[str, List[str]],
        output_dir: Path,
        class_label: str,
    ) -> Dict[str, int]:
        """
        Scrape images for a category (flood or normal).

        Returns stats dict with counts per city.
        """
        stats = {city: 0 for city in queries}
        index_offset = 0

        for city, city_queries in queries.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"CITY: {city.upper()}")
            logger.info(f"{'='*60}")

            for query in city_queries:
                count = self.scrape_query(
                    query,
                    output_dir,
                    class_label,
                    start_index=index_offset,
                )
                stats[city] += count
                index_offset += count

                # Delay between queries
                time.sleep(self.config["delay_between_queries"])

        return stats

    def scrape_flood_images(self) -> Dict[str, int]:
        """Scrape flood images from DuckDuckGo."""
        logger.info("\n" + "="*60)
        logger.info("SCRAPING FLOOD IMAGES FROM DUCKDUCKGO")
        logger.info("="*60)

        return self.scrape_category(
            queries=FLOOD_QUERIES,
            output_dir=PROCESSED_FLOOD_DIR,
            class_label="flood",
        )

    def scrape_normal_images(self) -> Dict[str, int]:
        """Scrape normal road images from DuckDuckGo."""
        logger.info("\n" + "="*60)
        logger.info("SCRAPING NORMAL ROAD IMAGES FROM DUCKDUCKGO")
        logger.info("="*60)

        return self.scrape_category(
            queries=NORMAL_QUERIES,
            output_dir=PROCESSED_NORMAL_DIR,
            class_label="normal",
        )

    def save_sources(self):
        """Save provenance metadata to sources.json."""
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        sources_file = METADATA_DIR / "sources.json"

        # Load existing sources if any
        existing = {}
        if sources_file.exists():
            try:
                with open(sources_file) as f:
                    existing = json.load(f)
            except json.JSONDecodeError:
                existing = {}

        # Merge with new sources
        existing.update(self.sources)

        with open(sources_file, 'w') as f:
            json.dump(existing, f, indent=2)

        logger.info(f"Saved {len(self.sources)} new source entries to {sources_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Download images from DuckDuckGo for flood detection"
    )
    parser.add_argument(
        "--flood", action="store_true",
        help="Scrape flood images only"
    )
    parser.add_argument(
        "--normal", action="store_true",
        help="Scrape normal road images only"
    )
    parser.add_argument(
        "--both", action="store_true",
        help="Scrape both flood and normal images"
    )

    args = parser.parse_args()

    # Default to both if nothing specified
    if not args.flood and not args.normal and not args.both:
        args.both = True

    scraper = DDGScraper()

    print("\n" + "="*60)
    print("DUCKDUCKGO FLOOD IMAGE SCRAPER")
    print("="*60)
    print(f"Max images per query: {DDG_CONFIG['max_images_per_query']}")
    print(f"Timeout: {DDG_CONFIG['timeout_seconds']}s")
    print("="*60 + "\n")

    flood_stats = {}
    normal_stats = {}

    if args.flood or args.both:
        flood_stats = scraper.scrape_flood_images()

    if args.normal or args.both:
        normal_stats = scraper.scrape_normal_images()

    # Save metadata
    scraper.save_sources()

    # Summary
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    print(f"Total downloaded: {scraper.total_downloaded}")
    print(f"Total failed: {scraper.total_failed}")

    if flood_stats:
        print("\nFlood images by city:")
        for city, count in flood_stats.items():
            print(f"  {city}: {count}")

    if normal_stats:
        print("\nNormal images by city:")
        for city, count in normal_stats.items():
            print(f"  {city}: {count}")

    print("="*60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
