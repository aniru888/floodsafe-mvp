"""
Search Service - Unified search across locations, reports, and users.

Provides intelligent search with:
- Location geocoding (Photon + Nominatim with caching)
- Full-text search on reports
- User search by username/display name
- Smart query intent detection
"""

import httpx
import math
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, text
from geoalchemy2.functions import ST_X, ST_Y, ST_DWithin, ST_MakePoint, ST_SetSRID
import json
import re

from ...infrastructure import models
from .location_aliases import expand_query_with_aliases, get_alias_suggestions


# Simple in-memory cache for geocoding results
_geocode_cache: Dict[str, tuple[List[Dict], datetime]] = {}
CACHE_TTL_MINUTES = 60  # Cache geocoding results for 1 hour


class SearchService:
    """Unified search service for FloodSafe."""

    def __init__(self, db: Session):
        self.db = db

    async def unified_search(
        self,
        query: str,
        search_type: Optional[str] = None,  # 'all', 'locations', 'reports', 'users'
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_meters: float = 5000,
        limit: int = 10,
        city_bounds: Optional[Dict[str, float]] = None  # {min_lat, max_lat, min_lng, max_lng}
    ) -> Dict[str, Any]:
        """
        Perform unified search across all entity types.

        Args:
            query: Search string
            search_type: Filter to specific type or 'all' for combined
            latitude/longitude: Center point for spatial searches
            radius_meters: Search radius for spatial queries
            limit: Max results per category
            city_bounds: Optional bounds to filter location results

        Returns:
            {
                "query": original query,
                "intent": detected intent,
                "locations": [...],
                "reports": [...],
                "users": [...],
                "suggestions": [...]
            }
        """
        if not query or len(query.strip()) < 2:
            return {
                "query": query,
                "intent": "empty",
                "locations": [],
                "reports": [],
                "users": [],
                "suggestions": []
            }

        query = query.strip()
        intent = self._detect_intent(query)

        results = {
            "query": query,
            "intent": intent,
            "locations": [],
            "reports": [],
            "users": [],
            "suggestions": []
        }

        # Determine which searches to run based on type or intent
        run_locations = search_type in (None, 'all', 'locations')
        run_reports = search_type in (None, 'all', 'reports')
        run_users = search_type in (None, 'all', 'users')

        # Run searches based on detected intent for optimal results
        if intent == 'location' or run_locations:
            results["locations"] = await self._search_locations(
                query, limit, city_bounds, latitude=latitude, longitude=longitude
            )

        if intent == 'report' or run_reports:
            results["reports"] = self._search_reports(
                query, latitude, longitude, radius_meters, limit
            )

        if intent == 'user' or run_users:
            results["users"] = self._search_users(query, limit)

        # Generate smart suggestions based on results
        results["suggestions"] = self._generate_suggestions(query, results)

        return results

    def _detect_intent(self, query: str) -> str:
        """
        Detect user intent from query patterns.

        Returns: 'location', 'report', 'user', or 'mixed'
        """
        query_lower = query.lower()

        # Explicit prefixes
        if query_lower.startswith('@location:') or query_lower.startswith('loc:'):
            return 'location'
        if query_lower.startswith('@report:') or query_lower.startswith('flood:'):
            return 'report'
        if query_lower.startswith('@user:') or query_lower.startswith('user:'):
            return 'user'

        # Location indicators
        location_keywords = [
            'road', 'street', 'colony', 'sector', 'block', 'market',
            'nagar', 'vihar', 'puri', 'puram', 'bagh', 'chowk',
            'station', 'metro', 'airport', 'hospital', 'mall',
            'near', 'area', 'locality', 'place'
        ]
        if any(kw in query_lower for kw in location_keywords):
            return 'location'

        # Report/flood indicators
        flood_keywords = [
            'flood', 'water', 'waterlog', 'rain', 'drainage',
            'overflow', 'submerge', 'blocked', 'stuck', 'impassable',
            'deep', 'knee', 'waist', 'ankle'
        ]
        if any(kw in query_lower for kw in flood_keywords):
            return 'report'

        # User indicators (starts with @)
        if query.startswith('@') and not query.startswith('@location') and not query.startswith('@report'):
            return 'user'

        # Default to mixed search
        return 'mixed'

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in meters between two points."""
        R = 6371000  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    async def _search_photon(
        self,
        query: str,
        lat: Optional[float],
        lng: Optional[float],
        limit: int = 20,
        lang: str = "en"
    ) -> List[Dict]:
        """
        Search locations using Photon geocoder API.

        Args:
            query: Search string
            lat/lng: Optional location bias for prioritizing nearby results
            limit: Maximum number of results
            lang: Language code for results

        Returns:
            List of location dicts in Nominatim-compatible format
        """
        try:
            params = {
                "q": query,
                "limit": limit,
                "lang": lang
            }

            # Add location bias if provided
            if lat is not None and lng is not None:
                params["lat"] = lat
                params["lon"] = lng

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://photon.komoot.io/api",
                    params=params,
                    headers={"User-Agent": "FloodSafe-MVP/1.0 (https://floodsafe.app)"}
                )

                logger.info(f"Photon HTTP {response.status_code}, body length={len(response.text)}")

                if response.status_code != 200:
                    logger.info(f"Photon non-200: {response.text[:200]}")
                    return []

                data = response.json()

                # Parse GeoJSON FeatureCollection
                if data.get("type") != "FeatureCollection":
                    logger.info(f"Photon unexpected type: {data.get('type')}")
                    return []

                locations = []
                for feature in data.get("features", []):
                    props = feature.get("properties", {})
                    coords = feature.get("geometry", {}).get("coordinates", [])

                    if len(coords) < 2:
                        continue

                    # Extract coordinates (GeoJSON is [lng, lat])
                    result_lng, result_lat = coords[0], coords[1]

                    # Build address dict (map Photon fields to Nominatim-style)
                    address = {}
                    if props.get("street"):
                        address["road"] = props["street"]
                    if props.get("housenumber"):
                        address["house_number"] = props["housenumber"]
                    if props.get("postcode"):
                        address["postcode"] = props["postcode"]
                    if props.get("city"):
                        address["city"] = props["city"]
                    if props.get("state"):
                        address["state"] = props["state"]
                    if props.get("country"):
                        address["country"] = props["country"]

                    # Use name as suburb if it's a place/locality
                    if props.get("osm_key") == "place" and props.get("name"):
                        address["suburb"] = props["name"]

                    # Build formatted name (similar to _format_location_name)
                    name_parts = []
                    if props.get("name"):
                        name_parts.append(props["name"])
                    if props.get("street"):
                        name_parts.append(props["street"])
                    if props.get("city"):
                        name_parts.append(props["city"])
                    formatted_name = ", ".join(name_parts[:3]) if name_parts else props.get("name", "")

                    # Build display name from all available address parts
                    display_parts = [
                        props.get("name"),
                        props.get("street"),
                        props.get("city"),
                        props.get("state"),
                        props.get("country")
                    ]
                    display_name = ", ".join(p for p in display_parts if p)

                    # Estimate importance from OSM value (default 0.5)
                    importance = 0.5
                    osm_value = props.get("osm_value", "")
                    # Higher importance for major features
                    if osm_value in ["city", "town"]:
                        importance = 0.9
                    elif osm_value in ["suburb", "neighbourhood", "village"]:
                        importance = 0.7
                    elif osm_value in ["road", "street"]:
                        importance = 0.6

                    locations.append({
                        "type": "location",
                        "display_name": display_name,
                        "lat": float(result_lat),
                        "lng": float(result_lng),
                        "address": address,
                        "importance": importance,
                        "formatted_name": formatted_name
                    })

                return locations

        except Exception as e:
            logger.info(f"Photon search error: {e}", exc_info=True)
            return []

    async def _search_nominatim(
        self,
        query: str,
        city_bounds: Optional[Dict[str, float]] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Search locations using Nominatim geocoder API."""
        try:
            params = {
                "q": query,
                "format": "json",
                "limit": limit,
                "countrycodes": city_bounds.get("country_code", "in") if city_bounds else "in",
                "addressdetails": 1,
                "dedupe": 0
            }

            if city_bounds:
                params["viewbox"] = (
                    f"{city_bounds['min_lng']},{city_bounds['max_lat']},"
                    f"{city_bounds['max_lng']},{city_bounds['min_lat']}"
                )
                params["bounded"] = 1

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params=params,
                    headers={"User-Agent": "FloodSafe-MVP/1.0 (https://floodsafe.app)"}
                )

                if response.status_code != 200:
                    return []

                results = response.json()

                return [
                    {
                        "type": "location",
                        "display_name": r.get("display_name", ""),
                        "lat": float(r.get("lat", 0)),
                        "lng": float(r.get("lon", 0)),
                        "address": r.get("address", {}),
                        "importance": float(r.get("importance", 0)),
                        "formatted_name": self._format_location_name(r)
                    }
                    for r in results
                ]
        except Exception as e:
            logger.error(f"Nominatim search error: {e}")
            return []

    async def _search_locations(
        self,
        query: str,
        limit: int,
        city_bounds: Optional[Dict[str, float]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> List[Dict]:
        """
        Search locations using Photon + Nominatim with caching.
        Expands common abbreviations (HSR -> HSR Layout Bangalore) for better results.
        Uses dual-source strategy: Photon for speed, Nominatim as supplement.
        """
        # Clean query of prefixes
        clean_query = re.sub(r'^(@location:|loc:)\s*', '', query, flags=re.IGNORECASE)

        # Expand query with location aliases for Nominatim
        # "HSR" -> "HSR Layout Bangalore", "CP" -> "Connaught Place Delhi"
        expanded_query = expand_query_with_aliases(clean_query)

        # Check cache using expanded query
        cache_key = f"photon:{clean_query.lower()}"
        if cache_key in _geocode_cache:
            cached_results, cached_time = _geocode_cache[cache_key]
            if datetime.utcnow() - cached_time < timedelta(minutes=CACHE_TTL_MINUTES):
                # Filter by bounds if provided
                if city_bounds:
                    filtered = self._filter_by_bounds(cached_results, city_bounds, limit)
                    return filtered
                return cached_results[:limit]

        # Default to city center when no user location provided (Photon needs geo-bias
        # from non-Indian servers like Koyeb Frankfurt to return Indian results)
        photon_lat = latitude if latitude is not None else (city_bounds.get('min_lat', 28.6) + city_bounds.get('max_lat', 28.7)) / 2 if city_bounds else 28.6315
        photon_lng = longitude if longitude is not None else (city_bounds.get('min_lng', 77.1) + city_bounds.get('max_lng', 77.3)) / 2 if city_bounds else 77.2167

        # Photon first (no rate limits, fast), Nominatim only as fallback
        # Nominatim has strict 1 req/sec policy — don't waste it when Photon succeeds
        logger.info(f"Search: Photon query='{clean_query}' lat={photon_lat} lng={photon_lng}")
        photon_results = await self._search_photon(
            clean_query, lat=photon_lat, lng=photon_lng, limit=20
        )
        logger.info(f"Search: Photon returned {len(photon_results)} results")

        # Only fall back to Nominatim if Photon returned too few results
        nominatim_results = []
        if len(photon_results) < 3:
            nominatim_results = await self._search_nominatim(
                expanded_query, city_bounds, limit=20
            )
            logger.info(f"Search: Nominatim fallback returned {len(nominatim_results)} results")

        # Merge Photon + Nominatim results, deduplicate by coordinates
        merged_results = photon_results.copy()

        for nom_result in nominatim_results:
            # Check if this coordinate already exists in merged results
            is_duplicate = False
            for existing in merged_results:
                if (abs(existing["lat"] - nom_result["lat"]) < 0.0005 and
                    abs(existing["lng"] - nom_result["lng"]) < 0.0005):
                    is_duplicate = True
                    break

            if not is_duplicate:
                merged_results.append(nom_result)

        # Sort results
        if latitude is not None and longitude is not None:
            # Sort by distance to user
            for result in merged_results:
                result["_distance"] = self._haversine_distance(
                    latitude, longitude, result["lat"], result["lng"]
                )
            merged_results.sort(key=lambda x: x.get("_distance", float('inf')))
            # Remove temporary distance field
            for result in merged_results:
                result.pop("_distance", None)
        else:
            # Sort by importance descending
            merged_results.sort(key=lambda x: x.get("importance", 0), reverse=True)

        # Cache merged results
        _geocode_cache[cache_key] = (merged_results, datetime.utcnow())

        # Filter by bounds if provided
        if city_bounds:
            return self._filter_by_bounds(merged_results, city_bounds, limit)

        return merged_results[:limit]

    def _format_location_name(self, result: Dict) -> str:
        """Format location name for display."""
        addr = result.get("address", {})
        parts = []

        if addr.get("road"):
            parts.append(addr["road"])
        if addr.get("neighbourhood"):
            parts.append(addr["neighbourhood"])
        if addr.get("suburb"):
            parts.append(addr["suburb"])
        if addr.get("city") or addr.get("town") or addr.get("village"):
            parts.append(addr.get("city") or addr.get("town") or addr.get("village"))

        if parts:
            return ", ".join(parts[:3])

        # Fallback to display_name
        return ", ".join(result.get("display_name", "").split(",")[:3])

    def _filter_by_bounds(
        self,
        locations: List[Dict],
        bounds: Dict[str, float],
        limit: int
    ) -> List[Dict]:
        """Filter locations to city bounds."""
        filtered = [
            loc for loc in locations
            if (bounds["min_lat"] <= loc["lat"] <= bounds["max_lat"] and
                bounds["min_lng"] <= loc["lng"] <= bounds["max_lng"])
        ]
        return filtered[:limit]

    def _search_reports(
        self,
        query: str,
        latitude: Optional[float],
        longitude: Optional[float],
        radius_meters: float,
        limit: int
    ) -> List[Dict]:
        """
        Search reports by description text and optional location.
        Uses ILIKE for text matching (PostgreSQL case-insensitive).
        """
        # Clean query of prefixes
        clean_query = re.sub(r'^(@report:|flood:)\s*', '', query, flags=re.IGNORECASE)

        # Build base query
        base_query = self.db.query(
            models.Report,
            ST_Y(models.Report.location).label('lat'),
            ST_X(models.Report.location).label('lng')
        )

        # Text search on description
        search_terms = clean_query.split()
        if search_terms:
            # Match any term in description
            conditions = [
                models.Report.description.ilike(f"%{term}%")
                for term in search_terms
            ]
            base_query = base_query.filter(or_(*conditions))

        # Optional spatial filter
        if latitude is not None and longitude is not None:
            point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
            base_query = base_query.filter(
                ST_DWithin(
                    models.Report.location,
                    point,
                    radius_meters,
                    use_spheroid=True
                )
            )

        # Order by recency and limit
        results = base_query.order_by(
            models.Report.timestamp.desc()
        ).limit(limit).all()

        # Transform results
        reports = []
        for report, lat, lng in results:
            reports.append({
                "type": "report",
                "id": str(report.id),
                "description": report.description or "",
                "lat": float(lat) if lat else None,
                "lng": float(lng) if lng else None,
                "water_depth": report.water_depth,
                "vehicle_passability": report.vehicle_passability,
                "verified": report.verified,
                "timestamp": report.timestamp.isoformat() if report.timestamp else None,
                "media_url": report.media_url,
                "highlight": self._highlight_match(report.description, clean_query)
            })

        return reports

    def _highlight_match(self, text: str, query: str) -> str:
        """Return snippet with matching terms highlighted."""
        if not text:
            return ""

        # Find first matching term position
        text_lower = text.lower()
        query_terms = query.lower().split()

        start_pos = 0
        for term in query_terms:
            pos = text_lower.find(term)
            if pos != -1:
                start_pos = max(0, pos - 30)
                break

        # Extract snippet
        snippet = text[start_pos:start_pos + 100]
        if start_pos > 0:
            snippet = "..." + snippet
        if len(text) > start_pos + 100:
            snippet = snippet + "..."

        return snippet

    def _search_users(self, query: str, limit: int) -> List[Dict]:
        """
        Search users by username or display name.
        """
        # Clean query of prefixes
        clean_query = re.sub(r'^(@user:|user:|@)\s*', '', query, flags=re.IGNORECASE)

        # Search both username and display_name
        results = self.db.query(models.User).filter(
            or_(
                models.User.username.ilike(f"%{clean_query}%"),
                models.User.display_name.ilike(f"%{clean_query}%")
            ),
            models.User.profile_public == True  # Only public profiles
        ).order_by(
            models.User.points.desc()  # Sort by reputation
        ).limit(limit).all()

        return [
            {
                "type": "user",
                "id": str(user.id),
                "username": user.username,
                "display_name": user.display_name,
                "points": user.points,
                "level": user.level,
                "reports_count": user.reports_count,
                "profile_photo_url": user.profile_photo_url
            }
            for user in results
        ]

    def _generate_suggestions(
        self,
        query: str,
        results: Dict[str, Any]
    ) -> List[Dict]:
        """
        Generate smart search suggestions based on results.
        """
        suggestions = []

        # If no results, suggest variations
        total_results = (
            len(results.get("locations", [])) +
            len(results.get("reports", [])) +
            len(results.get("users", []))
        )

        if total_results == 0:
            suggestions.append({
                "type": "tip",
                "text": f"No results for \"{query}\". Try:",
                "options": [
                    "Using simpler terms",
                    "Checking spelling",
                    "Searching for a nearby landmark"
                ]
            })

        # Suggest category-specific searches
        if results.get("locations") and not results.get("reports"):
            suggestions.append({
                "type": "action",
                "text": f"View flood reports near {results['locations'][0]['formatted_name']}",
                "action": "search_reports_near_location",
                "data": results['locations'][0]
            })

        # Popular searches in the area (could be expanded with analytics)
        if results["intent"] == "location":
            suggestions.append({
                "type": "popular",
                "text": "Popular searches: flooding, waterlogging, road conditions"
            })

        return suggestions

    def get_trending_searches(self, limit: int = 5) -> List[str]:
        """
        Get trending search terms based on recent reports.
        """
        # Get recent report descriptions and extract common terms
        recent_reports = self.db.query(models.Report.description).filter(
            models.Report.timestamp > datetime.utcnow() - timedelta(days=7)
        ).limit(100).all()

        # Simple word frequency (could be improved with NLP)
        word_count: Dict[str, int] = {}
        stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'is', 'it'}

        for (desc,) in recent_reports:
            if desc:
                words = desc.lower().split()
                for word in words:
                    word = re.sub(r'[^\w]', '', word)
                    if len(word) > 3 and word not in stop_words:
                        word_count[word] = word_count.get(word, 0) + 1

        # Return top trending terms
        trending = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in trending[:limit]]


def get_search_service(db: Session) -> SearchService:
    """Factory function to create SearchService."""
    return SearchService(db)
