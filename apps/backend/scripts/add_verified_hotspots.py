#!/usr/bin/env python3
"""Add research-agent-verified hotspots from DPUPKP and Agniban sources."""

import json
import math
import time
import requests
from pathlib import Path

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
PHOTON_URL = "https://photon.komoot.io/api/"
HEADERS = {"User-Agent": "FloodSafe/1.0 (flood-monitoring-nonprofit)"}

def geocode(query, center_lat, center_lng, country="id"):
    # Tier 1: Nominatim
    params = {"q": query, "format": "json", "limit": 1, "countrycodes": country}
    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
        results = r.json()
        if results:
            return round(float(results[0]["lat"]), 4), round(float(results[0]["lon"]), 4)
    except Exception:
        pass
    time.sleep(1.1)
    # Tier 4: Photon
    params2 = {"q": query, "limit": 1, "lat": center_lat, "lon": center_lng}
    try:
        r = requests.get(PHOTON_URL, params=params2, headers=HEADERS, timeout=10)
        data = r.json()
        if data.get("features"):
            c = data["features"][0]["geometry"]["coordinates"]
            return round(c[1], 4), round(c[0], 4)
    except Exception:
        pass
    return None


def is_dup(lat, lng, existing, threshold=0.001):
    for h in existing:
        if abs(lat - h["lat"]) < threshold and abs(lng - h["lng"]) < threshold:
            return h["name"]
    return None


