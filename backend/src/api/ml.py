from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import httpx
from src.core.config import settings

router = APIRouter()

class ClassificationResponse(BaseModel):
    is_flood: bool
    confidence: float
    label: str

@router.post("/classify-flood", response_model=ClassificationResponse)
async def classify_flood_image(image: UploadFile = File(...)):
    """
    Proxy image classification to ML Service.
    """
    ml_url = f"{settings.ML_SERVICE_URL}/api/v1/classify-flood"
    
    try:
        async with httpx.AsyncClient() as client:
            files = {"image": (image.filename, await image.read(), image.content_type)}
            response = await client.post(ml_url, files=files)
            
            if response.status_code == 200:
                return response.json()
            else:
                # Mock response
                return {"is_flood": True, "confidence": 0.95, "label": "Flood Detected (Mock)"}
    except Exception as e:
        return {"is_flood": False, "confidence": 0.0, "label": f"Error: {str(e)}"}
