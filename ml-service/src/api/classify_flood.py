"""
Flood Image Classification API.

Provides endpoints for classifying images as flood/no_flood using
TFLite-based MobileNet classifier (~3MB, no security restrictions).

CRITICAL SAFETY REQUIREMENT:
- Uses low threshold (0.3) to minimize false negatives
- Better to have false alarms than miss a real flood
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import io

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy-loaded classifier
_classifier = None
_model_loaded = False
_load_error: Optional[str] = None


class ClassificationResult(BaseModel):
    """Classification result model."""
    classification: str  # "flood" or "no_flood"
    confidence: float
    flood_probability: float
    is_flood: bool
    needs_review: bool
    probabilities: dict


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    model_type: str
    error: Optional[str] = None


def _get_classifier():
    """Get or initialize the classifier."""
    global _classifier, _model_loaded, _load_error

    if _classifier is not None:
        return _classifier

    try:
        from ..models.tflite_flood_classifier import get_classifier
        _classifier = get_classifier()
        _model_loaded = True
        logger.info("TFLite flood classifier loaded successfully")
        return _classifier
    except Exception as e:
        _load_error = str(e)
        logger.error(f"Failed to load TFLite classifier: {e}")
        return None


def initialize_classifier():
    """Initialize classifier on startup."""
    global _model_loaded, _load_error

    try:
        classifier = _get_classifier()
        if classifier is not None:
            _model_loaded = True
            logger.info("Flood classifier initialized")
        else:
            _model_loaded = False
            logger.warning("Flood classifier not available")
    except Exception as e:
        _model_loaded = False
        _load_error = str(e)
        logger.error(f"Classifier initialization failed: {e}")


@router.get("/health", response_model=HealthResponse)
async def classifier_health():
    """
    Check flood classifier health status.

    Returns:
        Health status including model loaded state
    """
    classifier = _get_classifier()

    return HealthResponse(
        status="healthy" if _model_loaded else "degraded",
        model_loaded=_model_loaded,
        model_type="tflite" if _model_loaded else "none",
        error=_load_error if not _model_loaded else None
    )


@router.post("/", response_model=ClassificationResult)
async def classify_image(
    file: UploadFile = File(..., description="Image file to classify")
):
    """
    Classify an uploaded image as flood or no_flood.

    SAFETY: Uses low threshold (0.3) to minimize false negatives.
    Better to have false alarms than miss a real flood.

    Args:
        file: Image file (JPEG, PNG, etc.)

    Returns:
        Classification result with probability and confidence

    Raises:
        503: If classifier not loaded
        400: If image cannot be processed
    """
    classifier = _get_classifier()

    if classifier is None:
        raise HTTPException(
            status_code=503,
            detail=f"Flood classifier not available: {_load_error}"
        )

    # Validate file type
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {content_type}. Expected image/*"
        )

    try:
        # Read file content
        content = await file.read()

        # Create file-like object for PIL
        image_bytes = io.BytesIO(content)

        # Run classification
        result = classifier.predict(image_bytes)

        logger.info(
            f"Classification: {result['classification']} "
            f"(confidence={result['confidence']:.2f}, "
            f"flood_prob={result['flood_probability']:.2f})"
        )

        return ClassificationResult(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not process image: {e}"
        )
    except Exception as e:
        logger.error(f"Classification error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {e}"
        )


@router.post("/url")
async def classify_image_url(url: str):
    """
    Classify an image from URL.

    Args:
        url: URL of image to classify

    Returns:
        Classification result

    Note: Not implemented yet - returns 501
    """
    raise HTTPException(
        status_code=501,
        detail="URL classification not implemented. Use file upload."
    )
