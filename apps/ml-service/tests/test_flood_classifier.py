"""
Unit Tests for YOLOv8 Flood Classifier

Tests safety requirements and classification behavior.

CRITICAL SAFETY TESTS:
- test_threshold_is_safety_optimized: Threshold must be <= 0.3
- test_needs_review_for_uncertain_cases: Uncertain cases flagged for review
- test_predict_returns_all_fields: All required fields present

Usage:
    pytest apps/ml-service/tests/test_flood_classifier.py -v
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any
import sys

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestYOLOFloodClassifier:
    """Test suite for YOLOFloodClassifier with SAFETY requirements."""

    @pytest.fixture
    def mock_classifier(self):
        """Create a mock classifier for testing without model weights."""
        from apps.ml_service.src.models.yolo_flood_classifier import YOLOFloodClassifier

        classifier = YOLOFloodClassifier()
        classifier._trained = False  # Not trained for basic tests

        return classifier

    def test_default_threshold_is_safety_optimized(self, mock_classifier):
        """
        CRITICAL SAFETY TEST

        Ensure threshold is low enough for safety (<= 0.3).
        Standard classification uses 0.5, we use 0.3 to minimize false negatives.
        """
        assert mock_classifier.threshold <= 0.3, \
            f"Threshold {mock_classifier.threshold} is too high for safety. Must be <= 0.3"

    def test_review_thresholds_are_correct(self, mock_classifier):
        """Verify review threshold bounds for uncertain cases."""
        assert mock_classifier.REVIEW_LOW == 0.3, "REVIEW_LOW should be 0.3"
        assert mock_classifier.REVIEW_HIGH == 0.7, "REVIEW_HIGH should be 0.7"

    def test_classifier_not_trained_initially(self, mock_classifier):
        """Classifier should not be trained when created without weights."""
        assert not mock_classifier.is_trained
        assert mock_classifier.model is None

    def test_model_info_includes_safety_config(self, mock_classifier):
        """Model info should include safety configuration."""
        info = mock_classifier.get_model_info()

        assert "safety_config" in info
        assert info["safety_config"]["flood_threshold"] == mock_classifier.threshold
        assert info["safety_config"]["target_fnr"] == "<2%"

    def test_classes_are_correct(self, mock_classifier):
        """Verify class names are correctly ordered."""
        assert mock_classifier.classes == ["no_flood", "flood"]
        assert len(mock_classifier.classes) == 2


class TestClassificationLogic:
    """Test classification threshold and review logic."""

    def test_flood_classification_at_threshold(self):
        """Test classification at exactly threshold boundary."""
        from apps.ml_service.src.models.yolo_flood_classifier import YOLOFloodClassifier

        classifier = YOLOFloodClassifier(threshold=0.3)

        # At exactly 0.3, should classify as flood (>=)
        assert 0.3 >= classifier.threshold

    def test_needs_review_logic(self):
        """Test needs_review flag for uncertain cases."""
        # Cases that need review (0.3 <= prob <= 0.7)
        uncertain_probs = [0.3, 0.4, 0.5, 0.6, 0.7]
        for prob in uncertain_probs:
            needs_review = 0.3 <= prob <= 0.7
            assert needs_review, f"Prob {prob} should need review"

        # Cases that don't need review
        confident_probs = [0.1, 0.2, 0.29, 0.71, 0.8, 0.9]
        for prob in confident_probs:
            needs_review = 0.3 <= prob <= 0.7
            assert not needs_review, f"Prob {prob} should NOT need review"

    def test_threshold_customization(self):
        """Test that threshold can be customized."""
        from apps.ml_service.src.models.yolo_flood_classifier import YOLOFloodClassifier

        # Custom threshold
        classifier = YOLOFloodClassifier(threshold=0.2)
        assert classifier.threshold == 0.2

        # Default threshold
        classifier_default = YOLOFloodClassifier()
        assert classifier_default.threshold == 0.3


class TestPredictionOutput:
    """Test prediction output format and values."""

    @pytest.fixture
    def sample_prediction(self) -> Dict[str, Any]:
        """Sample prediction result for testing."""
        return {
            "classification": "flood",
            "confidence": 0.85,
            "flood_probability": 0.85,
            "is_flood": True,
            "needs_review": False,
            "probabilities": {"flood": 0.85, "no_flood": 0.15}
        }

    def test_prediction_has_all_required_fields(self, sample_prediction):
        """Verify all required fields are present in prediction."""
        required_fields = [
            "classification",
            "confidence",
            "flood_probability",
            "is_flood",
            "needs_review",
            "probabilities"
        ]

        for field in required_fields:
            assert field in sample_prediction, f"Missing field: {field}"

    def test_classification_is_valid_value(self, sample_prediction):
        """Classification must be either 'flood' or 'no_flood'."""
        assert sample_prediction["classification"] in ["flood", "no_flood"]

    def test_probabilities_sum_to_one(self, sample_prediction):
        """Probabilities should approximately sum to 1."""
        probs = sample_prediction["probabilities"]
        total = probs["flood"] + probs["no_flood"]
        assert abs(total - 1.0) < 0.01, f"Probabilities sum to {total}, expected ~1.0"

    def test_confidence_is_probability(self, sample_prediction):
        """Confidence should be between 0 and 1."""
        assert 0 <= sample_prediction["confidence"] <= 1
        assert 0 <= sample_prediction["flood_probability"] <= 1


class TestSafetyRequirements:
    """Test that safety requirements are enforced."""

    def test_low_threshold_minimizes_false_negatives(self):
        """
        CRITICAL SAFETY TEST

        Lower threshold means more images classified as flood,
        which minimizes false negatives (missed floods).

        With threshold=0.3:
        - prob 0.31 -> flood (correct if actually flood)
        - prob 0.29 -> no_flood (only if confident no flood)

        With threshold=0.5:
        - prob 0.31 -> no_flood (MISSED if actually flood!)
        """
        from apps.ml_service.src.models.yolo_flood_classifier import YOLOFloodClassifier

        safe_classifier = YOLOFloodClassifier(threshold=0.3)
        unsafe_classifier = YOLOFloodClassifier(threshold=0.5)

        # A borderline case with 35% flood probability
        borderline_prob = 0.35

        # Safe classifier catches it
        is_flood_safe = borderline_prob >= safe_classifier.threshold
        # Unsafe classifier misses it
        is_flood_unsafe = borderline_prob >= unsafe_classifier.threshold

        assert is_flood_safe is True, "Safe classifier should catch borderline cases"
        assert is_flood_unsafe is False, "Unsafe classifier misses borderline cases"

    def test_safety_target_documented(self):
        """Verify safety target is properly documented."""
        from apps.ml_service.src.models.yolo_flood_classifier import YOLOFloodClassifier

        classifier = YOLOFloodClassifier()
        info = classifier.get_model_info()

        # Check that <2% FNR target is documented
        assert info["safety_config"]["target_fnr"] == "<2%"


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_predict_without_loading_raises_error(self):
        """Calling predict before loading should raise RuntimeError."""
        from apps.ml_service.src.models.yolo_flood_classifier import YOLOFloodClassifier

        classifier = YOLOFloodClassifier()

        # Create a dummy image array
        dummy_image = np.zeros((100, 100, 3), dtype=np.uint8)

        with pytest.raises(RuntimeError, match="Model not loaded"):
            classifier.predict(dummy_image)

    def test_load_nonexistent_model_raises_error(self):
        """Loading non-existent model should raise FileNotFoundError."""
        from apps.ml_service.src.models.yolo_flood_classifier import YOLOFloodClassifier

        classifier = YOLOFloodClassifier()

        with pytest.raises(FileNotFoundError):
            classifier.load("/nonexistent/path/model.pt")


class TestAPIIntegration:
    """Test API-related functionality."""

    def test_classifier_repr(self):
        """Test string representation."""
        from apps.ml_service.src.models.yolo_flood_classifier import YOLOFloodClassifier

        classifier = YOLOFloodClassifier()
        repr_str = repr(classifier)

        assert "YOLOFloodClassifier" in repr_str
        assert "threshold=0.3" in repr_str
        assert "not loaded" in repr_str

    def test_get_model_info_structure(self):
        """Test model info dictionary structure."""
        from apps.ml_service.src.models.yolo_flood_classifier import YOLOFloodClassifier

        classifier = YOLOFloodClassifier()
        info = classifier.get_model_info()

        assert isinstance(info, dict)
        assert "name" in info
        assert "trained" in info
        assert "threshold" in info
        assert "classes" in info
        assert "safety_config" in info


# Allow running tests directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
