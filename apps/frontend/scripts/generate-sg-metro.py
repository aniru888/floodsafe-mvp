#!/usr/bin/env python3
"""
Generate accurate Singapore MRT GeoJSON from OpenStreetMap via Overpass API.

Fetches subway routes, merges ordered way segments into continuous LineStrings,
and extracts station nodes with metadata. Outputs two GeoJSON files:
  - singapore-metro-lines.geojson (6 lines with 50-200+ points each)
  - singapore-metro-stations.geojson (138+ stations)

Usage:
    python apps/frontend/scripts/generate-sg-metro.py
"""

import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

# Fix Windows console encoding for Unicode station names from OSM
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Official MRT line colors and metadata
MRT_LINES = {
    "North South Line": {"code": "NSL", "color": "#CC0033", "ref": "NS"},
    "North-South Line": {"code": "NSL", "color": "#CC0033", "ref": "NS"},
    "East West Line": {"code": "EWL", "color": "#009645", "ref": "EW"},
    "East-West Line": {"code": "EWL", "color": "#009645", "ref": "EW"},
    "North East Line": {"code": "NEL", "color": "#9900AA", "ref": "NE"},
    "North-East Line": {"code": "NEL", "color": "#9900AA", "ref": "NE"},
    "Circle Line": {"code": "CCL", "color": "#FA9E0D", "ref": "CC"},
    "Downtown Line": {"code": "DTL", "color": "#005EC4", "ref": "DT"},
    "Thomson-East Coast Line": {"code": "TEL", "color": "#9D5B25", "ref": "TE"},
    "Thomson–East Coast Line": {"code": "TEL", "color": "#9D5B25", "ref": "TE"},
}

# Canonical names for deduplication (map code -> preferred name)
CANONICAL_NAMES = {
    "NSL": "North-South Line",
    "EWL": "East-West Line",
    "NEL": "North-East Line",
    "CCL": "Circle Line",
    "DTL": "Downtown Line",
    "TEL": "Thomson-East Coast Line",
}


def fetch_overpass(query: str, max_retries: int = 3) -> dict:
    """Execute an Overpass API query with retry logic."""
    for attempt in range(max_retries):
        try:
            print(f"  Querying Overpass API (attempt {attempt + 1}/{max_retries})...")
            resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=180)
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.Timeout, requests.exceptions.HTTPError) as e:
            if attempt < max_retries - 1:
                wait = 10 * (attempt + 1)
                print(f"  Retrying in {wait}s after error: {e}")
                time.sleep(wait)
            else:
                raise


def fetch_mrt_data() -> dict:
    """Fetch all Singapore MRT subway routes from Overpass.

    Uses a multi-step query:
    1. Find MRT relations (routes)
    2. Fetch relation member nodes WITH tags (stations/stops)
    3. Fetch ways and their nodes as skeleton (track geometry)
    """
    query = """
[out:json][timeout:180];
area["name"="Singapore"]["admin_level"="2"]->.sg;
(
  relation["route"="subway"](area.sg);
  relation["route"="train"]["network"~"MRT"](area.sg);
)->.rels;
.rels out body;
node(r.rels)->.rnodes;
.rnodes out body;
way(r.rels)->.rways;
.rways out body;
node(w.rways);
out skel qt;
"""
    return fetch_overpass(query)


def fetch_station_data() -> dict:
    """Fetch all Singapore MRT station nodes with their tags."""
    query = """
[out:json][timeout:60];
area["name"="Singapore"]["admin_level"="2"]->.sg;
(
  node["railway"="station"]["station"="subway"](area.sg);
  node["railway"="stop"]["train"="yes"](area.sg);
  node["public_transport"="stop_position"]["subway"="yes"](area.sg);
  node["railway"="station"]["network"~"MRT"](area.sg);
);
out body;
"""
    return fetch_overpass(query)


def parse_overpass_response(data: dict):
    """Parse Overpass response into nodes, ways, and relations."""
    nodes = {}
    ways = {}
    relations = []

    for element in data.get("elements", []):
        etype = element["type"]
        if etype == "node":
            nid = element["id"]
            tags = element.get("tags", {})
            # Don't overwrite a tagged node with a skeleton node
            if nid in nodes and not tags and nodes[nid].get("tags"):
                continue
            nodes[nid] = {
                "lat": element["lat"],
                "lon": element["lon"],
                "tags": tags,
            }
        elif etype == "way":
            ways[element["id"]] = {
                "nodes": element.get("nodes", []),
                "tags": element.get("tags", {}),
            }
        elif etype == "relation":
            relations.append(element)

    return nodes, ways, relations


