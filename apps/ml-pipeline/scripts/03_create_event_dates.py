"""
Phase 4: Create flood event date JSONs for Part B temporal analysis.

Curates verified flood event dates and dry reference dates for Bangalore
and Yogyakarta from the research document at:
    docs/plans/flood-event-dates-research.md

Flood dates: Only HIGH and MEDIUM confidence events with exact dates.
    Month-level (LOW) dates are excluded because SAR extraction needs
    specific dates to query Sentinel-1 imagery.

Dry dates: Selected from climatological dry seasons:
    - Bangalore (India): January-February (winter, <10mm monthly average)
    - Yogyakarta: June-August (BMKG dry season)
    Spread across the same years as flood events for temporal balance.

Storm clusters: Multi-day events from the same weather system are tagged
    with a shared storm_cluster ID. The temporal analysis phase uses these
    to count effective independent observations (effective n), not raw dates.

Output:
    apps/ml-pipeline/output/temporal/bangalore_event_dates.json
    apps/ml-pipeline/output/temporal/yogyakarta_event_dates.json

Usage:
    python scripts/03_create_event_dates.py
"""

import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "temporal"


def create_bangalore_event_dates() -> dict:
    """
    Curate Bangalore flood dates from research doc.

    Source: docs/plans/flood-event-dates-research.md, Section 2.
    All 16 events are post-2014 (Sentinel-1 era).
    Skipped: 2022-06-18 (LOW confidence, month-level only).
    """
    return {
        "city": "bangalore",
        "flood_dates": [
            {
                "date": "2014-09-26",
                "source": "Tandfonline research paper",
                "url": "https://www.tandfonline.com/doi/full/10.1080/19475683.2016.1144649",
                "affected_areas": ["Widespread"],
                "severity": "Cloudburst, 89.6mm in ~70 minutes",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2017-08-15",
                "source": "Scroll.in",
                "url": "https://scroll.in/latest/847311/in-photos-overnight-rain-wreaks-havoc-in-bengaluru-inundates-several-parts-of-the-city",
                "affected_areas": [
                    "Koramangala", "HSR Layout", "Shantinagar",
                    "Wilson Garden", "KR Puram",
                ],
                "severity": "HAL: 144mm, City: 129mm in 24h",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2018-08-14",
                "source": "FloodList",
                "url": "https://floodlist.com/asia/india-floods-landslides-karnataka-august-2018",
                "affected_areas": ["Karnataka-wide including Bengaluru"],
                "severity": "Severe flooding and landslides, state-level",
                "tier": 3,
                "confidence": "MEDIUM",
            },
            {
                "date": "2019-08-08",
                "source": "FloodList",
                "url": "https://floodlist.com/asia/india-floods-karnataka-august-2019",
                "affected_areas": ["Statewide"],
                "severity": "658mm cumulative Aug 1-14. 40+ dead, 400K displaced",
                "tier": 3,
                "confidence": "MEDIUM",
            },
            {
                "date": "2019-10-19",
                "source": "FloodList",
                "url": "https://floodlist.com/asia/india-karnataka-floods-october-2019",
                "affected_areas": ["Karnataka-wide including Bengaluru"],
                "severity": "140mm/24h at some gauges",
                "tier": 3,
                "confidence": "MEDIUM",
            },
            {
                "date": "2020-10-23",
                "source": "FloodList",
                "url": "https://floodlist.com/asia/india-bangalore-floods-october-2020",
                "affected_areas": [
                    "Koramangala", "HSR Layout", "Bommanahalli", "Ejipura",
                ],
                "severity": "80mm+ in 24h. 700 houses damaged, NDRF deployed",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2021-11-22",
                "source": "Phys.org",
                "url": "https://phys.org/news/2021-11-india-bangalore-heavy.html",
                "affected_areas": ["Widespread (lakes overflowed)"],
                "severity": "131.6mm in 12h. Knee-to-waist-deep water",
                "tier": 3,
                "confidence": "HIGH",
            },
            # 2022-06-18 SKIPPED: LOW confidence, month-level only ("week of Jun 16-22")
            {
                "date": "2022-08-29",
                "source": "ORF, Sigma Earth",
                "url": "https://www.orfonline.org/expert-speak/the-bengaluru-floods",
                "affected_areas": [
                    "ORR", "Mahadevapura", "Bellandur", "SE Bangalore",
                ],
                "severity": "City underwater for 2 days. Aug total: 370mm",
                "tier": 3,
                "confidence": "HIGH",
                "storm_cluster": "2022-aug-late",
            },
            {
                "date": "2022-08-30",
                "source": "ORF",
                "url": "https://www.orfonline.org/expert-speak/the-bengaluru-floods",
                "affected_areas": ["ORR (massive flooding, thousands stranded)"],
                "severity": "Continuation of Aug 29 event",
                "tier": 3,
                "confidence": "HIGH",
                "storm_cluster": "2022-aug-late",
            },
            {
                "date": "2022-09-04",
                "source": "India.com",
                "url": "https://www.india.com/karnataka/bengaluru-rain-live-updates-bellandur-sarjapura-road-whitefield-outer-ring-road-and-beml-flooded-check-latest-rain-photos-videos-bangalore-rain-5601313/",
                "affected_areas": [
                    "Bellandur", "Sarjapur Road", "Whitefield", "ORR",
                    "BEML Layout",
                ],
                "severity": "131.6mm in 24h (highest Sep daily since 2014)",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2024-08-12",
                "source": "The South First",
                "url": "https://thesouthfirst.com/karnataka/overnight-rains-cause-widespread-waterlogging-in-bengaluru-traffic-advisory-issued/",
                "affected_areas": [
                    "KR Market", "Jakkur underpass",
                    "ORR (Nagawara-Hebbal)", "Yelahanka",
                ],
                "severity": "Doddabommasandra Lake overflowed, 6ft flooding",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2024-09-19",
                "source": "National Herald",
                "url": "https://www.nationalheraldindia.com/amp/story/national/overnight-rain-leaves-bengaluru-waterlogged-imd-predicts-more-showers",
                "affected_areas": ["Low-lying areas citywide"],
                "severity": "Heavy overnight rain, widespread waterlogging",
                "tier": 3,
                "confidence": "MEDIUM",
            },
            {
                "date": "2024-10-21",
                "source": "Deccan Herald",
                "url": "https://www.deccanherald.com/india/karnataka/bengaluru/bengaluru-rains-live-updates-traffic-jam-death-toll-karnataka-flood-bangalore-rain-news-imd-weather-waterlogging-imd-3548824",
                "affected_areas": [
                    "Yelahanka", "Kodigehalli", "Kendriya Vihar",
                    "Bellandur", "Manyata Tech Park",
                ],
                "severity": "Start of 3-day event",
                "tier": 3,
                "confidence": "HIGH",
                "storm_cluster": "2024-oct-late",
            },
            {
                "date": "2024-10-22",
                "source": "The Watchers",
                "url": "https://watchers.news/2024/10/22/5-reported-dead-after-widespread-floods-hit-bengaluru-india/",
                "affected_areas": [
                    "Yelahanka", "Kodigehalli", "Kendriya Vihar",
                    "Bellandur", "Manyata Tech Park",
                ],
                "severity": "157mm in 6h at Yelahanka. 5-7 dead, 1000+ homes flooded",
                "tier": 3,
                "confidence": "HIGH",
                "storm_cluster": "2024-oct-late",
            },
            {
                "date": "2025-05-18",
                "source": "The Watchers",
                "url": "https://watchers.news/2025/05/21/bengaluru-flooding-three-dead-500-homes-damaged/",
                "affected_areas": [
                    "Koramangala", "Indiranagar", "Silk Board",
                    "HSR Layout", "BTM Layout", "Electronic City",
                ],
                "severity": "130mm in 12h (pre-monsoon). 3 dead, 500+ homes flooded",
                "tier": 3,
                "confidence": "HIGH",
            },
        ],
        "dry_dates": [
            # Bangalore dry season: January-February (winter).
            # IMD Bangalore: Jan avg rainfall ~4mm, Feb avg ~7mm.
            # Dates spread across flood event years for temporal balance.
            # Verification: will cross-check against Open-Meteo historical
            # API in Phase 5 extraction. Dates with >5mm are excluded then.
            {
                "date": "2017-01-15",
                "source": "IMD Bangalore climatological data",
                "verification": "January avg rainfall 4mm. Peak winter dry season",
            },
            {
                "date": "2019-02-10",
                "source": "IMD Bangalore climatological data",
                "verification": "February avg rainfall 7mm. Winter dry season",
            },
            {
                "date": "2020-01-20",
                "source": "IMD Bangalore climatological data",
                "verification": "January avg rainfall 4mm. Peak winter dry season",
            },
            {
                "date": "2021-02-01",
                "source": "IMD Bangalore climatological data",
                "verification": "February avg rainfall 7mm. Winter dry season",
            },
            {
                "date": "2022-01-15",
                "source": "IMD Bangalore climatological data",
                "verification": "January avg rainfall 4mm. Peak winter dry season",
            },
            {
                "date": "2024-02-10",
                "source": "IMD Bangalore climatological data",
                "verification": "February avg rainfall 7mm. Winter dry season",
            },
            {
                "date": "2025-01-20",
                "source": "IMD Bangalore climatological data",
                "verification": "January avg rainfall 4mm. Peak winter dry season",
            },
        ],
        "excluded": False,
        "exclusion_reason": None,
        "notes": {
            "total_flood_dates": 15,
            "storm_clusters": {
                "2022-aug-late": ["2022-08-29", "2022-08-30"],
                "2024-oct-late": ["2024-10-21", "2024-10-22"],
            },
            "independent_storms": 13,
            "skipped_low_confidence": ["2022-06-18 (month-level only)"],
            "tier_explanation": "Constrained XGBoost viable (15+ dates)",
            "wettest_years": "2022 (1957mm, wettest in 122 years), 2017 (1696mm, wettest in 127 years)",
        },
    }


