from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from src.db.session import get_db
from src.models.watch_area import WatchArea
from src.models.user import User
from src.schemas.watch_area import WatchAreaCreate, WatchAreaResponse
from src.api.deps import get_current_user
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

router = APIRouter()

@router.post("/", response_model=WatchAreaResponse)
async def create_watch_area(
    area_in: WatchAreaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Create geometry point
    point = Point(area_in.longitude, area_in.latitude)
    wkb_element = from_shape(point, srid=4326)

    watch_area = WatchArea(
        user_id=current_user.id,
        name=area_in.name,
        latitude=area_in.latitude,
        longitude=area_in.longitude,
        radius_meters=area_in.radius_meters,
        # location=wkb_element,
    )
    
    db.add(watch_area)
    await db.commit()
    await db.refresh(watch_area)
    return watch_area

@router.get("/", response_model=List[WatchAreaResponse])
async def get_watch_areas(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WatchArea)
        .where(WatchArea.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .order_by(WatchArea.created_at.desc())
    )
    return result.scalars().all()

@router.delete("/{id}")
async def delete_watch_area(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(WatchArea).where(WatchArea.id == id, WatchArea.user_id == current_user.id))
    watch_area = result.scalars().first()
    
    if not watch_area:
        raise HTTPException(status_code=404, detail="Watch area not found")
        
    await db.delete(watch_area)
    await db.commit()
    return {"ok": True}
