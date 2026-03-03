# Indore City Addition — Design Document

> **Date**: 2026-03-03
> **Status**: APPROVED
> **Approach**: 3-Phase Sequential (Foundation → Service Integration → Deploy + Verify)
> **Estimated Files**: 31 modifications/creations + 7 verification steps = 38 items

---

## 1. City Profile

| Attribute | Value | Source |
|-----------|-------|--------|
| **City** | Indore, Madhya Pradesh, India | — |
| **Population** | ~3.2 million (metro) | Census |
| **Center** | 22.7196°N, 75.8577°E (Rajwada) | latlong.net |
| **Bounds** | [22.52, 22.85] lat × [75.72, 75.97] lng | Verified to include Mhow, Rau, IIM Indore |
| **Elevation** | 440–650m (Malwa Plateau, avg 550m) | Geographic data |
| **Monsoon** | June–September (Southwest monsoon) | Same as Delhi |
| **Key Rivers** | Khan (Kanh), Saraswati, Kshipra, Gambhir | IMC reports |
| **City Code** | `IDR` | Following DEL/BLR/YGY/SIN pattern |
| **Country Code** | `in` (India, +91) | Same as Delhi/Bangalore |
| **Weather Source** | Open-Meteo | Same as Delhi/Bangalore (free, 14-day history) |

### Key Locations Verified

| Location | Latitude | Longitude | Within Bounds? |
|----------|----------|-----------|----------------|
| Rajwada (center) | 22.7186 | 75.8577 | ✅ (centered) |
| Rau | 22.6364 | 75.8107 | ✅ (12.9km buffer S) |
| IIM Indore | 22.6241 | 75.7956 | ✅ (11.5km buffer S) |
| Mhow | 22.5524 | 75.7565 | ✅ (3.5km buffer S) |
| Devi Ahilyabai Airport | 22.7218 | 75.8013 | ✅ (within) |
| Super Corridor (north) | ~22.82 | ~75.85 | ✅ (3.3km buffer N) |

---

## 2. FHI Calibration

```python
"indore": {
    "elev_min": 440,
    "elev_max": 650,
    "wet_months": [6, 7, 8, 9],
    "urban_fraction": 0.55,
    "default_elev": 550,
    "api_decay_k": 0.90,       # Between Delhi(0.92) and Bangalore(0.88)
    "rain_gate": 5.0,
    "weather_source": "open-meteo",
    "cache_ttl": 3600,          # 1 hour (same as Delhi/Bangalore)
    "precip_correction": 1.3,   # Moderate — less urban than Delhi
    "E_dampen": 0.85,
    "api_threshold": 85.0
}
```

**Rationale**: Indore sits on the Malwa Plateau (higher than Delhi 190-320m, lower than Bangalore 800-1000m). Urban drainage is moderate — Khan/Saraswati river channels exist but IMC reports urban encroachment causing blockages. The `api_decay_k=0.90` reflects this middle ground. Climate percentiles will be generated from ERA5 data for accurate P95 thresholds.

---

## 3. Hotspot Data

### Sources
- **IMC (Indore Municipal Corporation)**: Identified 112+ waterlogging-prone locations (per Free Press Journal reports)
- **Free Press Journal**: Named locations from monsoon reporting
- **Scribd documents**: Storm water drainage + fluvial flooding assessments

### Initial Hotspot Set (~37 locations from news/IMC reports)

**Ring Road Squares** (5):
Khajrana Square, Musakhedi Square, Pipliyahana Square, IT Park Square, Robot Square

**Major Squares — IMC Identified** (14):
Vijay Nagar Square, Satya Sai Square, Robert Square, Sayaji Square, Industry House Square, LIG Square, Teen Imli Square, Palasikar Square, Madhu Milan Square, Chandan Nagar Square, Nyay Nagar, Radisson Square, Luv Kush Square, Collectorate Square

**Low-Lying Areas** (6):
Chhawani, Krishnapura Chhatri, Juni Indore, Kulkarni ka Bhatti, Scheme 54, Dwarkapuri

**Bypass/Peripheral** (5):
Bicholi, Palda, Nayta Mundla, Ralamandal, Tejaji Nagar

**Corridors** (4):
Phoenix Mall to Radisson stretch, IIT Indore to IT Park stretch, Old Palasia Square (AB Road), BRTS corridor / AB Road

**Other** (3):
MR-9 Square (BRTS), Gangwal Bus Stand, St Paul to Bengali via Badigwaltoli

