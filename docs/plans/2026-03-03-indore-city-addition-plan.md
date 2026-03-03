# Indore City Addition — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Indore (Madhya Pradesh) as the 5th supported city in FloodSafe, fully deployed to production.

**Architecture:** 3-phase sequential — Foundation (config + data) → Service Integration (FHI, alerts, search) → Deploy + Verify. Each phase is independently deployable. Follows the same pattern used for Yogyakarta (6 commits) and Singapore (6+ commits).

**Tech Stack:** React 18/TypeScript (frontend), FastAPI/Python (backend), Open-Meteo (weather), Nominatim (geocoding), GDACS/GDELT (alerts)

**Design doc:** `docs/plans/2026-03-03-indore-city-addition-design.md`

---

## Phase 1: Foundation (Config + Data + Types)

### Task 1: Frontend City Config — cityConfigs.ts

**Files:**
- Modify: `apps/frontend/src/lib/map/cityConfigs.ts:111` (after singapore entry, before `} as const`)

**Step 1: Add Indore entry to CITIES object**

Insert after the `singapore` entry (line 111), before the closing `} as const;`:

```typescript
    indore: {
        name: 'indore',
        displayName: 'Indore',
        center: [75.8577, 22.7196] as [number, number],
        zoom: 12.5,
        pitch: 45,
        maxZoom: 17,
        minZoom: 12,
        bounds: [
            [75.72, 22.52],   // [minLng, minLat] — includes Mhow
            [75.97, 22.85]    // [maxLng, maxLat] — includes Super Corridor
        ] as [[number, number], [number, number]],
        pmtiles: {
            basemap: '',  // No local PMTiles — uses OpenFreeMap CDN fallback
            flood: ''     // No flood DEM layer
        }
        // No metro — Indore has BRTS but no metro rail
    },
```

**Step 2: Verify type auto-derives**

Run: `cd apps/frontend && npx tsc --noEmit 2>&1 | head -5`
Expected: CityKey now includes `'indore'` automatically (type = `keyof typeof CITIES`)

**Step 3: Commit**

```bash
# Don't commit yet — batch with other Phase 1 frontend files
```

---

### Task 2: Frontend City Utils — cityUtils.ts

**Files:**
- Modify: `apps/frontend/src/lib/cityUtils.ts:8-38`

**Step 1: Add Indore to all 4 record objects**

Add `indore` entry to each:

```typescript
// Line 12, after singapore: 'SIN',
  indore: 'IDR',

// Line 23, after singapore: 'Republic of Singapore',
  indore: 'Madhya Pradesh, India',

// Line 30, after singapore: 'Singapore',
  indore: 'MP',

// Line 37, after singapore line:
  indore: { code: '+91', placeholder: '+91 XXXXX XXXXX' },
```

---

### Task 3: Frontend City Coordinates — cityCoordinates.ts

**Files:**
- Modify: `apps/frontend/src/lib/cityCoordinates.ts:78` (after singapore entry)

**Step 1: Add Indore entry**

Insert after the `singapore` entry (line 78), before the closing `};`:

```typescript
  indore: {
    lat: 22.7196,
    lng: 75.8577,
    name: "Indore",
    displayName: "Indore",
    radiusKm: 25,
  },
```

---

### Task 4: Frontend Types — types.ts (3 locations)

**Files:**
- Modify: `apps/frontend/src/types.ts:122,326,344`

**Step 1: Update User.city_preference (line 122)**

```typescript
// FROM:
    city_preference?: 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore';
// TO:
    city_preference?: 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore' | 'indore';
```

**Step 2: Update OnboardingFormState.city (line 326)**

```typescript
// FROM:
    city: 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore' | null;
// TO:
    city: 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore' | 'indore' | null;
```

**Step 3: Update OnboardingAction SET_CITY payload (line 344)**

