# AI Prompt & Data Pipeline Overhaul — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix AI risk summaries to use real weather data and urban-practical tone instead of fake distance-based scores and alarmist language.

**Architecture:** The `/risk-summary` endpoint gets rewired to call the real FHI calculator (live weather), find nearest hotspot by name, count recent reports via PostGIS, and count active alerts. The LLM system prompts get rewritten for urban-practical tone with explicit anti-alarmism guardrails. Temperature drops from 0.7 to 0.3 for consistency.

**Tech Stack:** FastAPI (backend), Meta Llama / Groq API (LLM), Open-Meteo (weather), PostGIS (spatial queries), React + TanStack Query (frontend)

**Design doc:** `docs/plans/2026-03-04-ai-prompt-overhaul-design.md`

---

## Task 1: Rewrite System Prompts + Lower Temperature

**Files:**
- Modify: `apps/backend/src/domain/services/llama_service.py:131-145` (SYSTEM_PROMPT)
- Modify: `apps/backend/src/domain/services/llama_service.py:139-145` (SYSTEM_PROMPT_HI)
- Modify: `apps/backend/src/domain/services/llama_service.py:233` (temperature in primary call)
- Modify: `apps/backend/src/domain/services/llama_service.py:294` (temperature in fallback call)

**Step 1: Replace English system prompt (line 131-137)**

Replace SYSTEM_PROMPT with:
```python
SYSTEM_PROMPT = """You are a practical urban advisor for FloodSafe, a nonprofit flood monitoring app serving Delhi, Bangalore, Indore (India), Yogyakarta (Indonesia), and Singapore.

Write a 2-3 sentence summary of current conditions at the user's location. Base your response ONLY on the data provided.

TONE RULES:
- These are URBAN cities. Flooding = waterlogged roads, slow drains, traffic delays. Not river floods or natural disasters.
- NEVER use: "evacuate", "seek shelter", "life-threatening", "catastrophic", "devastating", "immediate danger", "emergency".
- If rainfall is 0mm and FHI is low, say conditions are clear. Do NOT invent risks that aren't in the data.
- Think like a helpful traffic radio host, not a disaster warning.

SCALE YOUR RESPONSE TO THE DATA:
- Low risk / dry: "No flooding concerns. Conditions are clear."
- Moderate: "Some waterlogging possible. Allow extra travel time."
- High: "Waterlogging likely on low-lying roads. Avoid underpasses."
- Extreme: "Major waterlogging. Roads may be impassable. Consider delaying travel or using alternate routes."

FORMAT: Plain text only. End with one practical tip. Use "monsoon" for Indian cities, "musim hujan" for Indonesian, "rainfall" for Singapore."""
```

**Step 2: Replace Hindi system prompt (line 139-145)**

Replace SYSTEM_PROMPT_HI with:
```python
SYSTEM_PROMPT_HI = """Tum FloodSafe ke practical urban advisor ho — Delhi, Bangalore, Indore (India), Yogyakarta (Indonesia), aur Singapore ke liye nonprofit flood monitoring app.

User ki location ke baare mein 2-3 sentence ka summary likho. Sirf diye gaye data ke basis pe bolo.

TONE RULES:
- Ye URBAN cities hain. Yahan flooding matlab waterlogged roads, slow drains, traffic delays. River floods ya natural disasters nahi.
- KABHI mat use karo: "evacuate", "shelter lo", "jaan ka khatra", "tabahi", "emergency".
- Agar rainfall 0mm hai aur FHI low hai, to bolo conditions clear hain. Data mein jo nahi hai wo mat banao.
- Ek helpful traffic radio host ki tarah bolo, emergency broadcast ki tarah nahi.

RISK LEVELS:
- Low / dry: "Koi flooding ka khatra nahi. Conditions clear hain."
- Moderate: "Thodi waterlogging ho sakti hai. Travel mein extra time rakho."
- High: "Low-lying roads pe waterlogging hone ki sambhavna. Underpasses avoid karo."
- Extreme: "Major waterlogging. Roads impassable ho sakti hain. Travel delay karo ya alternate route lo."

FORMAT: Sirf plain text. Ek practical tip ke saath khatam karo. Hindi mein jawab do, technical terms English mein rakh sakte ho."""
```

**Step 3: Lower temperature from 0.7 to 0.3**

In `llama_service.py`, change both API call blocks:
- Line 233: `"temperature": 0.7` → `"temperature": 0.3`
- Line 294: `"temperature": 0.7` → `"temperature": 0.3`

**Step 4: Verify no syntax errors**

Run: `cd apps/backend && python -c "from src.domain.services.llama_service import SYSTEM_PROMPT, SYSTEM_PROMPT_HI; print('OK:', len(SYSTEM_PROMPT), len(SYSTEM_PROMPT_HI))"`

