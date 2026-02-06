from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.session import Base

# Association table for User-Badge
user_badges = Table(
    "user_badges",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("badge_id", Integer, ForeignKey("badges.id"), primary_key=True),
    Column("earned_at", DateTime(timezone=True), server_default=func.now())
)

class Badge(Base):
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    icon_url = Column(String, nullable=True)
    points_required = Column(Integer, default=0)