```typescript
// FROM:
    | { type: 'SET_CITY'; payload: 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore' }
// TO:
    | { type: 'SET_CITY'; payload: 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore' | 'indore' }
```

---

### Task 5: WebMCPProvider — 4 Zod enums

**Files:**
- Modify: `apps/frontend/src/components/WebMCPProvider.tsx:18,27,246,330`

**Step 1: Update SearchInput city enum (line 18)**

```typescript
// FROM:
  city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore']).optional().describe('City filter'),
// TO:
  city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore']).optional().describe('City filter'),
```

**Step 2: Update SwitchCityInput enum (line 27)**

```typescript
// FROM:
  city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore']).describe('Target city'),
// TO:
  city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore']).describe('Target city'),
```

**Step 3: Update analyze-flood-risk prompt schema (line 246)**

```typescript
// FROM:
    argsSchema: { city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore']).describe('City to analyze') },
// TO:
    argsSchema: { city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore']).describe('City to analyze') },
```

**Step 4: Update verify-full-e2e prompt schema (line 330)**

```typescript
// FROM:
    argsSchema: { city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore']).default('delhi').describe('City to test') },
// TO:
    argsSchema: { city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore']).default('delhi').describe('City to test') },
```

---

### Task 6: NavigationPanel + SmartSearchBar prop types

**Files:**
- Modify: `apps/frontend/src/components/NavigationPanel.tsx:19`
- Modify: `apps/frontend/src/components/SmartSearchBar.tsx:20`

**Step 1: NavigationPanel city prop (line 19)**

```typescript
// FROM:
    city: 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore';
// TO:
    city: 'bangalore' | 'delhi' | 'yogyakarta' | 'singapore' | 'indore';
```

**Step 2: SmartSearchBar cityKey prop (line 20)**

```typescript
// FROM:
    cityKey?: 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore';
// TO:
    cityKey?: 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore' | 'indore';
```

---

### Task 7: Fix hasHotspots arrays (+ Bangalore bug fix)

**Files:**
- Modify: `apps/frontend/src/contexts/LocationTrackingContext.tsx:32`
- Modify: `apps/frontend/src/contexts/NavigationContext.tsx:62`

**Step 1: LocationTrackingContext (line 32)**

```typescript
// FROM:
    const hasHotspots = ['delhi', 'yogyakarta', 'singapore'].includes(city);
// TO:
    const hasHotspots = ['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore'].includes(city);
```

**Step 2: NavigationContext (line 62)**

```typescript
// FROM:
    const hasHotspots = ['delhi', 'yogyakarta', 'singapore'].includes(city);
// TO:
    const hasHotspots = ['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore'].includes(city);
```

**Note:** Adding `'bangalore'` fixes an existing bug — Bangalore has 200 hotspots since 2026-02-17 but was missing from these arrays.

---

### Task 8: MapComponent — HOTSPOT_CITIES

**Files:**
- Modify: `apps/frontend/src/components/MapComponent.tsx:101`

**Step 1: Add indore to HOTSPOT_CITIES**

```typescript
// FROM:
    const HOTSPOT_CITIES = ['delhi', 'bangalore', 'yogyakarta', 'singapore'];
// TO:
    const HOTSPOT_CITIES = ['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore'];
```

---

### Task 9: Nominatim country code fix — hooks.ts

**Files:**
- Modify: `apps/frontend/src/lib/api/hooks.ts:~400-401`

**Step 1: Replace hardcoded ternary with lookup**

Find the line that sets `countryCode` in the geocode/search hook:

```typescript
// FROM (approximate):
const countryCode = city === 'yogyakarta' ? 'id' : 'in';
// TO:
const CITY_COUNTRY_CODES: Record<string, string> = { yogyakarta: 'id', singapore: 'sg' };
const countryCode = CITY_COUNTRY_CODES[city] || 'in';
```

This is future-proof — any Indian city defaults to `'in'`, only non-India cities need explicit mapping.

---

### Task 10: Emergency Contacts