### Data Format
Matches existing pattern: `apps/backend/data/indore_waterlogging_hotspots.json`
```json
{
  "metadata": {
    "version": "1.0",
    "created": "2026-03-03",
    "source": "IMC reports, Free Press Journal, Smart City Indore",
    "total_hotspots": 37,
    "zones": ["Ring Road", "Central", "South", "Bypass"],
    "composition": "IMC identified + news reports"
  },
  "hotspots": [
    {
      "id": "indore-001",
      "name": "Vijay Nagar Square",
      "lat": 22.7534,
      "lng": 75.8938,
      "description": "Water accumulates due to slope — drainage issues and traffic disruptions",
      "zone": "Central",
      "severity_history": ["high", "high", "medium"],
      "source": "IMC/Free Press Journal"
    }
  ]
}
```

**Note**: Coordinates for each hotspot will be geocoded during implementation using Nominatim/OSM.

---

## 4. Emergency Contacts

| Contact | Number | Category |
|---------|--------|----------|
| Emergency (National) | 112 | emergency |
| Police Control Room | 0731-2435023 | police |
| Fire Brigade | 101 | fire |
| Disaster Helpline (National) | 1070 | disaster |
| MP SDMA | 0755-2441825 | disaster |
| Indore Municipal Corporation | 0731-2432222 | municipal |
| Ambulance (108) | 108 | medical |
| Flood/Drain Complaint (SEWAG) | 0731-2534666 | infrastructure |

---

## 5. IndoreFloodRelevanceScorer Keywords

**Areas/Neighborhoods**: Rajwada, Vijay Nagar, Palasia, Sapna Sangeeta, Bhawarkuan, Geeta Bhavan, Chhappan Dukan, Sarafa Bazaar, MG Road, AB Road, Rau, Mhow, Scheme 54/78/94, Sudama Nagar, Khajrana, Silicon City, Super Corridor, Nipania, Banganga, Pipliyahana, Musakhedi, Chhawani, Juni Indore, Tejaji Nagar, Dwarkapuri, Chandan Nagar, LIG, Nyay Nagar

**Rivers**: Khan River, Kanh, Saraswati River, Kshipra, Gambhir, Bilawali

**Landmarks**: Holkar Stadium, Devi Ahilyabai Airport, IIM Indore, IIT Indore, Lalbagh Palace, Central Mall, Treasure Island Mall, Nehru Park, Rajwada Palace, Gangwal Bus Stand

**Authorities**: IMC (Indore Municipal Corporation), MPSDMA, Indore District Collector, SEWAG, MP Fire Services, NDRF

**State**: Madhya Pradesh, MP, Central India, Malwa

---

## 6. Complete File Change Map

### Phase 1: Foundation (~22 files)

#### Frontend Config + Types (11 files)

| # | File | Change |
|---|------|--------|
| 1 | `apps/frontend/src/lib/map/cityConfigs.ts` | Add `indore` entry to CITIES (center, bounds [22.52-22.85, 75.72-75.97], zoom 12.5, empty PMTiles, no metro) |
| 2 | `apps/frontend/src/lib/cityUtils.ts` | Add to CITY_CODES (`IDR`), CITY_REGIONS (`Madhya Pradesh`), CITY_PHONE_DEFAULTS (`+91`) |
| 3 | `apps/frontend/src/lib/cityCoordinates.ts` | Add to CITY_COORDINATES (lat, lng, radiusKm: 25) |
| 4 | `apps/frontend/src/types.ts` | Add `'indore'` at 3 locations (lines 122, 326, 344) |
| 5 | `apps/frontend/src/components/WebMCPProvider.tsx` | Add `'indore'` to 4 Zod enums (lines 18, 27, 246, 330) |
| 6 | `apps/frontend/src/lib/constants/emergencyContacts.ts` | Add to CityFilter type, CITY_COUNTRY, contacts, function sigs (lines 12, 32, 481, 494) |
| 7 | `apps/frontend/src/components/NavigationPanel.tsx` | Add `'indore'` to city prop type (line 19) |
| 8 | `apps/frontend/src/components/SmartSearchBar.tsx` | Add `'indore'` to cityKey prop type (line 20) |
| 9 | `apps/frontend/src/contexts/LocationTrackingContext.tsx` | Add `'indore'` + `'bangalore'` to hasHotspots (line 32) — fixes existing bug |
| 10 | `apps/frontend/src/contexts/NavigationContext.tsx` | Add `'indore'` + `'bangalore'` to hasHotspots (line 62) — fixes existing bug |
| 11 | `apps/frontend/src/lib/api/hooks.ts` | Fix Nominatim country code: replace hardcoded ternary with CITY_COUNTRY lookup |

