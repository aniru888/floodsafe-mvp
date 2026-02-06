from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
import json
import httpx
from pathlib import Path
import logging
from ..core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Path to static hotspot data (using local data file for now)
def _get_static_hotspots_path() -> Optional[Path]:
    # Try multiple locations to find the file
    possible_paths = [
        Path("src/data/delhi_waterlogging_hotspots.json"),
        Path("data/delhi_waterlogging_hotspots.json"),
        Path("../ml-service/data/delhi_waterlogging_hotspots.json")
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    return None

@router.get("/")
async def get_hotspots():
    """
    Get waterlogging hotspots.
    Tries to fetch dynamic risk data from ML Service first.
    Falls back to static data if ML Service is unavailable.
    """
    # 1. Try to get dynamic data from ML Service
    ml_url = f"{settings.ML_SERVICE_URL}/api/v1/hotspots/all?include_fhi=true&include_rainfall=false"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(ml_url, timeout=180.0)
            
            if response.status_code == 200:
                data = response.json()
                # Ensure it's a valid FeatureCollection
                if data.get("type") == "FeatureCollection" and "features" in data:
                    logger.info("Successfully fetched dynamic hotspots from ML Service")
                    return data
            else:
                logger.warning(f"ML Service returned status {response.status_code}")
                
    except Exception as e:
        logger.warning(f"Failed to connect to ML Service: {e}. Falling back to static data.")

    # 2. Fallback to static data
    logger.info("Using static hotspot data fallback")
    data_path = _get_static_hotspots_path()
    
    # Fallback data if file not found (Prototype Mode)
    if not data_path:
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [77.2090, 28.6139]},
                    "properties": {"name": "Connaught Place", "severity": "high", "risk_score": 0.8}
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [77.2300, 28.6400]},
                    "properties": {"name": "ITO", "severity": "moderate", "risk_score": 0.5}
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [77.1000, 28.7000]},
                    "properties": {"name": "Rohini Sector 10", "severity": "low", "risk_score": 0.3}
                }
            ]
        }

    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            
        # Transform to GeoJSON if needed
        if isinstance(raw_data, dict) and "hotspots" in raw_data:
            features = []
            for item in raw_data["hotspots"]:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point", 
                        "coordinates": [item.get("lng", 0), item.get("lat", 0)]
                    },
                    "properties": item
                })
            return {"type": "FeatureCollection", "features": features}

        if isinstance(raw_data, list):
            features = []
            for item in raw_data:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point", 
                        "coordinates": [item.get("lng", 0), item.get("lat", 0)]
                    },
                    "properties": item
                })
            return {"type": "FeatureCollection", "features": features}
            
        return raw_data
        
    except Exception as e:
        logger.error(f"Error loading hotspots: {e}")
        raise HTTPException(status_code=500, detail=str(e))