**Files:**
- Modify: `apps/frontend/src/lib/constants/emergencyContacts.ts:12,32,481,494`

**Step 1: Add 'indore' to CityFilter type (line 12)**

```typescript
// FROM:
export type CityFilter = 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore' | 'all';
// TO:
export type CityFilter = 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore' | 'indore' | 'all';
```

**Step 2: Add to CITY_COUNTRY mapping (line ~32)**

```typescript
// After singapore: 'singapore',
    indore: 'india',
```

**Step 3: Add Indore emergency contacts**

Add after the Singapore contacts section (before the `getContactsForCity` function):

```typescript
    // ─── Indore, Madhya Pradesh ───────────────────────────────────────
    {
        id: 'indore-emergency',
        name: 'Emergency (Police/Fire/Ambulance)',
        number: '112',
        category: 'emergency',
        country: 'india',
        city: 'indore',
        description: 'National emergency number',
    },
    {
        id: 'indore-police',
        name: 'Indore Police Control Room',
        number: '0731-2435023',
        category: 'police',
        country: 'india',
        city: 'indore',
        description: 'Indore city police control room',
    },
    {
        id: 'indore-fire',
        name: 'Fire Brigade',
        number: '101',
        category: 'fire',
        country: 'india',
        city: 'indore',
        description: 'Fire brigade emergency',
    },
    {
        id: 'indore-disaster',
        name: 'Disaster Helpline',
        number: '1070',
        category: 'disaster',
        country: 'india',
        city: 'indore',
        description: 'National disaster helpline',
    },
    {
        id: 'indore-sdma',
        name: 'MP SDMA',
        number: '0755-2441825',
        category: 'disaster',
        country: 'india',
        city: 'indore',
        description: 'Madhya Pradesh State Disaster Management Authority',
    },
    {
        id: 'indore-imc',
        name: 'Indore Municipal Corporation',
        number: '0731-2432222',
        category: 'municipal',
        country: 'india',
        city: 'indore',
        description: 'IMC helpline for flood/drainage complaints',
    },
    {
        id: 'indore-ambulance',
        name: 'Ambulance (108)',
        number: '108',
        category: 'medical',
        country: 'india',
        city: 'indore',
        description: 'Emergency ambulance service',
    },
    {
        id: 'indore-sewag',
        name: 'SEWAG Flood/Drain Complaint',
        number: '0731-2534666',
        category: 'infrastructure',
        country: 'india',
        city: 'indore',
        description: 'Indore drainage and sewage authority',
    },
```

**Step 4: Update function signatures (lines 481, 494)**

```typescript
// FROM (line 481):
export function getContactsForCity(city: 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore' | null): EmergencyContact[] {
// TO:
export function getContactsForCity(city: 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore' | 'indore' | null): EmergencyContact[] {

// FROM (line 494):
export function getContactsByCategory(city: 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore' | null): {
// TO:
export function getContactsByCategory(city: 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore' | 'indore' | null): {
```

---

### Task 11: Backend — API city lists (6 files)

**Files:**
- Modify: `apps/backend/src/api/hotspots.py:20`
- Modify: `apps/backend/src/api/floodhub.py:~38`
- Modify: `apps/backend/src/api/search.py:~158,180,199`
- Modify: `apps/backend/src/api/external_alerts.py:35`
- Modify: `apps/backend/src/api/historical_floods.py:318`
- Modify: `apps/backend/src/domain/services/external_alerts/scheduler.py:38`

**Step 1: hotspots.py (line 20)**

```python
# FROM:
SUPPORTED_CITIES = {"delhi", "bangalore", "yogyakarta", "singapore"}
# TO:
SUPPORTED_CITIES = {"delhi", "bangalore", "yogyakarta", "singapore", "indore"}
```

**Step 2: floodhub.py (line ~38)**

```python
# Add after "SIN": "singapore", "SINGAPORE": "singapore",
    "IDR": "indore", "INDORE": "indore",
```

