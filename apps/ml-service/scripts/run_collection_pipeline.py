#!/usr/bin/env python3
"""
Master Data Collection Pipeline Orchestrator.

Runs the complete 5-stage pipeline for Indian flood image dataset:
1. Collection (YouTube + DuckDuckGo)
2. Standardization (resize, format)
3. Deduplication (MD5 + pHash + cross-query)
4. Quality Filter (resolution, blur, brightness)
5. Split Dataset (train/val/test)

Plus optional verification step.

Usage:
    # Full pipeline
    python -m apps.ml-service.scripts.run_collection_pipeline

    # Individual stages
    python -m apps.ml-service.scripts.run_collection_pipeline --collect-only
    python -m apps.ml-service.scripts.run_collection_pipeline --process-only
    python -m apps.ml-service.scripts.run_collection_pipeline --verify-only
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add scripts directory to path for local imports
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from data_collection.config import (
    DATA_DIR,
    RAW_DIR,
    PROCESSED_DIR,
    DATASET_DIR,
    METADATA_DIR,
    VALIDATION_RULES,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineStats:
    """Track statistics across all pipeline stages."""

    def __init__(self):
        self.start_time = datetime.now()
        self.stages: Dict[str, Dict[str, Any]] = {}
        self.errors: list = []

    def record_stage(self, name: str, stats: Dict[str, Any], duration: float):
        self.stages[name] = {
            "stats": stats,
            "duration_seconds": round(duration, 2),
        }

    def record_error(self, stage: str, error: str):
        self.errors.append({"stage": stage, "error": error})

    def summary(self) -> str:
        """Generate summary report."""
        total_time = (datetime.now() - self.start_time).total_seconds()

        lines = [
            "\n" + "=" * 70,
            "PIPELINE EXECUTION SUMMARY",
            "=" * 70,
            f"Total execution time: {total_time:.1f} seconds",
            f"Stages completed: {len(self.stages)}",
            f"Errors: {len(self.errors)}",
        ]

        for stage_name, data in self.stages.items():
            lines.append(f"\n{stage_name}:")
            lines.append(f"  Duration: {data['duration_seconds']}s")
            for key, val in data['stats'].items():
                if not isinstance(val, (dict, list)):
                    lines.append(f"  {key}: {val}")

        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f"  [{err['stage']}] {err['error']}")

        lines.append("=" * 70)
        return "\n".join(lines)


def run_collection(stats: PipelineStats, cities: list = None) -> bool:
    """
    Stage 1: Collect images from YouTube and DuckDuckGo.

    Args:
        stats: Pipeline statistics tracker
        cities: List of cities to collect for (default: all)

    Returns:
        True if successful
    """
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 1: DATA COLLECTION")
    logger.info("=" * 60)

    start = time.time()
    combined_stats = {
        "youtube_flood": 0,
        "youtube_normal": 0,
        "ddg_flood": 0,
        "ddg_normal": 0,
    }

    try:
        # Import scrapers
        from data_collection.youtube_scraper import scrape_youtube_all
        from data_collection.ddg_scraper import scrape_ddg_all

        # Run YouTube scraper
        logger.info("\n--- YouTube Scraper ---")
        try:
            yt_stats = scrape_youtube_all(cities=cities)
            combined_stats["youtube_flood"] = yt_stats.get("flood", {}).get("frames_extracted", 0)
            combined_stats["youtube_normal"] = yt_stats.get("normal", {}).get("frames_extracted", 0)
        except Exception as e:
            logger.warning(f"YouTube scraper failed: {e}")
            stats.record_error("collection_youtube", str(e))

        # Run DuckDuckGo scraper
        logger.info("\n--- DuckDuckGo Scraper ---")
        try:
            ddg_stats = scrape_ddg_all(cities=cities)
            combined_stats["ddg_flood"] = ddg_stats.get("flood", {}).get("images_saved", 0)
            combined_stats["ddg_normal"] = ddg_stats.get("normal", {}).get("images_saved", 0)
        except Exception as e:
            logger.warning(f"DuckDuckGo scraper failed: {e}")
            stats.record_error("collection_ddg", str(e))

        combined_stats["total_collected"] = sum(combined_stats.values())

        duration = time.time() - start
        stats.record_stage("1_collection", combined_stats, duration)

        logger.info(f"\nCollection complete: {combined_stats['total_collected']} images")
        return combined_stats["total_collected"] > 0

    except Exception as e:
        stats.record_error("collection", str(e))
        logger.error(f"Collection stage failed: {e}")
        return False


def run_standardization(stats: PipelineStats) -> bool:
    """
    Stage 2: Standardize all images to consistent format.

    Returns:
        True if successful
    """
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 2: STANDARDIZATION")
    logger.info("=" * 60)

    start = time.time()

    try:
        from data_processing.standardize import process_all

        result = process_all()

        duration = time.time() - start
        stats.record_stage("2_standardization", result, duration)

        logger.info(f"\nStandardization complete: {result['processed']} images processed")
        return True

    except Exception as e:
        stats.record_error("standardization", str(e))
        logger.error(f"Standardization stage failed: {e}")
        return False


def run_deduplication(stats: PipelineStats, remove: bool = False) -> bool:
    """
    Stage 3: Remove duplicate images.

    Args:
        remove: If True, actually delete duplicates

    Returns:
        True if successful
    """
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 3: DEDUPLICATION")
    logger.info("=" * 60)

    start = time.time()

    try:
        from data_processing.deduplicate import (
            deduplicate_dataset,
            remove_duplicates,
        )

        report = deduplicate_dataset()

        if remove and report["removed_count"] > 0:
            removed = remove_duplicates(report, dry_run=False)
            report["actually_removed"] = removed

        duration = time.time() - start
        stats.record_stage("3_deduplication", {
            "initial": report["initial_count"],
            "final": report["final_count"],
            "duplicates": report["removed_count"],
            "duplicate_rate": f"{report['duplicate_rate']*100:.1f}%",
        }, duration)

        logger.info(f"\nDeduplication complete: {report['removed_count']} duplicates found")
        return True

    except Exception as e:
        stats.record_error("deduplication", str(e))
        logger.error(f"Deduplication stage failed: {e}")
        return False


def run_quality_filter(stats: PipelineStats, remove: bool = False) -> bool:
    """
    Stage 4: Filter low-quality images.

    Args:
        remove: If True, actually delete rejected images

    Returns:
        True if successful
    """
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 4: QUALITY FILTER")
    logger.info("=" * 60)

    start = time.time()

    try:
        from data_processing.quality_filter import (
            filter_all,
            remove_rejected,
        )

        report = filter_all()

        if remove and report["rejected"] > 0:
            removed = remove_rejected(report, dry_run=False)
            report["actually_removed"] = removed

        duration = time.time() - start
        stats.record_stage("4_quality_filter", {
            "total": report["total"],
            "passed": report["passed"],
            "rejected": report["rejected"],
            "pass_rate": f"{report['pass_rate']*100:.1f}%",
        }, duration)

        logger.info(f"\nQuality filter complete: {report['passed']}/{report['total']} passed")
        return True

    except Exception as e:
        stats.record_error("quality_filter", str(e))
        logger.error(f"Quality filter stage failed: {e}")
        return False


def run_split(stats: PipelineStats) -> bool:
    """
    Stage 5: Split dataset into train/val/test.

    Returns:
        True if successful
    """
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 5: DATASET SPLIT")
    logger.info("=" * 60)

    start = time.time()

    try:
        from data_processing.split_dataset import split_dataset

        result = split_dataset()

        duration = time.time() - start
        stats.record_stage("5_split", {
            "train": result["totals"]["train"],
            "val": result["totals"]["val"],
            "test": result["totals"]["test"],
            "total": result["totals"]["total"],
            "flood": result["flood"]["total"],
            "no_flood": result["no_flood"]["total"],
        }, duration)

        logger.info(f"\nSplit complete: {result['totals']['total']} images split")
        return result["totals"]["total"] > 0

    except Exception as e:
        stats.record_error("split", str(e))
        logger.error(f"Split stage failed: {e}")
        return False


def run_verification(stats: PipelineStats) -> bool:
    """
    Verification Stage: Run all validation checks.

    Returns:
        True if all checks pass
    """
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION STAGE")
    logger.info("=" * 60)

    start = time.time()

    try:
        from data_processing.verify_dataset import verify_dataset

        report = verify_dataset()

        duration = time.time() - start
        stats.record_stage("verification", {
            "checks_passed": report["checks_passed"],
            "checks_failed": report["checks_failed"],
            "overall_pass": report["overall_pass"],
            "warnings": len(report.get("warnings", [])),
        }, duration)

        if report["overall_pass"]:
            logger.info("\nVerification PASSED - Dataset ready for training")
        else:
            logger.warning("\nVerification FAILED - See report for details")

        return report["overall_pass"]

    except Exception as e:
        stats.record_error("verification", str(e))
        logger.error(f"Verification stage failed: {e}")
        return False


def run_full_pipeline(
    cities: list = None,
    remove_duplicates: bool = True,
    remove_rejected: bool = True,
    skip_collection: bool = False,
) -> PipelineStats:
    """
    Run the complete 5-stage pipeline.

    Args:
        cities: List of cities to collect for
        remove_duplicates: Whether to delete duplicate files
        remove_rejected: Whether to delete quality-rejected files
        skip_collection: Skip collection if data already exists

    Returns:
        PipelineStats object with execution summary
    """
    stats = PipelineStats()

    print("\n" + "=" * 70)
    print("INDIAN FLOOD IMAGE DATASET PIPELINE")
    print("=" * 70)
    print(f"Started: {stats.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Cities: {cities or 'all'}")
    print(f"Remove duplicates: {remove_duplicates}")
    print(f"Remove rejected: {remove_rejected}")
    print("=" * 70)

    # Ensure directories exist
    for dir_path in [RAW_DIR, PROCESSED_DIR, DATASET_DIR, METADATA_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Stage 1: Collection
    if not skip_collection:
        if not run_collection(stats, cities):
            logger.warning("Collection stage had issues, continuing...")

    # Stage 2: Standardization
    if not run_standardization(stats):
        logger.warning("Standardization stage had issues, continuing...")

    # Stage 3: Deduplication
    if not run_deduplication(stats, remove=remove_duplicates):
        logger.warning("Deduplication stage had issues, continuing...")

    # Stage 4: Quality Filter
    if not run_quality_filter(stats, remove=remove_rejected):
        logger.warning("Quality filter stage had issues, continuing...")

    # Stage 5: Split
    if not run_split(stats):
        logger.error("Split stage failed!")
        return stats

    # Verification
    run_verification(stats)

    print(stats.summary())
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Run Indian flood image dataset pipeline"
    )

    # Stage selection
    parser.add_argument(
        "--collect-only", action="store_true",
        help="Only run collection stage"
    )
    parser.add_argument(
        "--process-only", action="store_true",
        help="Only run processing stages (standardize, dedup, filter, split)"
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Only run verification"
    )

    # Options
    parser.add_argument(
        "--cities", nargs="+",
        choices=["delhi", "mumbai", "bangalore", "chennai", "hyderabad"],
        help="Cities to collect data for (default: all)"
    )
    parser.add_argument(
        "--keep-duplicates", action="store_true",
        help="Don't delete duplicate files (just report)"
    )
    parser.add_argument(
        "--keep-rejected", action="store_true",
        help="Don't delete quality-rejected files (just report)"
    )
    parser.add_argument(
        "--skip-collection", action="store_true",
        help="Skip collection if data already exists"
    )

    args = parser.parse_args()

    stats = PipelineStats()

    if args.collect_only:
        run_collection(stats, args.cities)
        print(stats.summary())

    elif args.process_only:
        run_standardization(stats)
        run_deduplication(stats, remove=not args.keep_duplicates)
        run_quality_filter(stats, remove=not args.keep_rejected)
        run_split(stats)
        run_verification(stats)
        print(stats.summary())

    elif args.verify_only:
        run_verification(stats)
        print(stats.summary())

    else:
        # Full pipeline
        run_full_pipeline(
            cities=args.cities,
            remove_duplicates=not args.keep_duplicates,
            remove_rejected=not args.keep_rejected,
            skip_collection=args.skip_collection,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