#### Frontend Map (1 file)

| # | File | Change |
|---|------|--------|
| 12 | `apps/frontend/src/components/MapComponent.tsx` | Add `'indore'` to HOTSPOT_CITIES array (line 101) |

#### Backend Config (8 files)

| # | File | Change |
|---|------|--------|
| 13 | `apps/backend/src/api/hotspots.py` | Add `"indore"` to SUPPORTED_CITIES (line 20) |
| 14 | `apps/backend/src/api/floodhub.py` | Add `"IDR": "indore"` mapping (line ~38) |
| 15 | `apps/backend/src/api/search.py` | Add INDORE_BOUNDS + update regex + city conditionals (lines 158, 180, 199) |
| 16 | `apps/backend/src/api/external_alerts.py` | Add `indore = "indore"` to CityEnum (line 35) |
| 17 | `apps/backend/src/api/historical_floods.py` | Add `"indore"` to supported_cities (line 318) |
| 18 | `apps/backend/src/api/rainfall.py` | Add `"indore"` to CITY_FHI_CALIBRATION + auto-detect bounds (lines 39, 971) |
| 19 | `apps/backend/src/domain/services/external_alerts/scheduler.py` | Add `"indore"` to DEFAULT_CITIES (line 38) |
| 20 | `apps/backend/scripts/compute_climate_percentiles.py` | Add Indore centroid to CITY_CENTROIDS |

#### Data Files (2 files — CREATE)

| # | File | Action |
|---|------|--------|
| 21 | `apps/backend/data/indore_waterlogging_hotspots.json` | CREATE (~37 hotspots from IMC/news sources) |
| 22 | `apps/backend/data/indore_climate_percentiles.json` | GENERATE via compute_climate_percentiles.py |

### Phase 2: Service Integration (~9 files)

#### FHI & ML (2 files)

| # | File | Change |
|---|------|--------|
| 23 | `apps/backend/src/domain/ml/fhi_calculator.py` | Add CITY_CALIBRATION + CITY_BOUNDS entries for Indore |
| 24 | `apps/backend/src/domain/ml/hotspots_service.py` | Verify city-agnostic loading (should auto-work) |

#### External Alerts (4 files)

| # | File | Change |
|---|------|--------|
| 25 | `apps/backend/src/domain/services/external_alerts/gdacs_fetcher.py` | Add CITY_BOUNDS + include_states=["madhya pradesh"] |
| 26 | `apps/backend/src/domain/services/external_alerts/relevance_scorer.py` | CREATE IndoreFloodRelevanceScorer + update factory |
| 27 | `apps/backend/src/domain/services/external_alerts/gdelt_fetcher.py` | Add Indore query terms |
| 28 | `apps/backend/src/domain/services/external_alerts/telegram_fetcher.py` | Add Indore channel mapping (empty list initially) |

#### Other Services (3 files)

| # | File | Change |
|---|------|--------|
| 29 | `apps/backend/src/domain/services/floodhub_service.py` | Add CITY_BOUNDS entry for Indore |
| 30 | `apps/backend/src/domain/services/routing_service.py` | Add IDR city code mapping (lines 785, 897) |
| 31 | `apps/backend/src/domain/services/location_aliases.py` | Add ~30 Indore-specific aliases |

### Phase 3: Verify + Deploy (7 steps)

| # | Action | Details |
|---|--------|---------|
| 32 | Type check | `cd apps/frontend && npx tsc --noEmit` |
| 33 | Build | `cd apps/frontend && npm run build` |
| 34 | Generate climate percentiles | `python apps/backend/scripts/compute_climate_percentiles.py` |
| 35 | Git commit | Phase-based commits |
| 36 | Deploy backend | `./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend` |
| 37 | Deploy frontend | `cd apps/frontend && npx vercel --prod` |
| 38 | E2E verify | City switch, hotspots, search, alerts in production |

---

## 7. Files NOT Needing Changes (Verified)

These files auto-work or are city-specific to others:

| File | Reason |
|------|--------|
| `CityContext.tsx` | Dynamic via `Object.keys(CITIES)` |
| `OnboardingScreen.tsx` | Uses `getAvailableCities()` from CITIES |
| `OnboardingBot.tsx` | Generic, no city hardcoding |
| `ProfileScreen.tsx` | Dynamic city display |
| `pub_fetcher.py` | Singapore PUB-specific only |
| `nea_weather_service.py` | Singapore NEA-specific only |
| `HomeScreen.tsx` (isSingapore) | Singapore NEA UI only |
| `AlertsScreen.tsx` (PUB section) | Singapore PUB UI only |
| `phone_utils.py` | IN/+91 already works |
| Navigation/OSRM routing | Global, city-agnostic |
| WebMCP resources/contexts | Auto-derive from CITIES |