**Step 3: search.py — Add INDORE_BOUNDS (after SINGAPORE_BOUNDS)**

```python
INDORE_BOUNDS = {
    "min_lat": 22.52,
    "max_lat": 22.85,
    "min_lng": 75.72,
    "max_lng": 75.97,
    "country_code": "in",
}
```

And update the regex (line 180):
```python
# FROM:
city: Optional[str] = Query(None, regex="^(delhi|bangalore|yogyakarta|singapore)$", ...)
# TO:
city: Optional[str] = Query(None, regex="^(delhi|bangalore|yogyakarta|singapore|indore)$", ...)
```

And add city conditional (after singapore block, ~line 199):
```python
    elif city == 'indore':
        city_bounds = INDORE_BOUNDS
```

Also update the `smart_search` function's city conditional similarly.

**Step 4: external_alerts.py (line 35)**

```python
# FROM:
class CityEnum(str, Enum):
    delhi = "delhi"
    bangalore = "bangalore"
    yogyakarta = "yogyakarta"
    singapore = "singapore"
# TO (add after singapore):
    indore = "indore"
```

**Step 5: historical_floods.py (line 318)**

```python
# FROM:
"supported_cities": ["delhi", "delhi ncr", "new delhi", "singapore"],
# TO:
"supported_cities": ["delhi", "delhi ncr", "new delhi", "singapore", "indore"],
```

**Step 6: scheduler.py (line 38)**

```python
# FROM:
DEFAULT_CITIES = ["delhi", "bangalore", "yogyakarta", "singapore"]
# TO:
DEFAULT_CITIES = ["delhi", "bangalore", "yogyakarta", "singapore", "indore"]
```

---

### Task 12: Backend — rainfall.py FHI calibration

**Files:**
- Modify: `apps/backend/src/api/rainfall.py:39,971`

**Step 1: Add to CITY_FHI_CALIBRATION (line ~39)**

```python
# After singapore entry:
    "indore": {"elev_min": 440.0, "elev_max": 650.0, "wet_months": [6, 7, 8, 9], "urban_fraction": 0.55, "rain_gate_mm": 5.0, "precip_correction": 1.3, "E_dampen": 0.85},
```

**Step 2: Add to auto-detect bounds (line ~971)**

```python
# Add indore to the bounds dict:
"indore": (22.52, 22.85, 75.72, 75.97)
```

---

### Task 13: Climate percentiles script + generate

**Files:**
- Modify: `apps/backend/scripts/compute_climate_percentiles.py:~34`
- Create: `apps/backend/data/indore_climate_percentiles.json` (generated)

**Step 1: Add Indore centroid to CITY_CENTROIDS**

```python
# After singapore entry:
    "indore": {"lat": 22.7196, "lng": 75.8577},
```

**Step 2: Run script to generate percentiles**

```bash
cd apps/backend && python scripts/compute_climate_percentiles.py
```

Expected: Creates `apps/backend/data/indore_climate_percentiles.json` with monthly P50/P75/P90/P95/P99 values.

---

### Task 14: Create Indore hotspots data file

**Files:**
- Create: `apps/backend/data/indore_waterlogging_hotspots.json`

**Step 1: Create hotspots JSON**

Create the file with ~37 hotspots from IMC/news sources. Each hotspot needs:
- `id`: `indore-NNN`
- `name`: Location name
- `lat`/`lng`: Coordinates (geocode via Nominatim search: `{name}, Indore, India`)
- `description`: Waterlogging details
- `zone`: Geographic zone (Ring Road / Central / South / Bypass)
- `severity_history`: Array of severity levels
- `source`: "IMC/Free Press Journal"

