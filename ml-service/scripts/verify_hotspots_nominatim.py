"""
Hotspot Coordinate Verification Script using Nominatim.

This script verifies that the lat/lng coordinates for each waterlogging
hotspot actually correspond to the named location using OSM Nominatim
reverse geocoding.

Usage:
    python scripts/verify_hotspots_nominatim.py

Output:
    - Console report of verification results
    - JSON file with verified/flagged hotspots
"""

import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import urllib.request
import urllib.parse

# Rate limit for Nominatim: 1 request per second
NOMINATIM_DELAY = 1.1  # seconds between requests

# Nominatim endpoint
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

# User agent (required by Nominatim terms of service)
USER_AGENT = "FloodSafe-Delhi/1.0 (research-project)"


def reverse_geocode(lat: float, lng: float) -> Dict:
    """
    Reverse geocode a lat/lng coordinate using Nominatim.

    Args:
        lat: Latitude
        lng: Longitude

    Returns:
        Dict with address components
    """
    params = {
        "lat": lat,
        "lon": lng,
        "format": "json",
        "addressdetails": 1,
        "zoom": 16,  # Neighborhood level
    }

    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data
    except Exception as e:
        return {"error": str(e)}


def calculate_similarity(name1: str, name2: str) -> float:
    """
    Calculate simple similarity between two strings.
    Returns value between 0 and 1.
    """
    name1 = name1.lower().replace("_", " ").replace("-", " ")
    name2 = name2.lower().replace("_", " ").replace("-", " ")

    # Split into words
    words1 = set(name1.split())
    words2 = set(name2.split())

    # Check for key word matches
    if words1 & words2:  # Intersection
        return len(words1 & words2) / max(len(words1), len(words2))

    # Check if one contains the other
    if name1 in name2 or name2 in name1:
        return 0.7

    return 0.0


def verify_hotspot(hotspot: Dict) -> Dict:
    """
    Verify a single hotspot coordinate.

    Returns hotspot dict with verification fields added.
    """
    lat = hotspot["lat"]
    lng = hotspot["lng"]
    expected_name = hotspot["name"]

    # Reverse geocode
    result = reverse_geocode(lat, lng)

    if "error" in result:
        return {
            **hotspot,
            "verified": False,
            "verification_status": "error",
            "nominatim_error": result["error"],
            "confidence": 0.0,
        }

    # Extract address components
    address = result.get("address", {})
    display_name = result.get("display_name", "")

    # Get various name possibilities
    possible_names = [
        address.get("road", ""),
        address.get("neighbourhood", ""),
        address.get("suburb", ""),
        address.get("city_district", ""),
        address.get("amenity", ""),
        display_name,
    ]

    # Calculate best similarity
    best_similarity = 0.0
    best_match = ""

    for name in possible_names:
        if name:
            sim = calculate_similarity(expected_name, name)
            if sim > best_similarity:
                best_similarity = sim
                best_match = name

    # Determine verification status
    if best_similarity >= 0.5:
        status = "verified"
        verified = True
    elif best_similarity >= 0.3:
        status = "likely_correct"
        verified = True
    elif best_similarity > 0:
        status = "weak_match"
        verified = False
    else:
        status = "no_match"
        verified = False

    return {
        **hotspot,
        "verified": verified,
        "verification_status": status,
        "confidence": round(best_similarity, 2),
        "nominatim_address": display_name[:100],  # Truncate long addresses
        "matched_name": best_match[:50] if best_match else None,
        "address_components": {
            "road": address.get("road"),
            "neighbourhood": address.get("neighbourhood"),
            "suburb": address.get("suburb"),
        }
    }


def verify_all_hotspots(hotspots_file: Path) -> Tuple[List[Dict], Dict]:
    """
    Verify all hotspots from a JSON file.

    Returns:
        Tuple of (verified_hotspots, summary_stats)
    """
    with open(hotspots_file) as f:
        data = json.load(f)

    hotspots = data["hotspots"]
    verified = []
    stats = {
        "total": len(hotspots),
        "verified": 0,
        "likely_correct": 0,
        "weak_match": 0,
        "no_match": 0,
        "error": 0,
    }

    print(f"Verifying {len(hotspots)} hotspots...")
    print("=" * 60)

    for i, hotspot in enumerate(hotspots):
        print(f"[{i+1}/{len(hotspots)}] {hotspot['name'][:30]:30} ... ", end="", flush=True)

        result = verify_hotspot(hotspot)
        verified.append(result)

        status = result["verification_status"]
        stats[status] = stats.get(status, 0) + 1

        # Print result
        if result["verified"]:
            print(f"OK ({result['confidence']:.0%} - {status})")
        else:
            print(f"WARN ({status})")
            if status == "no_match":
                print(f"       Expected: {hotspot['name']}")
                print(f"       Got: {result.get('nominatim_address', 'N/A')[:50]}")

        # Rate limit
        time.sleep(NOMINATIM_DELAY)

    # Calculate summary
    stats["verified_count"] = stats["verified"] + stats["likely_correct"]
    stats["verification_rate"] = stats["verified_count"] / stats["total"] * 100

    return verified, stats


def main():
    """Run hotspot verification."""
    project_root = Path(__file__).parent.parent
    hotspots_file = project_root / "data" / "delhi_waterlogging_hotspots.json"
    output_file = project_root / "data" / "delhi_waterlogging_hotspots_verified.json"

    if not hotspots_file.exists():
        print(f"ERROR: Hotspots file not found: {hotspots_file}")
        sys.exit(1)

    print("\n" + "#" * 60)
    print("#  FLOODSAFE HOTSPOT COORDINATE VERIFICATION")
    print("#  Using OSM Nominatim Reverse Geocoding")
    print("#" * 60)

    verified_hotspots, stats = verify_all_hotspots(hotspots_file)

    # Print summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"  Total hotspots: {stats['total']}")
    print(f"  Verified:       {stats['verified']} ({stats['verified']/stats['total']*100:.1f}%)")
    print(f"  Likely correct: {stats['likely_correct']} ({stats['likely_correct']/stats['total']*100:.1f}%)")
    print(f"  Weak match:     {stats['weak_match']} ({stats['weak_match']/stats['total']*100:.1f}%)")
    print(f"  No match:       {stats['no_match']} ({stats['no_match']/stats['total']*100:.1f}%)")
    print(f"  Errors:         {stats.get('error', 0)}")
    print()
    print(f"  VERIFICATION RATE: {stats['verification_rate']:.1f}%")

    # Save verified hotspots
    with open(hotspots_file) as f:
        original_data = json.load(f)

    output_data = {
        "metadata": {
            **original_data["metadata"],
            "verification": {
                "date": time.strftime("%Y-%m-%d"),
                "method": "OSM Nominatim reverse geocoding",
                "stats": stats,
            }
        },
        "hotspots": verified_hotspots,
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nVerified hotspots saved to: {output_file}")

    # Decision
    print("\n" + "=" * 60)
    if stats["verification_rate"] >= 60:
        print("GO DECISION: Sufficient coordinates verified.")
        print("Hotspot data is usable for ML training.")
    else:
        print("WARNING: Low verification rate.")
        print("Review flagged hotspots and correct coordinates.")
    print("=" * 60)

    return stats["verification_rate"] >= 60


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
