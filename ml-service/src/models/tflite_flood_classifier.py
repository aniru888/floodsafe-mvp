"""
TensorFlow Lite-based Flood Image Classifier

Ultra-lightweight flood classifier using TFLite Runtime (~3MB model).
No executable stack requirements - works on all platforms including Koyeb.

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


class TFLiteFloodClassifier:
    """
    TFLite-based flood image classification.

    Binary classification: flood vs no_flood
    Uses TFLite Runtime for ultra-lightweight inference (~3MB).

    CRITICAL SAFETY REQUIREMENT:
    - False Negative Rate MUST be <2% (cannot miss real floods)
    - Uses low threshold (0.3) to maximize recall

    Attributes:
        FLOOD_THRESHOLD: Classification threshold (0.3 for safety)
        REVIEW_LOW: Lower bound of uncertainty range (0.3)
        REVIEW_HIGH: Upper bound of uncertainty range (0.7)
        interpreter: TFLite interpreter instance
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
        Initialize the TFLite flood classifier.

        Args:
            model_path: Path to TFLite model file (optional, load later)
            threshold: Classification threshold (default: 0.3 for safety)
        """
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.model_path = model_path
        self.classes = ["flood", "no_flood"]
        self.threshold = threshold or self.FLOOD_THRESHOLD
        self._loaded = False

        if model_path:
            self.load(model_path)

    def load(self, path: Union[str, Path]) -> "TFLiteFloodClassifier":
        """
        Load TFLite model.

        Args:
            path: Path to .tflite model file

        Returns:
            self for method chaining

        Raises:
            FileNotFoundError: If model file doesn't exist
            RuntimeError: If TFLite fails to load model
        """
        try:
            # Try tflite_runtime first (lighter), fall back to tensorflow
            runtime_type = None
            try:
                from tflite_runtime.interpreter import Interpreter
                runtime_type = "tflite_runtime"
            except ImportError:
                from tensorflow.lite.python.interpreter import Interpreter
                runtime_type = "tensorflow.lite"

            path = Path(path)
            if not path.exists():
                raise FileNotFoundError(f"TFLite model not found: {path}")

            # Log file info for debugging
            file_size = path.stat().st_size
            logger.info(f"Loading TFLite model from {path}...")
            logger.info(f"  Runtime: {runtime_type}")
            logger.info(f"  File size: {file_size / 1024 / 1024:.2f} MB")

            # Check FlatBuffer magic bytes
            with open(path, 'rb') as f:
                header = f.read(8)
                magic = header[4:8]
                if magic != b'TFL3':
                    raise RuntimeError(
                        f"Invalid TFLite file: expected TFL3 magic bytes, got {magic!r}. "
                        "Model may be corrupted or wrong format."
                    )
                logger.info(f"  Magic bytes: TFL3 (valid)")

            # Create interpreter
            self.interpreter = Interpreter(model_path=str(path))
            self.interpreter.allocate_tensors()

            # Get input/output details
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            self.model_path = str(path)
            self._loaded = True

            logger.info(f"TFLite flood classifier loaded successfully")
            logger.info(f"  Input shape: {self.input_details[0]['shape']}")
            logger.info(f"  Output shape: {self.output_details[0]['shape']}")

            return self

        except ImportError as e:
            logger.error(f"TFLite Runtime import failed: {e}")
            logger.error("Install with: pip install tflite-runtime==2.14.0")
            raise
        except FileNotFoundError:
            raise
        except Exception as e:
            # Log full traceback for debugging
            import traceback
            logger.error(f"Failed to load TFLite model: {type(e).__name__}: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            raise RuntimeError(f"Could not load TFLite model: {e}")

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
        if self.interpreter is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        try:
            # Preprocess image
            preprocessed = self._preprocess(image)

            # Run TFLite inference
            self.interpreter.set_tensor(self.input_details[0]['index'], preprocessed)
            self.interpreter.invoke()
            probs = self.interpreter.get_tensor(self.output_details[0]['index'])[0]

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
            batch_size: Batch size for inference (TFLite processes one at a time)

        Returns:
            List of prediction dictionaries
        """
        if self.interpreter is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        # TFLite processes one image at a time
        return [self.predict(img) for img in images]

    @property
    def is_loaded(self) -> bool:
        """Check if model has been loaded."""
        return self._loaded and self.interpreter is not None

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata."""
        return {
            "name": "TFLiteFloodClassifier",
            "architecture": "MobileNetV1 (TFLite)",
            "source": "Sohail Ahmed Khan (converted to TFLite)",
            "loaded": self._loaded,
            "model_path": self.model_path,
            "threshold": self.threshold,
            "classes": self.classes,
            "input_size": (224, 224, 3),
            "runtime": "tflite-runtime",
            "safety_config": {
                "flood_threshold": self.threshold,
                "review_low": self.REVIEW_LOW,
                "review_high": self.REVIEW_HIGH,
                "target_fnr": "<2%",
            }
        }

    def __repr__(self) -> str:
        status = "loaded" if self._loaded else "not loaded"
        return f"TFLiteFloodClassifier(threshold={self.threshold}, status={status})"


# Singleton instance for API use
_classifier_instance: Optional[TFLiteFloodClassifier] = None


def get_classifier() -> TFLiteFloodClassifier:
    """
    Get or create singleton classifier instance.

    CRITICAL: Only caches AFTER successful load to prevent
    returning broken instances from failed load attempts.

    Returns:
        Loaded TFLiteFloodClassifier instance

    Raises:
        RuntimeError: If model file not found or load fails
    """
    global _classifier_instance

    # Check if already loaded AND working (is_loaded checks interpreter != None)
    if _classifier_instance is not None and _classifier_instance.is_loaded:
        return _classifier_instance

    # Reset to None to force re-attempt if previous load failed
    _classifier_instance = None

    model_path = Path(__file__).parent.parent.parent / "models" / "flood_classifier.tflite"

    if not model_path.exists():
        raise RuntimeError(
            f"TFLite model not found at {model_path}. "
            "Run: python scripts/convert_tf214.py in TF 2.14 environment"
        )

    # Create and load in local variable first - only cache after SUCCESS
    classifier = TFLiteFloodClassifier()
    classifier.load(model_path)  # Must succeed before caching

    # Only cache after successful load
    _classifier_instance = classifier

    return _classifier_instance


# Convenience function for quick predictions
def classify_flood_image(
    image_path: str,
    model_path: str = "models/flood_classifier.tflite"
) -> Dict[str, Any]:
    """
    Convenience function for single image classification.

    Args:
        image_path: Path to image file
        model_path: Path to TFLite model

    Returns:
        Classification result dictionary
    """
    classifier = TFLiteFloodClassifier()
    classifier.load(model_path)
    return classifier.predict(image_path)