**Hotspot locations** (geocode coordinates during implementation):
1. Vijay Nagar Square, 2. Satya Sai Square, 3. Robert Square, 4. Sayaji Square,
5. Industry House Square, 6. LIG Square, 7. Teen Imli Square, 8. Khajrana Square,
9. Palasikar Square, 10. Madhu Milan Square, 11. Chandan Nagar Square, 12. Nyay Nagar,
13. Radisson Square, 14. Luv Kush Square, 15. Collectorate Square, 16. MR-9 Square,
17. Musakhedi Square, 18. Pipliyahana Square, 19. IT Park Square, 20. Robot Square,
21. Chhawani, 22. Krishnapura Chhatri, 23. Juni Indore, 24. Kulkarni ka Bhatti,
25. Scheme 54, 26. Dwarkapuri, 27. Bicholi, 28. Palda, 29. Nayta Mundla,
30. Ralamandal, 31. Tejaji Nagar, 32. Phoenix Mall area, 33. IIT Indore stretch,
34. Old Palasia Square, 35. BRTS corridor, 36. Gangwal Bus Stand, 37. Badigwaltoli

---

### Task 15: Phase 1 verification + commit

**Step 1: Type check frontend**

```bash
cd apps/frontend && npx tsc --noEmit
```

Expected: 0 errors

**Step 2: Build frontend**

```bash
cd apps/frontend && npm run build
```

Expected: Build succeeds

**Step 3: Commit Phase 1**

```bash
git add apps/frontend/src/lib/map/cityConfigs.ts \
  apps/frontend/src/lib/cityUtils.ts \
  apps/frontend/src/lib/cityCoordinates.ts \
  apps/frontend/src/types.ts \
  apps/frontend/src/components/WebMCPProvider.tsx \
  apps/frontend/src/components/NavigationPanel.tsx \
  apps/frontend/src/components/SmartSearchBar.tsx \
  apps/frontend/src/components/MapComponent.tsx \
  apps/frontend/src/contexts/LocationTrackingContext.tsx \
  apps/frontend/src/contexts/NavigationContext.tsx \
  apps/frontend/src/lib/api/hooks.ts \
  apps/frontend/src/lib/constants/emergencyContacts.ts \
  apps/backend/src/api/hotspots.py \
  apps/backend/src/api/floodhub.py \
  apps/backend/src/api/search.py \
  apps/backend/src/api/external_alerts.py \
  apps/backend/src/api/historical_floods.py \
  apps/backend/src/api/rainfall.py \
  apps/backend/src/domain/services/external_alerts/scheduler.py \
  apps/backend/scripts/compute_climate_percentiles.py \
  apps/backend/data/indore_waterlogging_hotspots.json \
  apps/backend/data/indore_climate_percentiles.json

git commit -m "feat: add Indore as 5th supported city — foundation config + data"
```

---

## Phase 2: Service Integration

### Task 16: FHI Calculator — calibration + bounds

**Files:**
- Modify: `apps/backend/src/domain/ml/fhi_calculator.py:~159,184`

**Step 1: Add to CITY_CALIBRATION dict (~line 159)**

```python
        "indore": {
            "elev_min": 440, "elev_max": 650,
            "wet_months": [6, 7, 8, 9],
            "urban_fraction": 0.55,
            "default_elev": 550,
            "api_decay_k": 0.90,
            "rain_gate": 5.0,
            "api_threshold": 85.0,
            "precip_correction": 1.3,
            "E_dampen": 0.85,
            "cache_ttl": 3600,
        },
```

**Step 2: Add to CITY_BOUNDS dict (~line 184)**

```python
        "indore": {"min_lat": 22.52, "max_lat": 22.85, "min_lng": 75.72, "max_lng": 75.97},
```

---

### Task 17: FloodHub service — city bounds

**Files:**
- Modify: `apps/backend/src/domain/services/floodhub_service.py:~157`

**Step 1: Add Indore entry to CITY_BOUNDS**

```python
        "indore": {
            "lat_min": 22.52,
            "lat_max": 22.85,
            "lng_min": 75.72,
            "lng_max": 75.97,
            "region_code": "IN",
            "country_code": "IN",
        },
```