def identify_line(relation: dict) -> dict | None:
    """Identify which MRT line a relation represents."""
    tags = relation.get("tags", {})
    name = tags.get("name", "")

    # Try exact match first
    if name in MRT_LINES:
        return MRT_LINES[name]

    # Try partial match
    for line_name, info in MRT_LINES.items():
        if line_name.lower() in name.lower():
            return info

    # Try by ref tag
    ref = tags.get("ref", "")
    for line_name, info in MRT_LINES.items():
        if info["ref"] == ref:
            return info

    return None


def merge_ways_to_linestring(relation: dict, ways: dict, nodes: dict) -> list[list[float]]:
    """Merge ordered way members of a relation into a continuous LineString.

    OSM relations store ways in order. Each way shares endpoint nodes with
    adjacent ways. We chain them by matching endpoints, flipping ways as needed.
    """
    # Extract way members in order
    way_ids = []
    for member in relation.get("members", []):
        if member["type"] == "way" and member.get("role", "") in ("", "forward", "backward"):
            wid = member["ref"]
            if wid in ways:
                way_ids.append(wid)

    if not way_ids:
        return []

    # Resolve each way to its coordinate list
    way_coords = []
    for wid in way_ids:
        coords = []
        for nid in ways[wid]["nodes"]:
            if nid in nodes:
                node = nodes[nid]
                coords.append([round(node["lon"], 6), round(node["lat"], 6)])
        if coords:
            way_coords.append(coords)

    if not way_coords:
        return []

    # Chain ways together by matching endpoints
    result = list(way_coords[0])

    for i in range(1, len(way_coords)):
        segment = way_coords[i]
        if not segment:
            continue

        # Check which end of the new segment connects to our chain
        last = result[-1]
        first_of_seg = segment[0]
        last_of_seg = segment[-1]

        dist_to_first = _coord_dist(last, first_of_seg)
        dist_to_last = _coord_dist(last, last_of_seg)

        if dist_to_last < dist_to_first:
            # Reverse the segment
            segment = list(reversed(segment))

        # Skip the first point if it matches (avoid duplicates)
        if result and segment and _coord_dist(result[-1], segment[0]) < 0.0001:
            result.extend(segment[1:])
        else:
            result.extend(segment)

    return result


