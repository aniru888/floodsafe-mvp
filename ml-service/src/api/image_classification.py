"""
Flood Image Classification API

FastAPI endpoints for classifying uploaded images as flood or non-flood.

CRITICAL SAFETY REQUIREMENT:
- Uses low threshold (0.3) to minimize false negatives (<2% target)
- Flags uncertain cases (0.3-0.7 probability) for human review
- Returns verification_score for use in report credibility

Endpoints:
- POST /classify-flood: Classify single image
- POST /classify-flood/batch: Classify multiple images
- GET /classify-flood/health: Check model status
"""

import io
import logging
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["image-classification"])

# Global model instance (loaded at startup by main.py)
flood_classifier = None


# --- Pydantic Models ---

class ClassificationResult(BaseModel):
    """Single image classification result."""
    classification: str  # "flood" or "no_flood"
    confidence: float  # 0.0-1.0
    flood_probability: float  # 0.0-1.0
    is_flood: bool
    needs_review: bool  # True if confidence is uncertain (0.3-0.7)
    verification_score: int  # 0-100 for report credibility
    probabilities: dict  # {"flood": 0.92, "no_flood": 0.08}


class BatchClassificationResult(BaseModel):
    """Batch classification results."""
    total: int
    flood_count: int
    no_flood_count: int
    needs_review_count: int
    results: List[ClassificationResult]


class ClassifierHealth(BaseModel):
    """Classifier health status."""
    status: str  # "healthy", "not_loaded", "error"
    model_loaded: bool
    model_path: Optional[str] = None
    threshold: Optional[float] = None
    message: Optional[str] = None


# --- API Endpoints ---

