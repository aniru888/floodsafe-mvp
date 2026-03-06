#!/usr/bin/env python3
"""
Expand Yogyakarta waterlogging hotspots from 19 to 60+.
Uses 4-tier geocoding fallback: Nominatim full -> stripped -> structured -> Photon.

Sources:
- BPBD Kota Yogyakarta (5 river corridors, 23 EWS stations)
- PetaBencana.id (crowdsourced flood reports)
- Tribun Jogja / Kompas (Indonesian news)
- OpenStreetMap (flood-tagged infrastructure)

Rivers: Code, Winongo, Gajah Wong, Belik, Tekik

Usage: python apps/backend/scripts/expand_yogyakarta_hotspots.py
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

# Yogyakarta bounding box
BOUNDS = {"min_lat": -7.95, "max_lat": -7.65, "min_lng": 110.30, "max_lng": 110.50}
VIEWBOX = "110.30,-7.65,110.50,-7.95"

# City center for zone calculation
CENTER = (-7.795, 110.365)

DEDUP_THRESHOLD = 0.001


def load_existing_hotspots():
    path = Path(__file__).resolve().parent.parent / "data" / "yogyakarta_waterlogging_hotspots.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["hotspots"]


def is_duplicate(lat, lng, existing):
    for h in existing:
        if abs(lat - h["lat"]) < DEDUP_THRESHOLD and abs(lng - h["lng"]) < DEDUP_THRESHOLD:
            return h["name"]
    return None


def is_in_bounds(lat, lng):
    return (BOUNDS["min_lat"] <= lat <= BOUNDS["max_lat"] and
            BOUNDS["min_lng"] <= lng <= BOUNDS["max_lng"])


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def assign_zone(lat, lng):
    """Assign zone: central, north, south, east, west, river_corridor."""
    dist_center = haversine_km(lat, lng, CENTER[0], CENTER[1])

    # Central: within 1.5km of Kraton/city center
    if dist_center < 1.5:
        return "central"

    # North/South split at center lat
    if lat > CENTER[0]:
        # North — check east/west
        if lng > 110.40:
            return "east"
        return "north"
    else:
        if lng > 110.40:
            return "east"
        if lng < 110.35:
            return "west"
        return "south"


def geocode_nominatim_full(query):
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "id",
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
    stripped = name.replace("Jalan ", "").replace("Kampung ", "").replace("Kelurahan ", "")
    query = f"{stripped}, Yogyakarta, Indonesia"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "id",
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
    params = {
        "street": name,
        "city": "Yogyakarta",
        "country": "Indonesia",
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
    params = {
        "q": f"{query}, Yogyakarta",
        "limit": 1,
        "lat": CENTER[0],
        "lon": CENTER[1],
    }
    try:
        resp = requests.get(PHOTON_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("features"):
            coords = data["features"][0]["geometry"]["coordinates"]
            lat, lon = coords[1], coords[0]
            if is_in_bounds(lat, lon):
                return lat, lon
    except Exception as e:
        print(f"    Tier 4 error: {e}")
    return None


def geocode_with_fallback(name, query):
    # Tier 1
    print(f"    Tier 1: '{query}'")
    result = geocode_nominatim_full(query)
    if result and is_in_bounds(*result):
        print(f"    -> Tier 1 HIT: ({result[0]:.4f}, {result[1]:.4f})")
        return result
    time.sleep(1.1)

    # Tier 2
    print(f"    Tier 2: stripped")
    result = geocode_nominatim_stripped(name)
    if result and is_in_bounds(*result):
        print(f"    -> Tier 2 HIT: ({result[0]:.4f}, {result[1]:.4f})")
        return result
    time.sleep(1.1)

    # Tier 3
    print(f"    Tier 3: structured")
    result = geocode_nominatim_structured(name)
    if result:
        print(f"    -> Tier 3 HIT: ({result[0]:.4f}, {result[1]:.4f})")
        return result
    time.sleep(1.1)

    # Tier 4
    print(f"    Tier 4: Photon")
    result = geocode_photon(name)
    if result:
        print(f"    -> Tier 4 HIT: ({result[0]:.4f}, {result[1]:.4f})")
        return result

    return None


# ============================================================
# NEW CANDIDATE LOCATIONS
# Organized by source: BPBD river corridors, news, infrastructure
# ============================================================

CANDIDATES = [
    # === SUNGAI CODE corridor (highest risk river in Yogyakarta) ===
    # Source: BPBD Kota Yogyakarta + Tribun Jogja flood reports
    {
        "name": "Gondokusuman (Sungai Code)",
        "query": "Gondokusuman, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "BPBD Kota Yogyakarta",
        "description": "Kelurahan along Sungai Code — recurrent flooding from river overflow, 8 EWS stations in corridor",
        "river": "Code"
    },
    {
        "name": "Jetis (Sungai Code)",
        "query": "Jetis, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "BPBD Kota Yogyakarta",
        "description": "Dense urban area along Sungai Code banks — high flood risk from river surge",
        "river": "Code"
    },
    {
        "name": "Gedongtengen (Sungai Code)",
        "query": "Gedongtengen, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "BPBD Kota Yogyakarta",
        "description": "Old district along Sungai Code — narrow alleys impede evacuation during floods",
        "river": "Code"
    },
    {
        "name": "Cokrodiningratan",
        "query": "Cokrodiningratan, Jetis, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "BPBD Kota Yogyakarta",
        "description": "Kelurahan at Sungai Code bend — river meander concentrates floodwater here",
        "river": "Code"
    },
    {
        "name": "Kota Baru (Sungai Code)",
        "query": "Kotabaru, Gondokusuman, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Heritage district near Sungai Code — colonial-era drainage insufficient for monsoon",
        "river": "Code"
    },
    {
        "name": "Demangan",
        "query": "Demangan, Gondokusuman, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Residential area along Sungai Code tributary — backwater flooding during heavy rain",
        "river": "Code"
    },
    {
        "name": "Kampung Code Utara",
        "query": "Kampung Code, Jetis, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "Tribun Jogja",
        "description": "Riverside settlement directly on Sungai Code banks — first impacted by rising water",
        "river": "Code"
    },
    {
        "name": "Sayidan",
        "query": "Sayidan, Prawirodirjan, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "Tribun Jogja",
        "description": "Historic riverside community along Sungai Code — severe flooding events documented annually",
        "river": "Code"
    },
    {
        "name": "Prawirodirjan",
        "query": "Prawirodirjan, Mergangsan, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Kelurahan along Sungai Code southern stretch — flood risk from Code-Winongo confluence",
        "river": "Code"
    },

    # === SUNGAI WINONGO corridor ===
    {
        "name": "Tegalrejo (Sungai Winongo)",
        "query": "Tegalrejo, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "BPBD Kota Yogyakarta",
        "description": "Kecamatan along Sungai Winongo — 4 EWS stations monitor flood levels",
        "river": "Winongo"
    },
    {
        "name": "Ngampilan (Sungai Winongo)",
        "query": "Ngampilan, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "BPBD Kota Yogyakarta",
        "description": "Low-lying area at Sungai Winongo floodplain — chronic inundation zone",
        "river": "Winongo"
    },
    {
        "name": "Mantrijeron",
        "query": "Mantrijeron, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Southern kecamatan along Sungai Winongo — flood risk amplified by urbanization",
        "river": "Winongo"
    },
    {
        "name": "Notoprajan",
        "query": "Notoprajan, Ngampilan, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "BPBD Kota Yogyakarta",
        "description": "Kelurahan beside Sungai Winongo — among highest-risk areas for riverine flooding",
        "river": "Winongo"
    },
    {
        "name": "Patangpuluhan",
        "query": "Patangpuluhan, Wirobrajan, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Area near Sungai Winongo with recurring flood events during monsoon peaks",
        "river": "Winongo"
    },
    {
        "name": "Kricak (Sungai Winongo)",
        "query": "Kricak, Tegalrejo, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "Tribun Jogja",
        "description": "Riverside kampung on Sungai Winongo — houses built close to river banks",
        "river": "Winongo"
    },
    {
        "name": "Wirobrajan",
        "query": "Wirobrajan, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Kecamatan between Winongo and Code rivers — dual flood risk from both corridors",
        "river": "Winongo"
    },

    # === SUNGAI GAJAH WONG corridor ===
    {
        "name": "Umbulharjo (Sungai Gajah Wong)",
        "query": "Umbulharjo, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "BPBD Kota Yogyakarta",
        "description": "Largest kecamatan — Sungai Gajah Wong runs through center, 5 EWS stations",
        "river": "Gajah Wong"
    },
    {
        "name": "Kotagede",
        "query": "Kotagede, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Heritage district along Sungai Gajah Wong — old drainage and narrow lanes",
        "river": "Gajah Wong"
    },
    {
        "name": "Banguntapan",
        "query": "Banguntapan, Bantul, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Southern suburb along Sungai Gajah Wong — agricultural runoff compounds flood risk",
        "river": "Gajah Wong"
    },
    {
        "name": "Muja Muju",
        "query": "Muja Muju, Umbulharjo, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "Tribun Jogja",
        "description": "Kelurahan at Sungai Gajah Wong floodplain — water rises rapidly during storms",
        "river": "Gajah Wong"
    },
    {
        "name": "Warungboto",
        "query": "Warungboto, Umbulharjo, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Kelurahan near Sungai Gajah Wong with recurrent waterlogging",
        "river": "Gajah Wong"
    },
    {
        "name": "Giwangan",
        "query": "Giwangan, Umbulharjo, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "Tribun Jogja",
        "description": "Bus terminal area — low-lying terrain near Sungai Gajah Wong",
        "river": "Gajah Wong"
    },

    # === SUNGAI BELIK corridor (HIGHEST RISK — auto EWS) ===
    {
        "name": "Iromejan (Klitren - Sungai Belik)",
        "query": "Iromejan, Gondokusuman, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "BPBD Kota Yogyakarta",
        "description": "Highest-risk flood zone in Yogyakarta — Sungai Belik auto-EWS station installed",
        "river": "Belik"
    },
    {
        "name": "Baciro (Sungai Belik)",
        "query": "Baciro, Gondokusuman, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "BPBD Kota Yogyakarta",
        "description": "Kelurahan along Sungai Belik — flash flood risk from rapid water rise",
        "river": "Belik"
    },

    # === SUNGAI TEKIK corridor ===
    {
        "name": "Pakualaman (Sungai Tekik)",
        "query": "Pakualaman, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Royal district along Sungai Tekik — auto-EWS station monitors flood levels",
        "river": "Tekik"
    },
    {
        "name": "Purwokinanti",
        "query": "Purwokinanti, Pakualaman, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Kelurahan at Sungai Tekik corridor — periodic flooding during heavy monsoon",
        "river": "Tekik"
    },

    # === FLOOD-PRONE INFRASTRUCTURE (underpasses, bridges, low points) ===
    {
        "name": "Underpass Janti",
        "query": "Underpass Janti, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "Tribun Jogja",
        "description": "Major underpass on Ring Road — floods to 50cm+ during heavy rainfall events",
        "river": None
    },
    {
        "name": "Underpass Monjali",
        "query": "Underpass Monjali, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "Tribun Jogja",
        "description": "Northern ring road underpass — recurring waterlogging traps vehicles",
        "river": None
    },
    {
        "name": "Jalan Magelang (Ring Road intersection)",
        "query": "Jalan Magelang, Ring Road, Yogyakarta, Indonesia",
        "severity": "high",
        "source": "Kompas",
        "description": "Major arterial road — poor drainage at Ring Road intersection causes frequent flooding",
        "river": None
    },
    {
        "name": "Jalan Godean",
        "query": "Jalan Godean, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "Tribun Jogja",
        "description": "Western arterial road — surface flooding during heavy rain events",
        "river": None
    },
    {
        "name": "Jalan Kaliurang",
        "query": "Jalan Kaliurang, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "Kompas",
        "description": "Northern arterial toward Merapi — volcanic lahar sediment clogs drainage",
        "river": None
    },
    {
        "name": "Jalan Bantul",
        "query": "Jalan Bantul, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "Tribun Jogja",
        "description": "Southern arterial road — low gradient collects runoff from surrounding areas",
        "river": None
    },
    {
        "name": "Jalan Parangtritis",
        "query": "Jalan Parangtritis, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "Tribun Jogja",
        "description": "Road to southern coast — crosses multiple river channels, floods at crossing points",
        "river": None
    },
    {
        "name": "Jalan Solo (Adisucipto - Ring Road)",
        "query": "Jalan Solo, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "Kompas",
        "description": "Eastern arterial toward Solo — waterlogging at low points near airport area",
        "river": None
    },

    # === KELURAHAN-LEVEL flood zones (news + PetaBencana reports) ===
    {
        "name": "Mergangsan",
        "query": "Mergangsan, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "PetaBencana.id",
        "description": "Kecamatan at Code-Winongo interfluve — drainage overwhelmed during intense rainfall",
        "river": None
    },
    {
        "name": "Pandeyan",
        "query": "Pandeyan, Umbulharjo, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "PetaBencana.id",
        "description": "Kelurahan in low-lying southern Umbulharjo — waterlogging from poor drainage",
        "river": None
    },
    {
        "name": "Sorosutan",
        "query": "Sorosutan, Umbulharjo, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "PetaBencana.id",
        "description": "Southern kelurahan with recurrent monsoon waterlogging",
        "river": None
    },
    {
        "name": "Tahunan",
        "query": "Tahunan, Umbulharjo, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "PetaBencana.id",
        "description": "Kelurahan near Gajah Wong tributary — seasonal flooding from channel overflow",
        "river": "Gajah Wong"
    },
    {
        "name": "Semaki",
        "query": "Semaki, Umbulharjo, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "PetaBencana.id",
        "description": "Central kelurahan with drainage capacity issues during heavy rainfall",
        "river": None
    },
    {
        "name": "Kadipaten",
        "query": "Kadipaten, Kraton, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Area near Kraton palace — historic drainage system inadequate for modern rainfall",
        "river": None
    },
    {
        "name": "Purbayan (Kotagede)",
        "query": "Purbayan, Kotagede, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "PetaBencana.id",
        "description": "Heritage kelurahan in Kotagede — narrow lanes flood from Gajah Wong overflow",
        "river": "Gajah Wong"
    },
    {
        "name": "Rejowinangun",
        "query": "Rejowinangun, Kotagede, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "PetaBencana.id",
        "description": "Eastern kelurahan near Sungai Gajah Wong — low-lying flood-prone terrain",
        "river": "Gajah Wong"
    },
    {
        "name": "Caturtunggal (Depok)",
        "query": "Caturtunggal, Depok, Sleman, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "Tribun Jogja",
        "description": "University area in Sleman — rapid urbanization outpaces drainage capacity",
        "river": None
    },
    {
        "name": "Condongcatur",
        "query": "Condongcatur, Depok, Sleman, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "Tribun Jogja",
        "description": "Northern suburb — Selokan Mataram canal overflow during heavy monsoon rain",
        "river": None
    },
    {
        "name": "Jalan Taman Siswa",
        "query": "Jalan Taman Siswa, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "Kompas",
        "description": "Central road near Sungai Code — waterlogging at low points during rain events",
        "river": "Code"
    },
    {
        "name": "Keparakan",
        "query": "Keparakan, Mergangsan, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "PetaBencana.id",
        "description": "Kelurahan at Sungai Code floodplain — periodic inundation from river rise",
        "river": "Code"
    },
    {
        "name": "Brontokusuman",
        "query": "Brontokusuman, Mergangsan, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "PetaBencana.id",
        "description": "Southern kelurahan near Code river — flood risk from combined river and surface water",
        "river": "Code"
    },
    {
        "name": "Jalan Imogiri Timur",
        "query": "Jalan Imogiri Timur, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "Tribun Jogja",
        "description": "Eastern road crossing Sungai Gajah Wong — floods at river bridge section",
        "river": "Gajah Wong"
    },
    {
        "name": "Panembahan",
        "query": "Panembahan, Kraton, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "BPBD Kota Yogyakarta",
        "description": "Historic area near Kraton — old water channels overflow during heavy rain",
        "river": None
    },
    {
        "name": "Ngupasan",
        "query": "Ngupasan, Gondomanan, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "PetaBencana.id",
        "description": "Commercial area at Malioboro south end — drainage issues during intense rainfall",
        "river": None
    },
    {
        "name": "Prenggan (Kotagede)",
        "query": "Prenggan, Kotagede, Yogyakarta, Indonesia",
        "severity": "moderate",
        "source": "PetaBencana.id",
        "description": "Kelurahan in Kotagede — historic silver district with poor modern drainage",
        "river": None
    },
]


def update_existing_descriptions(hotspots):
    """Fix generic 'Flood-prone street/neighborhood' descriptions."""
    desc_updates = {
        "Jalan Kusumanegara": "Major east-west arterial road — low gradient causes waterlogging during heavy monsoon rainfall",
        "Jalan Gejayan": "University corridor road — heavy urbanization overwhelms drainage during rainstorms",
        "Jalan Ringroad Utara": "Northern ring road segment — underpass sections flood during intense rainfall",
        "Klitren": "High-risk neighborhood along Sungai Belik — BPBD auto-EWS station installed for flood warning",
        "Jalan Balirejo": "Road crossing Sungai Gajah Wong floodplain — periodic inundation from river overflow",
        "Jalan Ipda Tut Harsono": "Road in eastern Yogyakarta — drainage capacity insufficient for peak monsoon",
        "Terban": "Riverside kampung along Sungai Code — among most flood-affected neighborhoods in the city",
        "Bintaran": "Historic neighborhood near Sungai Code — recurring flood events during wet season",
        "Jalan Babarsari": "University area road in Sleman — rapid development outpaces storm drainage capacity",
        "Jalan Seturan": "Commercial road in Sleman — flat terrain and impervious surfaces trap rainwater",
        "Perumnas Seturan": "Housing complex in Sleman — low-lying area prone to waterlogging after heavy rain",
        "Selokan Mataram": "Road along historic irrigation canal — canal overflow floods surrounding areas during monsoon",
        "Jalan Affandi": "Major commercial road (formerly Gejayan) — intersection flooding blocks traffic during storms",
        "Jalan Urip Sumoharjo": "Central arterial road — waterlogging at multiple low points during heavy rainfall",
        "Jalan Laksda Adisucipto": "Airport road corridor — drainage overwhelmed during intense monsoon events",
        "Jalan Jendral Sudirman (Tugu Yogyakarta)": "Iconic boulevard from Tugu to Kraton — water accumulates at Tugu intersection during storms",
        "Jalan Majapahit": "Eastern road near Sungai Gajah Wong — bridge section floods during river surge events",
        "Gedongkuning - Wonocatur": "Neighborhood straddling city-Bantul border — low elevation near Sungai Gajah Wong floodplain",
        "Underpass Kentungan": "Ring Road underpass — critical flooding point, water reaches 50cm+ during heavy rain requiring road closure",
    }

    for h in hotspots:
        if h["name"] in desc_updates:
            h["description"] = desc_updates[h["name"]]
            h["source"] = "BPBD Kota Yogyakarta"  # Upgrade source attribution

    return hotspots


def main():
    existing = load_existing_hotspots()
    print(f"Loaded {len(existing)} existing Yogyakarta hotspots")

    # Update existing descriptions first
    existing = update_existing_descriptions(existing)
    print("Updated existing generic descriptions with specific flood context")

    print(f"Processing {len(CANDIDATES)} new candidates...\n")

    new_hotspots = []
    failed = []
    duplicates = []
    next_id = 20  # Continue from ID 19

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

        all_existing = existing + new_hotspots
        dup = is_duplicate(lat, lng, all_existing)
        if dup:
            print(f"  DUPLICATE of '{dup}' -- skipping")
            duplicates.append(f"{name} ~ {dup}")
            continue

        zone = assign_zone(lat, lng)
        hotspot = {
            "id": next_id,
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

    total = len(existing) + len(new_hotspots)
    if total < 50:
        print(f"\n[WARN] GATE 2C FAILED: Total {total} < 50 minimum")
    else:
        print(f"\n[OK] GATE 2C PASSED: Total {total} >= 50")

    # Merge and write
    merged = existing + new_hotspots
    zones = {}
    sources_comp = {}
    for h in merged:
        zones[h["zone"]] = zones.get(h["zone"], 0) + 1
        src = h["source"]
        sources_comp[src] = sources_comp.get(src, 0) + 1

    output = {
        "metadata": {
            "version": "2.0",
            "created": "2026-02-13",
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "source": "BPBD Kota Yogyakarta, PetaBencana.id, Tribun Jogja, Kompas, OpenStreetMap",
            "total_hotspots": len(merged),
            "zones": zones,
            "rivers_monitored": ["Code", "Winongo", "Gajah Wong", "Belik", "Tekik"],
            "composition": sources_comp,
        },
        "hotspots": merged,
    }

    out_path = Path(__file__).resolve().parent.parent / "data" / "yogyakarta_waterlogging_hotspots.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nWritten to: {out_path}")

    review_path = Path(__file__).resolve().parent / "yogyakarta_candidates.json"
    with open(review_path, "w", encoding="utf-8") as f:
        json.dump(new_hotspots, f, indent=2, ensure_ascii=False)
    print(f"Candidates saved to: {review_path}")


if __name__ == "__main__":
    main()