def create_yogyakarta_event_dates() -> dict:
    """
    Curate Yogyakarta flood dates from research doc.

    Source: docs/plans/flood-event-dates-research.md, Section 3.
    34 total events (all post-2017). Only HIGH + MEDIUM with exact dates
    are included. Month-level (LOW) dates are excluded.

    Same-date entries (e.g., 2019-03-18 appears 3x for different locations)
    are merged into a single record with combined affected_areas.
    """
    return {
        "city": "yogyakarta",
        "flood_dates": [
            {
                "date": "2019-03-06",
                "source": "Kompas",
                "url": "https://regional.kompas.com/read/2019/03/06/22590481/banjir-dan-tanah-longsor-terjang-gunungkidul-belasan-orang-mengungsi",
                "affected_areas": ["Gedangsari, Gunungkidul"],
                "severity": "School flooded, bridge severed",
                "tier": 3,
                "confidence": "HIGH",
                "storm_cluster": "2019-mar",
            },
            {
                # Merged from 3 research doc entries (#28, #29, #30) -- same date
                "date": "2019-03-18",
                "source": "detikNews, Kompas (multiple articles)",
                "url": "https://news.detik.com/berita-jawa-tengah/d-4476423/dampak-banjir-dan-longsor-bantul-5-orang-meninggal-dunia",
                "affected_areas": [
                    "Imogiri, Bantul",
                    "Purwosari, Gunungkidul",
                    "Semanu, Gunungkidul",
                    "Pantai Baron, Gunungkidul",
                ],
                "severity": "5 fatalities, 4000 evacuees. 2m deep in 13 sub-districts. Underground river overflow at Baron",
                "tier": 3,
                "confidence": "HIGH",
                "storm_cluster": "2019-mar",
            },
            {
                "date": "2020-02-22",
                "source": "Kompas",
                "url": "https://regional.kompas.com/read/2020/02/22/07281041/detik-detik-banjir-bandang-sapu-siswa-peserta-susur-sungai-di-sleman",
                "affected_areas": ["Sempor River, Sleman"],
                "severity": "Flash flood during school trip, fatalities",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2020-03-08",
                "source": "Kompas",
                "url": "https://regional.kompas.com/read/2020/03/08/23515521/diguyur-hujan-deras-puluhan-rumah-di-gunungkidul-terendam-banjir",
                "affected_areas": ["Nglindur Kulon, Gunungkidul"],
                "severity": "Lake overflow, dozens of homes flooded",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2021-01-31",
                "source": "Kompas",
                "url": "https://regional.kompas.com/read/2021/01/31/13444301/banjir-di-gunungkidul-putus-jembatan-warga-harus-memutar-ke-jateng",
                "affected_areas": ["Girisubo, Gunungkidul"],
                "severity": "Bridge destroyed, homes flooded",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2022-10-13",
                "source": "Kompas",
                "url": "https://yogyakarta.kompas.com/read/2022/10/13/230508878/banjir-di-kulon-progo-puluhan-rumah-terendam-20-hektar-tanaman-palawija",
                "affected_areas": ["Agricultural areas, Kulon Progo"],
                "severity": "Dozens of homes flooded, 20+ hectares crops destroyed",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2022-12-05",
                "source": "Kompas",
                "url": "https://yogyakarta.kompas.com/read/2022/12/05/225458478/banjir-di-jalan-nasional-menuju-bandara-yia-kendaraan-memadat-dan-sempat",
                "affected_areas": ["Jalan Nasional to YIA Airport, Kulon Progo"],
                "severity": "National road flooded, traffic jam",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2023-01-26",
                "source": "Kompas",
                "url": "https://yogyakarta.kompas.com/read/2023/01/26/202837878/terdampak-banjir-3-sekolah-di-kulon-progo-diliburkan",
                "affected_areas": ["3 schools in Kulon Progo"],
                "severity": "Schools closed due to flooding",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2025-03-29",
                "source": "Kompas",
                "url": "https://yogyakarta.kompas.com/read/2025/03/29/143540978/banjir-dan-tanah-longsor-terjang-kulon-progo-19-lokasi-terdampak-mana",
                "affected_areas": ["19 locations in Kulon Progo"],
                "severity": "Simultaneous flash floods + landslides at 19 locations",
                "tier": 3,
                "confidence": "HIGH",
                "storm_cluster": "2025-mar-late",
            },
            {
                "date": "2025-03-30",
                "source": "CNN Indonesia",
                "url": "https://www.cnnindonesia.com/nasional/20250330130928-20-1214578/fakta-banjir-dan-longsor-di-yogyakarta-rendam-4-wilayah",
                "affected_areas": [
                    "Umbulharjo, Yogyakarta City",
                    "Wirobrajan, Yogyakarta City",
                ],
                "severity": "Urban flooding, roads cut off. 4 districts affected",
                "tier": 3,
                "confidence": "HIGH",
                "storm_cluster": "2025-mar-late",
            },
            {
                "date": "2025-11-10",
                "source": "Kompas",
                "url": "https://yogyakarta.kompas.com/read/2025/11/10/170805578/masuk-musim-hujan-yogyakarta-tetapkan-siaga-darurat-banjir-talud-longsor",
                "affected_areas": ["Yogyakarta City (city-wide)"],
                "severity": "City-wide emergency status declared",
                "tier": 3,
                "confidence": "HIGH",
            },
            {
                "date": "2026-02-25",
                "source": "Kompas",
                "url": "https://yogyakarta.kompas.com/read/2026/02/25/165941678/hujan-deras-kulon-progo-tanah-ambles-di-kalibawang-muncul-lagi",
                "affected_areas": ["Kokap, Kulon Progo", "Sentolo, Kulon Progo"],
                "severity": "Landslides, sinkholes from heavy rain",
                "tier": 3,
                "confidence": "HIGH",
            },
        ],
        "dry_dates": [
            # Yogyakarta dry season: June-August (BMKG records).
            # Average monthly rainfall: Jun ~45mm, Jul ~25mm, Aug ~15mm.
            # Dates spread across flood event years for temporal balance.
            # Verification: will cross-check against Open-Meteo historical
            # API in Phase 5 extraction. Dates with >5mm are excluded then.
            {
                "date": "2019-07-15",
                "source": "BMKG Yogyakarta climatological data",
                "verification": "July avg rainfall 25mm. Peak dry season",
            },
            {
                "date": "2020-07-20",
                "source": "BMKG Yogyakarta climatological data",
                "verification": "July avg rainfall 25mm. Peak dry season",
            },
            {
                "date": "2021-06-15",
                "source": "BMKG Yogyakarta climatological data",
                "verification": "June avg rainfall 45mm. Early dry season",
            },
            {
                "date": "2022-08-01",
                "source": "BMKG Yogyakarta climatological data",
                "verification": "August avg rainfall 15mm. Late dry season",
            },
            {
                "date": "2023-07-10",
                "source": "BMKG Yogyakarta climatological data",
                "verification": "July avg rainfall 25mm. Peak dry season",
            },
            {
                "date": "2024-06-25",
                "source": "BMKG Yogyakarta climatological data",
                "verification": "June avg rainfall 45mm. Early dry season",
            },
            {
                "date": "2025-07-15",
                "source": "BMKG Yogyakarta climatological data",
                "verification": "July avg rainfall 25mm. Peak dry season",
            },
        ],
        "excluded": False,
        "exclusion_reason": None,
        "notes": {
            "total_flood_dates": 12,
            "storm_clusters": {
                "2019-mar": ["2019-03-06", "2019-03-18"],
                "2025-mar-late": ["2025-03-29", "2025-03-30"],
            },
            "independent_storms": 10,
            "skipped_low_confidence": [
                "2017-11 (two events, month-level only)",
                "2021-11 (month-level only)",
                "2021-12 (month-level only, cold lava flood -- different phenomenon)",
                "2022-05 (month-level only)",
                "2022-11 (month-level only)",
                "2022-12 (second event, month-level only)",
                "2023-05 (two events, month-level only)",
                "2024-11 (month-level only)",
                "2024-12 (two events, month-level only)",
                "2025-03 (three MEDIUM events without exact dates, subsumed by 2025-03-29/30)",
                "2025-05 (month-level only)",
                "2025-08 (month-level only)",
                "2026-03 (month-level only)",
            ],
            "merged_entries": {
                "2019-03-18": "Merged 3 research doc entries (#28, #29, #30) -- same date, different locations",
            },
            "tier_explanation": "Mixed-effects model (8-14 dates) or borderline constrained XGBoost",
        },
    }


def main():
    """Generate event date JSONs for Part B cities."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for create_func in [create_bangalore_event_dates, create_yogyakarta_event_dates]:
        data = create_func()
        city = data["city"]
        path = OUTPUT_DIR / f"{city}_event_dates.json"

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        n_flood = len(data["flood_dates"])
        n_dry = len(data["dry_dates"])
        n_independent = data["notes"]["independent_storms"]
        print(
            f"{city}: {n_flood} flood dates ({n_independent} independent storms), "
            f"{n_dry} dry dates -> {path}"
        )

    print("\nDone. These JSONs feed into Phase 5 (SAR temporal extraction).")


if __name__ == "__main__":
    main()
