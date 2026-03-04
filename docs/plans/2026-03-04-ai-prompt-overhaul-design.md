# AI Prompt & Data Pipeline Overhaul

> Date: 2026-03-04
> Status: Approved
> Scope: Backend (llama_service, hotspots API, WhatsApp templates) + Frontend (hooks, components)

## Problem

The AI risk summaries shown on the HomeScreen (`AiRiskInsightsCard`) and via WhatsApp `/risk` command suffer from two root issues:

1. **Fake data pipeline** — The `/risk-summary` endpoint assigns FHI scores based on distance to nearest hotspot (0.7 if <500m, 0.5 if <1km) instead of calling the real FHI calculator with live weather data. Rainfall is always 0.0mm. Location is raw coordinates. This means summaries never change with weather and can claim "high risk" on a sunny day.

2. **Outdated/alarmist prompt** — The system prompt says "India and Indonesia" (missing 3 cities), tells the LLM to "convey urgency" for high/extreme risk, and provides no urban waterlogging context. The LLM defaults to dramatic flood language inappropriate for urban conditions.

## Design Principles

- **Practical commuter advice** — like a traffic radio host, not an emergency broadcast
- **Never alarmist** — even extreme conditions = "roads may be impassable, delay travel"
- **Data-responsive** — if rainfall is 0mm, say conditions are clear. Don't invent risks
- **Urban-aware** — waterlogged roads, underpasses, traffic delays. Not river floods

## Changes

### 1. Fix Data Pipeline (`apps/backend/src/api/hotspots.py`)

Replace hardcoded distance-based FHI with real data:

| Data | Source | Method |
|------|--------|--------|
| Real FHI score | `FHICalculator.calculate_fhi_for_location(lat, lng)` | Already exists, just not wired |
| Actual rainfall | FHI result components | From FHI calculation |
| Elevation | FHI result `elevation_m` | From FHI calculation |
| Location name | New `name` query param from frontend | Watch area / route name |
| Nearby reports count | `Report` model + `ST_DWithin` | New PostGIS count query |
| Active alerts count | Unified alerts query by city | New count query |

**Dependencies:**
- Add `db: Session = Depends(get_db)` to endpoint (needed for reports/alerts queries)
- Add `name: Optional[str]` query param (optional, falls back to nearest hotspot name or coordinates)
- Import `FHICalculator` (already available in the module)

**Latency:** FHI calls Open-Meteo (up to 2s) but cached per-city (1hr Delhi, 30min Yogyakarta, 5min Singapore). LLM already has 5s timeout. Total worst case ~7s first call, <5s cached.

### 2. Rewrite System Prompts (`apps/backend/src/domain/services/llama_service.py`)

**English:**
```
You are a practical urban advisor for FloodSafe, a nonprofit flood
monitoring app serving Delhi, Bangalore, Indore (India), Yogyakarta
(Indonesia), and Singapore.

Write a 2-3 sentence summary of current conditions at the user's
location. Base your response ONLY on the data provided.

TONE RULES:
- These are URBAN cities. Flooding = waterlogged roads, slow drains,
  traffic delays. Not river floods or natural disasters.
- NEVER use: "evacuate", "seek shelter", "life-threatening",
  "catastrophic", "devastating", "immediate danger", "emergency".
- If rainfall is 0mm and FHI is low, say conditions are clear. Do NOT
  invent risks that aren't in the data.
- Think like a helpful traffic radio host, not a disaster warning.

SCALE YOUR RESPONSE TO THE DATA:
- Low risk / dry: "No flooding concerns. Conditions are clear."
- Moderate: "Some waterlogging possible. Allow extra travel time."
- High: "Waterlogging likely on low-lying roads. Avoid underpasses."
- Extreme: "Major waterlogging. Roads may be impassable. Consider
  delaying travel or using alternate routes."

FORMAT: Plain text only. End with one practical tip. Use "monsoon"
for Indian cities, "musim hujan" for Indonesian, "rainfall" for
Singapore.
```

**Hindi:** Same structure, translated to conversational Hindi/Hinglish.

**Temperature:** 0.7 → 0.3 (more consistent output)

### 3. Pass Location Name from Frontend

**`apps/frontend/src/lib/api/hooks.ts`** — Add `name` param to `useRiskSummary()`:
```typescript
export function useRiskSummary(lat: number | null, lng: number | null, language: string, name?: string)
```

**`apps/frontend/src/components/AiRiskInsightsCard.tsx`** — Pass watch area name or route destination name to the hook.

### 4. Soften WhatsApp Templates (`apps/backend/src/domain/services/whatsapp/message_templates.py`)

| Level | Current | New |
|-------|---------|-----|
| HIGH | "AVOID this area if possible. Use alternative routes." | "Waterlogging likely in this area. Consider alternate routes if commuting." |
| MODERATE | "Avoid underpasses and low areas during rain." | "Some waterlogging possible. Take care near underpasses and low-lying roads." |
| LOW | (no change) | (no change) |

### 5. Fix Terminology (`apps/frontend/src/components/screens/HomeScreen.tsx`)

Change `severe: 'SEVERE FLOOD RISK'` to `extreme: 'EXTREME FLOOD RISK'` to match backend terminology.

## Files Changed (6)

| File | Change |
|------|--------|
| `apps/backend/src/domain/services/llama_service.py` | Rewrite system prompts (EN + HI), temperature 0.7→0.3 |
| `apps/backend/src/api/hotspots.py` | Wire real FHI + reports + alerts into `/risk-summary` |
| `apps/backend/src/domain/services/whatsapp/message_templates.py` | Soften HIGH/MODERATE templates |
| `apps/frontend/src/lib/api/hooks.ts` | Add `name` param to `useRiskSummary()` |
| `apps/frontend/src/components/AiRiskInsightsCard.tsx` | Pass location name to hook |
| `apps/frontend/src/components/screens/HomeScreen.tsx` | Fix `severe` → `extreme` label |

## What's NOT Changing

- Onboarding bot translations (already appropriate)
- FHI calculator math (correct, just wasn't being called)
- AiRiskInsightsCard display logic (data is the problem, not display)
- Wit.ai NLU (intent classification only)
- MobileNet classifier (binary detection)
- Groq rate limits (same call count, better data per call)
- Response shape (backward compatible)

## Risks

| Risk | Mitigation |
|------|-----------|
| FHI API latency (~2s first call) | Cached per-city with TTL |
| LLM still produces bad output | Temp 0.3 + banned words + data-responsive rules |
| Breaking endpoint signature | `name` param is optional with fallback |
| DB session needed | Standard FastAPI pattern, used by all other endpoints |
