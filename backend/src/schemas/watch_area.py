from pydantic import BaseModel
from datetime import datetime

class WatchAreaBase(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_meters: int = 500

class WatchAreaCreate(WatchAreaBase):
    pass

class WatchAreaResponse(WatchAreaBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True
