#!/usr/bin/env python3
"""
Batch geocode location aliases for map label display.

Extracts unique locations from LOCATION_ALIASES, deduplicates,
assigns tiers (zoom levels), geocodes with road-snapping,
and outputs GeoJSON files per city for the frontend.

Usage:
    python apps/backend/scripts/geocode_alias_labels.py
    python apps/backend/scripts/geocode_alias_labels.py --city delhi
    python apps/backend/scripts/geocode_alias_labels.py --city singapore --resume
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from collections import defaultdict

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PHOTON_URL = "https://photon.komoot.io/api/"  # No rate limit, OSM-based
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
HEADERS = {"User-Agent": "FloodSafe/1.0 (flood-monitoring-nonprofit)"}
PHOTON_DELAY = 0.3  # Photon has no rate limit, but be polite
NOMINATIM_DELAY = 1.5  # Nominatim reverse: 1 req/sec policy

# City config: center (for Photon geo-bias), bounds (for validation)
# Expanded Delhi to include NCR (Noida, Gurugram, Faridabad, Ghaziabad)
CITY_CONFIG = {
    "delhi": {
        "center": (28.6139, 77.2090),  # (lat, lng)
        "bounds": {"min_lat": 28.35, "max_lat": 28.95, "min_lng": 76.80, "max_lng": 77.55},
    },
    "bangalore": {
        "center": (12.9716, 77.5946),
        "bounds": {"min_lat": 12.60, "max_lat": 13.40, "min_lng": 77.20, "max_lng": 77.90},
    },
    "yogyakarta": {
        "center": (-7.7956, 110.3695),
        "bounds": {"min_lat": -8.05, "max_lat": -7.55, "min_lng": 110.20, "max_lng": 110.60},
    },
    "singapore": {
        "center": (1.3521, 103.8198),
        "bounds": {"min_lat": 1.15, "max_lat": 1.50, "min_lng": 103.55, "max_lng": 104.10},
    },
    "indore": {
        "center": (22.7196, 75.8577),
        "bounds": {"min_lat": 22.45, "max_lat": 22.90, "min_lng": 75.65, "max_lng": 76.05},
    },
}

# Patterns for city detection from display name
CITY_PATTERNS = {
    "delhi": re.compile(r"(?:Delhi|New Delhi|NCR)", re.I),
    "bangalore": re.compile(r"(?:Bangalore|Bengaluru)", re.I),
    "yogyakarta": re.compile(r"(?:Yogyakarta|Jogja|Sleman|Bantul|DIY|Prambanan|Kalasan)", re.I),
    "singapore": re.compile(r"Singapore", re.I),
    "indore": re.compile(r"(?:Indore|Mhow|Pithampur|Sanwer|Simrol|Rau)", re.I),
}

# NCR satellite cities → treat as Delhi
NCR_PATTERNS = re.compile(
    r"(?:Noida|Greater Noida|Gurugram|Gurgaon|Faridabad|Ghaziabad|Indirapuram|Vaishali|Dwarka)", re.I
)

# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------

# Keywords that push an alias to tier 3 (most specific)
TIER3_PATTERNS = re.compile(
    r"(?:"
    r"\b(?:Block|Phase|Sector|Stage|Lane|Gali|Cross)\s*\d"
    r"|Hawker Centre|Food Centre|Kopitiam"
    r"|\bSR\s*\d"  # Student Residence numbers
    r"|\bScheme\s*\d"  # Indore scheme numbers
    r"|1st Block|2nd Block|3rd Block|4th Block|5th Block|6th Block|7th Block|8th Block"
    r"|1st Stage|2nd Stage|3rd Stage"
    r"|Extension$"
    r")", re.I
)

# Keywords for tier 2 (moderate)
TIER2_PATTERNS = re.compile(
    r"(?:"
    r"(?:Metro|MRT|Station|LRT)\b"
    r"|(?:Road|Marg|Flyover|Underpass|Bridge|Expressway|Highway|Bypass)\b"
    r"|(?:Mall|Plaza|City Mall|Mega Mall)\b"
    r"|(?:Tech Park|IT Park|Technology Park|Software Park|Industrial)\b"
    r"|(?:University|Institute|College|Academy|IIM|IIT|NUS|NTU)\b"
    r"|(?:Hospital|Medical|AIIMS)\b"
    r"|(?:Lake|Tank|Pond)\b"
    r"|(?:Market|Bazaar|Haat)\b"
    r"|(?:Temple|Mosque|Church|Gurudwara)\b"
    r")", re.I
)

# Tier 1: Major area/district names (no numbers, not too specific)
# This is the default if nothing else matches AND the name is short/generic enough

# Area-type result classes from Nominatim that indicate polygon centroids
AREA_TYPES = {
    "administrative", "suburb", "village", "town", "city",
    "neighbourhood", "quarter", "hamlet", "county",
    "residential", "commercial", "industrial",
}


def detect_city(display_name: str) -> str | None:
    """Detect which city a display name belongs to."""
    # Check NCR first (before Delhi, since NCR names don't contain "Delhi")
    if NCR_PATTERNS.search(display_name):
        return "delhi"
    for city, pattern in CITY_PATTERNS.items():
        if pattern.search(display_name):
            return city
    return None


def assign_tier(display_name: str, clean_name: str) -> int:
    """Assign zoom tier: 1=always visible, 2=zoom 13+, 3=zoom 14.5+."""
    if TIER3_PATTERNS.search(clean_name) or TIER3_PATTERNS.search(display_name):
        return 3
    if TIER2_PATTERNS.search(clean_name) or TIER2_PATTERNS.search(display_name):
        return 2
    # Tier 1: short, generic area names (no numbers, not too long)
    # If the clean name has numbers or is very long, push to tier 2
    if re.search(r"\d", clean_name) or len(clean_name) > 30:
        return 2
    return 1


def assign_category(display_name: str) -> str:
    """Auto-classify the location into a category."""
    dn = display_name.lower()
    if any(kw in dn for kw in ("metro", "mrt", "lrt", "station")):
        return "metro_station"
    if any(kw in dn for kw in ("road", "marg", "jalan", "jl ")):
        return "road"
    if any(kw in dn for kw in ("mall", "plaza", "city mall")):
        return "mall"
    if any(kw in dn for kw in ("university", "institute", "college", "iim", "iit", "nus", "ntu", "ugm", "uny")):
        return "institution"
    if any(kw in dn for kw in ("lake", "tank", "river", "canal", "nadi", "sungai", "kali ")):
        return "water_body"
    if any(kw in dn for kw in ("temple", "mosque", "church", "gurudwara", "masjid")):
        return "religious"
    if any(kw in dn for kw in ("market", "bazaar", "haat", "pasar")):
        return "market"
    if any(kw in dn for kw in ("hospital", "medical", "aiims")):
        return "hospital"
    if any(kw in dn for kw in ("airport", "bandara")):
        return "airport"
    if any(kw in dn for kw in ("park", "garden", "taman")):
        return "park"
    if any(kw in dn for kw in ("flyover", "underpass", "bridge")):
        return "infrastructure"
    if any(kw in dn for kw in ("expressway", "highway", "bypass")):
        return "expressway"
    return "neighborhood"


def clean_display_name(display_name: str) -> str:
    """Strip city suffix from display name for map label."""
    # Remove trailing city names
    cleaned = display_name
    for suffix in [
        " Bangalore", " Bengaluru", " Delhi", " New Delhi", " NCR",
        " Yogyakarta", " Jogja", " Singapore", " Indore",
        " Sleman", " Bantul", " DIY",
        " Noida", " Greater Noida", " Gurugram", " Gurgaon",
        " Faridabad", " Ghaziabad",
    ]:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    return cleaned.strip()


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def _nominatim_request(url: str, params: dict, max_retries: int = 5) -> dict | None:
    """Make a Nominatim request with retry on 429 rate limit errors."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code == 429:
                wait = (attempt + 1) * 10  # 10s, 20s, 30s, 40s, 50s backoff
                print(f"429-wait{wait}s ", end="", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if "429" in str(e):
                wait = (attempt + 1) * 10
                print(f"429-wait{wait}s ", end="", flush=True)
                time.sleep(wait)
                continue
            print(f"    HTTP ERROR: {e}")
            return None
        except Exception as e:
            print(f"    REQUEST ERROR: {e}")
            return None
    print("    MAX RETRIES EXCEEDED")
    return None


def forward_geocode(query: str, city: str) -> dict | None:
    """Forward geocode using Photon (no rate limit, OSM-based)."""
    config = CITY_CONFIG[city]
    center_lat, center_lng = config["center"]
    params = {
        "q": query,
        "lat": center_lat,
        "lon": center_lng,
        "limit": 3,  # Get a few results to pick best
        "lang": "en",
    }
    try:
        resp = requests.get(PHOTON_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None

        # Pick the first result that falls within city bounds
        bounds = config["bounds"]
        for f in features:
            coords = f["geometry"]["coordinates"]  # [lng, lat]
            lat, lng = coords[1], coords[0]
            if (bounds["min_lat"] <= lat <= bounds["max_lat"]
                    and bounds["min_lng"] <= lng <= bounds["max_lng"]):
                props = f.get("properties", {})
                return {
                    "lat": lat,
                    "lng": lng,
                    "osm_type": props.get("osm_type", ""),
                    "type": props.get("type", ""),
                    "class": props.get("osm_key", ""),
                    "display": props.get("name", query),
                }

        # If no result in bounds, use first result anyway (might still be close)
        f = features[0]
        coords = f["geometry"]["coordinates"]
        props = f.get("properties", {})
        return {
            "lat": coords[1],
            "lng": coords[0],
            "osm_type": props.get("osm_type", ""),
            "type": props.get("type", ""),
            "class": props.get("osm_key", ""),
            "display": props.get("name", query),
        }
    except Exception as e:
        print(f"PHOTON ERROR: {e} ", end="")
    return None


def reverse_geocode_snap(lat: float, lng: float, city: str) -> dict | None:
    """Reverse geocode at zoom=16 (street level) to snap to nearest road."""
    config = CITY_CONFIG[city]
    params = {
        "lat": lat,
        "lon": lng,
        "zoom": 16,  # Street level
        "format": "json",
    }
    result = _nominatim_request(NOMINATIM_REVERSE_URL, params)
    if result and "lat" in result and "lon" in result:
        snapped_lat = float(result["lat"])
        snapped_lng = float(result["lon"])
        # Only use snapped coords if they're still within bounds
        bounds = config["bounds"]
        if (bounds["min_lat"] <= snapped_lat <= bounds["max_lat"]
                and bounds["min_lng"] <= snapped_lng <= bounds["max_lng"]):
            return {"lat": snapped_lat, "lng": snapped_lng}
    return None


def is_in_bounds(lat: float, lng: float, city: str) -> bool:
    """Check if coordinates fall within city bounds."""
    b = CITY_CONFIG[city]["bounds"]
    return b["min_lat"] <= lat <= b["max_lat"] and b["min_lng"] <= lng <= b["max_lng"]


def needs_road_snap(result: dict) -> bool:
    """Check if geocode result is an area polygon that should be snapped to road."""
    return (
        result["osm_type"] == "relation"
        or result["type"] in AREA_TYPES
        or result["class"] in ("boundary", "place", "landuse")
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def extract_unique_locations() -> dict[str, list[dict]]:
    """Extract and deduplicate locations from LOCATION_ALIASES."""
    # Add backend src to path for import
    backend_src = Path(__file__).resolve().parent.parent / "src"
    sys.path.insert(0, str(backend_src.parent))

    from src.domain.services.location_aliases import LOCATION_ALIASES

    # Deduplicate: group alias keys by display name
    reverse_map: dict[str, list[str]] = defaultdict(list)
    for alias_key, display_name in LOCATION_ALIASES.items():
        reverse_map[display_name].append(alias_key)

    # Organize by city
    by_city: dict[str, list[dict]] = defaultdict(list)
    skipped = 0

    for display_name, alias_keys in reverse_map.items():
        city = detect_city(display_name)
        if city is None:
            skipped += 1
            continue

        clean_name = clean_display_name(display_name)
        tier = assign_tier(display_name, clean_name)
        category = assign_category(display_name)

        by_city[city].append({
            "display_name": display_name,
            "clean_name": clean_name,
            "query": display_name,  # Use full name as geocoding query
            "tier": tier,
            "category": category,
            "alias_keys": alias_keys,
        })

    print(f"\n=== EXTRACTION SUMMARY ===")
    total = 0
    for city in sorted(by_city):
        count = len(by_city[city])
        tiers = defaultdict(int)
        for loc in by_city[city]:
            tiers[loc["tier"]] += 1
        print(f"  {city}: {count} unique locations (T1:{tiers[1]} T2:{tiers[2]} T3:{tiers[3]})")
        total += count
    print(f"  TOTAL: {total} unique locations ({skipped} skipped)")

    return dict(by_city)


def geocode_city(city: str, locations: list[dict], output_path: Path,
                 resume: bool = False, no_snap: bool = False) -> dict:
    """Geocode all locations for a city and output GeoJSON."""
    features = []
    failed = []
    snapped_count = 0

    # Load existing results if resuming
    existing_names = set()
    if resume and output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        features = existing.get("features", [])
        existing_names = {f["properties"]["name"] for f in features}
        print(f"  Resuming: {len(existing_names)} already geocoded")

    remaining = [loc for loc in locations if loc["clean_name"] not in existing_names]
    print(f"  Geocoding {len(remaining)} locations for {city}...")

    for i, loc in enumerate(remaining):
        print(f"  [{i+1}/{len(remaining)}] {loc['clean_name']}...", end=" ", flush=True)

        # Forward geocode
        result = forward_geocode(loc["query"], city)
        time.sleep(PHOTON_DELAY)

        if not result:
            print("NOT FOUND")
            failed.append(loc["clean_name"])
            continue

        lat, lng = result["lat"], result["lng"]

        # Check bounds
        if not is_in_bounds(lat, lng, city):
            print(f"OUT OF BOUNDS ({lat:.4f}, {lng:.4f})")
            failed.append(loc["clean_name"])
            continue

        # Road-snap if result is an area polygon (uses Nominatim reverse)
        if not no_snap and needs_road_snap(result):
            snapped = reverse_geocode_snap(lat, lng, city)
            time.sleep(NOMINATIM_DELAY)
            if snapped:
                lat, lng = snapped["lat"], snapped["lng"]
                snapped_count += 1
                print(f"SNAPPED ({lat:.4f}, {lng:.4f})")
            else:
                print(f"OK-area ({lat:.4f}, {lng:.4f})")
        else:
            print(f"OK ({lat:.4f}, {lng:.4f})")

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(lng, 6), round(lat, 6)],  # GeoJSON: [lng, lat]
            },
            "properties": {
                "name": loc["clean_name"],
                "tier": loc["tier"],
                "category": loc["category"],
            },
        })

        # Save progress every 50 features (resumable)
        if (i + 1) % 50 == 0:
            _write_geojson(output_path, features)
            print(f"  --- Progress saved: {len(features)} features ---")

    # Final save
    _write_geojson(output_path, features)

    stats = {
        "total": len(locations),
        "geocoded": len(features),
        "failed": len(failed),
        "snapped": snapped_count,
    }
    print(f"\n  {city} RESULTS: {stats['geocoded']}/{stats['total']} geocoded, "
          f"{stats['snapped']} road-snapped, {stats['failed']} failed")
    if failed:
        print(f"  Failed: {', '.join(failed[:20])}" + (" ..." if len(failed) > 20 else ""))

    return stats