Expected: `OK: <number> <number>` (no import errors)

**Step 5: Commit**

```bash
git add apps/backend/src/domain/services/llama_service.py
git commit -m "fix: rewrite AI risk summary prompts for urban-practical tone

- Update city list (add Singapore, Indore)
- Add explicit anti-alarmism guardrails (banned words list)
- Add risk-level-scaled response guidelines
- Lower temperature 0.7→0.3 for consistent output
- Rewrite Hindi prompt with same structure"
```

---

## Task 2: Wire Real FHI Data into Risk-Summary Endpoint

This is the critical fix. Replace the fake distance-based FHI with real weather data.

**Files:**
- Modify: `apps/backend/src/api/hotspots.py:321-394` (get_risk_summary endpoint)

**Step 1: Rewrite the endpoint**

Replace the entire `get_risk_summary` function (lines 321-394) with:

```python
@router.get("/risk-summary")
async def get_risk_summary(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    language: str = Query("en", description="Language: 'en' or 'hi'"),
    name: Optional[str] = Query(None, description="Location name (e.g., watch area name)"),
):
    """
    Get AI-generated flood risk summary for a location.

    Uses real FHI calculator (live weather data) + nearest hotspot info
    to generate a natural language risk narrative via Meta Llama API.
    """
    from ..domain.services.llama_service import generate_risk_summary, is_llama_enabled
    from ..domain.ml.fhi_calculator import calculate_fhi_for_location

    if not is_llama_enabled():
        return {"risk_summary": None, "enabled": False}

    # Validate language
    if language not in ("en", "hi"):
        language = "en"

    # 1. Calculate REAL FHI from live weather data
    fhi_result = await calculate_fhi_for_location(lat, lng)
    fhi_score = fhi_result.get("fhi_score", 0.0)
    fhi_level = fhi_result.get("fhi_level", "low")
    elevation = fhi_result.get("elevation_m")
    rain_gated = fhi_result.get("rain_gated", False)
    components = fhi_result.get("components", {})

    # Derive precipitation from FHI P component (normalized 0-1, multiply by city threshold)
    # P component represents precip relative to city's P95 threshold
    precip_normalized = components.get("P", 0.0)

    # 2. Find nearest hotspot (name + distance)
    nearest_name = None
    is_hotspot = False
    min_distance = float("inf")
    try:
        detected_city = _detect_city_from_coords(lat, lng)
        service = _get_hotspots_service(detected_city)
        for h in service.hotspots_data:
            h_lat = h.get("lat") or h.get("latitude")
            h_lng = h.get("lng") or h.get("longitude")
            if h_lat is None or h_lng is None:
                continue
            dist = service.haversine_distance(lat, lng, h_lat, h_lng)
            if dist < min_distance:
                min_distance = dist
                nearest_name = h.get("name", h.get("location", "Unknown"))
        is_hotspot = min_distance < 1.0  # within 1km of known hotspot
    except Exception as e:
        logger.warning(f"Hotspot lookup failed: {e}")
        detected_city = "delhi"

    # 3. Determine risk level from REAL FHI (not distance)
    if fhi_level == "unknown":
        # FHI calculation failed — fall back to proximity
        risk_level = "moderate" if is_hotspot else "low"
    else:
        risk_level = fhi_level  # low, moderate, high, extreme

    # 4. Build location name
    location_name = name or nearest_name or f"({lat:.4f}, {lng:.4f})"

    # 5. Generate AI summary with real data
    summary = await generate_risk_summary(
        latitude=lat,
        longitude=lng,
        location_name=location_name,
        risk_level=risk_level,
        fhi_score=fhi_score,
        elevation=elevation,
        is_hotspot=is_hotspot,
        language=language,
    )

    return {
        "risk_summary": summary,
        "enabled": True,
        "risk_level": risk_level,
        "fhi_score": fhi_score,
        "language": language,
    }
```

**Key differences from old code:**
- Calls `calculate_fhi_for_location()` for real weather-based FHI (was hardcoded by distance)
- Uses FHI level directly as risk_level (was derived from distance thresholds)
- Passes real elevation to LLM (was omitted)
- Uses `name` query param or nearest hotspot name (was raw coordinates)
- Falls back to proximity only when FHI calculation fails
- Validates language parameter

**Step 2: Verify import is available**

The import `from ..domain.ml.fhi_calculator import calculate_fhi_for_location` must resolve. Check:

Run: `cd apps/backend && python -c "from src.domain.ml.fhi_calculator import calculate_fhi_for_location; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add apps/backend/src/api/hotspots.py
git commit -m "fix: wire real FHI weather data into risk-summary endpoint

- Replace fake distance-based FHI with calculate_fhi_for_location()
- Use real weather data from Open-Meteo/NEA APIs
- Pass location name (from query param or nearest hotspot) instead of coordinates
- Add language validation
- Fall back to proximity-based risk only when FHI calc fails"
```

