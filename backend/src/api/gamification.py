from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.session import get_db
from src.models.user import User
from src.models.gamification import Badge, user_badges
from src.api.deps import get_current_user
from pydantic import BaseModel
from typing import List

router = APIRouter()

class BadgeSchema(BaseModel):
    id: int
    name: str
    description: str | None
    icon_url: str | None

    class Config:
        from_attributes = True

class UserStats(BaseModel):
    points: int
    level: int
    reputation_score: int
    badges: List[BadgeSchema]

@router.get("/me", response_model=UserStats)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch user badges (mocking association loading for prototype speed)
    # In production, use joinedload
    return {
        "points": current_user.points,
        "level": current_user.level,
        "reputation_score": current_user.reputation_score,
        "badges": [] # Populate real badges in next iteration
    }

@router.post("/earn/{points}")
async def earn_points(
    points: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    current_user.points += points
    # Simple level up logic
    new_level = 1 + (current_user.points // 100)
    if new_level > current_user.level:
        current_user.level = new_level
    
    await db.commit()
    await db.refresh(current_user)
    return {"points": current_user.points, "level": current_user.level}