---

### Task 18: GDACS fetcher — city bounds

**Files:**
- Modify: `apps/backend/src/domain/services/external_alerts/gdacs_fetcher.py:~69`

**Step 1: Add Indore entry**

```python
        "indore": {
            "bounds": (22.52, 22.85, 75.72, 75.97),
            "name": "Indore",
            "include_states": ["madhya pradesh"],
        },
```

---

### Task 19: IndoreFloodRelevanceScorer

**Files:**
- Modify: `apps/backend/src/domain/services/external_alerts/relevance_scorer.py`

**Step 1: Create IndoreFloodRelevanceScorer class**

Add before the `get_relevance_scorer()` factory function:

```python
class IndoreFloodRelevanceScorer(BaseFloodRelevanceScorer):
    """Relevance scorer for Indore, Madhya Pradesh."""

    INDORE_LOCATIONS = {
        "areas": [
            "rajwada", "vijay nagar", "palasia", "old palasia", "sapna sangeeta",
            "bhawarkuan", "geeta bhavan", "chhappan dukan", "sarafa", "mg road",
            "ab road", "rau", "mhow", "scheme 54", "scheme 78", "scheme 94",
            "sudama nagar", "khajrana", "silicon city", "super corridor", "nipania",
            "banganga", "pipliyahana", "musakhedi", "chhawani", "juni indore",
            "tejaji nagar", "dwarkapuri", "chandan nagar", "nyay nagar", "lg nagar",
            "bicholi", "palda", "nayta mundla", "ralamandal", "krishnapura",
            "kulkarni ka bhatti", "gangwal bus stand", "industry house",
            "satya sai", "radisson", "luv kush", "collectorate", "palasikar",
            "madhu milan", "teen imli", "robot square", "it park",
        ],
        "rivers": [
            "khan river", "kanh river", "saraswati river", "kshipra",
            "gambhir river", "bilawali",
        ],
        "landmarks": [
            "holkar stadium", "devi ahilyabai airport", "iim indore", "iit indore",
            "lalbagh palace", "central mall", "treasure island", "nehru park",
            "rajwada palace", "patalpani", "ralamandal sanctuary",
        ],
        "authorities": [
            "imc", "indore municipal corporation", "mpsdma", "mp sdma",
            "indore collector", "sewag", "indore police", "mp fire",
            "ndrf", "sdrf",
        ],
        "state": [
            "madhya pradesh", "mp", "central india", "malwa",
            "indore district", "indore division",
        ],
    }

    def _compute_location_score(self, text_lower: str) -> float:
        score = 0.0
        for area in self.INDORE_LOCATIONS["areas"]:
            if area in text_lower:
                score += 3.0
        for river in self.INDORE_LOCATIONS["rivers"]:
            if river in text_lower:
                score += 2.5
        for landmark in self.INDORE_LOCATIONS["landmarks"]:
            if landmark in text_lower:
                score += 2.0
        for auth in self.INDORE_LOCATIONS["authorities"]:
            if auth in text_lower:
                score += 1.5
        for state_ref in self.INDORE_LOCATIONS["state"]:
            if state_ref in text_lower:
                score += 1.0
        return min(score, 10.0)
```

**Step 2: Update factory function**

```python
# In get_relevance_scorer(), add before the default return:
    elif city_lower == "indore":
        return IndoreFloodRelevanceScorer()
```

---

### Task 20: GDELT fetcher — Indore query terms

**Files:**
- Modify: `apps/backend/src/domain/services/external_alerts/gdelt_fetcher.py:~72`

**Step 1: Add Indore query entry**

```python
        "indore": {
            "query": '("indore" OR "madhya pradesh") AND (flood OR "flash flood" OR waterlogging OR "heavy rain" OR "khan river")',
            "language": "English",
        },
```

---

### Task 21: Telegram fetcher — empty channel mapping

