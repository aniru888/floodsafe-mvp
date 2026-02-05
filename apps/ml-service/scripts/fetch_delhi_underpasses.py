"""
Fetch Delhi Underpasses from OpenStreetMap.

Uses Overpass API to query for road underpasses in Delhi NCR.

OSM Tags for underpasses:
- tunnel=yes (general tunnel)
- tunnel=underpass (specific underpass)
- layer=-1 (below ground level)
- highway=* (road types)

Usage:
    cd apps/ml-service
    python scripts/fetch_delhi_underpasses.py
"""

import json
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Delhi NCR bounding box (approximate)
# South, West, North, East
DELHI_BBOX = "28.40,76.80,28.90,77.40"

def fetch_underpasses() -> List[Dict[str, Any]]:
    """
    Fetch underpass locations from OpenStreetMap using Overpass API.

    Queries for:
    1. Ways tagged as tunnel=underpass
    2. Ways tagged as tunnel=yes with highway tag
    3. Ways with layer=-1 or layer=-2 (below ground)
    """

    # Overpass QL query for Delhi underpasses
    query = f"""
    [out:json][timeout:60];
    (
      // Explicit underpasses
      way["tunnel"="underpass"]["highway"](28.40,76.80,28.90,77.40);

      // Tunnels that are roads
      way["tunnel"="yes"]["highway"](28.40,76.80,28.90,77.40);

      // Roads below ground level
      way["layer"="-1"]["highway"](28.40,76.80,28.90,77.40);
      way["layer"="-2"]["highway"](28.40,76.80,28.90,77.40);

      // Covered roads (sometimes used for underpasses)
      way["covered"="yes"]["highway"](28.40,76.80,28.90,77.40);
    );
    out center;
    """

    print("Querying Overpass API for Delhi underpasses...")
    print(f"Bounding box: {DELHI_BBOX}")

    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=120
        )
        response.raise_for_status()
        data = response.json()

        elements = data.get("elements", [])
        print(f"Found {len(elements)} raw elements")

        return elements

    except requests.exceptions.RequestException as e:
        print(f"Error fetching from Overpass API: {e}")
        return []


def process_underpasses(elements: List[Dict]) -> List[Dict[str, Any]]:
    """
    Process raw OSM elements into underpass records.

    Extracts center coordinates and relevant tags.
    """
    underpasses = []
    seen_ids = set()

    for elem in elements:
        osm_id = elem.get("id")

        # Skip duplicates
        if osm_id in seen_ids:
            continue
        seen_ids.add(osm_id)

        # Get center coordinates
        center = elem.get("center", {})
        lat = center.get("lat")
        lng = center.get("lon")

        if not lat or not lng:
            continue

        # Get tags
        tags = elem.get("tags", {})

        # Build underpass record
        underpass = {
            "osm_id": osm_id,
            "lat": lat,
            "lng": lng,
            "name": tags.get("name", tags.get("ref", f"Underpass_{osm_id}")),
            "highway_type": tags.get("highway", "unknown"),
            "tunnel_type": tags.get("tunnel", "unknown"),
            "layer": tags.get("layer", "0"),
            "surface": tags.get("surface", "unknown"),
            "lanes": tags.get("lanes", "unknown"),
            "maxheight": tags.get("maxheight", "unknown"),
            "tags": tags,
        }

        underpasses.append(underpass)

    return underpasses


def deduplicate_nearby(underpasses: List[Dict], threshold_m: float = 100) -> List[Dict]:
    """
    Remove underpasses that are very close to each other.
    Keeps the one with more complete information.
    """
    from math import radians, sin, cos, sqrt, atan2

    def haversine(lat1, lon1, lat2, lon2):
        """Calculate distance in meters between two points."""
        R = 6371000  # Earth radius in meters

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    def info_score(up):
        """Score based on completeness of information."""
        score = 0
        if up.get("name") and not up["name"].startswith("Underpass_"):
            score += 10
        if up.get("highway_type") != "unknown":
            score += 2
        if up.get("maxheight") != "unknown":
            score += 1
        if up.get("lanes") != "unknown":
            score += 1
        return score

    # Sort by info score (higher first)
    sorted_ups = sorted(underpasses, key=info_score, reverse=True)

    keep = []
    for up in sorted_ups:
        is_duplicate = False
        for kept in keep:
            dist = haversine(up["lat"], up["lng"], kept["lat"], kept["lng"])
            if dist < threshold_m:
                is_duplicate = True
                break

        if not is_duplicate:
            keep.append(up)

    return keep


