"""
FloodSafe ML Service - Lightweight Deployment (FHI + Image Classification).

This is a lightweight FastAPI service that provides:
- FHI (Flood Hazard Index) calculation using Open-Meteo API
- Hotspots endpoint with live FHI data
- Flood image classification using ONNX Runtime (MobileNet)

This version does NOT include:
- GEE (Google Earth Engine) integration
- TensorFlow (replaced with ONNX Runtime ~50MB)
- Full ensemble ML models (LSTM/GNN/LightGBM)

Total deployment size: ~150MB (vs 1.4GB+ for full service)
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FloodSafe ML Service (FHI-Only)",
    description="Lightweight FHI calculation service using Open-Meteo API",
    version="1.0.0-fhi",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
)

# CORS - allow all origins for now (ML service is internal)
CORS_ORIGINS = os.getenv("BACKEND_CORS_ORIGINS", "").split(",") if os.getenv("BACKEND_CORS_ORIGINS") else [
    "http://localhost:8000",
    "http://localhost:5175",
    "https://floodsafe-backend-floodsafe-dda84554.koyeb.app",
    "https://floodsafe-mvp-frontend.vercel.app",
]
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + ["*"],  # Be permissive for internal service
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from .api.hotspots import router as hotspots_router, initialize_hotspots_router
from .api.classify_flood import router as classify_router, initialize_classifier

# Include hotspots router
app.include_router(
    hotspots_router,
    prefix="/api/v1/hotspots",
    tags=["hotspots"],
)

# Include flood classification router
app.include_router(
    classify_router,
    prefix="/api/v1/classify-flood",
    tags=["classification"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("=" * 60)
    logger.info("Starting FloodSafe ML Service (Lightweight Mode)...")
    logger.info("=" * 60)

    hotspot_count = 0
    classifier_loaded = False

    # Initialize hotspots service (loads JSON data)
    try:
        logger.info("Initializing hotspots service...")
        initialize_hotspots_router()

        # Import to check loaded count
        from .api import hotspots
        hotspot_count = len(hotspots.hotspots_data)
        logger.info(f"  Hotspots loaded: {hotspot_count}")
        logger.info(f"  FHI calculator: using Open-Meteo API (free, no auth)")
    except Exception as e:
        logger.error(f"[ERROR] Hotspots initialization failed: {e}")
        raise

    # Initialize flood classifier (ONNX model)
    try:
        logger.info("Initializing flood classifier (ONNX)...")
        initialize_classifier()

        # Check if model loaded
        from .api import classify_flood
        classifier_loaded = classify_flood._model_loaded
        if classifier_loaded:
            logger.info("  Flood classifier: ONNX MobileNet loaded")
        else:
            logger.warning(f"  Flood classifier: NOT loaded ({classify_flood._load_error})")
    except Exception as e:
        logger.warning(f"[WARN] Classifier initialization failed: {e}")
        # Don't raise - classifier is optional, hotspots are primary

    # Startup summary
    logger.info("=" * 60)
    logger.info("ML Service (Lightweight) startup complete")
    logger.info(f"  Hotspots: {hotspot_count} locations")
    logger.info(f"  FHI: Open-Meteo API (live weather)")
    logger.info(f"  Flood Classifier: {'ONNX (loaded)' if classifier_loaded else 'not available'}")
    logger.info(f"  GEE: disabled")
    logger.info(f"  Docs: /api/v1/docs")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down ML Service (FHI-Only)...")


@app.get("/")
async def root():
    """Root endpoint."""
    # Check classifier status
    try:
        from .api import classify_flood
        classifier_loaded = classify_flood._model_loaded
    except Exception:
        classifier_loaded = False

    return {
        "service": "FloodSafe ML Service (Lightweight)",
        "version": "1.1.0",
        "status": "running",
        "mode": "lightweight",
        "docs": "/api/v1/docs",
        "health": "/health",
        "features": {
            "fhi": True,
            "hotspots": True,
            "image_classification": classifier_loaded,
            "gee": False,
            "ensemble_models": False,
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    from .api import hotspots

    # Check classifier status
    try:
        from .api import classify_flood
        classifier_loaded = classify_flood._model_loaded
        classifier_error = classify_flood._load_error
    except Exception:
        classifier_loaded = False
        classifier_error = "import failed"

    return {
        "status": "healthy",
        "service": "FloodSafe ML Service (Lightweight)",
        "mode": "lightweight",
        "hotspots_loaded": len(hotspots.hotspots_data) > 0,
        "hotspots_count": len(hotspots.hotspots_data),
        "fhi_source": "open-meteo",
        "classifier_loaded": classifier_loaded,
        "classifier_error": classifier_error if not classifier_loaded else None,
    }


if __name__ == "__main__":
    import uvicorn

    # Use PORT env var for Koyeb (auto-set) or FASTAPI_PORT or default 8002
    api_port = int(os.getenv("PORT", os.getenv("FASTAPI_PORT", "8002")))

    uvicorn.run(
        "src.main_fhi:app",
        host="0.0.0.0",
        port=api_port,
        log_level="info",
    )