**Files:**
- Modify: `apps/backend/src/domain/services/external_alerts/telegram_fetcher.py:38`

**Step 1: Add empty Indore channel list**

```python
# After "singapore": ["pubfloodalerts"],
    "indore": [],  # No Indore-specific Telegram flood channels identified yet
```

---

### Task 22: Routing service — city code mapping

**Files:**
- Modify: `apps/backend/src/domain/services/routing_service.py:785,897`

**Step 1: Add to city_map (line 785)**

```python
# FROM:
city_map = {"DEL": "delhi", "BLR": "bangalore", "YOG": "yogyakarta", "SIN": "singapore"}
# TO:
city_map = {"DEL": "delhi", "BLR": "bangalore", "YOG": "yogyakarta", "SIN": "singapore", "IDR": "indore"}
```

**Step 2: Add to metro file mapping if applicable (line ~897)**

No metro for Indore — but if the mapping dict needs a key, add `"IDR": None` or skip if the code handles missing keys gracefully.

---

### Task 23: Location aliases

**Files:**
- Modify: `apps/backend/src/domain/services/location_aliases.py`

**Step 1: Add Indore aliases section**

```python
    # ─── Indore / Madhya Pradesh ───
    "rajwada": "Rajwada Palace, Indore",
    "vijay nagar": "Vijay Nagar, Indore",
    "palasia": "Palasia, Indore",
    "sapna sangeeta": "Sapna Sangeeta Road, Indore",
    "bhawarkuan": "Bhawarkuan Square, Indore",
    "chhappan dukan": "Chhappan Dukan (56 Shops), Indore",
    "sarafa bazaar": "Sarafa Bazaar, Indore",
    "khajrana": "Khajrana, Indore",
    "pipliyahana": "Pipliyahana, Indore",
    "rau": "Rau, Indore",
    "mhow": "Mhow (Dr. Ambedkar Nagar), Indore",
    "iim indore": "IIM Indore, Rau",
    "iit indore": "IIT Indore, Simrol",
    "super corridor": "Super Corridor, Indore",
    "ab road": "Agra Bombay Road, Indore",
    "mg road": "Mahatma Gandhi Road, Indore",
    "scheme 54": "Scheme No. 54, Indore",
    "scheme 78": "Scheme No. 78, Indore",
    "lalbagh": "Lalbagh Palace, Indore",
    "holkar stadium": "Holkar Cricket Stadium, Indore",
    "treasure island": "Treasure Island Mall, Indore",
    "nehru park": "Nehru Park, Indore",
    "gangwal bus stand": "Gangwal Bus Stand, Indore",
    "patalpani": "Patalpani Waterfall, Indore",
    "banganga": "Banganga, Indore",
    "nipania": "Nipania, Indore",
    "musakhedi": "Musakhedi, Indore",
    "juni indore": "Juni Indore (Old Indore)",
    "chhawani": "Chhawani, Indore",
    "silicon city": "Silicon City, Indore",
```

---

### Task 24: Verify hotspots service auto-loading

**Files:**
- Read: `apps/backend/src/domain/ml/hotspots_service.py`

**Step 1: Verify the file loading pattern**

Confirm the service loads `{city}_waterlogging_hotspots.json` dynamically. If it does, no code change needed.

If there's a hardcoded city check, add `"indore"` to it.

---

### Task 25: Phase 2 verification + commit

**Step 1: Run backend tests**

```bash
cd apps/backend && python -m pytest -x -q 2>&1 | tail -10
```

**Step 2: Frontend type check + build**

```bash
cd apps/frontend && npx tsc --noEmit && npm run build
```

**Step 3: Commit Phase 2**

