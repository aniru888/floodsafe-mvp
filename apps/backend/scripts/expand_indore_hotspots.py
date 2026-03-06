#!/usr/bin/env python3
"""
Expand Indore waterlogging hotspots from 37 to 60+.
Uses 4-tier geocoding fallback: Nominatim full → stripped → structured → Photon.

Sources:
- Free Press Journal (waterlogging road list)
- KnockSense (rainfall/waterlogging report)
- Ground Report (Smart City gaps)
- Daily Pioneer (CM review of waterlogging)
- IMC (Indore Municipal Corporation) records

Usage: python apps/backend/scripts/expand_indore_hotspots.py
"""

import json
import math
import time
import requests
from pathlib import Path
from datetime import datetime

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
PHOTON_URL = "https://photon.komoot.io/api/"
HEADERS = {"User-Agent": "FloodSafe/1.0 (flood-monitoring-nonprofit)"}

# Indore bounding box
BOUNDS = {"min_lat": 22.52, "max_lat": 22.85, "min_lng": 75.72, "max_lng": 75.97}
VIEWBOX = "75.72,22.85,75.97,22.52"  # left,top,right,bottom

# Rajwada center for zone calculation
RAJWADA = (22.7186, 75.8576)

# Dedup distance threshold (~111m)
DEDUP_THRESHOLD = 0.001


def load_existing_hotspots():
    """Load existing 37 hotspots for dedup."""
    path = Path(__file__).resolve().parent.parent / "data" / "indore_waterlogging_hotspots.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["hotspots"]


def is_duplicate(lat, lng, existing):
    """Check if coordinates are within DEDUP_THRESHOLD of any existing hotspot."""
    for h in existing:
        if abs(lat - h["lat"]) < DEDUP_THRESHOLD and abs(lng - h["lng"]) < DEDUP_THRESHOLD:
            return h["name"]
    return None


def is_in_bounds(lat, lng):
    return (BOUNDS["min_lat"] <= lat <= BOUNDS["max_lat"] and
            BOUNDS["min_lng"] <= lng <= BOUNDS["max_lng"])


