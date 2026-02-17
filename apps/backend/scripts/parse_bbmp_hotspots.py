#!/usr/bin/env python3
"""
Parse BBMP (Bruhat Bengaluru Mahanagara Palike) Flood Vulnerable Locations KML file.

Data source: OpenCity.in CKAN portal
- Primary: BBMP Flood Vulnerable Locations (~209 records)
  https://data.opencity.in/dataset/bbmp-flood-vulnerable-locations

Output: apps/backend/data/bangalore_waterlogging_hotspots.json
"""

import json
import math
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.request import urlopen

# BBMP Flood Vulnerable Locations KML (primary dataset, ~209 records)
KML_URL = "https://data.opencity.in/dataset/b03218ea-4b7c-4fa9-ab67-b9054d7ecc4c/resource/a7d8a01f-1fbc-41e1-85f0-f15ea16b2d27/download/6b3c63b0-f461-4e9c-a2c2-006f734c5b41.kml"

# Bangalore bounding box for coordinate validation
BLR_BOUNDS = {"lat_min": 12.6, "lat_max": 13.4, "lng_min": 77.2, "lng_max": 77.9}

# BBMP zone normalization mapping
ZONE_NORMALIZE = {
    "rr nagar": "rr_nagar",
    "r.r.nagar": "rr_nagar",
    "r.r. nagar": "rr_nagar",
    "rajarajeshwari nagar": "rr_nagar",
    "bommanahalli": "bommanahalli",
    "south": "south",
    "mahadevapura": "mahadevapura",
    "west": "west",
    "east": "east",
    "dasarahalli": "dasarahalli",
    "yelahanka": "yelahanka",
}


def normalize_zone(zone_raw: str) -> str:
    """Normalize BBMP zone names to consistent lowercase_underscore format."""
    if not zone_raw:
        return "unknown"
    key = zone_raw.strip().lower()
    return ZONE_NORMALIZE.get(key, key.replace(" ", "_"))


def download_kml(url: str) -> str:
    """Download KML file content from URL."""
    print(f"Downloading KML from: {url}")
    with urlopen(url) as response:
        content = response.read().decode("utf-8")
    print(f"Downloaded {len(content)} bytes")
    return content


def parse_kml(kml_content: str) -> list[dict]:
    """Parse KML Placemarks, extracting coordinates and ExtendedData fields."""
    root = ET.fromstring(kml_content)

    # KML uses a namespace
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    placemarks = root.findall(".//kml:Placemark", ns)
    print(f"Found {len(placemarks)} Placemarks in KML")

    hotspots = []
    skipped = 0

    for i, pm in enumerate(placemarks, start=1):
        # Extract name
        name_el = pm.find("kml:name", ns)
        name = name_el.text.strip() if name_el is not None and name_el.text else f"Location {i}"

        # Extract coordinates from Point
        coords_el = pm.find(".//kml:coordinates", ns)
        if coords_el is None or not coords_el.text:
            print(f"  SKIP #{i} '{name}': no coordinates")
            skipped += 1
            continue

        coords_text = coords_el.text.strip()
        parts = coords_text.split(",")
        try:
            lng = float(parts[0])
            lat = float(parts[1])
        except (ValueError, IndexError):
            print(f"  SKIP #{i} '{name}': invalid coordinates '{coords_text}'")
            skipped += 1
            continue

        # Validate coordinates are not NaN and within Bangalore bounds
        if math.isnan(lat) or math.isnan(lng):
            print(f"  SKIP #{i} '{name}': NaN coordinates")
            skipped += 1
            continue

        if not (BLR_BOUNDS["lat_min"] <= lat <= BLR_BOUNDS["lat_max"] and
                BLR_BOUNDS["lng_min"] <= lng <= BLR_BOUNDS["lng_max"]):
            print(f"  SKIP #{i} '{name}': outside Bangalore bounds ({lat}, {lng})")
            skipped += 1
            continue

        # Extract ExtendedData fields (ZONE, WARD_NAME, WARDNO, LOCATION_N, etc.)
        extended = {}
        for data_el in pm.findall(".//kml:SimpleData", ns):
            field_name = data_el.get("name", "")
            field_value = data_el.text.strip() if data_el.text else ""
            extended[field_name] = field_value

        # Also try Data/value pattern (alternate KML format)
        for data_el in pm.findall(".//kml:Data", ns):
            field_name = data_el.get("name", "")
            value_el = data_el.find("kml:value", ns)
            if value_el is not None and value_el.text:
                extended[field_name] = value_el.text.strip()

        # Build hotspot entry
        zone_raw = extended.get("ZONE", extended.get("Zone", ""))
        ward_name = extended.get("WARD_NAME", extended.get("Ward_Name", extended.get("WARD", "")))
        ward_no_str = extended.get("WARDNO", extended.get("Ward_No", extended.get("WardNo", "")))
        location_name = extended.get("LocationName", extended.get("LOCATION_N", extended.get("Location_Name", "")))

        # Use location name from ExtendedData if available, else use Placemark name
        display_name = location_name if location_name else name

        # Parse ward number
        ward_no = None
        if ward_no_str:
            try:
                ward_no = int(float(ward_no_str))
            except (ValueError, TypeError):
                pass

        zone = normalize_zone(zone_raw)

        # Build description with ward info
        desc_parts = ["BBMP-identified flood vulnerable location"]
        if ward_name:
            desc_parts.append(f"in {ward_name} ward")
        if zone_raw:
            desc_parts.append(f"({zone_raw} zone)")

        hotspot = {
            "id": len(hotspots) + 1,
            "name": display_name,
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "description": " ".join(desc_parts),
            "zone": zone,
            "severity_history": "high",
            "source": "BBMP",
            "category": "flood_vulnerable",
        }

        if ward_name:
            hotspot["ward_name"] = ward_name
        if ward_no is not None:
            hotspot["ward_no"] = ward_no

        hotspots.append(hotspot)

    print(f"\nParsed: {len(hotspots)} hotspots, skipped: {skipped}")
    return hotspots


def build_output(hotspots: list[dict]) -> dict:
    """Build the final JSON structure matching existing city file format."""
    zone_counts = Counter(h["zone"] for h in hotspots)

    return {
        "metadata": {
            "version": "1.0",
            "created": "2026-02-17",
            "source": "BBMP Official Flood Vulnerable Locations (OpenCity.in)",
            "total_hotspots": len(hotspots),
            "zones": dict(sorted(zone_counts.items())),
            "composition": {
                "bbmp_flood_vulnerable": len(hotspots),
            },
        },
        "hotspots": hotspots,
    }


def main():
    # Download KML
    try:
        kml_content = download_kml(KML_URL)
    except Exception as e:
        print(f"ERROR downloading KML: {e}")
        sys.exit(1)

    # Parse hotspots
    hotspots = parse_kml(kml_content)

    if not hotspots:
        print("ERROR: No hotspots parsed!")
        sys.exit(1)

    # Build output
    output = build_output(hotspots)

    # Write to data directory
    out_path = Path(__file__).parent.parent / "data" / "bangalore_waterlogging_hotspots.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(hotspots)} hotspots to {out_path}")
    print(f"Zones: {dict(Counter(h['zone'] for h in hotspots))}")

    # Summary stats
    with_ward = sum(1 for h in hotspots if "ward_name" in h)
    print(f"With ward name: {with_ward}/{len(hotspots)}")


if __name__ == "__main__":
    main()