def _write_geojson(path: Path, features: list[dict]):
    """Write GeoJSON FeatureCollection to file."""
    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(geojson, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Geocode location aliases for map labels")
    parser.add_argument("--city", choices=list(CITY_CONFIG.keys()), help="Geocode a specific city only")
    parser.add_argument("--resume", action="store_true", help="Resume from previous progress")
    parser.add_argument("--extract-only", action="store_true", help="Only extract and print stats, no geocoding")
    parser.add_argument("--no-snap", action="store_true", help="Skip Nominatim road-snapping (Photon coords only)")
    args = parser.parse_args()

    # Extract unique locations
    by_city = extract_unique_locations()

    if args.extract_only:
        return

    # Output directory
    frontend_public = Path(__file__).resolve().parent.parent.parent / "frontend" / "public"

    cities_to_process = [args.city] if args.city else list(CITY_CONFIG.keys())
    all_stats = {}

    for city in cities_to_process:
        if city not in by_city:
            print(f"\n  Skipping {city}: no aliases found")
            continue

        output_path = frontend_public / f"{city}-alias-labels.geojson"
        print(f"\n{'='*60}")
        print(f"  CITY: {city.upper()}")
        print(f"  Output: {output_path}")
        print(f"{'='*60}")

        stats = geocode_city(city, by_city[city], output_path,
                             resume=args.resume, no_snap=args.no_snap)
        all_stats[city] = stats

    # Print final summary
    print(f"\n{'='*60}")
    print("  FINAL SUMMARY")
    print(f"{'='*60}")
    total_geocoded = 0
    total_failed = 0
    for city, stats in all_stats.items():
        tiers = {"1": 0, "2": 0, "3": 0}
        geojson_path = frontend_public / f"{city}-alias-labels.geojson"
        if geojson_path.exists():
            data = json.loads(geojson_path.read_text(encoding="utf-8"))
            for f in data["features"]:
                tiers[str(f["properties"]["tier"])] += 1
        print(f"  {city}: {stats['geocoded']} features (T1:{tiers['1']} T2:{tiers['2']} T3:{tiers['3']})")
        total_geocoded += stats["geocoded"]
        total_failed += stats["failed"]
    print(f"  TOTAL: {total_geocoded} geocoded, {total_failed} failed")


if __name__ == "__main__":
    main()
