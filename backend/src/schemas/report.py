from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ReportBase(BaseModel):
    latitude: float
    longitude: float
    description: Optional[str] = None
    water_level: Optional[int] = 0 # 0=None, 1=Low, 2=Medium, 3=High

class ReportCreate(ReportBase):
    pass

class ReportResponse(ReportBase):
    id: int
    user_id: int
    image_url: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
