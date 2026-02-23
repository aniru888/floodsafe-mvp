from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from .infrastructure import models  # noqa: F401 - ensures models are loaded

# NOTE: Database schema is now managed by Alembic migrations.
# Run `alembic upgrade head` to apply migrations.
# See apps/backend/alembic/ for migration files.

from .api import webhook, reports, users, sensors, otp, watch_areas, daily_routes, reputation, leaderboards, badges, routes_api, auth, alerts, search, predictions, saved_routes, historical_floods, hotspots, external_alerts, rainfall, gamification, comments, ml, floodhub, circles, sos, whatsapp_meta, push
from .domain.services.external_alerts import start_scheduler, stop_scheduler
from .domain.services.floodhub_service import init_floodhub_service

from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings

logger = logging.getLogger(__name__)


def validate_config():
    """Validate critical configuration settings on startup."""
    DEFAULT_JWT_SECRET = "floodsafe-jwt-secret-change-in-production-min-32-chars"

    # Check JWT secret in production
    if settings.is_production:
        if settings.JWT_SECRET_KEY == DEFAULT_JWT_SECRET:
            raise RuntimeError(
                "SECURITY ERROR: JWT_SECRET_KEY must be changed from default in production! "
                "Set a secure random string via environment variable."
            )

    # Always check JWT secret length (minimum 32 chars for security)
    if len(settings.JWT_SECRET_KEY) < 32:
        raise RuntimeError(
            f"SECURITY ERROR: JWT_SECRET_KEY must be at least 32 characters "
            f"(current: {len(settings.JWT_SECRET_KEY)} chars)"
        )

    # Warn about CORS in production
    if settings.is_production:
        localhost_origins = [o for o in settings.BACKEND_CORS_ORIGINS if "localhost" in o]
        if localhost_origins:
            logger.warning(
                f"WARNING: CORS origins contain localhost URLs in production: {localhost_origins}. "
                "Consider removing localhost from BACKEND_CORS_ORIGINS env var."
            )

    logger.info(f"Config validation passed. Production mode: {settings.is_production}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan events for startup and shutdown."""
    # Startup
    logger.info("Starting FloodSafe API...")

    # Validate configuration
    validate_config()

    # Initialize FloodHub service (optional - gracefully disabled if no API key)
    floodhub_svc = init_floodhub_service(api_key=settings.GOOGLE_FLOODHUB_API_KEY or None)
    if floodhub_svc.enabled:
        logger.info("FloodHub service initialized with API key")
    else:
        logger.info("FloodHub service disabled (no API key configured)")

    start_scheduler()
    logger.info("External alerts scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down FloodSafe API...")
    stop_scheduler()
    logger.info("External alerts scheduler stopped")


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(webhook.router, prefix="/api/whatsapp", tags=["whatsapp"])
app.include_router(whatsapp_meta.router, prefix="/api/whatsapp-meta", tags=["whatsapp-meta"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(sensors.router, prefix="/api/sensors", tags=["sensors"])
app.include_router(otp.router, prefix="/api", tags=["otp"])
app.include_router(watch_areas.router, prefix="/api/watch-areas", tags=["watch-areas"])
app.include_router(daily_routes.router, prefix="/api/daily-routes", tags=["daily-routes"])
app.include_router(reputation.router, prefix="/api/reputation", tags=["reputation"])
app.include_router(leaderboards.router, prefix="/api/leaderboards", tags=["leaderboards"])
app.include_router(badges.router, prefix="/api/badges", tags=["badges"])
app.include_router(routes_api.router, prefix="/api", tags=["routing"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(external_alerts.router, prefix="/api", tags=["external-alerts"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(saved_routes.router, prefix="/api", tags=["saved-routes"])
app.include_router(historical_floods.router, prefix="/api/historical-floods", tags=["historical-floods"])
app.include_router(hotspots.router, prefix="/api/hotspots", tags=["hotspots"])
app.include_router(rainfall.router, prefix="/api/rainfall", tags=["rainfall"])
app.include_router(gamification.router, prefix="/api/gamification", tags=["gamification"])
app.include_router(comments.router, prefix="/api", tags=["comments"])
app.include_router(ml.router, prefix="/api/ml", tags=["ml"])
app.include_router(floodhub.router, prefix="/api", tags=["floodhub"])
app.include_router(circles.router, prefix="/api/circles", tags=["safety-circles"])
app.include_router(sos.router, prefix="/api/sos", tags=["sos"])
app.include_router(push.router, prefix="/api", tags=["push"])

@app.get("/health")
def health_check():
    return {"status": "healthy"}
 