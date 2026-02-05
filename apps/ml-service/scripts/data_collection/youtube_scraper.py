#!/usr/bin/env python3
"""
YouTube Indian Flood Video Frame Extractor.

Downloads flood/normal road videos from YouTube and extracts frames
with strict anti-overfitting rules.

ZERO REGISTRATION REQUIRED - Uses yt-dlp (no API key needed).

Anti-Overfitting Rules Enforced:
- Min 10s between frames (prevent temporal correlation)
- Max 30 frames per video (prevent video dominance)
- Skip intro/outro (30s start, 15s end)
- Min 1min video duration (ignore short clips)

Usage:
    python -m apps.ml-service.scripts.data_collection.youtube_scraper --flood
    python -m apps.ml-service.scripts.data_collection.youtube_scraper --normal
    python -m apps.ml-service.scripts.data_collection.youtube_scraper --both
"""

import subprocess
import json
import logging
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import argparse

try:
    import cv2
except ImportError:
    print("ERROR: opencv-python not installed. Run: pip install opencv-python")
    sys.exit(1)

from .config import (
    YOUTUBE_CONFIG,
    YOUTUBE_FLOOD_DIR,
    YOUTUBE_NORMAL_DIR,
    PROCESSED_FLOOD_DIR,
    PROCESSED_NORMAL_DIR,
    METADATA_DIR,
    FLOOD_QUERIES,
    NORMAL_QUERIES,
    generate_image_name,
    get_city_from_query,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YouTubeScraper:
    """
    Download videos from YouTube and extract frames with anti-overfitting rules.
    """

    def __init__(self):
        self.config = YOUTUBE_CONFIG
        self.sources: Dict[str, dict] = {}  # Track provenance
        self.total_videos = 0
        self.total_frames = 0

    def check_yt_dlp(self) -> bool:
        """Check if yt-dlp is installed."""
        try:
            result = subprocess.run(
                ["yt-dlp", "--version"],
                capture_output=True,
                text=True
            )
            logger.info(f"yt-dlp version: {result.stdout.strip()}")
            return True
        except FileNotFoundError:
            logger.error("yt-dlp not found. Install with: pip install yt-dlp")
            return False

    def check_ffmpeg(self) -> bool:
        """Check if FFmpeg is installed (required by yt-dlp)."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True
            )
            logger.info("FFmpeg is available")
            return True
        except FileNotFoundError:
            logger.error("FFmpeg not found. Install from ffmpeg.org or via package manager")
            return False

    def search_videos(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search YouTube for videos matching query.

        Returns list of video info dicts with id, title, duration.
        """
        cmd = [
            "yt-dlp",
            f"ytsearch{max_results}:{query}",
            "--dump-json",
            "--flat-playlist",
            "--no-download",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            videos = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        info = json.loads(line)
                        videos.append({
                            "id": info.get("id"),
                            "title": info.get("title", "Unknown"),
                            "duration": info.get("duration", 0),
                            "url": f"https://www.youtube.com/watch?v={info.get('id')}",
                        })
                    except json.JSONDecodeError:
                        continue
            return videos
        except subprocess.TimeoutExpired:
            logger.warning(f"Search timeout for query: {query}")
            return []
        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return []

    def download_video(self, video_id: str, output_dir: Path) -> Optional[Path]:
        """
        Download a single video.

        Returns path to downloaded video or None if failed.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(output_dir / f"{video_id}.%(ext)s")

        cmd = [
            "yt-dlp",
            f"https://www.youtube.com/watch?v={video_id}",
            "-f", self.config["video_quality"],
            "-o", output_template,
            "--no-playlist",
            "--quiet",
        ]

        try:
            subprocess.run(cmd, check=True, timeout=300)

            # Find downloaded file (could be .mp4, .webm, etc.)
            for ext in [".mp4", ".webm", ".mkv"]:
                video_path = output_dir / f"{video_id}{ext}"
                if video_path.exists():
                    return video_path

            logger.warning(f"Video {video_id} downloaded but file not found")
            return None

        except subprocess.CalledProcessError as e:
            logger.error(f"Download failed for {video_id}: {e}")
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"Download timeout for {video_id}")
            return None

    def extract_frames(
        self,
        video_path: Path,
        output_dir: Path,
        query: str,
        video_id: str,
        class_label: str,  # 'flood' or 'normal'
    ) -> int:
        """
        Extract frames from video with anti-overfitting rules.

        Rules enforced:
        - Min frame_interval_seconds between frames
        - Max max_frames_per_video frames
        - Skip first skip_first_seconds
        - Skip last skip_last_seconds

        Returns number of frames extracted.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"Cannot open video: {video_path}")
            return 0

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        # Apply anti-overfitting rules
        skip_start = int(self.config["skip_first_seconds"] * fps)
        skip_end = int(self.config["skip_last_seconds"] * fps)
        frame_interval = int(self.config["frame_interval_seconds"] * fps)
        max_frames = self.config["max_frames_per_video"]

        # Check minimum duration
        if duration < self.config["min_video_duration"]:
            logger.info(f"Video too short ({duration:.0f}s < {self.config['min_video_duration']}s): {video_path.name}")
            cap.release()
            return 0

        # Calculate valid frame range
        start_frame = skip_start
        end_frame = max(start_frame + 1, total_frames - skip_end)

        extracted = 0
        frame_idx = start_frame
        city = get_city_from_query(query)

        while frame_idx < end_frame and extracted < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if not ret:
                break

            # Resize to standard size
            frame = cv2.resize(frame, (640, 480))

            # Generate filename
            filename = generate_image_name("yt", query, extracted)
            output_path = output_dir / filename

            # Avoid overwriting
            while output_path.exists():
                extracted += 1
                filename = generate_image_name("yt", query, extracted)
                output_path = output_dir / filename

            # Save frame
            cv2.imwrite(
                str(output_path),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, 85]
            )

            # Track provenance
            frame_time = frame_idx / fps
            self.sources[filename] = {
                "source": "youtube",
                "video_id": video_id,
                "frame_time": round(frame_time, 1),
                "query": query,
                "download_date": datetime.now().isoformat()[:10],
                "city": city,
                "class": class_label,
                "estimated_severity": "unknown",  # To be manually labeled
            }

            extracted += 1
            frame_idx += frame_interval

        cap.release()
        return extracted

    def scrape_category(
        self,
        queries: Dict[str, List[str]],
        video_dir: Path,
        output_dir: Path,
        class_label: str,
    ) -> Dict[str, int]:
        """
        Scrape videos for a category (flood or normal).

        Args:
            queries: Dict of city -> list of search queries
            video_dir: Where to save downloaded videos
            output_dir: Where to save extracted frames
            class_label: 'flood' or 'normal'

        Returns:
            Stats dict with counts per city
        """
        stats = {city: 0 for city in queries}
        total_videos = 0

        for city, city_queries in queries.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"CITY: {city.upper()}")
            logger.info(f"{'='*60}")

            for query in city_queries:
                if total_videos >= self.config["max_total_videos"]:
                    logger.warning("Session video limit reached")
                    break

                logger.info(f"\nSearching: {query}")

                # Search for videos
                videos = self.search_videos(
                    query,
                    max_results=self.config["max_videos_per_query"]
                )

                logger.info(f"Found {len(videos)} videos")

                for video in videos:
                    if total_videos >= self.config["max_total_videos"]:
                        break

                    # Skip short videos
                    if video["duration"] < self.config["min_video_duration"]:
                        logger.info(f"  Skipping (too short): {video['title'][:40]}...")
                        continue

                    video_id = video["id"]
                    logger.info(f"  Processing: {video['title'][:50]}...")

                    # Download video
                    video_path = self.download_video(video_id, video_dir)
                    if not video_path:
                        continue

                    total_videos += 1

                    # Extract frames
                    frames = self.extract_frames(
                        video_path,
                        output_dir,
                        query,
                        video_id,
                        class_label,
                    )

                    stats[city] += frames
                    self.total_frames += frames
                    logger.info(f"    Extracted {frames} frames")

                    # Rate limiting
                    time.sleep(self.config["delay_between_downloads"])

        self.total_videos = total_videos
        return stats

    def scrape_flood_videos(self) -> Dict[str, int]:
        """Scrape flood videos from YouTube."""
        logger.info("\n" + "="*60)
        logger.info("SCRAPING FLOOD VIDEOS")
        logger.info("="*60)

        return self.scrape_category(
            queries=FLOOD_QUERIES,
            video_dir=YOUTUBE_FLOOD_DIR,
            output_dir=PROCESSED_FLOOD_DIR,
            class_label="flood",
        )

    def scrape_normal_videos(self) -> Dict[str, int]:
        """Scrape normal road videos from YouTube."""
        logger.info("\n" + "="*60)
        logger.info("SCRAPING NORMAL ROAD VIDEOS")
        logger.info("="*60)

        return self.scrape_category(
            queries=NORMAL_QUERIES,
            video_dir=YOUTUBE_NORMAL_DIR,
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
        description="Download YouTube videos and extract frames for flood detection"
    )
    parser.add_argument(
        "--flood", action="store_true",
        help="Scrape flood videos only"
    )
    parser.add_argument(
        "--normal", action="store_true",
        help="Scrape normal road videos only"
    )
    parser.add_argument(
        "--both", action="store_true",
        help="Scrape both flood and normal videos"
    )

    args = parser.parse_args()

    # Default to both if nothing specified
    if not args.flood and not args.normal and not args.both:
        args.both = True

    scraper = YouTubeScraper()

    # Check dependencies
    if not scraper.check_yt_dlp():
        return 1
    if not scraper.check_ffmpeg():
        return 1

    print("\n" + "="*60)
    print("YOUTUBE FLOOD IMAGE SCRAPER")
    print("="*60)
    print(f"Frame interval: {YOUTUBE_CONFIG['frame_interval_seconds']}s")
    print(f"Max frames/video: {YOUTUBE_CONFIG['max_frames_per_video']}")
    print(f"Max total videos: {YOUTUBE_CONFIG['max_total_videos']}")
    print("="*60 + "\n")

    flood_stats = {}
    normal_stats = {}

    if args.flood or args.both:
        flood_stats = scraper.scrape_flood_videos()

    if args.normal or args.both:
        normal_stats = scraper.scrape_normal_videos()

    # Save metadata
    scraper.save_sources()

    # Summary
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    print(f"Total videos processed: {scraper.total_videos}")
    print(f"Total frames extracted: {scraper.total_frames}")

    if flood_stats:
        print("\nFlood frames by city:")
        for city, count in flood_stats.items():
            print(f"  {city}: {count}")

    if normal_stats:
        print("\nNormal frames by city:")
        for city, count in normal_stats.items():
            print(f"  {city}: {count}")

    print("="*60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