@router.post("/classify-flood", response_model=ClassificationResult)
async def classify_flood_image(
    image: UploadFile = File(..., description="Image file to classify (JPEG, PNG)")
):
    """
    Classify uploaded image as flood or not flood.

    SAFETY-FIRST: Uses low threshold (0.3) to minimize false negatives.
    Missing a real flood is more dangerous than flagging a non-flood.

    Returns:
        ClassificationResult with:
        - classification: "flood" or "no_flood"
        - confidence: Classification confidence (0.0-1.0)
        - flood_probability: Raw probability of flood (0.0-1.0)
        - is_flood: Boolean classification
        - needs_review: True if uncertain (0.3-0.7 probability)
        - verification_score: 0-100 for report credibility scoring
    """
    if flood_classifier is None:
        raise HTTPException(
            status_code=503,
            detail="Flood classifier not loaded. Model weights may be missing."
        )

    # Validate file type
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {image.content_type}. Expected image/*"
        )

    try:
        from PIL import Image

        # Read image
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents))

        # Convert to RGB if necessary
        if pil_image.mode not in ("RGB", "L"):
            pil_image = pil_image.convert("RGB")

        # Classify
        result = flood_classifier.predict(pil_image)

        # Calculate verification score (0-100)
        # Higher score = more confident classification
        verification_score = int(result["confidence"] * 100)

        # Adjust score based on flood status (for report credibility)
        # If classified as flood, higher confidence = higher score
        # If classified as no_flood, we still trust the image but note it
        if not result["is_flood"]:
            # Image doesn't look like flood - lower verification score
            # This will flag the report for review
            verification_score = min(verification_score, 40)

        return ClassificationResult(
            classification=result["classification"],
            confidence=result["confidence"],
            flood_probability=result["flood_probability"],
            is_flood=result["is_flood"],
            needs_review=result["needs_review"],
            verification_score=verification_score,
            probabilities=result["probabilities"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}"
        )


@router.post("/classify-flood/batch", response_model=BatchClassificationResult)
async def classify_flood_images_batch(
    images: List[UploadFile] = File(..., description="Multiple image files to classify")
):
    """
    Classify multiple images in a batch.

    Useful for processing multiple photos from a single flood report.

    Returns:
        BatchClassificationResult with aggregated stats and individual results
    """
    if flood_classifier is None:
        raise HTTPException(
            status_code=503,
            detail="Flood classifier not loaded"
        )

    if len(images) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 images per batch"
        )

    results = []
    flood_count = 0
    no_flood_count = 0
    needs_review_count = 0

    for image in images:
        try:
            from PIL import Image as PILImage

            contents = await image.read()
            pil_image = PILImage.open(io.BytesIO(contents))

            if pil_image.mode not in ("RGB", "L"):
                pil_image = pil_image.convert("RGB")

            result = flood_classifier.predict(pil_image)

            verification_score = int(result["confidence"] * 100)
            if not result["is_flood"]:
                verification_score = min(verification_score, 40)

            classification_result = ClassificationResult(
                classification=result["classification"],
                confidence=result["confidence"],
                flood_probability=result["flood_probability"],
                is_flood=result["is_flood"],
                needs_review=result["needs_review"],
                verification_score=verification_score,
                probabilities=result["probabilities"]
            )

            results.append(classification_result)

            if result["is_flood"]:
                flood_count += 1
            else:
                no_flood_count += 1

            if result["needs_review"]:
                needs_review_count += 1

        except Exception as e:
            logger.warning(f"Failed to classify image {image.filename}: {e}")
            # Include failed result with low confidence
            results.append(ClassificationResult(
                classification="no_flood",
                confidence=0.0,
                flood_probability=0.0,
                is_flood=False,
                needs_review=True,
                verification_score=0,
                probabilities={"flood": 0.0, "no_flood": 0.0}
            ))

    return BatchClassificationResult(
        total=len(images),
        flood_count=flood_count,
        no_flood_count=no_flood_count,
        needs_review_count=needs_review_count,
        results=results
    )


@router.get("/classify-flood/health", response_model=ClassifierHealth)
async def classifier_health():
    """
    Check flood classifier health status.

    Returns model loading status, threshold settings, and any error messages.
    """
    if flood_classifier is None:
        return ClassifierHealth(
            status="not_loaded",
            model_loaded=False,
            message="Model weights not found. Training required."
        )

    if not flood_classifier.is_trained:
        return ClassifierHealth(
            status="not_trained",
            model_loaded=False,
            message="Model loaded but not trained"
        )

    return ClassifierHealth(
        status="healthy",
        model_loaded=True,
        model_path=flood_classifier.model_path,
        threshold=flood_classifier.threshold,
        message=f"Model ready. Safety threshold: {flood_classifier.threshold}"
    )


@router.get("/classify-flood/info")
async def classifier_info():
    """
    Get detailed classifier information.

    Returns model metadata, safety configuration, and usage instructions.
    """
    if flood_classifier is None:
        return {
            "status": "not_loaded",
            "message": "Model not available"
        }

    return {
        "status": "healthy",
        "model_info": flood_classifier.get_model_info(),
        "usage": {
            "endpoint": "/classify-flood",
            "method": "POST",
            "content_type": "multipart/form-data",
            "field": "image",
            "accepted_formats": ["image/jpeg", "image/png", "image/webp"]
        },
        "safety_requirements": {
            "target_false_negative_rate": "<2%",
            "classification_threshold": 0.3,
            "review_range": "0.3-0.7 probability triggers needs_review flag"
        }
    }


# --- Helper Functions ---

def initialize_classifier() -> bool:
    """
    Initialize the flood classifier.

    Called by main.py during startup.
    Uses MobileNet pretrained model (Sohail Ahmed Khan's weights).

    Returns:
        True if classifier loaded successfully, False otherwise
    """
    global flood_classifier

    try:
        from ..models.mobilenet_flood_classifier import MobileNetFloodClassifier

        # Check for trained model (MobileNet H5 weights)
        model_paths = [
            Path(__file__).parent.parent.parent / "models" / "sohail_flood_model.h5",
            Path("models/sohail_flood_model.h5"),
            Path("/app/models/sohail_flood_model.h5"),  # Docker path
        ]

        model_path = None
        for path in model_paths:
            if path.exists():
                model_path = path
                break

        if model_path is None:
            logger.warning("No MobileNet flood classifier found")
            logger.warning("  Expected at: models/sohail_flood_model.h5")
            logger.warning("  Download from: https://github.com/sohailahmedkhan/Flood-Detection-from-Images-using-Deep-Learning")

            flood_classifier = None
            return False

        # Load the MobileNet classifier
        flood_classifier = MobileNetFloodClassifier()
        flood_classifier.load(str(model_path))

        logger.info(f"MobileNet flood classifier loaded from {model_path}")
        logger.info(f"  Threshold: {flood_classifier.threshold}")
        logger.info(f"  Classes: {flood_classifier.classes}")

        return True

    except ImportError as e:
        logger.error(f"Failed to import MobileNetFloodClassifier: {e}")
        logger.error("  Install tensorflow: pip install tensorflow")
        flood_classifier = None
        return False

    except Exception as e:
        logger.error(f"Failed to initialize flood classifier: {e}")
        flood_classifier = None
        return False


def get_classifier():
    """Get the global classifier instance."""
    return flood_classifier
