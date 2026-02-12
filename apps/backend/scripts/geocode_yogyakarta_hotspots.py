#!/usr/bin/env python3
"""
One-time script to geocode Yogyakarta flood-prone locations using Nominatim.
Outputs yogyakarta_waterlogging_hotspots.json matching Delhi's data format.

Usage: python apps/backend/scripts/geocode_yogyakarta_hotspots.py
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "FloodSafe/1.0 (flood-monitoring-nonprofit)"}

# Yogyakarta bounding box (matches CITY_BOUNDS in fhi_calculator.py)
VIEWBOX = "110.30,-7.65,110.50,-7.95"  # left,top,right,bottom
BOUNDS = {"min_lat": -7.95, "max_lat": -7.65, "min_lng": 110.30, "max_lng": 110.50}

# Locations to geocode with metadata
LOCATIONS = [
    {"name": "Jalan Kusumanegara", "query": "Jalan Kusumanegara, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Jalan Gejayan", "query": "Jalan Gejayan, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Jalan Ringroad Utara", "query": "Jalan Ring Road Utara, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Klitren", "query": "Klitren, Gondokusuman, Yogyakarta", "severity": "moderate", "type": "neighborhood"},
    {"name": "Jalan Balirejo", "query": "Jalan Balirejo, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Jalan Ipda Tut Harsono", "query": "Jalan Ipda Tut Harsono, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Terban", "query": "Terban, Gondokusuman, Yogyakarta", "severity": "moderate", "type": "neighborhood"},
    {"name": "Bintaran", "query": "Bintaran, Mergangsan, Yogyakarta", "severity": "moderate", "type": "neighborhood"},
    {"name": "Jalan Babarsari", "query": "Jalan Babarsari, Sleman, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Jalan Seturan", "query": "Jalan Seturan Raya, Sleman, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Perumnas Seturan", "query": "Perumnas Seturan, Sleman, Yogyakarta", "severity": "moderate", "type": "neighborhood"},
    {"name": "Selokan Mataram", "query": "Selokan Mataram, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Jalan Affandi", "query": "Jalan Affandi, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Jalan Urip Sumoharjo", "query": "Jalan Urip Sumoharjo, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Jalan Laksda Adisucipto", "query": "Jalan Laksda Adisucipto, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Jalan Jendral Sudirman (Tugu Yogyakarta)", "query": "Jalan Jenderal Sudirman, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Jalan Majapahit", "query": "Jalan Majapahit, Yogyakarta", "severity": "moderate", "type": "street"},
    {"name": "Gedongkuning - Wonocatur", "query": "Gedongkuning, Banguntapan, Yogyakarta", "severity": "moderate", "type": "neighborhood"},
    {"name": "Underpass Kentungan", "query": "Kentungan, Condongcatur, Sleman, Yogyakarta", "severity": "high", "type": "underpass"},
]


def geocode(query: str) -> dict | None:
    """Geocode a location using Nominatim."""
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "country_codes": "id",
        "viewbox": VIEWBOX,
        "bounded": 1,
    }
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        results = resp.json()
        if results:
            return {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"]), "display": results[0].get("display_name", "")}
    except Exception as e:
        print(f"  ERROR: {e}")
    return None


def assign_zone(lat: float, lng: float) -> str:
    """Assign zone based on lat/lng quadrants within Yogyakarta."""
    center_lat = -7.795
    center_lng = 110.38
    if lat > center_lat:
        return "north"
    elif lng > center_lng:
        return "east"
    else:
        return "central"


def is_in_bounds(lat: float, lng: float) -> bool:
    return (BOUNDS["min_lat"] <= lat <= BOUNDS["max_lat"] and
            BOUNDS["min_lng"] <= lng <= BOUNDS["max_lng"])


def main():
    print(f"Geocoding {len(LOCATIONS)} Yogyakarta flood hotspots...\n")

    hotspots = []
    failed = []

    for i, loc in enumerate(LOCATIONS):
        print(f"[{i+1}/{len(LOCATIONS)}] {loc['name']}...")
        result = geocode(loc["query"])

        if result and is_in_bounds(result["lat"], result["lng"]):
            zone = assign_zone(result["lat"], result["lng"])
            hotspot = {
                "id": i + 1,
                "name": loc["name"],
                "lat": round(result["lat"], 6),
                "lng": round(result["lng"], 6),
                "description": f"Flood-prone {loc['type']} in Yogyakarta",
                "zone": zone,
                "severity_history": loc["severity"],
                "source": "local_reports",
            }
            hotspots.append(hotspot)
            print(f"  OK: ({result['lat']:.6f}, {result['lng']:.6f}) zone={zone}")
        elif result:
            print(f"  OUT OF BOUNDS: ({result['lat']:.6f}, {result['lng']:.6f})")
            failed.append(loc["name"])
        else:
            print(f"  NOT FOUND")
            failed.append(loc["name"])

        # Nominatim rate limit: 1 request per second
        if i < len(LOCATIONS) - 1:
            time.sleep(1.1)

    # Build output
    zones = {}
    for h in hotspots:
        zones[h["zone"]] = zones.get(h["zone"], 0) + 1

    output = {
        "metadata": {
            "version": "1.0",
            "created": datetime.now().strftime("%Y-%m-%d"),
            "source": "Local flood reports + Nominatim geocoding",
            "total_hotspots": len(hotspots),
            "zones": zones,
            "composition": {"local_reports": len(hotspots)},
        },
        "hotspots": hotspots,
    }

    # Write to backend data dir
    backend_data = Path(__file__).resolve().parent.parent / "data" / "yogyakarta_waterlogging_hotspots.json"
    with open(backend_data, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nWritten to: {backend_data}")

    # Copy to ml-service data dir
    ml_data = Path(__file__).resolve().parent.parent.parent / "ml-service" / "data" / "yogyakarta_waterlogging_hotspots.json"
    if ml_data.parent.exists():
        with open(ml_data, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Copied to: {ml_data}")

    print(f"\nResults: {len(hotspots)} geocoded, {len(failed)} failed")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