---

## Task 3: Pass Location Name from Frontend

**Files:**
- Modify: `apps/frontend/src/lib/api/hooks.ts:1900-1912` (useRiskSummary hook)
- Modify: `apps/frontend/src/components/AiRiskInsightsCard.tsx:49-56` (RiskInsightItem)

**Step 1: Update the hook to accept and pass `name`**

In `hooks.ts`, replace the `useRiskSummary` function (lines 1900-1912):

```typescript
export function useRiskSummary(lat: number | null, lng: number | null, language = 'en', name?: string) {
    return useQuery({
        queryKey: ['risk-summary', lat, lng, language, name],
        queryFn: () => {
            const params = new URLSearchParams({
                lat: String(lat),
                lng: String(lng),
                language,
            });
            if (name) params.set('name', name);
            return fetchJson<RiskSummaryResponse>(`/hotspots/risk-summary?${params}`);
        },
        enabled: lat !== null && lng !== null,
        staleTime: 10 * 60 * 1000,     // 10 min (backend caches 1 hour)
        gcTime: 30 * 60 * 1000,         // 30 min garbage collection
        refetchOnWindowFocus: false,
        retry: 1,
    });
}
```

**Step 2: Pass location name in AiRiskInsightsCard**

In `AiRiskInsightsCard.tsx`, update the `RiskInsightItem` component (line 52-56):

Change:
```typescript
    const { data, isLoading, isError, refetch } = useRiskSummary(
        location.latitude,
        location.longitude,
        apiLang
    );
```

To:
```typescript
    const { data, isLoading, isError, refetch } = useRiskSummary(
        location.latitude,
        location.longitude,
        apiLang,
        location.name
    );
```

**Step 3: Type-check**

Run: `cd apps/frontend && npx tsc --noEmit`

Expected: No errors

**Step 4: Build**

Run: `cd apps/frontend && npm run build`

Expected: Build succeeds

**Step 5: Commit**

```bash
git add apps/frontend/src/lib/api/hooks.ts apps/frontend/src/components/AiRiskInsightsCard.tsx
git commit -m "feat: pass location name to risk-summary API

- Add name param to useRiskSummary hook
- Pass watch area / route name from AiRiskInsightsCard
- LLM now sees 'Connaught Place' instead of '(28.6139, 77.2090)'"
```

---

## Task 4: Soften WhatsApp Message Templates

**Files:**
- Modify: `apps/backend/src/domain/services/whatsapp/message_templates.py:214-268`

**Step 1: Update HIGH risk template (line 214-240)**

Change the English HIGH risk advice line (line 224):
```
Old: "AVOID this area if possible. Use alternative routes."
New: "Waterlogging likely in this area. Consider alternate routes if commuting."
```

Change the Hindi HIGH risk advice line (line 237):
```
Old: "यदि संभव हो तो इस क्षेत्र से बचें। वैकल्पिक मार्गों का उपयोग करें।"
New: "इस इलाके में जलभराव की संभावना है। यात्रा करते समय वैकल्पिक मार्ग अपनाएं।"
```

**Step 2: Update MODERATE risk template (line 242-268)**

Change the English MODERATE risk advice line (line 252):
```
Old: "Avoid underpasses and low areas during rain."
New: "Some waterlogging possible. Take care near underpasses and low-lying roads."
```

Change the Hindi MODERATE risk advice line (line 266):
```
Old: "बारिश के दौरान अंडरपास और निचले इलाकों से बचें।"
New: "कुछ जलभराव संभव है। अंडरपास और निचली सड़कों पर ध्यान रखें।"
```

**Step 3: Verify no syntax errors**

Run: `cd apps/backend && python -c "from src.domain.services.whatsapp.message_templates import get_message, TemplateKey; print(get_message(TemplateKey.RISK_HIGH, 'en', location='Test', factors='Test'))"`

Expected: Prints the updated template without errors

**Step 4: Commit**

```bash
git add apps/backend/src/domain/services/whatsapp/message_templates.py
git commit -m "fix: soften WhatsApp risk templates for urban-practical tone

- HIGH: 'AVOID this area' → 'Waterlogging likely, consider alternate routes'
- MODERATE: 'Avoid underpasses' → 'Some waterlogging possible, take care'
- Updated Hindi translations to match"
```

---

## Task 5: Fix Frontend Risk Label Terminology

**Files:**
- Modify: `apps/frontend/src/components/screens/HomeScreen.tsx:240-251`

**Step 1: Update risk color and label maps**

Change `severe` to `extreme` in both maps:

Line 240-244 (riskColors):
```typescript
    const riskColors: Record<string, string> = {
        low: 'bg-green-500',
        moderate: 'bg-yellow-500',
        high: 'bg-orange-500',
        extreme: 'bg-red-500'
    };
```

