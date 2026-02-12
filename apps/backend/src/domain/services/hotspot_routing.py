"""
Hotspot-Aware Routing Integration Module

Provides hotspot data fetching and route analysis for flood-safe navigation.
Implements HARD AVOID strategy: routes must avoid HIGH/EXTREME FHI hotspots.

Part of FloodSafe - Nonprofit flood monitoring platform.
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
import logging
from geopy.distance import geodesic

from src.core.config import settings

logger = logging.getLogger(__name__)

# Proximity threshold for hotspot detection (meters)
HOTSPOT_PROXIMITY_METERS = 300

# FHI level thresholds
class FHILevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


# FHI-based delay penalties (seconds) - only for MODERATE level
# HIGH and EXTREME are HARD AVOID - route must not pass through
FHI_DELAY_PENALTIES = {
    FHILevel.LOW: 0,           # No penalty
    FHILevel.MODERATE: 60,     # 1 minute warning delay
    # HIGH and EXTREME: Route rejected, not penalized
}


@dataclass
class HotspotRisk:
    """
    Represents a hotspot's risk assessment relative to a route.
    Used for route analysis and UI display.
    """
    id: int
    name: str
    lat: float
    lng: float
    zone: str
    fhi_score: float
    fhi_level: str
    fhi_color: str
    severity_history: str
    distance_to_route_m: float
    estimated_delay_seconds: int
    must_avoid: bool  # True if HIGH or EXTREME

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class RouteHotspotAnalysis:
    """
    Complete hotspot analysis for a route.
    """
    total_hotspots_nearby: int
    hotspots_to_avoid: int
    hotspots_with_warnings: int
    highest_fhi_score: Optional[float]
    highest_fhi_level: Optional[str]
    total_delay_seconds: int
    route_is_safe: bool  # False if any HIGH/EXTREME hotspots within proximity
    must_reroute: bool   # True if HARD AVOID hotspots detected
    nearby_hotspots: List[HotspotRisk]
    warning_message: Optional[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_hotspots_nearby": self.total_hotspots_nearby,
            "hotspots_to_avoid": self.hotspots_to_avoid,
            "hotspots_with_warnings": self.hotspots_with_warnings,
            "highest_fhi_score": self.highest_fhi_score,
            "highest_fhi_level": self.highest_fhi_level,
            "total_delay_seconds": self.total_delay_seconds,
            "route_is_safe": self.route_is_safe,
            "must_reroute": self.must_reroute,
            "nearby_hotspots": [h.to_dict() for h in self.nearby_hotspots],
            "warning_message": self.warning_message,
        }


async def fetch_hotspots_with_fhi(
    include_fhi: bool = True,
    test_fhi_override: str = None,
    city: str = "delhi",
) -> List[Dict]:
    """
    Fetch all hotspots for a city with current FHI scores from ML service.

    Returns empty list if ML service is unavailable (graceful degradation).

    Args:
        include_fhi: Whether to include live FHI calculation (default True)
        test_fhi_override: Override FHI for testing: 'high', 'extreme', or 'mixed'
        city: City key (delhi, bangalore, yogyakarta)

    Returns:
        List of GeoJSON features with hotspot properties
    """
    if not settings.ML_SERVICE_ENABLED:
        logger.info("ML service disabled, skipping hotspot fetch")
        return []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {"include_rainfall": "true", "city": city} if include_fhi else {"city": city}
            if test_fhi_override:
                params["test_fhi_override"] = test_fhi_override
                logger.info(f"Fetching hotspots with TEST MODE: {test_fhi_override}")
            response = await client.get(
                f"{settings.ML_SERVICE_URL}/api/v1/hotspots/all",
                params=params
            )

            if response.status_code == 200:
                data = response.json()
                features = data.get("features", [])
                logger.info(f"Fetched {len(features)} hotspots with FHI data")
                return features
            else:
                logger.warning(f"Hotspots fetch returned status {response.status_code}")
                return []

    except httpx.TimeoutException:
        logger.warning("Hotspot fetch timed out after 30s")
        return []
    except httpx.RequestError as e:
        logger.warning(f"Failed to fetch hotspots: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching hotspots: {e}")
        return []


def find_hotspots_near_route(
    route_coords: List[List[float]],  # [[lng, lat], ...]
    hotspots: List[Dict],
    proximity_m: float = HOTSPOT_PROXIMITY_METERS
) -> List[HotspotRisk]:
    """
    Find hotspots within proximity of a route path.

    Samples every 10th route point for performance on long routes.

    Args:
        route_coords: List of [longitude, latitude] coordinates
        hotspots: GeoJSON features from fetch_hotspots_with_fhi()
        proximity_m: Buffer distance in meters (default 300m)

    Returns:
        List of HotspotRisk sorted by distance (closest first)
    """
    if not route_coords or not hotspots:
        return []

    nearby: List[HotspotRisk] = []
    proximity_km = proximity_m / 1000.0

    for hotspot in hotspots:
        props = hotspot.get("properties", {})
        geometry = hotspot.get("geometry", {})
        coords = geometry.get("coordinates", [])

        if len(coords) < 2:
            continue

        # Hotspot coordinates [lng, lat] -> (lat, lng) for geopy
        hotspot_point = (coords[1], coords[0])
        min_distance_km = float("inf")

        # Sample route points (every 10th for performance)
        sample_step = max(1, len(route_coords) // 100)  # At most 100 samples
        for route_coord in route_coords[::sample_step]:
            if len(route_coord) < 2:
                continue
            route_point = (route_coord[1], route_coord[0])  # [lng, lat] -> (lat, lng)

            try:
                distance = geodesic(route_point, hotspot_point).kilometers
                min_distance_km = min(min_distance_km, distance)

                # Early exit if very close
                if min_distance_km < 0.05:  # 50m
                    break
            except Exception:
                continue

        if min_distance_km <= proximity_km:
            fhi_level = props.get("fhi_level", "moderate").lower()
            fhi_score = props.get("fhi_score", 0.25)

            # Determine if this hotspot requires HARD AVOID
            must_avoid = fhi_level in [FHILevel.HIGH.value, FHILevel.EXTREME.value]

            # Calculate delay only for MODERATE (HIGH/EXTREME are avoided entirely)
            if must_avoid:
                delay = 0  # Route should be rejected, not delayed
            else:
                delay = FHI_DELAY_PENALTIES.get(FHILevel(fhi_level), 0)

            nearby.append(HotspotRisk(
                id=props.get("id", 0),
                name=props.get("name", "Unknown Hotspot"),
                lat=coords[1],
                lng=coords[0],
                zone=props.get("zone", "unknown"),
                fhi_score=fhi_score,
                fhi_level=fhi_level,
                fhi_color=props.get("fhi_color", "#9ca3af"),
                severity_history=props.get("severity_history", "moderate"),
                distance_to_route_m=round(min_distance_km * 1000, 1),
                estimated_delay_seconds=delay,
                must_avoid=must_avoid,
            ))

    # Sort by distance (closest first)
    nearby.sort(key=lambda h: h.distance_to_route_m)
    return nearby


def analyze_route_hotspots(
    route_coords: List[List[float]],
    hotspots: List[Dict],
    proximity_m: float = HOTSPOT_PROXIMITY_METERS
) -> RouteHotspotAnalysis:
    """
    Perform complete hotspot analysis for a route.

    Implements HARD AVOID strategy:
    - Routes with HIGH/EXTREME hotspots within proximity are marked unsafe
    - MODERATE hotspots add delay penalties and warnings
    - LOW hotspots are noted but don't affect routing

    Args:
        route_coords: List of [longitude, latitude] coordinates
        hotspots: GeoJSON features from fetch_hotspots_with_fhi()
        proximity_m: Buffer distance in meters

    Returns:
        RouteHotspotAnalysis with safety assessment and details
    """
    nearby = find_hotspots_near_route(route_coords, hotspots, proximity_m)

    if not nearby:
        return RouteHotspotAnalysis(
            total_hotspots_nearby=0,
            hotspots_to_avoid=0,
            hotspots_with_warnings=0,
            highest_fhi_score=None,
            highest_fhi_level=None,
            total_delay_seconds=0,
            route_is_safe=True,
            must_reroute=False,
            nearby_hotspots=[],
            warning_message=None,
        )

    # Count by category
    hotspots_to_avoid = [h for h in nearby if h.must_avoid]
    hotspots_with_warnings = [h for h in nearby if h.fhi_level == FHILevel.MODERATE.value]

    # Calculate totals
    total_delay = sum(h.estimated_delay_seconds for h in nearby)
    highest_fhi = max(nearby, key=lambda h: h.fhi_score)

    # Determine if route is safe (no HARD AVOID hotspots)
    must_reroute = len(hotspots_to_avoid) > 0
    route_is_safe = not must_reroute

    # Generate warning message
    warning_message = _generate_warning_message(hotspots_to_avoid, hotspots_with_warnings)

    return RouteHotspotAnalysis(
        total_hotspots_nearby=len(nearby),
        hotspots_to_avoid=len(hotspots_to_avoid),
        hotspots_with_warnings=len(hotspots_with_warnings),
        highest_fhi_score=highest_fhi.fhi_score,
        highest_fhi_level=highest_fhi.fhi_level,
        total_delay_seconds=total_delay,
        route_is_safe=route_is_safe,
        must_reroute=must_reroute,
        nearby_hotspots=nearby[:10],  # Limit to top 10 for UI
        warning_message=warning_message,
    )


def _generate_warning_message(
    avoid_hotspots: List[HotspotRisk],
    warning_hotspots: List[HotspotRisk]
) -> Optional[str]:
    """
    Generate user-friendly warning message based on hotspot analysis.
    """
    if not avoid_hotspots and not warning_hotspots:
        return None

    extreme_count = sum(1 for h in avoid_hotspots if h.fhi_level == FHILevel.EXTREME.value)
    high_count = sum(1 for h in avoid_hotspots if h.fhi_level == FHILevel.HIGH.value)
    moderate_count = len(warning_hotspots)

    parts = []

    if extreme_count > 0:
        hotspot_names = [h.name for h in avoid_hotspots if h.fhi_level == FHILevel.EXTREME.value][:2]
        names_str = ", ".join(hotspot_names)
        parts.append(f"DANGER: {extreme_count} extreme flood risk area(s) - {names_str}")

    if high_count > 0:
        hotspot_names = [h.name for h in avoid_hotspots if h.fhi_level == FHILevel.HIGH.value][:2]
        names_str = ", ".join(hotspot_names)
        parts.append(f"WARNING: {high_count} high flood risk area(s) - {names_str}")

    if moderate_count > 0 and not avoid_hotspots:
        parts.append(f"Caution: {moderate_count} waterlogging hotspot(s) along route")

    if parts:
        if avoid_hotspots:
            return " | ".join(parts) + " - Route must be changed"
        return " | ".join(parts)

    return None


def calculate_hotspots_avoided(
    normal_analysis: RouteHotspotAnalysis,
    safe_analysis: RouteHotspotAnalysis
) -> Dict:
    """
    Compare two route analyses to calculate hotspots avoided.

    Args:
        normal_analysis: Analysis of the normal/fastest route
        safe_analysis: Analysis of the FloodSafe alternative route

    Returns:
        Dictionary with comparison metrics
    """
    avoided_count = normal_analysis.total_hotspots_nearby - safe_analysis.total_hotspots_nearby
    avoid_hotspots_diff = normal_analysis.hotspots_to_avoid - safe_analysis.hotspots_to_avoid

    # Names of hotspots avoided
    normal_ids = {h.id for h in normal_analysis.nearby_hotspots}
    safe_ids = {h.id for h in safe_analysis.nearby_hotspots}
    avoided_ids = normal_ids - safe_ids

    avoided_hotspots = [
        h for h in normal_analysis.nearby_hotspots
        if h.id in avoided_ids
    ]

    return {
        "total_hotspots_avoided": max(0, avoided_count),
        "critical_hotspots_avoided": max(0, avoid_hotspots_diff),
        "time_saved_seconds": max(0, normal_analysis.total_delay_seconds - safe_analysis.total_delay_seconds),
        "avoided_hotspot_names": [h.name for h in avoided_hotspots[:5]],
        "normal_route_safe": normal_analysis.route_is_safe,
        "safe_route_safe": safe_analysis.route_is_safe,
    }