def main():
    data_dir = Path(__file__).resolve().parent.parent / "data"

    # === YOGYAKARTA: DPUPKP official + BPBD high-value ===
    yogya_additions = [
        ("Jalan Batikan", "Jalan Batikan, Yogyakarta, Indonesia", "DPUPKP Kota Yogyakarta",
         "moderate", "Official DPUPKP waterlogging point -- drainage capacity inadequate for heavy rainfall"),
        ("Jalan Kusbini (Langensari)", "Jalan Kusbini, Yogyakarta, Indonesia", "DPUPKP Kota Yogyakarta",
         "moderate", "Official DPUPKP waterlogging point near Balai Yasa -- drainage obstruction"),
        ("Jalan Atmosukarto", "Jalan Atmosukarto, Yogyakarta, Indonesia", "DPUPKP Kota Yogyakarta",
         "moderate", "Official DPUPKP waterlogging point -- surface water accumulation during heavy rain"),
        ("Jalan Parangtritis Selatan (Jogokariyan)", "Jogokariyan, Mantrijeron, Yogyakarta, Indonesia",
         "DPUPKP Kota Yogyakarta", "high",
         "Official DPUPKP waterlogging point at Simpang Menukan/Jogokariyan intersection"),
        ("Tegalpanggung (Sungai Code)", "Tegalpanggung, Danurejan, Yogyakarta, Indonesia",
         "BPBD Kota Yogyakarta", "high",
         "Kelurahan along Sungai Code -- combined flood and landslide risk zone"),
        ("Bener (Sungai Winongo)", "Bener, Tegalrejo, Yogyakarta, Indonesia",
         "BPBD Kota Yogyakarta", "high",
         "Kelurahan on Sungai Winongo banks -- UGM flood study identified high-risk zone"),
        ("Pakuncen (Sungai Winongo)", "Pakuncen, Wirobrajan, Yogyakarta, Indonesia",
         "BPBD Kota Yogyakarta", "high",
         "Kelurahan with combined flood and landslide risk along Sungai Winongo"),
        ("Tegalgendu (Sungai Gajah Wong)", "Tegalgendu, Kotagede, Yogyakarta, Indonesia",
         "BPBD Kota Yogyakarta", "high",
         "BPBD CCTV+EWS monitoring point at Sungai Gajah Wong crossing"),
    ]

    d = json.load(open(data_dir / "yogyakarta_waterlogging_hotspots.json", "r", encoding="utf-8"))
    existing = d["hotspots"]
    next_id = max(h["id"] for h in existing if isinstance(h["id"], int)) + 1

    print("=== YOGYAKARTA ADDITIONS (DPUPKP + BPBD) ===")
    added_y = 0
    for name, query, source, severity, desc in yogya_additions:
        coords = geocode(query, -7.795, 110.365, "id")
        time.sleep(1.1)
        if not coords:
            print(f"  FAILED: {name}")
            continue
        lat, lng = coords
        if not (-7.95 <= lat <= -7.65 and 110.30 <= lng <= 110.50):
            print(f"  OUT OF BOUNDS: {name} ({lat}, {lng})")
            continue
        dup_name = is_dup(lat, lng, existing)
        if dup_name:
            print(f"  DUPLICATE: {name} ~ {dup_name}")
            continue
        # Zone assignment
        center_lat, center_lng = -7.795, 110.365
        dist = math.sqrt((lat - center_lat)**2 + (lng - center_lng)**2) * 111
        if dist < 1.5:
            zone = "central"
        elif lat > center_lat:
            zone = "east" if lng > 110.40 else "north"
        else:
            if lng > 110.40:
                zone = "east"
            elif lng < 110.35:
                zone = "west"
            else:
                zone = "south"

        hotspot = {
            "id": next_id, "name": name, "lat": lat, "lng": lng,
            "description": desc, "zone": zone,
            "severity_history": severity, "source": source,
        }
        existing.append(hotspot)
        next_id += 1
        added_y += 1
        print(f"  ADDED: {name} ({lat}, {lng}) zone={zone}")

    # Update metadata
    d["metadata"]["total_hotspots"] = len(existing)
    zones = {}
    for h in existing:
        zones[h["zone"]] = zones.get(h["zone"], 0) + 1
    d["metadata"]["zones"] = zones
    d["metadata"]["source"] = "BPBD Kota Yogyakarta, DPUPKP Kota Yogyakarta, PetaBencana.id, Tribun Jogja, Kompas"
    with open(data_dir / "yogyakarta_waterlogging_hotspots.json", "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    print(f"Yogyakarta: {added_y} added, total now {len(existing)}")

    # === INDORE: Agniban + FPJ verified ===
    indore_additions = [
        ("Super Corridor", "Super Corridor, Indore, Madhya Pradesh", "Free Press Journal",
         "high", "Metro construction debris blocked drainage -- 2-2.5 feet waterlogging over 2km stretch"),
        ("Gangaur Ghat", "Gangaur Ghat, Indore, Madhya Pradesh", "Free Press Journal",
         "high", "Khan River ghat area -- overflowing during peak monsoon floods"),
        ("Peeliya Khal", "Peeliya Khal, Indore, Madhya Pradesh", "Free Press Journal",
         "high", "Low-lying settlement -- houses flooded and residents evacuated during heavy rain"),
        ("Tulsi Nagar", "Tulsi Nagar, Indore, Madhya Pradesh", "Free Press Journal",
         "moderate", "Residential area with stagnant water issues reported to IMC commissioner"),
        ("North Toda", "North Toda, Indore, Madhya Pradesh", "Agniban",
         "high", "Riverside settlement near Khan River -- homes submerged during monsoon overflow"),
        ("South Toda", "South Toda, Indore, Madhya Pradesh", "Agniban",
         "high", "Riverside settlement near Khan River -- chronic flooding from river overflow"),
    ]

    d2 = json.load(open(data_dir / "indore_waterlogging_hotspots.json", "r", encoding="utf-8"))
    existing2 = d2["hotspots"]
    next_id2 = 70

    print("\n=== INDORE ADDITIONS (Agniban + FPJ verified) ===")
    added_i = 0
    for name, query, source, severity, desc in indore_additions:
        coords = geocode(query, 22.7186, 75.8576, "in")
        time.sleep(1.1)
        if not coords:
            print(f"  FAILED: {name}")
            continue
        lat, lng = coords
        if not (22.52 <= lat <= 22.85 and 75.72 <= lng <= 75.97):
            print(f"  OUT OF BOUNDS: {name} ({lat}, {lng})")
            continue
        dup_name = is_dup(lat, lng, existing2)
        if dup_name:
            print(f"  DUPLICATE: {name} ~ {dup_name}")
            continue

        dist_center = math.sqrt((lat - 22.7186)**2 + (lng - 75.8576)**2) * 111
        if dist_center < 2:
            zone = "Central"
        elif lat < 22.71:
            zone = "Bypass" if lng < 75.85 else "South"
        elif 3 <= dist_center <= 6:
            zone = "Ring Road"
        else:
            zone = "Other"

        hotspot = {
            "id": f"indore-{next_id2:03d}", "name": name, "lat": lat, "lng": lng,
            "description": desc, "zone": zone,
            "severity_history": severity, "source": source,
        }
        existing2.append(hotspot)
        next_id2 += 1
        added_i += 1
        print(f"  ADDED: {name} ({lat}, {lng}) zone={zone}")

    d2["metadata"]["total_hotspots"] = len(existing2)
    zones2 = {}
    for h in existing2:
        zones2[h["zone"]] = zones2.get(h["zone"], 0) + 1
    d2["metadata"]["zones"] = zones2
    d2["metadata"]["source"] = "IMC, Free Press Journal, Smart City Indore, KnockSense, Ground Report, Daily Pioneer, Agniban"
    with open(data_dir / "indore_waterlogging_hotspots.json", "w", encoding="utf-8") as f:
        json.dump(d2, f, indent=2, ensure_ascii=False)
    print(f"Indore: {added_i} added, total now {len(existing2)}")


if __name__ == "__main__":
    main()
