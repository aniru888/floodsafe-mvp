"""
CLIP-based Image Filter for Flood Dataset Curation.

Uses OpenCLIP to filter images by semantic similarity to flood-related prompts.
Keeps only images that match "urban road flooded with water" pattern.

Usage:
    python scripts/data_processing/clip_filter.py \
        --input data/roadway_flooding/images/ \
        --output data/clip_filtered/ \
        --threshold 0.25
"""

import argparse
import shutil
from pathlib import Path
from typing import List, Tuple
import logging

import open_clip
import torch
from PIL import Image

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# Prompts for flood detection
FLOOD_PROMPTS = [
    "photo of flooded urban road with vehicles",
    "photo of waterlogged street with cars stuck in water",
    "photo of road covered with flood water during rain",
    "photo of vehicles driving through flooded street",
    "photo of monsoon flooding on city road",
]

# Prompts for non-road/irrelevant content
REJECT_PROMPTS = [
    "aerial view satellite image of flood",
    "map or infographic about flooding",
    "screenshot or diagram",
    "indoor scene or building interior",
    "river or lake flooding rural area",
    "news article or text overlay",
]


class CLIPFilter:
    """Filter images using CLIP semantic similarity."""

    def __init__(self, model_name: str = 'ViT-B-32', pretrained: str = 'laion2b_s34b_b79k'):
        """Initialize CLIP model."""
        logger.info(f"Loading OpenCLIP {model_name}...")
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained
        )
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.model.eval()

        # Pre-compute text embeddings
        self._compute_text_embeddings()
        logger.info("CLIP model loaded and ready")

    def _compute_text_embeddings(self):
        """Pre-compute text embeddings for efficiency."""
        all_prompts = FLOOD_PROMPTS + REJECT_PROMPTS
        text_tokens = self.tokenizer(all_prompts)

        with torch.no_grad():
            self.text_features = self.model.encode_text(text_tokens)
            self.text_features /= self.text_features.norm(dim=-1, keepdim=True)

        self.n_flood_prompts = len(FLOOD_PROMPTS)

    def score_image(self, image_path: Path) -> Tuple[float, float, bool]:
        """
        Score an image for flood relevance.

        Returns:
            Tuple of (flood_score, reject_score, should_keep)
        """
        try:
            image = Image.open(image_path).convert('RGB')
            image_tensor = self.preprocess(image).unsqueeze(0)

            with torch.no_grad():
                image_features = self.model.encode_image(image_tensor)
                image_features /= image_features.norm(dim=-1, keepdim=True)

                # Compute similarity to all prompts
                similarity = (image_features @ self.text_features.T).squeeze(0)

            # Best flood score vs best reject score
            flood_scores = similarity[:self.n_flood_prompts]
            reject_scores = similarity[self.n_flood_prompts:]

            flood_score = flood_scores.max().item()
            reject_score = reject_scores.max().item()

            # Keep if flood score beats reject score
            should_keep = flood_score > reject_score

            return flood_score, reject_score, should_keep

        except Exception as e:
            logger.warning(f"Error processing {image_path}: {e}")
            return 0.0, 0.0, False

    def filter_directory(
        self,
        input_dir: Path,
        output_dir: Path,
        threshold: float = 0.25,
        min_flood_score: float = 0.20
    ) -> dict:
        """
        Filter all images in a directory.

        Args:
            input_dir: Directory containing images
            output_dir: Directory to copy filtered images
            threshold: Minimum margin (flood_score - reject_score)
            min_flood_score: Minimum absolute flood score

        Returns:
            Statistics dict
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find all images
        extensions = ['.jpg', '.jpeg', '.png', '.webp']
        images = []
        for ext in extensions:
            images.extend(input_dir.glob(f'*{ext}'))
            images.extend(input_dir.glob(f'*{ext.upper()}'))

        logger.info(f"Found {len(images)} images in {input_dir}")

        stats = {
            'total': len(images),
            'kept': 0,
            'rejected': 0,
            'errors': 0,
            'kept_files': [],
            'rejected_files': [],
        }

        for i, img_path in enumerate(images):
            flood_score, reject_score, should_keep = self.score_image(img_path)
            margin = flood_score - reject_score

            # Apply thresholds
            passes_margin = margin >= threshold
            passes_min_score = flood_score >= min_flood_score
            final_keep = should_keep and passes_margin and passes_min_score

            if final_keep:
                # Copy to output directory
                dst = output_dir / img_path.name
                shutil.copy2(img_path, dst)
                stats['kept'] += 1
                stats['kept_files'].append(img_path.name)
            else:
                stats['rejected'] += 1
                stats['rejected_files'].append((img_path.name, flood_score, reject_score))

            # Progress logging
            if (i + 1) % 50 == 0:
                logger.info(f"Processed {i + 1}/{len(images)} - Kept: {stats['kept']}")

        logger.info(f"Filtering complete: {stats['kept']}/{stats['total']} images kept")
        return stats


def main():
    parser = argparse.ArgumentParser(description='Filter images using CLIP')
    parser.add_argument('--input', required=True, help='Input directory')
    parser.add_argument('--output', required=True, help='Output directory')
    parser.add_argument('--threshold', type=float, default=0.05,
                        help='Margin threshold (flood - reject score)')
    parser.add_argument('--min-score', type=float, default=0.20,
                        help='Minimum flood score')
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        raise ValueError(f"Input directory not found: {input_dir}")

    # Initialize filter
    clip_filter = CLIPFilter()

    # Run filter
    stats = clip_filter.filter_directory(
        input_dir=input_dir,
        output_dir=output_dir,
        threshold=args.threshold,
        min_flood_score=args.min_score
    )

    # Print summary
    print("\n" + "=" * 60)
    print("CLIP FILTER RESULTS")
    print("=" * 60)
    print(f"Total images: {stats['total']}")
    print(f"Kept (road floods): {stats['kept']} ({stats['kept']/stats['total']*100:.1f}%)")
    print(f"Rejected: {stats['rejected']}")
    print(f"\nFiltered images saved to: {output_dir}")

    # Show sample rejections
    if stats['rejected_files']:
        print("\nSample rejected images (name, flood_score, reject_score):")
        for name, f_score, r_score in stats['rejected_files'][:5]:
            print(f"  {name}: flood={f_score:.3f}, reject={r_score:.3f}")


if __name__ == '__main__':
    main()
