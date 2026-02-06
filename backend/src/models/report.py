from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from src.db.session import Base
import enum

class ReportStatus(str, enum.Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Location data
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    # location = Column(Geometry("POINT", srid=4326), nullable=False) # PostGIS geometry removed for SQLite
    
    # Report details
    image_url = Column(String, nullable=True)
    description = Column(String, nullable=True)
    water_level = Column(Integer, nullable=True) # 0-3 scale (Low, Medium, High, Extreme)
    
    status = Column(String, default=ReportStatus.UNVERIFIED)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", backref="reports")
