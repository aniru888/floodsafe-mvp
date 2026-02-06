"""
FloodSafe ML Service - Main Application.

FastAPI service for flood prediction using ensemble ML models.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .core.config import settings
from .api import predictions, hotspots, image_classification
from .data.gee_client import gee_client

# Optional imports - may not be available in production (HuggingFace)
FeatureExtractor = None
try:
    from .features.extractor import FeatureExtractor as _FE
    FeatureExtractor = _FE
except ImportError:
    pass  # GEE-based feature extractor not needed in production

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    predictions.router,
    prefix=f"{settings.API_V1_STR}/predictions",
    tags=["predictions"],
)
app.include_router(
    hotspots.router,
    prefix=f"{settings.API_V1_STR}/hotspots",
    tags=["hotspots"],
)
app.include_router(
    image_classification.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["image-classification"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("=" * 60)
    logger.info(f"Starting {settings.PROJECT_NAME}...")
    logger.info("=" * 60)

    # Initialize GEE (only if enabled - disabled on HuggingFace)
    gee_available = False
    try:
        logger.info("Initializing Google Earth Engine...")
        gee_client.initialize()
        gee_available = gee_client.is_available
        if gee_available:
            logger.info("[OK] GEE initialized successfully")
        else:
            logger.info("[SKIP] GEE disabled (GEE_ENABLED=false)")
    except Exception as e:
        logger.warning(f"[WARN] GEE initialization failed: {e}")

    # Initialize feature extractor (only if GEE is available)
    if gee_available and FeatureExtractor:
        try:
            logger.info("Initializing feature extractor...")
            predictions.feature_extractor = FeatureExtractor(lazy_load=True)
            logger.info("[OK] Feature extractor ready")
        except Exception as e:
            logger.warning(f"[WARN] Feature extractor failed: {e}")
    else:
        logger.info("[SKIP] Feature extractor (GEE disabled)")
        predictions.feature_extractor = None

    # Skip ensemble model - it's not trained and not needed
    # In production, we use XGBoost for hotspots and MobileNet for images
    predictions.ensemble_model = None
    logger.info("[SKIP] Ensemble model (shelved - using XGBoost for hotspots)")

    # Initialize hotspots service (XGBoost model - TRAINED and working!)
    try:
        logger.info("Initializing hotspots service...")
        hotspots.initialize_hotspots_router()
        logger.info(f"  Hotspots loaded: {len(hotspots.hotspots_data)}")
        logger.info(f"  XGBoost model: {'trained' if hotspots.hotspot_model and hotspots.hotspot_model.is_trained else 'not available'}")
    except Exception as e:
        logger.error(f"[ERROR] Hotspots initialization failed: {e}")

    # Load pre-computed grid predictions cache
    try:
        logger.info("Loading grid predictions cache...")
        if predictions.load_grid_predictions_cache():
            cache_points = len(predictions.grid_predictions_cache.get("features", []))
            logger.info(f"[OK] Grid predictions cache loaded: {cache_points} points")
        else:
            logger.info("[SKIP] No grid predictions cache")
    except Exception as e:
        logger.warning(f"[WARN] Grid cache loading failed: {e}")

    # Initialize flood image classifier (MobileNet - TRAINED and working!)
    try:
        logger.info("Initializing flood image classifier...")
        if image_classification.initialize_classifier():
            classifier = image_classification.get_classifier()
            logger.info(f"[OK] MobileNet flood classifier loaded (threshold: {classifier.threshold})")
        else:
            logger.warning("[WARN] Flood classifier not available")
    except Exception as e:
        logger.warning(f"[WARN] Flood classifier failed: {e}")

    # Startup summary
    classifier = image_classification.get_classifier()
    logger.info("=" * 60)
    logger.info("ML Service startup complete")
    logger.info(f"  Hotspots: {len(hotspots.hotspots_data)} locations")
    logger.info(f"  XGBoost: {'ready' if hotspots.hotspot_model and hotspots.hotspot_model.is_trained else 'N/A'}")
    logger.info(f"  MobileNet: {'ready' if classifier and classifier.is_trained else 'N/A'}")
    logger.info(f"  GEE: {'enabled' if gee_available else 'disabled'}")
    logger.info(f"  Docs: {settings.API_V1_STR}/docs")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down ML Service...")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": f"{settings.API_V1_STR}/docs",
        "health": "/api/v1/predictions/health",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
    }


if __name__ == "__main__":
    import uvicorn

    # Use FASTAPI_PORT env var for HF Spaces (7860) or local dev (8002)
    api_port = int(os.getenv("FASTAPI_PORT", "8002"))
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=api_port,
        reload=True,
        log_level="info",
    )