def check_overlap_with_hotspots(underpasses: List[Dict], hotspots_file: Path) -> Dict[str, Any]:
    """
    Check how many underpasses overlap with known hotspots.
    """
    from math import radians, sin, cos, sqrt, atan2

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    # Load hotspots
    with open(hotspots_file) as f:
        hotspots_data = json.load(f)
    hotspots = hotspots_data["hotspots"]

    # Find overlaps (within 200m)
    overlapping = []
    new_candidates = []

    for up in underpasses:
        is_known = False
        for hs in hotspots:
            dist = haversine(up["lat"], up["lng"], hs["lat"], hs["lng"])
            if dist < 200:
                is_known = True
                overlapping.append({
                    "underpass": up,
                    "hotspot": hs["name"],
                    "distance_m": dist
                })
                break

        if not is_known:
            new_candidates.append(up)

    return {
        "total_underpasses": len(underpasses),
        "overlapping_with_hotspots": len(overlapping),
        "new_candidates": len(new_candidates),
        "overlaps": overlapping,
        "candidates": new_candidates
    }


def main():
    """Main function to fetch and process Delhi underpasses."""
    print("\n" + "=" * 60)
    print("DELHI UNDERPASS DISCOVERY")
    print("Fetching from OpenStreetMap")
    print("=" * 60)

    project_root = Path(__file__).parent.parent

    # Fetch from OSM
    elements = fetch_underpasses()

    if not elements:
        print("No elements found. Check network connection.")
        return

    # Process into underpass records
    underpasses = process_underpasses(elements)
    print(f"\nProcessed {len(underpasses)} unique underpasses")

    # Deduplicate nearby
    underpasses = deduplicate_nearby(underpasses, threshold_m=100)
    print(f"After deduplication: {len(underpasses)} underpasses")

    # Check overlap with known hotspots
    hotspots_file = project_root / "data" / "delhi_waterlogging_hotspots.json"
    if hotspots_file.exists():
        overlap_analysis = check_overlap_with_hotspots(underpasses, hotspots_file)

        print(f"\n" + "-" * 60)
        print("OVERLAP ANALYSIS")
        print("-" * 60)
        print(f"Total underpasses found: {overlap_analysis['total_underpasses']}")
        print(f"Already known hotspots: {overlap_analysis['overlapping_with_hotspots']}")
        print(f"NEW candidates: {overlap_analysis['new_candidates']}")

        if overlap_analysis['overlaps']:
            print(f"\nKnown hotspots matched:")
            for o in overlap_analysis['overlaps'][:10]:
                print(f"  - {o['underpass']['name']} <-> {o['hotspot']} ({o['distance_m']:.0f}m)")

        new_candidates = overlap_analysis['candidates']
    else:
        print("Hotspots file not found, skipping overlap analysis")
        new_candidates = underpasses

    # Show sample of new candidates
    if new_candidates:
        print(f"\n" + "-" * 60)
        print(f"NEW UNDERPASS CANDIDATES (first 20)")
        print("-" * 60)
        for up in new_candidates[:20]:
            name = up['name']
            if len(name) > 40:
                name = name[:37] + "..."
            print(f"  [{up['highway_type']:12}] {name}")
            print(f"    Location: ({up['lat']:.4f}, {up['lng']:.4f})")

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "source": "OpenStreetMap Overpass API",
        "bbox": DELHI_BBOX,
        "total_found": len(underpasses),
        "new_candidates_count": len(new_candidates),
        "all_underpasses": underpasses,
        "new_candidates": new_candidates,
    }

    output_file = project_root / "data" / "delhi_underpasses_osm.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n" + "=" * 60)
    print(f"Results saved to: {output_file}")
    print(f"Total underpasses: {len(underpasses)}")
    print(f"New candidates (not in known hotspots): {len(new_candidates)}")
    print("=" * 60)

    return output


if __name__ == "__main__":
    results = main()
