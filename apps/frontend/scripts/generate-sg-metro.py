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

# Gap detection: segments further apart than this are branch lines, not continuations.
# 0.005 degrees ≈ 550m at Singapore's latitude (1.3°N). Real adjacent ways share endpoints
# (gap < 1m), while branch lines like EWL Changi Airport spur have multi-km gaps.
GAP_THRESHOLD = 0.005

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

# Official terminal stations with approximate coordinates from LTA rail map.
# Used to validate that generated lines start/end at the correct locations.
EXPECTED_TERMINALS = {
    "NSL": {"Jurong East": [103.742, 1.333], "Marina South Pier": [103.863, 1.271]},
    "EWL": {"Tuas Link": [103.637, 1.341], "Pasir Ris": [103.949, 1.373]},
    "NEL": {"HarbourFront": [103.823, 1.265], "Punggol Coast": [103.911, 1.415]},
    "CCL": {"HarbourFront": [103.823, 1.265], "Marina Bay": [103.854, 1.275]},
    "DTL": {"Bukit Panjang": [103.764, 1.384], "Expo": [103.962, 1.335]},
    "TEL": {"Woodlands North": [103.786, 1.448], "Bayshore": [103.942, 1.313]},
}

# Known station-proximity exceptions (branch lines, OSM gaps).
# Stations listed here are expected to exceed the proximity threshold.
STATION_PROXIMITY_EXCEPTIONS = {
    "EWL": {"Changi Airport", "Expo"},       # CG branch line
    "CCL": {"Dhoby Ghaut", "Bras Basah", "Esplanade"},  # Stage 6 gap in OSM
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

    # Chain ways together by matching endpoints, skipping branch segments
    result = list(way_coords[0])
    skipped_branches = 0

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
        min_dist = min(dist_to_first, dist_to_last)

        # Skip segments that are far from the chain end — these are branch lines
        if min_dist > GAP_THRESHOLD:
            skipped_branches += 1
            continue

        if dist_to_last < dist_to_first:
            # Reverse the segment
            segment = list(reversed(segment))

        # Skip the first point if it matches (avoid duplicates)
        if result and segment and _coord_dist(result[-1], segment[0]) < 0.0001:
            result.extend(segment[1:])
        else:
            result.extend(segment)

    if skipped_branches:
        tags = relation.get("tags", {})
        print(f"    Skipped {skipped_branches} branch segment(s) in {tags.get('name', '?')}")

    return result


def _coord_dist(a: list[float], b: list[float]) -> float:
    """Simple Euclidean distance between two [lon, lat] coordinates."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _remove_backtrack(coords: list[list[float]], window: int = 20, threshold: float = 0.0003) -> list[list[float]]:
    """Remove spur/backtrack loops where a later point nearly matches an earlier one.

    Scans within a sliding window for near-duplicate coordinates. When found,
    the points between them (the spur) are removed. This fixes artifacts like
    DTL's southwest spike at Bukit Panjang where overlapping OSM ways cause
    the line to trace out and snap back.

    Args:
        coords: LineString coordinates [lon, lat].
        window: How far ahead to look for a match (20 points ≈ short spurs).
        threshold: Distance in degrees to consider a "match" (~33m).
    """
    if len(coords) < 4:
        return coords

    result = list(coords)
    i = 0
    while i < len(result) - 2:
        # Look ahead within the window for a point near result[i]
        for j in range(i + 2, min(i + window, len(result))):
            if _coord_dist(result[i], result[j]) < threshold:
                # Found a backtrack: remove the spur between i+1 and j
                spur_len = j - i - 1
                if spur_len > 0:
                    del result[i + 1: j]
                break
        i += 1

    return result


def _smooth_zigzag_start(coords: list[list[float]], max_check: int = 5) -> list[list[float]]:
    """Remove zigzag points at the start of a line.

    Checks the first few coordinates for direction reversals (negative dot product
    of consecutive direction vectors). Removes offending initial points until the
    line flows consistently.

    Args:
        coords: LineString coordinates [lon, lat].
        max_check: Maximum number of initial points to examine.
    """
    if len(coords) < 4:
        return coords

    result = list(coords)
    removed = 0

    while len(result) >= 4 and removed < max_check:
        # Direction vectors for first two segments
        d1 = [result[1][0] - result[0][0], result[1][1] - result[0][1]]
        d2 = [result[2][0] - result[1][0], result[2][1] - result[1][1]]

        # Dot product — negative means reversal
        dot = d1[0] * d2[0] + d1[1] * d2[1]
        if dot < 0:
            result.pop(0)
            removed += 1
        else:
            break

    return result


def _close_loop_if_needed(coords: list[list[float]], code: str, threshold: float = 0.002) -> list[list[float]]:
    """Close a loop for the Circle Line (CCL) if endpoints are near each other.

    CCL Stage 6 opened in 2025, completing the full circle. If the first and last
    coordinates are within ~220m (0.002 degrees), append the first point to close
    the ring — this makes MapLibre render a smooth loop without a gap.

    Args:
        coords: LineString coordinates [lon, lat].
        code: MRT line code (only applies to "CCL").
        threshold: Max distance between endpoints to trigger closure.
    """
    if code != "CCL" or len(coords) < 10:
        return coords

    # Check if already closed (first == last)
    if _coord_dist(coords[0], coords[-1]) < 0.0001:
        return coords  # Already a closed ring

    # Close the ring if endpoints are near enough
    if _coord_dist(coords[0], coords[-1]) < threshold:
        return coords + [coords[0]]

    return coords


def _postprocess_line(coords: list[list[float]], code: str) -> list[list[float]]:
    """Apply all post-processing steps to a merged line's coordinates.

    Pipeline: remove backtracks → smooth zigzag start → close loop (CCL only).
    """
    coords = _remove_backtrack(coords)
    coords = _smooth_zigzag_start(coords)
    coords = _close_loop_if_needed(coords, code)
    return coords


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
            new_coords = _postprocess_line(new_coords, code)
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

        # Post-process: remove backtracks, smooth start, close CCL loop
        coords = _postprocess_line(coords, code)

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



def _min_distance_to_line(point: list[float], line_coords: list[list[float]]) -> float:
    """Minimum distance from a point to any segment in a polyline."""
    min_dist = float("inf")
    for i in range(len(line_coords) - 1):
        d = _point_line_distance(point, line_coords[i], line_coords[i + 1])
        if d < min_dist:
            min_dist = d
    return min_dist


def _validate_against_stations(
    lines_geojson: dict,
    stations_geojson: dict,
    threshold: float = 0.005,
) -> bool:
    """Validate generated line geometry against known station positions.

    Performs two checks:
    1. Station proximity — each station on a line should be within `threshold`
       (~550m at equator) of the line geometry.
    2. Terminal endpoints — each line's start/end should be near its official
       terminal stations (from EXPECTED_TERMINALS).

    Returns True if all non-excepted checks pass.
    """
    print("\nStep 6: Validation (station-proximity + terminal check)")

    # Index lines by code
    lines_by_code: dict[str, list[list[float]]] = {}
    for feat in lines_geojson["features"]:
        code = feat["properties"]["code"]
        lines_by_code[code] = feat["geometry"]["coordinates"]

    # Index stations by line
    stations_by_line: dict[str, list[dict]] = {code: [] for code in lines_by_code}
    for feat in stations_geojson["features"]:
        name = feat["properties"]["name"]
        coords = feat["geometry"]["coordinates"]  # [lon, lat]
        line_str = feat["properties"]["line"]      # e.g. "NSL" or "NSL/EWL"
        for line_code in line_str.split("/"):
            if line_code in stations_by_line:
                stations_by_line[line_code].append({"name": name, "coords": coords})

    all_pass = True

    # --- Check 1: Station proximity ---
    print("  Station proximity (threshold: {:.0f}m):".format(threshold * 111_000))
    for code in sorted(lines_by_code.keys()):
        line_coords = lines_by_code[code]
        stations = stations_by_line.get(code, [])
        exceptions = STATION_PROXIMITY_EXCEPTIONS.get(code, set())

        hits = 0
        misses = []
        for st in stations:
            dist = _min_distance_to_line(st["coords"], line_coords)
            if dist <= threshold:
                hits += 1
            else:
                is_expected = st["name"] in exceptions
                misses.append((st["name"], dist, is_expected))
                if not is_expected:
                    all_pass = False

        total = len(stations)
        pct = (hits / total * 100) if total > 0 else 0
        unexpected = [m for m in misses if not m[2]]
        status = "PASS" if not unexpected else "FAIL"
        print(f"    {code}: {hits}/{total} ({pct:.0f}%) [{status}]", end="")
        if misses:
            expected_str = ", ".join(
                f"{n} ({d * 111:.1f}km, expected)" for n, d, exp in misses if exp
            )
            unexpected_str = ", ".join(
                f"{n} ({d * 111:.1f}km)" for n, d, exp in misses if not exp
            )
            parts = [s for s in [expected_str, unexpected_str] if s]
            print(f"  missed: {'; '.join(parts)}", end="")
        print()

    # --- Check 2: Terminal endpoints ---
    print("  Terminal endpoint check (1km tolerance):")
    terminal_threshold = 0.009  # ~1km
    for code, terminals in EXPECTED_TERMINALS.items():
        if code not in lines_by_code:
            print(f"    {code}: SKIP (no line geometry)")
            continue

        line_coords = lines_by_code[code]
        # Check first and last 5 coordinates (line could be reversed)
        head = line_coords[:5]
        tail = line_coords[-5:]

        terminal_ok = True
        for name, expected_coord in terminals.items():
            # Find min distance to either end
            d_head = min(_coord_dist(expected_coord, c) for c in head)
            d_tail = min(_coord_dist(expected_coord, c) for c in tail)
            d_min = min(d_head, d_tail)
            end_label = "start" if d_head < d_tail else "end"

            if d_min > terminal_threshold:
                print(f"    {code} {name}: FAIL ({d_min * 111:.1f}km from nearest end)")
                terminal_ok = False
                all_pass = False
            else:
                print(f"    {code} {name}: PASS (near {end_label}, {d_min * 111:.1f}km)")

    # --- Overall ---
    overall = "ALL CHECKS PASSED" if all_pass else "SOME CHECKS FAILED"
    print(f"\n  Validation result: {overall}")
    return all_pass

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

    # Step 6: Validate generated geometry against known stations
    _validate_against_stations(lines_geojson, stations_geojson)

    # Step 7: Write output
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
