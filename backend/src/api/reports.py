from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from src.db.session import get_db
from src.models.report import Report
from src.models.user import User
from src.schemas.report import ReportResponse
from src.api.deps import get_current_user
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
import shutil
import os
import uuid

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/", response_model=ReportResponse)
async def create_report(
    latitude: float = Form(...),
    longitude: float = Form(...),
    description: str = Form(None),
    water_level: int = Form(0),
    image: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image_url = None
    if image:
        # Save image locally for MVP
        filename = f"{uuid.uuid4()}_{image.filename}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        image_url = f"/static/{filename}"

    # Create geometry point
    point = Point(longitude, latitude)
    wkb_element = from_shape(point, srid=4326)

    report = Report(
        user_id=current_user.id,
        latitude=latitude,
        longitude=longitude,
        # location=wkb_element,
        description=description,
        water_level=water_level,
        image_url=image_url,
    )
    
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report

@router.get("/", response_model=List[ReportResponse])
async def get_reports(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Report).offset(skip).limit(limit).order_by(Report.created_at.desc()))
    reports = result.scalars().all()
    return reports
