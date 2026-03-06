#!/usr/bin/env python3
"""
Verify hotspot data quality for all cities.
Checks: bounds, duplicates, schema, IDs, coordinates, sources, zone distribution.

Usage: python apps/backend/scripts/verify_hotspots.py
"""

import json
import math
from pathlib import Path

CITY_CONFIGS = {
    "delhi": {
        "file": "delhi_waterlogging_hotspots.json",
        "bounds": {"min_lat": 28.40, "max_lat": 28.90, "min_lng": 76.80, "max_lng": 77.40},
    },
    "bangalore": {
        "file": "bangalore_waterlogging_hotspots.json",
        "bounds": {"min_lat": 12.80, "max_lat": 13.20, "min_lng": 77.40, "max_lng": 77.80},
    },
    "yogyakarta": {
        "file": "yogyakarta_waterlogging_hotspots.json",
        "bounds": {"min_lat": -7.95, "max_lat": -7.65, "min_lng": 110.30, "max_lng": 110.50},
    },
    "singapore": {
        "file": "singapore_waterlogging_hotspots.json",
        "bounds": {"min_lat": 1.20, "max_lat": 1.47, "min_lng": 103.60, "max_lng": 104.05},
    },
    "indore": {
        "file": "indore_waterlogging_hotspots.json",
        "bounds": {"min_lat": 22.52, "max_lat": 22.85, "min_lng": 75.72, "max_lng": 75.97},
    },
}

DEDUP_THRESHOLD = 0.001  # ~111m
REQUIRED_FIELDS = ["id", "name", "lat", "lng", "description", "zone", "severity_history", "source"]


def verify_city(city_name, config):
    data_dir = Path(__file__).resolve().parent.parent / "data"
    filepath = data_dir / config["file"]

    if not filepath.exists():
        print(f"  [SKIP] File not found: {filepath}")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    hotspots = data.get("hotspots", [])
    metadata = data.get("metadata", {})
    bounds = config["bounds"]
    errors = []
    warnings = []

    # 1. Metadata total matches actual
    if metadata.get("total_hotspots") != len(hotspots):
        errors.append(f"Metadata total ({metadata.get('total_hotspots')}) != actual ({len(hotspots)})")

    # 2. Schema validation
    for h in hotspots:
        for field in REQUIRED_FIELDS:
            if field not in h or h[field] is None or h[field] == "":
                errors.append(f"Missing/empty field '{field}' in hotspot '{h.get('name', 'UNNAMED')}'")

    # 3. Bounds check
    oob = []
    for h in hotspots:
        lat, lng = h.get("lat", 0), h.get("lng", 0)
        if not (bounds["min_lat"] <= lat <= bounds["max_lat"] and bounds["min_lng"] <= lng <= bounds["max_lng"]):
            oob.append(h["name"])
    if oob:
        errors.append(f"Out of bounds: {oob}")

    # 4. Duplicate check (coordinates within threshold)
    dupes = []
    for i, h1 in enumerate(hotspots):
        for j, h2 in enumerate(hotspots):
            if j <= i:
                continue
            if abs(h1["lat"] - h2["lat"]) < DEDUP_THRESHOLD and abs(h1["lng"] - h2["lng"]) < DEDUP_THRESHOLD:
                dupes.append(f"'{h1['name']}' ~ '{h2['name']}' (dist: {abs(h1['lat']-h2['lat']):.4f},{abs(h1['lng']-h2['lng']):.4f})")
    if dupes:
        warnings.append(f"Near-duplicates ({len(dupes)}): {'; '.join(dupes[:5])}")

    # 5. ID uniqueness
    ids = [h["id"] for h in hotspots]
    if len(set(ids)) != len(ids):
        seen = set()
        dupe_ids = [x for x in ids if x in seen or seen.add(x)]
        errors.append(f"Duplicate IDs: {dupe_ids}")

    # 6. Coordinate precision (at least 4 decimal places)
    low_precision = []
    for h in hotspots:
        lat_str = str(h["lat"])
        lng_str = str(h["lng"])
        lat_dp = len(lat_str.split(".")[-1]) if "." in lat_str else 0
        lng_dp = len(lng_str.split(".")[-1]) if "." in lng_str else 0
        if lat_dp < 4 or lng_dp < 4:
            low_precision.append(f"{h['name']} (lat:{lat_dp}dp, lng:{lng_dp}dp)")
    if low_precision:
        warnings.append(f"Low precision ({len(low_precision)}): {', '.join(low_precision[:5])}")

    # 7. Source attribution
    no_source = [h["name"] for h in hotspots if not h.get("source") or h["source"] == ""]
    if no_source:
        errors.append(f"Missing source: {no_source}")

    # 8. Zone distribution
    zones = {}
    for h in hotspots:
        z = h.get("zone", "unknown")
        zones[z] = zones.get(z, 0) + 1
    total = len(hotspots)
    for z, count in zones.items():
        pct = count / total * 100
        if pct > 40:
            warnings.append(f"Zone '{z}' has {pct:.0f}% of hotspots ({count}/{total})")

    # 9. Severity validation
    valid_severities = {"high", "moderate", "low", "medium"}
    bad_sev = [h["name"] for h in hotspots if h.get("severity_history") not in valid_severities]
    if bad_sev:
        errors.append(f"Invalid severity: {bad_sev}")

    # Report
    print(f"\n  {'='*50}")
    print(f"  {city_name.upper()}: {len(hotspots)} hotspots")
    print(f"  Zones: {zones}")
    sources = {}
    for h in hotspots:
        src = h.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    print(f"  Sources: {sources}")

    if errors:
        print(f"  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    [ERROR] {e}")
    if warnings:
        print(f"  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"    [WARN] {w}")
    if not errors and not warnings:
        print(f"  [OK] All checks passed")
    elif not errors:
        print(f"  [OK] No errors (warnings only)")

    return len(errors) == 0


def main():
    print("Hotspot Data Verification")
    print("=" * 60)

    all_pass = True
    for city, config in CITY_CONFIGS.items():
        passed = verify_city(city, config)
        if passed is False:
            all_pass = False

    print(f"\n{'='*60}")
    if all_pass:
        print("[OK] All cities passed verification")
    else:
        print("[FAIL] Some cities have errors - fix before deploying")


if __name__ == "__main__":
    main()
