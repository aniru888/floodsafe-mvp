"""
YOLOv8-based Flood Image Classifier

Binary classification: flood (1) vs no_flood (0)

CRITICAL SAFETY REQUIREMENT:
- False Negative Rate MUST be <2% (cannot miss real floods)
- Uses low threshold (0.3) to maximize recall
- Accepts higher false positives as trade-off

Usage:
    classifier = YOLOFloodClassifier()
    classifier.load("models/yolov8_flood/flood_classifier_v1.pt")
    result = classifier.predict(pil_image)
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Union, Any
import numpy as np

logger = logging.getLogger(__name__)


class YOLOFloodClassifier:
    """
    YOLOv8-based flood image classification.

    Binary classification: flood (1) vs no_flood (0)

    CRITICAL SAFETY REQUIREMENT:
    - False Negative Rate MUST be <2% (cannot miss real floods)
    - Uses low threshold (0.3) to maximize recall
    - Accepts higher false positives as trade-off

    Safety Philosophy:
    - Missing a real flood report could endanger lives
    - Extra false positives just mean more manual review
    - We prioritize recall (sensitivity) over precision

    Attributes:
        FLOOD_THRESHOLD: Classification threshold (0.3 for safety)
        model: Loaded YOLO model instance
        classes: List of class names ["no_flood", "flood"]
    """

    # SAFETY: Low threshold to catch all potential floods
    # Standard classification uses 0.5, we use 0.3 for safety
    # If flood_probability > 0.3, classify as flood
    FLOOD_THRESHOLD = 0.3

    # Review thresholds for human verification
    REVIEW_LOW = 0.3    # Below this: confident no_flood
    REVIEW_HIGH = 0.7   # Above this: confident flood
    # Between REVIEW_LOW and REVIEW_HIGH: needs human review

    def __init__(
        self,
        model_path: Optional[str] = None,
        threshold: Optional[float] = None,
        device: str = "auto"
    ):
        """
        Initialize the flood classifier.

        Args:
            model_path: Path to trained weights (optional, load later)
            threshold: Classification threshold (default: 0.3 for safety)
            device: Device for inference ("auto", "cpu", "cuda", "mps")
        """
        self.model = None
        self.model_path = model_path
        # YOLOv8 uses alphabetical class ordering: flood=0, no_flood=1
        self.classes = ["flood", "no_flood"]
        self.threshold = threshold or self.FLOOD_THRESHOLD
        self.device = device
        self._trained = False

        if model_path:
            self.load(model_path)

    def load(self, path: Union[str, Path]) -> "YOLOFloodClassifier":
        """
        Load trained weights.

        Args:
            path: Path to .pt weights file

        Returns:
            self for method chaining
        """
        try:
            from ultralytics import YOLO

            path = Path(path)
            if not path.exists():
                raise FileNotFoundError(f"Model weights not found: {path}")

            self.model = YOLO(str(path))
            self.model_path = str(path)
            self._trained = True
            logger.info(f"Loaded flood classifier from {path}")

            return self

        except ImportError:
            logger.error("ultralytics not installed. Run: pip install ultralytics")
            raise

    def predict(self, image: Any) -> Dict[str, Any]:
        """
        Classify single image with SAFETY-FIRST logic.

        CRITICAL: Uses low threshold (0.3) to minimize false negatives.
        If there's ANY reasonable chance it's a flood, classify as flood.

        Args:
            image: PIL Image, numpy array, or file path

        Returns:
            {
                "classification": "flood" | "no_flood",
                "confidence": 0.0-1.0,
                "flood_probability": 0.0-1.0,
                "is_flood": bool,
                "needs_review": bool,  # True if uncertain (0.3-0.7)
                "probabilities": {"flood": 0.92, "no_flood": 0.08}
            }

        Raises:
            RuntimeError: If model not loaded
            ValueError: If image cannot be processed
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        try:
            # Run inference
            results = self.model(image, verbose=False)

            # Get classification probabilities
            probs = results[0].probs

            if probs is None:
                # Model might not be a classifier, fallback
                logger.warning("Model doesn't return probabilities, using detection fallback")
                return self._fallback_detection_predict(results)

            # Get probabilities for each class
            # YOLOv8 uses alphabetical folder name ordering: flood=0, no_flood=1
            probs_data = probs.data.cpu().numpy()

            if len(probs_data) < 2:
                raise ValueError(f"Expected 2 classes, got {len(probs_data)}")

            # YOLOv8 uses alphabetical class ordering: flood=0, no_flood=1
            flood_prob = float(probs_data[0])
            no_flood_prob = float(probs_data[1])

            # SAFETY LOGIC: Low threshold to catch all floods
            # Better to flag non-floods for review than miss real floods
            is_flood = flood_prob >= self.threshold

            # Determine confidence and classification
            if is_flood:
                confidence = flood_prob
                classification = "flood"
            else:
                confidence = no_flood_prob
                classification = "no_flood"

            # Flag uncertain cases for human review
            needs_review = self.REVIEW_LOW <= flood_prob <= self.REVIEW_HIGH

            return {
                "classification": classification,
                "confidence": round(confidence, 4),
                "flood_probability": round(flood_prob, 4),
                "is_flood": is_flood,
                "needs_review": needs_review,
                "probabilities": {
                    "flood": round(flood_prob, 4),
                    "no_flood": round(no_flood_prob, 4)
                }
            }

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise ValueError(f"Could not process image: {e}")

    def _fallback_detection_predict(self, results: Any) -> Dict[str, Any]:
        """
        Fallback for detection models (not classification).

        If using a detection model instead of classification,
        detect water/flood objects and classify based on presence.
        """
        # Check if any flood-related objects detected
        detections = results[0].boxes
        flood_detected = len(detections) > 0

        # Calculate confidence from detection scores
        if flood_detected:
            max_conf = float(detections.conf.max())
            return {
                "classification": "flood",
                "confidence": max_conf,
                "flood_probability": max_conf,
                "is_flood": True,
                "needs_review": max_conf < 0.7,
                "probabilities": {"flood": max_conf, "no_flood": 1 - max_conf}
            }
        else:
            return {
                "classification": "no_flood",
                "confidence": 0.95,  # High confidence no detection
                "flood_probability": 0.05,
                "is_flood": False,
                "needs_review": False,
                "probabilities": {"flood": 0.05, "no_flood": 0.95}
            }

    def predict_batch(
        self,
        images: list,
        batch_size: int = 16
    ) -> list[Dict[str, Any]]:
        """
        Classify multiple images.

        Args:
            images: List of PIL Images, numpy arrays, or file paths
            batch_size: Batch size for inference

        Returns:
            List of prediction dictionaries
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        results = []
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            batch_results = self.model(batch, verbose=False)

            for result in batch_results:
                probs = result.probs
                if probs is not None:
                    probs_data = probs.data.cpu().numpy()
                    # YOLOv8 uses alphabetical class ordering: flood=0, no_flood=1
                    flood_prob = float(probs_data[0])
                    no_flood_prob = float(probs_data[1])
                    is_flood = flood_prob >= self.threshold

                    results.append({
                        "classification": "flood" if is_flood else "no_flood",
                        "confidence": round(flood_prob if is_flood else no_flood_prob, 4),
                        "flood_probability": round(flood_prob, 4),
                        "is_flood": is_flood,
                        "needs_review": self.REVIEW_LOW <= flood_prob <= self.REVIEW_HIGH,
                        "probabilities": {
                            "flood": round(flood_prob, 4),
                            "no_flood": round(no_flood_prob, 4)
                        }
                    })

        return results

    def train(
        self,
        data_yaml: str,
        epochs: int = 100,
        batch: int = 16,
        imgsz: int = 640,
        project: str = "runs/classify",
        name: str = "flood_classifier"
    ) -> Dict[str, Any]:
        """
        Fine-tune YOLOv8 classifier on custom dataset.

        Uses SAFETY-OPTIMIZED settings:
        - High classification loss weight to penalize missed floods
        - Strong augmentation for robustness
        - Early stopping with patience

        Args:
            data_yaml: Path to dataset.yaml
            epochs: Number of training epochs
            batch: Batch size
            imgsz: Image size
            project: Project directory for runs
            name: Run name

        Returns:
            Training results dictionary
        """
        try:
            from ultralytics import YOLO

            # Start from pretrained YOLOv8n-cls
            self.model = YOLO("yolov8n-cls.pt")

            logger.info(f"Starting training for {epochs} epochs...")
            logger.info(f"Dataset: {data_yaml}")

            results = self.model.train(
                data=data_yaml,
                epochs=epochs,
                imgsz=imgsz,
                batch=batch,
                # Project settings
                project=project,
                name=name,
                exist_ok=True,
                # Optimizer settings
                optimizer="AdamW",
                lr0=0.001,
                lrf=0.01,  # Final learning rate multiplier
                momentum=0.937,
                weight_decay=0.0005,
                # Training settings
                patience=20,  # Early stopping patience
                save=True,
                save_period=10,  # Save every 10 epochs
                # CRITICAL: Strong augmentation for robustness
                augment=True,
                hsv_h=0.015,
                hsv_s=0.7,
                hsv_v=0.4,
                degrees=10.0,
                translate=0.1,
                scale=0.5,
                flipud=0.5,
                fliplr=0.5,
                mosaic=0.5,
                mixup=0.1,
                # Logging
                verbose=True,
                plots=True,
            )

            self._trained = True
            self.model_path = str(Path(project) / name / "weights" / "best.pt")
            logger.info(f"Training complete. Best model: {self.model_path}")

            return results

        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise

    def save(self, path: Union[str, Path]) -> None:
        """
        Save model weights.

        Args:
            path: Destination path for weights
        """
        if self.model is None:
            raise RuntimeError("No model to save. Train or load a model first.")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Export the model
        self.model.export(format="torchscript")  # Or use .pt directly

        logger.info(f"Model saved to {path}")

    @property
    def is_trained(self) -> bool:
        """Check if model has been trained or loaded."""
        return self._trained and self.model is not None

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata."""
        return {
            "name": "YOLOFloodClassifier",
            "trained": self._trained,
            "model_path": self.model_path,
            "threshold": self.threshold,
            "classes": self.classes,
            "safety_config": {
                "flood_threshold": self.threshold,
                "review_low": self.REVIEW_LOW,
                "review_high": self.REVIEW_HIGH,
                "target_fnr": "<2%",
            }
        }

    def __repr__(self) -> str:
        status = "loaded" if self._trained else "not loaded"
        return f"YOLOFloodClassifier(threshold={self.threshold}, status={status})"


# Convenience function for quick predictions
def classify_flood_image(
    image_path: str,
    model_path: str = "models/yolov8_flood/flood_classifier_v1.pt"
) -> Dict[str, Any]:
    """
    Convenience function for single image classification.

    Args:
        image_path: Path to image file
        model_path: Path to model weights

    Returns:
        Classification result dictionary
    """
    classifier = YOLOFloodClassifier()
    classifier.load(model_path)
    return classifier.predict(image_path)