```bash
git add apps/backend/src/domain/ml/fhi_calculator.py \
  apps/backend/src/domain/services/floodhub_service.py \
  apps/backend/src/domain/services/routing_service.py \
  apps/backend/src/domain/services/location_aliases.py \
  apps/backend/src/domain/services/external_alerts/gdacs_fetcher.py \
  apps/backend/src/domain/services/external_alerts/relevance_scorer.py \
  apps/backend/src/domain/services/external_alerts/gdelt_fetcher.py \
  apps/backend/src/domain/services/external_alerts/telegram_fetcher.py

git commit -m "feat: integrate Indore into all backend services — FHI, FloodHub, alerts, routing"
```

---

## Phase 3: Deploy + Verify

### Task 26: Deploy to Production

**Step 1: Push to git**

```bash
git push origin master
```

**Step 2: Deploy backend to Koyeb**

```bash
./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend
```

Wait for deployment to complete (~2-3 minutes).

**Step 3: Deploy frontend to Vercel**

```bash
cd apps/frontend && npx vercel --prod
```

Wait for deployment (~1-2 minutes).

---

### Task 27: E2E Production Verification

**Step 1: Backend health check**

```bash
curl https://floodsafe-backend-floodsafe-dda84554.koyeb.app/health
```

Expected: `{"status": "ok"}`

**Step 2: Hotspots endpoint**

```bash
curl "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/hotspots/all?city=indore" | python -c "import sys,json; d=json.load(sys.stdin); print(f'Hotspots: {len(d.get(\"features\", d if isinstance(d, list) else []))}')"
```

Expected: `Hotspots: 37` (or similar count)

**Step 3: Search endpoint**

```bash
curl "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/search/locations?q=Rajwada&city=indore" | python -c "import sys,json; d=json.load(sys.stdin); print(f'Results: {len(d)}')"
```

Expected: 1+ results within Indore bounds

**Step 4: FloodHub status**

```bash
curl "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/floodhub/status?city=IDR"
```

Expected: JSON response (may have 0 gauges — that's OK)

**Step 5: Frontend verification**

Open https://floodsafe.live, switch to Indore city, verify:
- [ ] City appears in city picker
- [ ] Map centers on Indore (lat ~22.72, lng ~75.86)
- [ ] Hotspots load and display on map
- [ ] Emergency contacts show Indore-specific numbers
- [ ] Search returns Indore locations
- [ ] No console errors

---

### Task 28: Final commit + documentation

**Step 1: Update FEATURES.md**

Add Indore to the supported cities list.

**Step 2: Update MEMORY.md**

Add Indore city addition to recent development trajectory.

**Step 3: Final commit**

```bash
git add -A
git commit -m "docs: add Indore to feature documentation and memory"
git push origin master
```

---

## Appendix: Indore Data Reference

### Geographic Bounds
- **SW corner**: [75.72, 22.52] (Mhow area)
- **NE corner**: [75.97, 22.85] (Super Corridor)
- **Center**: [75.8577, 22.7196] (Rajwada)

### FHI Parameters
- Elevation: 440-650m (Malwa Plateau)
- Wet months: June-September
- Decay constant: 0.90
- Weather: Open-Meteo (same as Delhi/Bangalore)

### Key Rivers
- Khan (Kanh) River — passes through city center
- Saraswati River — eastern boundary
- Kshipra River — nearby (Ujjain connection)

### Sources
- [Free Press Journal — Waterlogging roads list](https://www.freepressjournal.in/indore/waterlogging-in-indore-commuters-face-pain-of-rapid-development-avoid-these-roads-to-escape-traffic-snarls-full-list-here)
- [Free Press Journal — IMC waterlogging brainstorm](https://www.freepressjournal.in/indore/indore-city-officers-brainstorm-to-address-water-logging-traffic-issues)
- [Free Press Journal — Night monitors deployment](https://www.freepressjournal.in/indore/indore-night-monitors-to-be-deployed-in-all-zones-to-tackle-rainwater-woes)
- [IIT-Indore Flood Risk Monitoring App](https://www.freepressjournal.in/indore/iit-indore-develops-smart-flood-risk-monitoring-tool-app-to-identify-high-flood-prone-areas)
