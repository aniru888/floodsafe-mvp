"""
Search API - Unified search endpoint for locations, reports, and users.

Provides:
- GET /search/ - Unified search with smart intent detection
- GET /search/locations/ - Location-specific search
- GET /search/reports/ - Report text search
- GET /search/users/ - User search
- GET /search/suggestions/ - Search suggestions and trending
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from ..infrastructure.database import get_db
from ..domain.services.search_service import get_search_service


router = APIRouter(prefix="/search", tags=["search"])


# Response Models
class LocationResult(BaseModel):
    type: str = "location"
    display_name: str
    lat: float
    lng: float
    address: Dict[str, Any] = {}
    importance: float = 0
    formatted_name: str


class ReportResult(BaseModel):
    type: str = "report"
    id: str
    description: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    water_depth: Optional[str] = None
    vehicle_passability: Optional[str] = None
    verified: bool = False
    timestamp: Optional[str] = None
    media_url: Optional[str] = None
    highlight: str = ""


class UserResult(BaseModel):
    type: str = "user"
    id: str
    username: str
    display_name: Optional[str] = None
    points: int = 0
    level: int = 1
    reports_count: int = 0
    profile_photo_url: Optional[str] = None


class SearchSuggestion(BaseModel):
    type: str
    text: str
    options: Optional[List[str]] = None
    action: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class UnifiedSearchResponse(BaseModel):
    query: str
    intent: str
    locations: List[Dict[str, Any]] = []
    reports: List[Dict[str, Any]] = []
    users: List[Dict[str, Any]] = []
    suggestions: List[Dict[str, Any]] = []


class TrendingResponse(BaseModel):
    trending: List[str]
    recent_areas: List[str] = []


# City bounds for filtering
DELHI_BOUNDS = {
    "min_lat": 28.40,
    "max_lat": 28.88,
    "min_lng": 76.84,
    "max_lng": 77.35,
    "country_code": "in",
}

BANGALORE_BOUNDS = {
    "min_lat": 12.75,
    "max_lat": 13.20,
    "min_lng": 77.35,
    "max_lng": 77.80,
    "country_code": "in",
}

YOGYAKARTA_BOUNDS = {
    "min_lat": -7.95,
    "max_lat": -7.65,
    "min_lng": 110.30,
    "max_lng": 110.50,
    "country_code": "id",
}

SINGAPORE_BOUNDS = {
    "min_lat": 1.15,
    "max_lat": 1.47,
    "min_lng": 103.60,
    "max_lng": 104.05,
    "country_code": "sg",
}


@router.get("/", response_model=UnifiedSearchResponse)
async def unified_search(
    q: str = Query(..., min_length=2, description="Search query"),
    type: Optional[str] = Query(
        None,
        description="Search type: 'all', 'locations', 'reports', 'users'"
    ),
    lat: Optional[float] = Query(None, description="Latitude for spatial search"),
    lng: Optional[float] = Query(None, description="Longitude for spatial search"),
    radius: float = Query(5000, ge=100, le=50000, description="Search radius in meters"),
    limit: int = Query(30, ge=1, le=100, description="Max results per category"),
    city: str = Query("all", description="City filter: 'delhi', 'bangalore', 'yogyakarta', or 'all'"),
    db: Session = Depends(get_db)
):
    """
    Unified search across locations, reports, and users.

    **Smart Intent Detection:**
    - Location keywords (road, sector, colony) → prioritize location results
    - Flood keywords (water, flooding, impassable) → prioritize report results
    - @username pattern → search for users
    - Explicit prefixes: `@location:`, `@report:`, `@user:`

    **Examples:**
    - `Connaught Place` → locations in Delhi
    - `flooding near metro` → reports about flooding
    - `@john` → users with "john" in username
    - `@location:Nehru Place` → explicit location search

    **City Filtering:**
    - city='delhi' → only Delhi results
    - city='bangalore' → only Bangalore results
    - city='all' → no geographic filtering (default)
    """
    # Select city bounds based on city parameter
    city_bounds = None
    if city.lower() == 'delhi':
        city_bounds = DELHI_BOUNDS
    elif city.lower() == 'bangalore':
        city_bounds = BANGALORE_BOUNDS
    elif city.lower() == 'yogyakarta':
        city_bounds = YOGYAKARTA_BOUNDS
    elif city.lower() == 'singapore':
        city_bounds = SINGAPORE_BOUNDS
    # For 'all' or any other value, don't filter by bounds (city_bounds = None)

    search_service = get_search_service(db)
    results = await search_service.unified_search(
        query=q,
        search_type=type,
        latitude=lat,
        longitude=lng,
        radius_meters=radius,
        limit=limit,
        city_bounds=city_bounds
    )

    return results


@router.get("/locations/", response_model=List[LocationResult])
async def search_locations(
    q: str = Query(..., min_length=2, description="Location search query"),
    limit: int = Query(30, ge=1, le=50, description="Max results"),
    city: Optional[str] = Query(None, regex="^(delhi|bangalore|yogyakarta|singapore)$", description="City filter: 'delhi', 'bangalore', 'yogyakarta', or 'singapore'"),
    db: Session = Depends(get_db)
):
    """
    Search for locations using geocoding.

    Uses Nominatim with caching for efficiency.
    Alias expansion for common abbreviations (HSR -> HSR Layout Bangalore).

    When city is provided, results are filtered to that city's bounds.
    """
    # Determine city bounds based on city parameter
    city_bounds = None
    if city == 'delhi':
        city_bounds = DELHI_BOUNDS
    elif city == 'bangalore':
        city_bounds = BANGALORE_BOUNDS
    elif city == 'yogyakarta':
        city_bounds = YOGYAKARTA_BOUNDS
    elif city == 'singapore':
        city_bounds = SINGAPORE_BOUNDS

    search_service = get_search_service(db)
    results = await search_service.unified_search(
        query=q,
        search_type="locations",
        city_bounds=city_bounds,
        limit=limit
    )

    return results.get("locations", [])


@router.get("/reports/", response_model=List[ReportResult])
async def search_reports(
    q: str = Query(..., min_length=2, description="Report search query"),
    lat: Optional[float] = Query(None, description="Center latitude"),
    lng: Optional[float] = Query(None, description="Center longitude"),
    radius: float = Query(5000, ge=100, le=50000, description="Radius in meters"),
    limit: int = Query(30, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    Search flood reports by description text.

    **Search terms:**
    - Matches any word in the query against report descriptions
    - Case-insensitive matching
    - Results ordered by timestamp (newest first)

    **Spatial filtering:**
    - Optionally filter by location radius
    - Provide lat/lng and radius for nearby reports
    """
    search_service = get_search_service(db)
    results = await search_service.unified_search(
        query=q,
        search_type="reports",
        latitude=lat,
        longitude=lng,
        radius_meters=radius,
        limit=limit
    )

    return results.get("reports", [])


@router.get("/users/", response_model=List[UserResult])
async def search_users(
    q: str = Query(..., min_length=2, description="Username search query"),
    limit: int = Query(15, ge=1, le=50, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    Search users by username or display name.

    - Only returns users with public profiles
    - Results ordered by reputation points
    - Supports partial matching
    """
    search_service = get_search_service(db)
    results = await search_service.unified_search(
        query=q,
        search_type="users",
        limit=limit
    )

    return results.get("users", [])


@router.get("/suggestions/", response_model=TrendingResponse)
async def get_search_suggestions(
    limit: int = Query(5, ge=1, le=20, description="Number of suggestions"),
    db: Session = Depends(get_db)
):
    """
    Get trending search terms and popular areas.

    Based on recent report activity and search patterns.
    """
    search_service = get_search_service(db)
    trending = search_service.get_trending_searches(limit=limit)

    # Could add recent areas based on reports
    return {
        "trending": trending,
        "recent_areas": []  # TODO: Implement based on report locations
    }
