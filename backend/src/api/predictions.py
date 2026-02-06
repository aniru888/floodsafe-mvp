from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import httpx
from src.core.config import settings

router = APIRouter()

class PredictionRequest(BaseModel):
    latitude: float
    longitude: float
    horizon_days: int = 0

@router.post("/predict")
async def predict_flood_risk(request: PredictionRequest):
    """
    Proxy flood risk prediction to ML Service.
    """
    ml_url = f"{settings.ML_SERVICE_URL}/api/v1/predictions/risk-assessment"
    
    try:
        async with httpx.AsyncClient() as client:
            # Pass data to ML service
            # ML Service expects: latitude, longitude, radius_km (optional)
            payload = {
                "latitude": request.latitude,
                "longitude": request.longitude,
                "radius_km": 5.0 
            }
            response = await client.post(ml_url, json=payload)
            
            if response.status_code == 200:
                return response.json()
            else:
                # Fallback mock response if ML service fails or is not ready
                return {
                    "risk_score": 0.45,
                    "risk_level": "moderate",
                    "confidence": 0.85,
                    "details": "ML Service unavailable, returning fallback estimation."
                }
    except Exception as e:
        # Fallback
        return {
            "risk_score": 0.3,
            "risk_level": "low",
            "confidence": 0.0,
            "error": str(e)
        }