def _coord_dist(a: list[float], b: list[float]) -> float:
    """Simple Euclidean distance between two [lon, lat] coordinates."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def extract_stations(relations: list, ways: dict, nodes: dict) -> list[dict]:
    """Extract station nodes from relations."""
    stations = {}  # name -> station data (dedup by name)

    for relation in relations:
        line_info = identify_line(relation)
        if not line_info:
            continue

        for member in relation.get("members", []):
            if member["type"] == "node" and member.get("role", "") in ("stop", "stop_entry_only", "stop_exit_only", "platform"):
                nid = member["ref"]
                if nid in nodes:
                    node = nodes[nid]
                    tags = node.get("tags", {})
                    name = tags.get("name", tags.get("name:en", ""))
                    if not name:
                        continue

                    # Clean up station name
                    name = name.replace(" MRT Station", "").replace(" MRT station", "")
                    name = name.replace(" station", "").replace(" Station", "")

                    if name in stations:
                        # Add this line to existing station
                        existing_lines = stations[name]["lines"]
                        if line_info["code"] not in existing_lines:
                            existing_lines.append(line_info["code"])
                    else:
                        stations[name] = {
                            "name": name,
                            "lon": round(node["lon"], 6),
                            "lat": round(node["lat"], 6),
                            "lines": [line_info["code"]],
                            "color": line_info["color"],
                        }

    # Also scan for station nodes directly (some aren't in relations)
    for nid, node in nodes.items():
        tags = node.get("tags", {})
        if tags.get("railway") == "station" or tags.get("station") == "subway":
            name = tags.get("name", tags.get("name:en", ""))
            if not name:
                continue
            name = name.replace(" MRT Station", "").replace(" MRT station", "")
            name = name.replace(" station", "").replace(" Station", "")

            if name not in stations:
                # Determine line from ref or network
                ref = tags.get("ref", "")
                color = "#888888"
                line_codes = []
                for code_prefix, info in [("NS", MRT_LINES["North-South Line"]),
                                           ("EW", MRT_LINES["East-West Line"]),
                                           ("NE", MRT_LINES["North-East Line"]),
                                           ("CC", MRT_LINES["Circle Line"]),
                                           ("DT", MRT_LINES["Downtown Line"]),
                                           ("TE", MRT_LINES["Thomson-East Coast Line"])]:
                    if ref.startswith(code_prefix):
                        color = info["color"]
                        line_codes.append(info["code"])
                        break

                stations[name] = {
                    "name": name,
                    "lon": round(node["lon"], 6),
                    "lat": round(node["lat"], 6),
                    "lines": line_codes if line_codes else ["unknown"],
                    "color": color,
                }

    return list(stations.values())


def simplify_linestring(coords: list[list[float]], tolerance: float = 0.0002) -> list[list[float]]:
    """Douglas-Peucker simplification to reduce point count while preserving shape.

    Tolerance of 0.0002 degrees ~ 22m at equator. Keeps curves accurate while
    removing redundant points on straight segments.
    """
    if len(coords) <= 2:
        return coords

    # Find the point with maximum distance from the line between first and last
    max_dist = 0
    max_idx = 0
    start = coords[0]
    end = coords[-1]

    for i in range(1, len(coords) - 1):
        dist = _point_line_distance(coords[i], start, end)
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > tolerance:
        left = simplify_linestring(coords[:max_idx + 1], tolerance)
        right = simplify_linestring(coords[max_idx:], tolerance)
        return left[:-1] + right
    else:
        return [coords[0], coords[-1]]


def _point_line_distance(point, line_start, line_end):
    """Perpendicular distance from point to line segment."""
    dx = line_end[0] - line_start[0]
    dy = line_end[1] - line_start[1]
    if dx == 0 and dy == 0:
        return _coord_dist(point, line_start)
    t = max(0, min(1, ((point[0] - line_start[0]) * dx + (point[1] - line_start[1]) * dy) / (dx * dx + dy * dy)))
    proj = [line_start[0] + t * dx, line_start[1] + t * dy]
    return _coord_dist(point, proj)


def build_lines_geojson(relations: list, ways: dict, nodes: dict) -> dict:
    """Build metro lines GeoJSON FeatureCollection."""
    features = []
    seen_codes = set()

    for relation in relations:
        line_info = identify_line(relation)
        if not line_info:
            tags = relation.get("tags", {})
            print(f"  Skipping unrecognized relation: {tags.get('name', 'unnamed')} (ref={tags.get('ref', '?')})")
            continue

        code = line_info["code"]
        if code in seen_codes:
            # Already processed this line — check if this relation has more detail
            new_coords = merge_ways_to_linestring(relation, ways, nodes)
            for feat in features:
                if feat["properties"]["code"] == code:
                    existing_raw = feat.get("_raw_count", len(feat["geometry"]["coordinates"]))
                    if len(new_coords) > existing_raw:
                        # This version is longer (more detailed) — use it
                        if len(new_coords) > 500:
                            simplified = simplify_linestring(new_coords, tolerance=0.00015)
                        else:
                            simplified = new_coords
                        feat["geometry"]["coordinates"] = simplified
                        feat["_raw_count"] = len(new_coords)
                        print(f"  {CANONICAL_NAMES.get(code, code)}: updated with {len(new_coords)} raw -> {len(simplified)} pts")
                    break
            continue

        coords = merge_ways_to_linestring(relation, ways, nodes)
        if not coords:
            print(f"  Warning: No coordinates for {CANONICAL_NAMES.get(code, code)}")
            continue

        # Simplify if very dense (>500 points) — keeps file size reasonable
        raw_count = len(coords)
        if raw_count > 500:
            coords = simplify_linestring(coords, tolerance=0.00015)

        print(f"  {CANONICAL_NAMES.get(code, code)}: {raw_count} raw points -> {len(coords)} simplified")

        seen_codes.add(code)
        feat = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "properties": {
                "name": CANONICAL_NAMES.get(code, code),
                "color": line_info["color"],
                "code": code,
            },
            "_raw_count": raw_count,
        }
        features.append(feat)

    # Sort by canonical order
    order = ["NSL", "EWL", "NEL", "CCL", "DTL", "TEL"]
    features.sort(key=lambda f: order.index(f["properties"]["code"]) if f["properties"]["code"] in order else 99)

    # Remove internal metadata before output
    for feat in features:
        feat.pop("_raw_count", None)

    return {"type": "FeatureCollection", "features": features}


def build_stations_geojson(stations: list[dict]) -> dict:
    """Build metro stations GeoJSON FeatureCollection."""
    features = []
    for station in sorted(stations, key=lambda s: s["name"]):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [station["lon"], station["lat"]],
            },
            "properties": {
                "name": station["name"],
                "line": "/".join(station["lines"]),
                "color": station["color"],
                "interchange": len(station["lines"]) > 1,
            },
        })

    return {"type": "FeatureCollection", "features": features}


def main():
    output_dir = Path(__file__).resolve().parent.parent / "public"

    print("=== Singapore MRT GeoJSON Generator ===\n")

    # Step 1: Fetch data from Overpass
    print("Step 1: Fetching MRT data from OpenStreetMap...")
    data = fetch_mrt_data()

    elements = data.get("elements", [])
    print(f"  Received {len(elements)} route elements")

    print("  Fetching station data...")
    station_data = fetch_station_data()
    station_elements = station_data.get("elements", [])
    print(f"  Received {len(station_elements)} station elements\n")

    # Merge station nodes (with tags) into the main data
    # The main query has skeleton nodes (no tags), so we overlay full station data
    station_nodes_by_id = {}
    for el in station_elements:
        if el["type"] == "node":
            station_nodes_by_id[el["id"]] = el

    # Step 2: Parse into structures
    print("Step 2: Parsing nodes, ways, and relations...")
    nodes, ways, relations = parse_overpass_response(data)

    # Overlay station tags onto skeleton nodes
    for nid, station_el in station_nodes_by_id.items():
        if nid in nodes:
            nodes[nid]["tags"] = station_el.get("tags", {})
        else:
            nodes[nid] = {
                "lat": station_el["lat"],
                "lon": station_el["lon"],
                "tags": station_el.get("tags", {}),
            }

    print(f"  Nodes: {len(nodes)}, Ways: {len(ways)}, Relations: {len(relations)}")
    print(f"  Station nodes with tags: {len(station_nodes_by_id)}\n")

    # Filter to MRT relations only
    mrt_relations = [r for r in relations if identify_line(r) is not None]
    print(f"  Identified {len(mrt_relations)} MRT line relations:")
    for r in mrt_relations:
        info = identify_line(r)
        tags = r.get("tags", {})
        print(f"    - {tags.get('name', '?')} => {info['code']}")
    print()

    # Step 3: Build lines GeoJSON
    print("Step 3: Building metro lines GeoJSON...")
    lines_geojson = build_lines_geojson(relations, ways, nodes)
    print(f"  Generated {len(lines_geojson['features'])} line features\n")

    # Step 4: Extract stations
    print("Step 4: Extracting stations...")
    stations = extract_stations(relations, ways, nodes)
    stations_geojson = build_stations_geojson(stations)
    print(f"  Generated {len(stations_geojson['features'])} station features\n")

    # Step 5: Summary
    print("Step 5: Summary")
    for feat in lines_geojson["features"]:
        props = feat["properties"]
        n_coords = len(feat["geometry"]["coordinates"])
        print(f"  {props['name']} ({props['code']}): {n_coords} points, color={props['color']}")

    interchange_count = sum(1 for f in stations_geojson["features"] if f["properties"]["interchange"])
    print(f"\n  Total stations: {len(stations_geojson['features'])} ({interchange_count} interchanges)")

    # Step 6: Write output
    lines_path = output_dir / "singapore-metro-lines.geojson"
    stations_path = output_dir / "singapore-metro-stations.geojson"

    with open(lines_path, "w", encoding="utf-8") as f:
        json.dump(lines_geojson, f, separators=(",", ":"))
    print(f"\n  Wrote {lines_path} ({lines_path.stat().st_size:,} bytes)")

    with open(stations_path, "w", encoding="utf-8") as f:
        json.dump(stations_geojson, f, separators=(",", ":"))
    print(f"  Wrote {stations_path} ({stations_path.stat().st_size:,} bytes)")

    print("\nDone!")


if __name__ == "__main__":
    main()
