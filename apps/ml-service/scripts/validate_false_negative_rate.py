"""
CRITICAL SAFETY VALIDATION SCRIPT

This script MUST pass before deploying the flood classifier model.
Validates that False Negative Rate is <2% (cannot miss real floods).

SAFETY PHILOSOPHY:
- Missing a real flood report could endanger lives
- False positives (flagging non-floods) = extra manual review = acceptable
- False negatives (missing floods) = danger to public = UNACCEPTABLE

REQUIREMENTS:
- False Negative Rate < 2% (>98% recall)
- Model threshold must be <= 0.3 for safety

Usage:
    python -m apps.ml-service.scripts.validate_false_negative_rate
    python -m apps.ml-service.scripts.validate_false_negative_rate --model path/to/model.pt
    python -m apps.ml-service.scripts.validate_false_negative_rate --test-dir path/to/test/flood/
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Base paths
SCRIPT_DIR = Path(__file__).parent
ML_SERVICE_DIR = SCRIPT_DIR.parent
DATA_DIR = ML_SERVICE_DIR / "data"
MODELS_DIR = ML_SERVICE_DIR / "models"
FLOOD_IMAGES_DIR = DATA_DIR / "flood_images"

# Safety thresholds
MAX_FALSE_NEGATIVE_RATE = 0.02  # 2% - CRITICAL requirement
MIN_RECALL = 0.98  # 98% - must detect this many floods
MAX_CLASSIFICATION_THRESHOLD = 0.3  # Safety threshold


def validate_model(
    model_path: str,
    test_flood_dir: str,
    threshold: float = MAX_CLASSIFICATION_THRESHOLD
) -> Dict[str, Any]:
    """
    Test model against known flood images.

    REQUIREMENT: <2% false negative rate (>98% recall)

    Args:
        model_path: Path to trained model weights
        test_flood_dir: Directory containing known flood images
        threshold: Classification threshold (default: 0.3)

    Returns:
        Validation results dictionary
    """
    try:
        from PIL import Image
        from ..src.models.yolo_flood_classifier import YOLOFloodClassifier
    except ImportError:
        # Try alternative import for direct script execution
        try:
            sys.path.insert(0, str(ML_SERVICE_DIR))
            from src.models.yolo_flood_classifier import YOLOFloodClassifier
            from PIL import Image
        except ImportError as e:
            logger.error(f"Import error: {e}")
            logger.error("Make sure ultralytics and PIL are installed")
            return {"passed": False, "error": str(e)}

    # Load model
    model_path = Path(model_path)
    if not model_path.exists():
        logger.error(f"Model not found: {model_path}")
        return {"passed": False, "error": "Model not found"}

    logger.info(f"Loading model from {model_path}")
    classifier = YOLOFloodClassifier(threshold=threshold)
    classifier.load(str(model_path))

    # Validate threshold
    if classifier.threshold > MAX_CLASSIFICATION_THRESHOLD:
        logger.warning(f"Model threshold ({classifier.threshold}) > safety threshold ({MAX_CLASSIFICATION_THRESHOLD})")
        logger.warning("Setting threshold to 0.3 for safety validation")
        classifier.threshold = MAX_CLASSIFICATION_THRESHOLD

    # Find test images
    test_dir = Path(test_flood_dir)
    if not test_dir.exists():
        logger.error(f"Test directory not found: {test_dir}")
        return {"passed": False, "error": "Test directory not found"}

    flood_images = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        flood_images.extend(list(test_dir.glob(ext)))

    if not flood_images:
        logger.error(f"No flood images found in {test_dir}")
        return {"passed": False, "error": "No test images found"}

    logger.info(f"Testing {len(flood_images)} flood images...")

    # Test each image
    total_floods = len(flood_images)
    detected_floods = 0
    missed_floods = 0
    needs_review_count = 0
    results: List[Dict[str, Any]] = []

    for img_path in flood_images:
        try:
            image = Image.open(img_path)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")

            result = classifier.predict(image)

            if result["is_flood"]:
                detected_floods += 1
                results.append({
                    "file": img_path.name,
                    "detected": True,
                    "flood_probability": result["flood_probability"],
                    "confidence": result["confidence"]
                })
            else:
                missed_floods += 1
                results.append({
                    "file": img_path.name,
                    "detected": False,
                    "flood_probability": result["flood_probability"],
                    "confidence": result["confidence"]
                })
                logger.warning(f"MISSED FLOOD: {img_path.name} (prob: {result['flood_probability']:.3f})")

            if result["needs_review"]:
                needs_review_count += 1

        except Exception as e:
            logger.error(f"Error processing {img_path.name}: {e}")
            missed_floods += 1
            results.append({
                "file": img_path.name,
                "detected": False,
                "error": str(e)
            })

    # Calculate metrics
    false_negative_rate = missed_floods / total_floods if total_floods > 0 else 1.0
    recall = detected_floods / total_floods if total_floods > 0 else 0.0

    # Create summary
    validation_result = {
        "timestamp": datetime.now().isoformat(),
        "model_path": str(model_path),
        "threshold": classifier.threshold,
        "test_directory": str(test_dir),
        "metrics": {
            "total_flood_images": total_floods,
            "floods_detected": detected_floods,
            "floods_missed": missed_floods,
            "false_negative_rate": round(false_negative_rate, 4),
            "recall": round(recall, 4),
            "needs_review_count": needs_review_count,
        },
        "safety_thresholds": {
            "max_false_negative_rate": MAX_FALSE_NEGATIVE_RATE,
            "min_recall": MIN_RECALL,
            "max_classification_threshold": MAX_CLASSIFICATION_THRESHOLD,
        },
        "passed": false_negative_rate < MAX_FALSE_NEGATIVE_RATE,
        "missed_images": [r for r in results if not r.get("detected", True)],
    }

    return validation_result


def print_results(validation_result: Dict[str, Any]) -> None:
    """Print validation results in a formatted way."""
    metrics = validation_result.get("metrics", {})
    passed = validation_result.get("passed", False)

    print("\n" + "="*60)
    print("SAFETY VALIDATION RESULTS")
    print("="*60)
    print(f"Model: {validation_result.get('model_path', 'Unknown')}")
    print(f"Threshold: {validation_result.get('threshold', 0.3)}")
    print(f"Test Images: {metrics.get('total_flood_images', 0)}")
    print("-"*60)
    print(f"Floods Correctly Identified: {metrics.get('floods_detected', 0)}")
    print(f"Floods MISSED: {metrics.get('floods_missed', 0)}")
    print(f"Needs Review: {metrics.get('needs_review_count', 0)}")
    print("-"*60)
    print(f"FALSE NEGATIVE RATE: {metrics.get('false_negative_rate', 1.0)*100:.2f}%")
    print(f"Target: <{MAX_FALSE_NEGATIVE_RATE*100:.0f}%")
    print(f"RECALL: {metrics.get('recall', 0)*100:.2f}%")
    print(f"Target: >{MIN_RECALL*100:.0f}%")
    print("="*60)

    if passed:
        print(f"\n{'='*60}")
        print(f" PASSED: False Negative Rate < {MAX_FALSE_NEGATIVE_RATE*100:.0f}%")
        print(f" MODEL IS SAFE TO DEPLOY")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'='*60}")
        print(f" FAILED: False Negative Rate >= {MAX_FALSE_NEGATIVE_RATE*100:.0f}%")
        print(f" DO NOT DEPLOY THIS MODEL")
        print(f"{'='*60}")

        # Show missed images
        missed = validation_result.get("missed_images", [])
        if missed:
            print("\nMISSED FLOOD IMAGES:")
            for m in missed[:10]:  # Show first 10
                prob = m.get("flood_probability", 0)
                print(f"  - {m['file']} (prob: {prob:.3f})")

            if len(missed) > 10:
                print(f"  ... and {len(missed) - 10} more")

            # Suggest threshold adjustment
            missed_probs = [m.get("flood_probability", 0) for m in missed]
            if missed_probs:
                max_missed_prob = max(missed_probs)
                suggested_threshold = max(0.1, max_missed_prob - 0.05)
                print(f"\nSUGGESTION: Lower threshold to {suggested_threshold:.2f}")

        print()


def main():
    parser = argparse.ArgumentParser(
        description="Validate flood classifier for safety requirements"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=str(MODELS_DIR / "yolov8_flood" / "flood_classifier_v1.pt"),
        help="Path to trained model weights"
    )
    parser.add_argument(
        "--test-dir",
        type=str,
        default=str(FLOOD_IMAGES_DIR / "test" / "flood"),
        help="Directory containing test flood images"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=MAX_CLASSIFICATION_THRESHOLD,
        help=f"Classification threshold (default: {MAX_CLASSIFICATION_THRESHOLD})"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file for results"
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("FLOOD CLASSIFIER SAFETY VALIDATION")
    print("="*60)
    print(f"Model: {args.model}")
    print(f"Test Directory: {args.test_dir}")
    print(f"Threshold: {args.threshold}")
    print(f"\nSAFETY REQUIREMENT: <{MAX_FALSE_NEGATIVE_RATE*100:.0f}% False Negative Rate")
    print("="*60 + "\n")

    # Run validation
    result = validate_model(
        model_path=args.model,
        test_flood_dir=args.test_dir,
        threshold=args.threshold
    )

    # Print results
    print_results(result)

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Results saved to {output_path}")

    # Return exit code based on pass/fail
    if result.get("passed"):
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