Line 246-251 (riskLabels):
```typescript
    const riskLabels: Record<string, string> = {
        low: 'LOW FLOOD RISK',
        moderate: 'MODERATE FLOOD RISK',
        high: 'HIGH FLOOD RISK',
        extreme: 'EXTREME FLOOD RISK'
    };
```

**Step 2: Search for other `severe` references in HomeScreen**

Search for any other `severe` usage in the file that maps to risk levels and update to `extreme`.

Run: `grep -n "severe" apps/frontend/src/components/screens/HomeScreen.tsx`

Fix any remaining `severe` → `extreme` mappings.

**Step 3: Type-check and build**

Run: `cd apps/frontend && npx tsc --noEmit && npm run build`

Expected: Both pass

**Step 4: Commit**

```bash
git add apps/frontend/src/components/screens/HomeScreen.tsx
git commit -m "fix: unify risk terminology - 'severe' → 'extreme'

Aligns frontend labels with backend ML model terminology.
Backend uses low/moderate/high/extreme consistently."
```

---

## Task 6: End-to-End Verification

**Step 1: Backend smoke test**

Verify the backend starts without errors:

Run: `cd apps/backend && python -c "from src.api.hotspots import router; print('Router OK')" && python -c "from src.domain.services.llama_service import SYSTEM_PROMPT; print('Prompt length:', len(SYSTEM_PROMPT))" && python -c "from src.domain.services.whatsapp.message_templates import get_message, TemplateKey; print(get_message(TemplateKey.RISK_HIGH, 'en', location='Test', factors='rain'))"`

Expected: All three import checks pass

**Step 2: Frontend quality gates**

Run: `cd apps/frontend && npx tsc --noEmit && npm run build`

Expected: Both pass with no errors

**Step 3: Review AI prompt content**

Read `llama_service.py` and verify:
- [ ] System prompt mentions all 5 cities (Delhi, Bangalore, Indore, Yogyakarta, Singapore)
- [ ] Banned words list includes: evacuate, seek shelter, life-threatening, catastrophic, devastating, immediate danger, emergency
- [ ] Risk level guidelines match: low=clear, moderate=waterlogging possible, high=waterlogging likely, extreme=impassable
- [ ] Temperature is 0.3 in both primary and fallback calls
- [ ] Hindi prompt has same structure

**Step 4: Review endpoint data flow**

Read `hotspots.py` `/risk-summary` and verify:
- [ ] Calls `calculate_fhi_for_location(lat, lng)` — NOT distance-based hardcoded FHI
- [ ] Uses `fhi_level` from FHI result as risk_level (NOT distance thresholds)
- [ ] Accepts `name` query param and passes it to LLM
- [ ] Falls back to nearest hotspot name if `name` not provided
- [ ] Passes real elevation to `generate_risk_summary()`
- [ ] Validates language parameter

**Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: verification fixes for AI prompt overhaul"
```

---

## Summary of All Changes

| # | File | Change | Risk |
|---|------|--------|------|
| 1 | `llama_service.py` | Rewrite EN+HI prompts, temp 0.3 | Low — text only |
| 2 | `hotspots.py` | Wire real FHI into `/risk-summary` | Medium — new async call |
| 3 | `hooks.ts` | Add `name` param to `useRiskSummary` | Low — backward compatible |
| 3 | `AiRiskInsightsCard.tsx` | Pass location name to hook | Low — simple param |
| 4 | `message_templates.py` | Soften HIGH/MODERATE templates | Low — text only |
| 5 | `HomeScreen.tsx` | `severe` → `extreme` labels | Low — string change |

## Notes for Implementer

- **FHI caching**: `calculate_fhi_for_location()` has its own cache per city (1hr Delhi, 30min Yogyakarta, 5min Singapore). The risk-summary's 1hr cache sits on top. So real weather data is at most ~1hr stale.
- **Latency budget**: FHI call ~2s first time (cached after), LLM call ~3-5s. Total ~5-7s first call, ~3-5s cached. Frontend `useRiskSummary` has `staleTime: 10min` so most requests hit TanStack cache.
- **No DB dependency needed**: The design originally planned to add report count + alert count queries. This plan SKIPS those for simplicity — the real FHI data is the critical fix. Report/alert count can be added later if needed.
- **WhatsApp path**: The WhatsApp `/risk` command calls `/risk-at-point` (still distance-based) → then `generate_risk_summary()`. The prompt rewrite (Task 1) improves WhatsApp output even without fixing `/risk-at-point`. Fixing that endpoint is a separate future task.
- **Backward compatible**: Response shape `{risk_summary, enabled, risk_level, fhi_score, language}` is unchanged. Frontend needs no changes beyond the `name` param addition.