def haversine_km(lat1, lng1, lat2, lng2):
    """Approximate distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def assign_zone(lat, lng):
    """Assign zone based on location relative to Indore landmarks."""
    dist_center = haversine_km(lat, lng, RAJWADA[0], RAJWADA[1])

    # Central: within 2km of Rajwada
    if dist_center < 2.0:
        return "Central"

    # South: south of Khan River (approx lat 22.71)
    if lat < 22.71:
        # Bypass: west of 75.85
        if lng < 75.85:
            return "Bypass"
        return "South"

    # Corridor: along AB Road (lng ~75.85-75.87, lat 22.71-22.75)
    if 75.84 <= lng <= 75.88 and 22.71 <= lat <= 22.75:
        return "Corridor"

    # Ring Road: roughly on the ring road belt (distance 3-5km from center)
    if 3.0 <= dist_center <= 6.0:
        return "Ring Road"

    # East/West split
    if lng > 75.87:
        return "East"
    if lng < 75.82:
        return "West"

    return "Other"


def geocode_nominatim_full(query):
    """Tier 1: Full free-text query."""
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "in",
        "viewbox": VIEWBOX,
        "bounded": 1,
    }
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"    Tier 1 error: {e}")
    return None


def geocode_nominatim_stripped(name):
    """Tier 2: Strip 'Square'/'Chowk' suffix and retry."""
    stripped = name.replace(" Square", "").replace(" Chowk", "").replace(" Chauraha", "")
    query = f"{stripped}, Indore, Madhya Pradesh"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "in",
        "viewbox": VIEWBOX,
        "bounded": 1,
    }
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"    Tier 2 error: {e}")
    return None


def geocode_nominatim_structured(name):
    """Tier 3: Structured query with street/city/state."""
    params = {
        "street": name,
        "city": "Indore",
        "state": "Madhya Pradesh",
        "country": "India",
        "format": "json",
        "limit": 1,
    }
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        results = resp.json()
        if results:
            lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
            if is_in_bounds(lat, lon):
                return lat, lon
    except Exception as e:
        print(f"    Tier 3 error: {e}")
    return None


def geocode_photon(query):
    """Tier 4: Photon API (no rate limit, same OSM data)."""
    params = {
        "q": f"{query}, Indore",
        "limit": 1,
        "lat": RAJWADA[0],
        "lon": RAJWADA[1],
    }
    try:
        resp = requests.get(PHOTON_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("features"):
            coords = data["features"][0]["geometry"]["coordinates"]
            lat, lon = coords[1], coords[0]  # GeoJSON: [lng, lat]
            if is_in_bounds(lat, lon):
                return lat, lon
    except Exception as e:
        print(f"    Tier 4 error: {e}")
    return None


def geocode_with_fallback(name, query):
    """4-tier geocoding with Nominatim rate limiting."""
    # Tier 1: Full query
    print(f"    Tier 1: '{query}'")
    result = geocode_nominatim_full(query)
    if result and is_in_bounds(*result):
        print(f"    -> Tier 1 HIT: ({result[0]:.4f}, {result[1]:.4f})")
        return result
    time.sleep(1.1)

    # Tier 2: Stripped name
    print(f"    Tier 2: stripped name")
    result = geocode_nominatim_stripped(name)
    if result and is_in_bounds(*result):
        print(f"    -> Tier 2 HIT: ({result[0]:.4f}, {result[1]:.4f})")
        return result
    time.sleep(1.1)

    # Tier 3: Structured
    print(f"    Tier 3: structured")
    result = geocode_nominatim_structured(name)
    if result:
        print(f"    -> Tier 3 HIT: ({result[0]:.4f}, {result[1]:.4f})")
        return result
    time.sleep(1.1)

    # Tier 4: Photon (no rate limit needed)
    print(f"    Tier 4: Photon")
    result = geocode_photon(name)
    if result:
        print(f"    -> Tier 4 HIT: ({result[0]:.4f}, {result[1]:.4f})")
        return result

    return None


# ============================================================
# NEW CANDIDATE LOCATIONS
# Each has: name, query (for geocoding), severity, source, description
# These are locations NOT in the existing 37, sourced from news articles
# ============================================================

CANDIDATES = [
    # --- Free Press Journal (comprehensive waterlogging road list) ---
    {
        "name": "Annapurna Road",
        "query": "Annapurna Road, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Major commercial road — chronic waterlogging blocks traffic during monsoon"
    },
    {
        "name": "Rajendra Nagar",
        "query": "Rajendra Nagar, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Residential colony with poor drainage — water enters ground-floor houses"
    },
    {
        "name": "Vaishali Nagar",
        "query": "Vaishali Nagar, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Low-lying residential area prone to monsoon waterlogging"
    },
    {
        "name": "Sadar Bazar",
        "query": "Sadar Bazar, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Historic market area — narrow lanes and clogged drains cause flooding"
    },
    {
        "name": "Juna Risala",
        "query": "Juna Risala, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Old military quarter — aging drainage infrastructure overwhelmed during heavy rain"
    },
    {
        "name": "Badwali Chowki",
        "query": "Badwali Chowki, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Junction area with inadequate storm drains"
    },
    {
        "name": "Moti Tabela",
        "query": "Moti Tabela, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Dense commercial area — runoff from surrounding roads converges here"
    },
    {
        "name": "Harsiddhi",
        "query": "Harsiddhi, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Temple area near Khan River — prone to backwater flooding"
    },
    {
        "name": "Malviya Nagar",
        "query": "Malviya Nagar, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Residential area with insufficient drainage capacity during peak monsoon"
    },
    {
        "name": "Nandlalpura",
        "query": "Nandlalpura, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Low-lying area near nullah — recurring waterlogging every monsoon season"
    },
    {
        "name": "Siyaganj",
        "query": "Siyaganj, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Commercial hub — impervious surfaces and flat terrain trap rainwater"
    },
    {
        "name": "Hukumchand Mill area",
        "query": "Hukumchand Colony, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Former mill area — poor urban planning leads to drainage issues"
    },
    {
        "name": "MIG Colony",
        "query": "MIG Colony, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Government housing colony with aging stormwater infrastructure"
    },
    {
        "name": "Nanda Nagar",
        "query": "Nanda Nagar, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Residential area — drainage overwhelmed by rapid urbanization"
    },
    {
        "name": "Sudama Nagar",
        "query": "Sudama Nagar, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Low-gradient area with recurring road waterlogging"
    },
    {
        "name": "Geeta Bhawan Square",
        "query": "Geeta Bhawan, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Major intersection — water accumulation due to poor gradient and high traffic"
    },
    {
        "name": "Regal Square",
        "query": "Regal Square, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Central Indore junction — chronic waterlogging disrupts traffic"
    },
    {
        "name": "Nehru Nagar",
        "query": "Nehru Nagar, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Residential area with inadequate stormwater drainage system"
    },
    {
        "name": "Scheme 78",
        "query": "Scheme 78, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Smart City Indore",
        "description": "Planned residential scheme with drainage capacity issues"
    },
    {
        "name": "Tilak Nagar",
        "query": "Tilak Nagar, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Colony near major road — surface runoff from adjacent areas"
    },
    {
        "name": "GPO Square",
        "query": "General Post Office, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Central postal area junction — low point collects water from surrounding streets"
    },
    {
        "name": "Bhagirathpura",
        "query": "Bhagirathpura, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "KnockSense",
        "description": "Dense residential area with old drainage network unable to handle monsoon load"
    },
    {
        "name": "Navlakha Square",
        "query": "Navlakha, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Major commercial junction — multiple road convergence creates waterlogging"
    },
    {
        "name": "Raj Mahal Colony",
        "query": "Raj Mahal Colony, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Ground Report",
        "description": "Residential area — Smart City drainage upgrades pending"
    },
    {
        "name": "Palhar Nagar",
        "query": "Palhar Nagar, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "KnockSense",
        "description": "Low-lying area with chronic monsoon waterlogging"
    },

    # --- KnockSense / Ground Report / Daily Pioneer ---
    {
        "name": "Sapna Sangeeta Road",
        "query": "Sapna Sangeeta Road, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "KnockSense",
        "description": "Major arterial road — waterlogging blocks traffic during heavy rainfall events"
    },
    {
        "name": "Palasia Square",
        "query": "New Palasia, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Daily Pioneer",
        "description": "Commercial hub — flat terrain and impervious surfaces cause rapid water accumulation"
    },
    {
        "name": "Sneh Nagar",
        "query": "Sneh Nagar, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Ground Report",
        "description": "Residential colony with waterlogging near main road intersections"
    },
    {
        "name": "Aerodrome Road",
        "query": "Aerodrome Road, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "KnockSense",
        "description": "Wide road with poor side drainage — water pools on both edges during rain"
    },
    {
        "name": "Banganga (Khan River Bridge)",
        "query": "Banganga, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Daily Pioneer",
        "description": "Khan River bridge area — river overflow floods surrounding roads and colonies"
    },
    {
        "name": "Bada Ganpati",
        "query": "Bada Ganpati, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Heritage temple area — old city drainage overwhelmed by monsoon rains"
    },
    {
        "name": "Rajwada (Holkar Palace area)",
        "query": "Rajwada Palace, Indore, Madhya Pradesh",
        "severity": "high",
        "source": "Free Press Journal",
        "description": "Historic palace square — lowest point in old city, water converges from all directions"
    },
    {
        "name": "Pardeshipura",
        "query": "Pardeshipura, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Ground Report",
        "description": "Dense residential area near railway — poor cross-drainage under rail tracks"
    },
    {
        "name": "Chappan Dukan",
        "query": "Chappan Dukan, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Famous street food market — waterlogging during heavy spells affects businesses"
    },
    {
        "name": "Khajuri Bazar",
        "query": "Khajuri Bazar, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Free Press Journal",
        "description": "Old market area — narrow lanes with clogged drainage channels"
    },
    {
        "name": "Rau (AB Road South)",
        "query": "Rau Circle, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "KnockSense",
        "description": "Southern suburb on AB Road — highway drainage insufficient for urban runoff"
    },
    {
        "name": "Dewas Naka",
        "query": "Dewas Naka, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Daily Pioneer",
        "description": "Northern entry point — highway underpass waterlogging during monsoon"
    },
    {
        "name": "Manik Bagh Road",
        "query": "Manik Bagh Road, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "KnockSense",
        "description": "Road near Manik Bagh palace — slope runoff from surrounding hills"
    },
    {
        "name": "Shivaji Nagar",
        "query": "Shivaji Nagar, Indore, Madhya Pradesh",
        "severity": "moderate",
        "source": "Ground Report",
        "description": "Residential area with waterlogging at low points near nullah"
    },
]


def main():
    existing = load_existing_hotspots()
    print(f"Loaded {len(existing)} existing Indore hotspots")
    print(f"Processing {len(CANDIDATES)} new candidates...\n")

    new_hotspots = []
    failed = []
    duplicates = []
    next_id = 38  # Continue from indore-037

    for i, cand in enumerate(CANDIDATES):
        name = cand["name"]
        print(f"\n[{i+1}/{len(CANDIDATES)}] {name}")

        coords = geocode_with_fallback(name, cand["query"])

        if not coords:
            print(f"  FAILED: Could not geocode")
            failed.append(name)
            continue

        lat, lng = round(coords[0], 4), round(coords[1], 4)

        if not is_in_bounds(lat, lng):
            print(f"  OUT OF BOUNDS: ({lat}, {lng})")
            failed.append(name)
            continue

        # Check against existing + newly added
        all_existing = existing + new_hotspots
        dup = is_duplicate(lat, lng, all_existing)
        if dup:
            print(f"  DUPLICATE of '{dup}' — skipping")
            duplicates.append(f"{name} ~ {dup}")
            continue

        zone = assign_zone(lat, lng)
        hotspot = {
            "id": f"indore-{next_id:03d}",
            "name": name,
            "lat": lat,
            "lng": lng,
            "description": cand["description"],
            "zone": zone,
            "severity_history": cand["severity"],
            "source": cand["source"],
        }
        new_hotspots.append(hotspot)
        next_id += 1
        print(f"  ADDED: ({lat}, {lng}) zone={zone}")

    # Summary
    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  New hotspots: {len(new_hotspots)}")
    print(f"  Failed geocoding: {len(failed)}")
    print(f"  Duplicates skipped: {len(duplicates)}")
    print(f"  Total (existing + new): {len(existing) + len(new_hotspots)}")

    if failed:
        print(f"\nFailed locations:")
        for f_name in failed:
            print(f"  - {f_name}")

    if duplicates:
        print(f"\nDuplicates:")
        for d in duplicates:
            print(f"  - {d}")

    # Gate check
    total = len(existing) + len(new_hotspots)
    if total < 55:
        print(f"\n[WARN] GATE 1C FAILED: Total {total} < 55 minimum")
        print("Consider adding more candidates or debugging failed geocoding")
    else:
        print(f"\n[OK] GATE 1C PASSED: Total {total} >= 55")

    # Merge and write
    merged = existing + new_hotspots
    zones = {}
    for h in merged:
        zones[h["zone"]] = zones.get(h["zone"], 0) + 1

    output = {
        "metadata": {
            "version": "2.0",
            "created": "2026-03-03",
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "source": "IMC, Free Press Journal, Smart City Indore, KnockSense, Ground Report, Daily Pioneer",
            "total_hotspots": len(merged),
            "zones": zones,
            "composition": "IMC identified + multi-source news reports"
        },
        "hotspots": merged,
    }

    # Write to backend data dir
    out_path = Path(__file__).resolve().parent.parent / "data" / "indore_waterlogging_hotspots.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nWritten to: {out_path}")

    # Also write candidates-only for review
    review_path = Path(__file__).resolve().parent / "indore_candidates.json"
    with open(review_path, "w", encoding="utf-8") as f:
        json.dump(new_hotspots, f, indent=2, ensure_ascii=False)
    print(f"Candidates saved to: {review_path}")


if __name__ == "__main__":
    main()
