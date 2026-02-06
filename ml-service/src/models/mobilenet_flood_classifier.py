"""
MobileNet-based Flood Image Classifier

Uses Sohail Ahmed Khan's pretrained MobileNetV1 model for binary flood classification.
Replaces YOLOv8 classifier with a model that achieved 100% accuracy on Indian flood images.

CRITICAL SAFETY REQUIREMENT:
- False Negative Rate MUST be <2% (cannot miss real floods)
- Uses low threshold (0.3) to maximize recall
- Accepts higher false positives as trade-off

Model Source: https://github.com/sohailahmedkhan/Flood-Detection-from-Images-using-Deep-Learning
Tested: 2025-12-27 - 100% accuracy on 20 Indian test images
"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional, Union, Any, List
import numpy as np

logger = logging.getLogger(__name__)


class MobileNetFloodClassifier:
    """
    MobileNet-based flood image classification.

    Binary classification: flood vs no_flood
    Uses Sohail Ahmed Khan's pretrained weights with custom H5 loader
    for Keras 3.x compatibility.

    CRITICAL SAFETY REQUIREMENT:
    - False Negative Rate MUST be <2% (cannot miss real floods)
    - Uses low threshold (0.3) to maximize recall

    Attributes:
        FLOOD_THRESHOLD: Classification threshold (0.3 for safety)
        REVIEW_LOW: Lower bound of uncertainty range (0.3)
        REVIEW_HIGH: Upper bound of uncertainty range (0.7)
        model: Loaded Keras model instance
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
        device: str = "auto"  # Ignored for TF, kept for API compatibility
    ):
        """
        Initialize the flood classifier.

        Args:
            model_path: Path to trained weights (optional, load later)
            threshold: Classification threshold (default: 0.3 for safety)
            device: Ignored (TensorFlow handles device automatically)
        """
        self.model = None
        self.model_path = model_path
        # Sohail's model: [flood, no_flood] order
        self.classes = ["flood", "no_flood"]
        self.threshold = threshold or self.FLOOD_THRESHOLD
        self._trained = False

        # Suppress TensorFlow warnings
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

        if model_path:
            self.load(model_path)

    def _build_model(self):
        """Build MobileNet architecture matching Sohail's model."""
        import tensorflow as tf
        from tensorflow.keras.applications import MobileNet
        from tensorflow.keras import layers, Model

        # Suppress TF warnings
        tf.get_logger().setLevel('ERROR')

        # Create MobileNet base (same as Sohail's architecture)
        base = MobileNet(
            input_shape=(224, 224, 3),
            include_top=False,
            weights=None,  # Don't load ImageNet weights
            pooling='avg'  # Global average pooling
        )

        # Add classification head (2 classes: flood, no_flood)
        x = base.output
        output = layers.Dense(2, activation='softmax', name='dense')(x)
        model = Model(inputs=base.input, outputs=output)

        return model

    def _load_weights_from_h5(self, model, h5_path: Path) -> int:
        """
        Load weights from Sohail's H5 file into fresh MobileNet.

        Keras 3.x has serialization incompatibility with older H5 files,
        so we load weights manually layer by layer.

        Args:
            model: Keras model to load weights into
            h5_path: Path to H5 weights file

        Returns:
            Number of layers with weights loaded
        """
        import h5py

        loaded_count = 0
        with h5py.File(h5_path, 'r') as f:
            weights_group = f['model_weights']
            h5_layer_names = set(weights_group.keys())

            for layer in model.layers:
                # Skip layers without weights
                if not layer.weights:
                    continue

                # Check if layer exists in H5 file
                if layer.name not in h5_layer_names:
                    continue

                try:
                    layer_weights = weights_group[layer.name][layer.name]
                    weight_list = []

                    # Get weight names and sort by Keras expected order
                    weight_names = list(layer_weights.keys())

                    def weight_order(name):
                        """Sort weights: kernel -> gamma -> beta -> mean -> var -> bias"""
                        if 'kernel' in name or 'depthwise_kernel' in name:
                            return 0
                        elif 'gamma' in name:
                            return 1
                        elif 'beta' in name:
                            return 2
                        elif 'moving_mean' in name:
                            return 3
                        elif 'moving_variance' in name:
                            return 4
                        elif 'bias' in name:
                            return 5
                        return 99

                    for wname in sorted(weight_names, key=weight_order):
                        weight_list.append(np.array(layer_weights[wname]))

                    if weight_list:
                        layer.set_weights(weight_list)
                        loaded_count += 1

                except Exception as e:
                    logger.warning(f"Could not load weights for {layer.name}: {e}")

        return loaded_count

    def load(self, path: Union[str, Path]) -> "MobileNetFloodClassifier":
        """
        Load trained weights.

        Args:
            path: Path to .h5 weights file

        Returns:
            self for method chaining

        Raises:
            FileNotFoundError: If weights file doesn't exist
            ValueError: If no weights could be loaded
            ImportError: If TensorFlow not installed
        """
        try:
            import tensorflow as tf

            # Suppress TF warnings
            tf.get_logger().setLevel('ERROR')

            path = Path(path)
            if not path.exists():
                raise FileNotFoundError(f"Model weights not found: {path}")

            # Build fresh model architecture
            logger.info(f"Building MobileNet architecture...")
            self.model = self._build_model()

            # Load weights from H5 file
            logger.info(f"Loading weights from {path}...")
            loaded_count = self._load_weights_from_h5(self.model, path)

            if loaded_count == 0:
                raise ValueError("No weights loaded from H5 file")

            self.model_path = str(path)
            self._trained = True
            logger.info(f"Loaded MobileNet flood classifier ({loaded_count} layers)")

            return self

        except ImportError:
            logger.error("TensorFlow not installed. Run: pip install tensorflow")
            raise

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
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        try:
            # Preprocess image
            preprocessed = self._preprocess(image)

            # Run inference
            probs = self.model.predict(preprocessed, verbose=0)[0]

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
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        results = []

        for i in range(0, len(images), batch_size):
            batch_images = images[i:i + batch_size]

            # Preprocess batch
            batch_preprocessed = np.vstack([
                self._preprocess(img) for img in batch_images
            ])

            # Run inference
            batch_probs = self.model.predict(batch_preprocessed, verbose=0)

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
    def is_trained(self) -> bool:
        """Check if model has been trained or loaded."""
        return self._trained and self.model is not None

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata."""
        return {
            "name": "MobileNetFloodClassifier",
            "architecture": "MobileNetV1",
            "source": "Sohail Ahmed Khan (pretrained)",
            "trained": self._trained,
            "model_path": self.model_path,
            "threshold": self.threshold,
            "classes": self.classes,
            "input_size": (224, 224, 3),
            "safety_config": {
                "flood_threshold": self.threshold,
                "review_low": self.REVIEW_LOW,
                "review_high": self.REVIEW_HIGH,
                "target_fnr": "<2%",
            }
        }

    def __repr__(self) -> str:
        status = "loaded" if self._trained else "not loaded"
        return f"MobileNetFloodClassifier(threshold={self.threshold}, status={status})"


# Convenience function for quick predictions
def classify_flood_image(
    image_path: str,
    model_path: str = "models/sohail_flood_model.h5"
) -> Dict[str, Any]:
    """
    Convenience function for single image classification.

    Args:
        image_path: Path to image file
        model_path: Path to model weights

    Returns:
        Classification result dictionary
    """
    classifier = MobileNetFloodClassifier()
    classifier.load(model_path)
    return classifier.predict(image_path)
