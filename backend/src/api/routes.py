from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import httpx
from shapely.geometry import LineString, Point, shape
from shapely.ops import transform
import pyproj
from src.db.session import get_db
from src.models.report import Report
from src.models.watch_area import WatchArea
from sqlalchemy.future import select
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

class RouteRequest(BaseModel):
    origin: List[float] # [lng, lat]
    destination: List[float] # [lng, lat]
    mode: str = "driving"

class RouteResponse(BaseModel):
    geometry: dict # GeoJSON
    duration: float
    distance: float
    risk_score: int
    alerts: List[str]

@router.post("/calculate", response_model=List[RouteResponse])
async def calculate_route(request: RouteRequest, db: AsyncSession = Depends(get_db)):
    # 1. Fetch route from OSRM
    osrm_url = f"http://router.project-osrm.org/route/v1/{request.mode}/{request.origin[0]},{request.origin[1]};{request.destination[0]},{request.destination[1]}?overview=full&geometries=geojson&alternatives=true"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(osrm_url)
        if response.status_code != 200:
            raise HTTPException(status_code=503, detail="Routing service unavailable")
        
        data = response.json()
        if data["code"] != "Ok":
            raise HTTPException(status_code=400, detail="Could not calculate route")

    routes = data["routes"]
    analyzed_routes = []

    # 2. Fetch active flood reports
    result = await db.execute(select(Report))
    active_reports = result.scalars().all()
    
    # 3. Analyze each route for flood intersection
    for route in routes:
        route_geom = shape(route["geometry"])
        risk_score = 0
        alerts = []

        # Check intersection with reports
        # Note: In a real app, use PostGIS ST_DWithin for efficiency. 
        # Here we do a simple check in Python for prototype speed.
        for report in active_reports:
            # Simple distance check (approximate)
            # 0.001 degrees is roughly 100m
            report_point = Point(report.longitude, report.latitude)
            if route_geom.distance(report_point) < 0.001: 
                risk_score += 10
                alerts.append(f"Flood reported near route: {report.description or 'Waterlogging'}")

        analyzed_routes.append({
            "geometry": route["geometry"],
            "duration": route["duration"],
            "distance": route["distance"],
            "risk_score": risk_score,
            "alerts": alerts
        })

    # Sort by risk score (lowest first)
    analyzed_routes.sort(key=lambda x: x["risk_score"])
    
    return analyzed_routes
