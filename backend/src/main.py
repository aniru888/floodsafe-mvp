from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from src.api import auth, reports, watch_areas, routes, gamification, hotspots, ml, predictions
from src.db.session import engine, Base
import os

app = FastAPI(title="FloodSafe API", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (uploads)
os.makedirs("uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="uploads"), name="static")

# Routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(watch_areas.router, prefix="/api/v1/watch-areas", tags=["watch-areas"])
app.include_router(routes.router, prefix="/api/v1/routes", tags=["routes"])
app.include_router(gamification.router, prefix="/api/v1/gamification", tags=["gamification"])
app.include_router(hotspots.router, prefix="/api/v1/hotspots", tags=["hotspots"])
app.include_router(ml.router, prefix="/api/v1/ml", tags=["ml"])
app.include_router(predictions.router, prefix="/api/v1/predictions", tags=["predictions"])

@app.on_event("startup")
async def startup():
    # Create tables (for development only - use Alembic in prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
def read_root():
    return {"message": "Welcome to FloodSafe API v2"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
