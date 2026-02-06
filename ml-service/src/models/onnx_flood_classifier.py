"""
ONNX-based Flood Image Classifier

Lightweight flood classifier using ONNX Runtime instead of TensorFlow.
Provides the same interface as MobileNetFloodClassifier but with 90% smaller
deployment footprint (~50MB vs 500MB).

CRITICAL SAFETY REQUIREMENT:
- False Negative Rate MUST be <2% (cannot miss real floods)
- Uses low threshold (0.3) to maximize recall
- Accepts higher false positives as trade-off

Model: MobileNetV1 converted from Sohail Ahmed Khan's pretrained weights
Source: https://github.com/sohailahmedkhan/Flood-Detection-from-Images-using-Deep-Learning
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Union, Any, List
import numpy as np

logger = logging.getLogger(__name__)


class ONNXFloodClassifier:
    """
    ONNX-based flood image classification.

    Binary classification: flood vs no_flood
    Uses ONNX Runtime for lightweight inference (~50MB vs 500MB TensorFlow).

    CRITICAL SAFETY REQUIREMENT:
    - False Negative Rate MUST be <2% (cannot miss real floods)
    - Uses low threshold (0.3) to maximize recall

    Attributes:
        FLOOD_THRESHOLD: Classification threshold (0.3 for safety)
        REVIEW_LOW: Lower bound of uncertainty range (0.3)
        REVIEW_HIGH: Upper bound of uncertainty range (0.7)
        session: ONNX Runtime inference session
        classes: List of class names ["flood", "no_flood"]
    """

    # SAFETY: Low threshold to catch all potential floods
    FLOOD_THRESHOLD = 0.3

    # Review thresholds for human verification
    REVIEW_LOW = 0.3    # Below this: confident no_flood
    REVIEW_HIGH = 0.7   # Above this: confident flood

    def __init__(
        self,
        model_path: Optional[str] = None,
        threshold: Optional[float] = None,
    ):
        """
        Initialize the ONNX flood classifier.

        Args:
            model_path: Path to ONNX model file (optional, load later)
            threshold: Classification threshold (default: 0.3 for safety)
        """
        self.session = None
        self.input_name = None
        self.model_path = model_path
        self.classes = ["flood", "no_flood"]
        self.threshold = threshold or self.FLOOD_THRESHOLD
        self._loaded = False

        if model_path:
            self.load(model_path)

    def load(self, path: Union[str, Path]) -> "ONNXFloodClassifier":
        """
        Load ONNX model.

        Args:
            path: Path to .onnx model file

        Returns:
            self for method chaining

        Raises:
            FileNotFoundError: If model file doesn't exist
            RuntimeError: If ONNX Runtime fails to load model
        """
        try:
            import onnxruntime as ort

            path = Path(path)
            if not path.exists():
                raise FileNotFoundError(f"ONNX model not found: {path}")

            logger.info(f"Loading ONNX model from {path}...")

            # Create inference session
            self.session = ort.InferenceSession(
                str(path),
                providers=['CPUExecutionProvider']  # CPU only for compatibility
            )

            # Get input name for inference
            self.input_name = self.session.get_inputs()[0].name
            self.model_path = str(path)
            self._loaded = True

            logger.info(f"ONNX flood classifier loaded successfully")
            logger.info(f"  Input name: {self.input_name}")
            logger.info(f"  Input shape: {self.session.get_inputs()[0].shape}")

            return self

        except ImportError:
            logger.error("ONNX Runtime not installed. Run: pip install onnxruntime")
            raise
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            raise RuntimeError(f"Could not load ONNX model: {e}")

    def _preprocess(self, image: Any) -> np.ndarray:
        """
        Preprocess image for MobileNet input.

        Args:
            image: PIL Image, numpy array, or file path

        Returns:
            Preprocessed numpy array with shape (1, 224, 224, 3)
        """
        from PIL import Image

        # Convert to PIL Image if needed
        if isinstance(image, np.ndarray):
            pil_image = Image.fromarray(image.astype('uint8'))
        elif isinstance(image, (str, Path)):
            pil_image = Image.open(image)
        elif isinstance(image, Image.Image):
            pil_image = image
        elif hasattr(image, 'read'):
            # File-like object (UploadFile)
            pil_image = Image.open(image)
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

        # Resize to MobileNet input size
        pil_image = pil_image.convert('RGB').resize((224, 224), Image.BILINEAR)

        # MobileNet preprocessing: scale to [-1, 1]
        arr = np.array(pil_image, dtype=np.float32)
        arr = (arr / 127.5) - 1.0

        return np.expand_dims(arr, axis=0)

    def predict(self, image: Any) -> Dict[str, Any]:
        """
        Classify single image with SAFETY-FIRST logic.

        CRITICAL: Uses low threshold (0.3) to minimize false negatives.
        If there's ANY reasonable chance it's a flood, classify as flood.

        Args:
            image: PIL Image, numpy array, file path, or file-like object

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
        if self.session is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        try:
            # Preprocess image
            preprocessed = self._preprocess(image)

            # Run ONNX inference
            outputs = self.session.run(None, {self.input_name: preprocessed})
            probs = outputs[0][0]  # Shape: (2,)

            # Sohail's model: [flood_prob, no_flood_prob]
            flood_prob = float(probs[0])
            no_flood_prob = float(probs[1])

            # SAFETY LOGIC: Low threshold to catch all floods
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

    def predict_batch(
        self,
        images: List[Any],
        batch_size: int = 16
    ) -> List[Dict[str, Any]]:
        """
        Classify multiple images.

        Args:
            images: List of PIL Images, numpy arrays, or file paths
            batch_size: Batch size for inference

        Returns:
            List of prediction dictionaries
        """
        if self.session is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        results = []

        for i in range(0, len(images), batch_size):
            batch_images = images[i:i + batch_size]

            # Preprocess batch
            batch_preprocessed = np.vstack([
                self._preprocess(img) for img in batch_images
            ])

            # Run ONNX inference
            outputs = self.session.run(None, {self.input_name: batch_preprocessed})
            batch_probs = outputs[0]

            for probs in batch_probs:
                flood_prob = float(probs[0])
                no_flood_prob = float(probs[1])
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

    @property
    def is_loaded(self) -> bool:
        """Check if model has been loaded."""
        return self._loaded and self.session is not None

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata."""
        return {
            "name": "ONNXFloodClassifier",
            "architecture": "MobileNetV1 (ONNX)",
            "source": "Sohail Ahmed Khan (converted to ONNX)",
            "loaded": self._loaded,
            "model_path": self.model_path,
            "threshold": self.threshold,
            "classes": self.classes,
            "input_size": (224, 224, 3),
            "runtime": "onnxruntime",
            "safety_config": {
                "flood_threshold": self.threshold,
                "review_low": self.REVIEW_LOW,
                "review_high": self.REVIEW_HIGH,
                "target_fnr": "<2%",
            }
        }

    def __repr__(self) -> str:
        status = "loaded" if self._loaded else "not loaded"
        return f"ONNXFloodClassifier(threshold={self.threshold}, status={status})"


# Singleton instance for API use
_classifier_instance: Optional[ONNXFloodClassifier] = None


def get_classifier() -> ONNXFloodClassifier:
    """
    Get or create singleton classifier instance.

    Returns:
        Loaded ONNXFloodClassifier instance

    Raises:
        RuntimeError: If model file not found
    """
    global _classifier_instance

    if _classifier_instance is None:
        model_path = Path(__file__).parent.parent.parent / "models" / "flood_classifier.onnx"

        if not model_path.exists():
            raise RuntimeError(
                f"ONNX model not found at {model_path}. "
                "Run: python scripts/convert_to_onnx.py"
            )

        _classifier_instance = ONNXFloodClassifier()
        _classifier_instance.load(model_path)

    return _classifier_instance


# Convenience function for quick predictions
def classify_flood_image(
    image_path: str,
    model_path: str = "models/flood_classifier.onnx"
) -> Dict[str, Any]:
    """
    Convenience function for single image classification.

    Args:
        image_path: Path to image file
        model_path: Path to ONNX model

    Returns:
        Classification result dictionary
    """
    classifier = ONNXFloodClassifier()
    classifier.load(model_path)
    return classifier.predict(image_path)