---

## 8. Bug Fixes (Discovered During Audit)

| Bug | File | Fix |
|-----|------|-----|
| Bangalore missing from hasHotspots | `LocationTrackingContext.tsx:32` | Add `'bangalore'` (has 200 hotspots since 2026-02-17) |
| Bangalore missing from hasHotspots | `NavigationContext.tsx:62` | Add `'bangalore'` |

---

## 9. What Is NOT In Scope

| Item | Reason | When |
|------|--------|------|
| XGBoost model training | Only Delhi has trained model; FHI severity fallback is acceptable for MVP | After first monsoon season with ground truth |
| Historical floods data | Only Delhi has this; optional enhancement | If IMC/media data found |
| PMTiles basemap | OpenFreeMap CDN works; only Delhi has custom tiles | If offline mode needed |
| Transit (BRTS) GeoJSON | No metro; BRTS data skipped per user decision | Optional future |
| Custom weather API | Open-Meteo works for all Indian cities | Never (unless accuracy issues) |

---

## 10. Google FloodHub Availability (Verified 2026-03-03)

**Verification method**: Chrome DevTools browser automation on `sites.research.google/floods` centered on Indore (22.71°N, 75.86°E).

| Layer | Available? | Details |
|-------|-----------|---------|
| **High-confidence river gauges** | No | No physical gauge pins visible at any zoom level within Indore bounds |
| **Lower-confidence (virtual) gauges** | **Yes** | Dozens of green "Normal" dots across entire Indore region when extended coverage enabled |
| **Urban flash floods (Beta)** | **Yes** | "Highly likely" and "Likely" categories available within 24h forecast |
| **Narmada River gauges** | **Yes** | Multiple gauges visible along Narmada (~50km south of Indore center) |
| **Regional coverage** | Dense | Gauges on Khan, Saraswati, Shipra/Kshipra tributaries and surrounding areas (Dewas, Ujjain, Dhar) |

**Implication for FloodSafe**: `floodhub_service.py` CITY_BOUNDS for Indore will return gauge data via the API (same `regionCode: "IN"` + bounding box filter pattern as Delhi). The FloodHub tab will show gauge data, but forecasts may be less accurate (lower-confidence). This is the same pattern as Yogyakarta — our existing graceful degradation handles this well.

---

## 11. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Hotspot coordinates slightly off | Medium | Low | Geocode via Nominatim during impl, verify on map |
| FHI thresholds not calibrated | Medium | Medium | Use class defaults, tune after first monsoon |
| FloodHub returns no high-confidence gauges | Confirmed | Low | Lower-confidence (virtual) gauges available via extended coverage — dozens in Indore region. Same pattern as Yogyakarta. Urban flash flood (Beta) layer also available. |
| Emergency numbers outdated | Low | High | Cross-verified against IMC website |
| Missing hotspot locations | Medium | Low | Start with 37, expand with IMC data later |

---

## 12. Sources

- [Free Press Journal — Waterlogging locations in Indore](https://www.freepressjournal.in/indore/waterlogging-in-indore-commuters-face-pain-of-rapid-development-avoid-these-roads-to-escape-traffic-snarls-full-list-here)
- [Free Press Journal — IMC brainstorm on waterlogging](https://www.freepressjournal.in/indore/indore-city-officers-brainstorm-to-address-water-logging-traffic-issues)
- [Free Press Journal — Night monitors deployment](https://www.freepressjournal.in/indore/indore-night-monitors-to-be-deployed-in-all-zones-to-tackle-rainwater-woes)
- [IIT-Indore Flood Risk Monitoring Tool](https://www.freepressjournal.in/indore/iit-indore-develops-smart-flood-risk-monitoring-tool-app-to-identify-high-flood-prone-areas)
- [CTCN — Indore & Surat Vulnerability Assessment](https://www.ctc-n.org/sites/www.ctc-n.org/files/resources/indore_surat_vulnerability_and_risk_assessment_report.pdf)
- [Scribd — Storm Water Drainage Indore](https://www.scribd.com/document/853835043/Storm-Water-Drainage-Indore-1)
- [Scribd — Fluvial Flooding Indore](https://www.scribd.com/document/853835115/Fluvial-Flooding-Indore)
