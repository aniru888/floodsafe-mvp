# AI Enhancements Design — StormShield-Inspired Features

> **Date**: 2026-03-14
> **Status**: Design approved, pending implementation
> **Scope**: Tier 1 (AI Chatbot, AI Alert Text, Address Risk Lookup) + Tier 2 (Scenario Simulation, Enhanced FloodHub Charts)
> **Inspiration**: [StormShield AI](https://github.com/Tanishaaaaaaa/StormShield) (Gemini-powered flood dashboard) + [DOFA-EuroSAT](https://github.com/Bmaina/dofa-eurosat-segmentation) (satellite segmentation — Tier 3, deferred)

---

## Table of Contents

1. [Motivation & Gap Analysis](#1-motivation--gap-analysis)
2. [Feature Specifications](#2-feature-specifications)
3. [Backend API Design](#3-backend-api-design)
4. [Frontend Component Design](#4-frontend-component-design)
5. [Rate Limit Budget & Caching Strategy](#5-rate-limit-budget--caching-strategy)
6. [Dependency & Risk Analysis](#6-dependency--risk-analysis)
7. [File Change Map](#7-file-change-map)
8. [Testing Plan](#8-testing-plan)
9. [Deferred: Tier 3 Satellite ML](#9-deferred-tier-3-satellite-ml)

---

## 1. Motivation & Gap Analysis

### Source Repositories Analyzed

| Repo | What It Does | Key Takeaway for FloodSafe |
|------|-------------|---------------------------|
| [StormShield AI](https://github.com/Tanishaaaaaaa/StormShield) | Streamlit flood dashboard for Montgomery, AL. Uses Gemini 2.0/2.5 Flash for LLM-generated alerts + RAG chatbot. XGBoost water level prediction. SMS alerts via 2Factor.in. FEMA flood zone lookup. Green infrastructure simulation. | **LLM-powered chatbot + AI alert narration + scenario simulation** are high-value UX patterns FloodSafe lacks |
| [DOFA-EuroSAT](https://github.com/Bmaina/dofa-eurosat-segmentation) | Satellite image segmentation using DOFA vision transformer. Wavelength-conditioned encoder handles optical + SAR. 10 land cover classes including River/SeaLake. Transfer learning ready (35M trainable of 140M total params). | **Satellite flood extent mapping** is a long-term opportunity but requires labeled training data for South/Southeast Asia. Deferred to Tier 3. |

### What StormShield Has That FloodSafe Doesn't

| # | StormShield Feature | StormShield Implementation | FloodSafe Status | Action |
|---|--------------------|-----------------------------|-----------------|--------|
| 1 | **In-app AI chatbot** | Gemini 2.5 Flash RAG with 5-turn history, real-time context (gauges, alerts, FEMA zones, weather) | ❌ No in-app chat. Groq/Llama exists but only for WhatsApp + AiRiskInsightsCard | **BUILD** — Floating chatbot FAB |
| 2 | **LLM-generated alert text** | Gemini 2.0 Flash generates 60-word plain-language bulletins per alert | ❌ Alerts are template text, no AI narration | **BUILD** — Lazy AI summary on alerts |
| 3 | **Address flood zone lookup** | Geocode address → FEMA flood zone + local weather via spatial query | ⚠️ SmartSearch exists but doesn't show FHI risk or AI summary for addresses | **BUILD** — Address → FHI + AI narrative |
| 4 | **Scenario simulation** | "Moderate Rain", "Heavy Rain", "Flood" modes with synthetic data overrides | ❌ No "what-if" projection of FHI under different conditions | **BUILD** — FHI projection card |
| 5 | **Gauge prediction chart with confidence** | Plotly chart with T+30 prediction diamond, confidence error bars, flood stage threshold line | ⚠️ ForecastChart exists but no confidence bands or visual threshold emphasis | **ENHANCE** — Add confidence bands |
| 6 | Green infrastructure simulation | Tree-planting impact calculator | ❌ | **SKIP** — Niche, low user value |
| 7 | SMS OTP subscription | Phone verification + SMS broadcast via 2Factor.in | ✅ WhatsApp is better for target markets | **SKIP** — Already have WhatsApp |
| 8 | USGS/FEMA data sources | US-specific gauge + flood zone data | ✅ FloodHub + Open-Meteo covers 5 cities | **SKIP** — US-only data |

### What DOFA-EuroSAT Offers (Deferred)

| Capability | Relevance | Why Deferred |
|-----------|-----------|-------------|
| Water body segmentation (River + SeaLake classes) | Could detect flood extent from Sentinel-2 | Needs South Asian training data, GPU infrastructure, 140M param model |
| Wavelength-conditioned encoder | Same model works with SAR (cloud-penetrating) | Operational SAR pipeline is a major ML project |
| Transfer learning (35M trainable params) | Fine-tune for binary flood/no-flood | Needs labeled flood extent masks — data collection effort |
| TorchScript export | Production deployment | Could run in ml-service but Koyeb may lack GPU |

**Decision**: Tier 3 is deferred. Tier 1+2 delivers immediate user value with zero new dependencies.

---

## 2. Feature Specifications

### Feature 1: In-App AI Chatbot

**What**: A floating chat assistant available from any screen. Users ask flood safety questions and get AI-powered answers grounded in real-time FHI data, weather, hotspot status, and active alerts.

**User stories**:
- "Is it safe to drive through Minto Bridge right now?"
- "What areas should I avoid in Delhi today?"
- "When will the rain stop?"
- "Explain what FHI 0.65 means for my commute"

**Behavior**:
- Floating Action Button (FAB) in bottom-right corner
- Tap → slide-up chat panel (max 70vh height, 380px width on desktop, full-width on mobile)
- 5-turn conversation memory (sliding window, in-memory, 30-min TTL)
- Real-time context injection: user's city, nearest hotspot, FHI score, weather, active alert count
- Quick action buttons: "Check my area", "What if heavy rain?", "Safe routes"
- Typing indicator while waiting for Groq response
- Graceful degradation: "AI service is busy — try again in a few minutes" when rate-limited
- Multilingual: EN, HI, ID (auto-detected from user's language setting)

**Not in scope**:
- Persistent chat history (no database storage)
- File/image upload in chat
- Voice input (future enhancement)

### Feature 2: AI-Generated Alert Summaries

**What**: Each alert card gets a "💡 Explain this alert" button. Tapping it generates a plain-language AI summary explaining what the alert means for the user's specific area.

**Behavior**:
- Lazy-loaded — only calls Groq when user taps (saves quota)
- AI summary explains: what the alert means, what areas are affected, what to do
- Cached per alert ID (1hr TTL) — same alert returns cached response
- Tone: Practical advisor, not alarmist (reuses existing llama_service prompts)
- Collapsible — user can hide the summary

### Feature 3: Address Risk Lookup

**What**: User types an address (in chatbot or via dedicated search) → gets geocoded location → FHI score → nearest hotspot → AI-narrated risk assessment.

**Behavior**:
- Reuses existing search_service.py for geocoding (Nominatim + 2100+ location aliases)
- Finds nearest hotspot within 2km radius
- Calculates real-time FHI for the geocoded coordinates
- Generates AI narrative combining all context
- Response includes mini risk card with progress bar visualization

**Integration points**:
- Primary: Inside the chatbot (user types address naturally)
- Secondary: SmartSearchBar could link to risk lookup results

### Feature 4: Scenario Simulation

**What**: "What if heavy rain?" card showing projected FHI changes for user's watch areas under different rainfall scenarios.

**Scenarios**:
| Scenario | Precipitation Override | Description |
|----------|----------------------|-------------|
| Light Rain | +10mm/hr for 3hrs | Typical drizzle |
| Heavy Rain | +30mm/hr for 3hrs | Significant rainfall |
| Extreme | +60mm/hr for 3hrs | Cloudburst / extreme event |

**Behavior**:
- Card on HomeScreen below AiRiskInsightsCard
- Shows current vs projected FHI for each watch area (max 3)
- Color-coded progress bars (emerald → amber → orange → red)
- AI-generated summary of what the scenario means ("avoid underpasses", "delay travel")
- Clear "PROJECTED — estimates only" disclaimer
- Requires user to have watch areas set up

### Feature 5: Enhanced FloodHub Forecast Charts

**What**: Improve existing `ForecastChart.tsx` with confidence bands, threshold areas, and better visual indicators.

**Enhancements**:
- **Confidence band**: Semi-transparent area (±10% of predicted level) using Recharts `<Area>`
- **Threshold background bands**: Color-coded horizontal areas (green < warning < danger < extreme)
- **Current level indicator**: Prominent dot with "Now" label at the transition between observed and forecast
- **Legend**: Small legend showing observed vs forecast line styles

**No new API needed** — uses existing FloodHub forecast data. Pure frontend enhancement.

---

## 3. Backend API Design

### New Router: `apps/backend/src/api/ai_chat.py`

**Registration** in `main.py`:
```python
from .api import ai_chat
app.include_router(ai_chat.router, prefix="/api/ai", tags=["ai"])
```

#### Endpoint 1: POST `/api/ai/chat`

Multi-turn conversational AI endpoint.

```python
# Request
{
    "message": "Is Minto Bridge safe right now?",
    "conversation_id": "uuid-optional",     # Omit for new conversation
    "lat": 28.6139,                          # Optional — user's location
    "lng": 77.2090,                          # Optional
    "city": "delhi"                          # Required for context
}

# Response (200)
{
    "reply": "Minto Bridge area currently has moderate flood risk (FHI 0.45). Light rain is expected over the next 3 hours. The underpass may see ankle-deep water — consider alternate routes via Barakhamba Road.",
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "context_used": ["fhi", "hotspot", "weather", "alerts"],
    "rate_limited": false
}

# Response (200, rate-limited)
{
    "reply": null,
    "conversation_id": "...",
    "context_used": [],
    "rate_limited": true
}
```

**Implementation details**:
- Auth: `Depends(get_current_user_optional)` — works without login but personalizes if logged in
- Context assembly: Gathers FHI score + nearest hotspot + weather + alert count for the city
- System prompt: Extended version of existing `SYSTEM_PROMPT` with conversation context
- Conversation memory: `Dict[str, ConversationState]` in-memory, 5-turn sliding window, 30-min TTL per conversation, max 200 active conversations, LRU eviction
- Rate limit: Shares existing llama_service rate limiter (100/min, 1800/day)
- Timeout: 15s on Groq call, returns graceful error on timeout
- Language: Auto-detected from user profile or `Accept-Language` header

**Context injection template** (passed as user message prefix to Groq):
```
CONTEXT (real-time data for {city}):
- Location: {nearest_hotspot_name} ({distance_km}km away)
- Flood Hazard Index: {fhi_score} ({fhi_level})
- Weather: {precip_24h_mm}mm rain in 24h, intensity {hourly_max_mm}mm/hr
- Active alerts: {alert_count} ({alert_types})
- Monsoon season: {is_monsoon}

USER QUESTION: {message}
```

#### Endpoint 2: GET `/api/ai/address-risk`

Address-to-risk assessment with AI narrative.

```python
# Request
GET /api/ai/address-risk?address=Connaught+Place+Delhi&language=en

# Response (200)
{
    "address": "Connaught Place, New Delhi, Delhi, India",
    "lat": 28.6315,
    "lng": 77.2167,
    "nearest_hotspot": {
        "name": "Connaught Place Underpass",
        "distance_km": 0.3,
        "severity": "moderate"
    },
    "fhi_score": 0.45,
    "fhi_level": "moderate",
    "fhi_components": {
        "P": 0.35, "I": 0.28, "S": 0.52,
        "A": 0.48, "R": 0.35, "E": 0.72
    },
    "risk_summary": "Connaught Place has moderate flood risk right now. Light rain is forecast for the next 6 hours. The nearby underpass may see shallow waterlogging — stick to main roads.",
    "weather_snapshot": {
        "precip_24h_mm": 12.5,
        "temp_c": 32,
        "humidity_pct": 78
    },
    "cached": true
}
```

**Implementation**:
- Geocoding: Reuse `search_service.py` (Nominatim + alias mapping)
- FHI: Call `calculate_fhi_for_location(lat, lng)`
- Hotspot: Find nearest via PostGIS `ST_DWithin`
- AI summary: Call `generate_risk_summary()` from llama_service (same as existing risk-summary)
- Cache: By geohash-6 (~1.2km precision) + language, 1hr TTL
- Auth: None required (public endpoint)
- Rate limit: Shares Groq quota

#### Endpoint 3: POST `/api/ai/simulate`

What-if scenario FHI projection.

```python
# Request
{
    "city": "delhi",
    "scenario": "heavy_rain",    # "light_rain" | "heavy_rain" | "extreme"
    "locations": [               # Max 5 locations
        {"lat": 28.6315, "lng": 77.2167, "name": "Connaught Place"},
        {"lat": 28.5672, "lng": 77.2100, "name": "Lajpat Nagar"}
    ]
}

# Response (200)
{
    "scenario": "heavy_rain",
    "scenario_description": "Sustained 30mm/hr rainfall for 3 hours",
    "projections": [
        {
            "name": "Connaught Place",
            "current_fhi": 0.15,
            "current_level": "low",
            "projected_fhi": 0.72,
            "projected_level": "high",
            "delta": "+0.57"
        },
        {
            "name": "Lajpat Nagar",
            "current_fhi": 0.20,
            "current_level": "low",
            "projected_fhi": 0.55,
            "projected_level": "moderate",
            "delta": "+0.35"
        }
    ],
    "ai_summary": "Under heavy rain, avoid Minto Bridge underpass and ITO junction. Connaught Place would see significant waterlogging in low-lying areas. Consider delaying non-essential travel.",
    "disclaimer": "Projections are estimates based on current conditions + simulated rainfall. Actual conditions may vary."
}
```

**Implementation**:
- FHI calculator with precipitation override (inject scenario rainfall into weather data)
- Scenario definitions hardcoded in service (not user-configurable)
- AI summary: One Groq call per simulation (not per location)
- Cache: By `(city, scenario, sorted_location_hashes)`, 30-min TTL
- Auth: `Depends(get_current_user_optional)` — optional
- Max 5 locations per request (prevent abuse)

#### Endpoint 4: GET `/api/ai/alert-summary/{alert_id}`

AI explanation of a specific alert.

```python
# Request
GET /api/ai/alert-summary/550e8400-e29b-41d4-a716-446655440000?language=en

# Response (200)
{
    "alert_id": "550e8400-...",
    "summary": "This IMD warning means heavy rain (30-60mm) is expected in Delhi NCR over the next 12 hours. Areas near Yamuna riverbank and low-lying underpasses are most at risk. If you're in these areas, plan to leave before 6 PM.",
    "cached": true
}
```

**Implementation**:
- Fetches alert details from database
- Constructs context: alert source, severity, affected area, timestamp, + current weather
- Generates summary via llama_service
- Cache: By alert_id + language, 1hr TTL (alerts don't change)
- Auth: None required (public)

### Existing Endpoint Enhancement

#### `GET /api/hotspots/risk-summary` — Add scenario parameter

```python
# Existing endpoint, add optional query param:
GET /api/hotspots/risk-summary?lat=28.6&lng=77.2&language=en&scenario=heavy_rain

# When scenario is set:
# - FHI calculator uses boosted precipitation instead of real weather
# - Response includes "scenario" field
# - Cache key includes scenario
```

### New Service: `apps/backend/src/domain/services/ai_chat_service.py`

Thin orchestration layer that:
1. Manages conversation memory (in-memory dict)
2. Assembles real-time context for Groq prompts
3. Delegates to llama_service for actual API calls
4. Handles scenario FHI overrides

**Does NOT duplicate llama_service** — calls it for all Groq interactions.

---

## 4. Frontend Component Design

### 4a. Floating AI Chatbot

**New files**:
- `apps/frontend/src/components/ai-chat/AiChatFab.tsx` — FAB button
- `apps/frontend/src/components/ai-chat/AiChatPanel.tsx` — Chat panel
- `apps/frontend/src/components/ai-chat/ChatMessage.tsx` — Message bubble
- `apps/frontend/src/components/ai-chat/QuickActions.tsx` — Preset action buttons
- `apps/frontend/src/components/ai-chat/RiskCard.tsx` — Inline risk display in chat

**Layout & positioning**:
```
Z-index: 180 (above map popups at 150, below modals at 200)
FAB position:
  Mobile:  fixed bottom-20 right-4  (above bottom nav at ~64px)
  Desktop: fixed bottom-6 right-6   (no bottom nav)
Panel:
  Mobile:  fixed inset-x-0 bottom-0, h-[70vh], rounded-t-2xl
  Desktop: fixed bottom-6 right-6, w-[380px] h-[600px], rounded-2xl
Rendered via: React Portal to document.body
```

**Component tree**:
```
<Portal>
  {!isOpen && <AiChatFab onClick={toggle} />}
  {isOpen && (
    <AiChatPanel onClose={toggle}>
      <ChatHeader />
      <ChatMessages messages={messages} />
      <QuickActions onAction={handleQuickAction} />
      <ChatInput onSend={handleSend} disabled={isLoading} />
    </AiChatPanel>
  )}
</Portal>
```

**API hook**: `useAiChat()` in `hooks.ts`
```typescript
// New hook — uses mutation (not query) since it's a POST
const useAiChat = () => {
  return useMutation({
    mutationFn: (params: { message: string; conversation_id?: string; city: string; lat?: number; lng?: number }) =>
      fetchJson<AiChatResponse>('/ai/chat', { method: 'POST', body: JSON.stringify(params) }),
  });
};
```

**Where rendered**: Inside `App.tsx` or `ResponsiveLayout.tsx`, after all screens but before Toaster. Conditionally rendered when user is on any screen except Login/Onboarding.

### 4b. AI Alert Summary Enhancement

**Modified file**: `apps/frontend/src/components/AlertCard.tsx`

**Changes**:
- Add `[💡 Explain]` button (small, text-style, at bottom of card)
- On click: call `useAlertSummary(alertId, language)` hook
- Show loading skeleton → AI text → collapse/expand toggle
- Cache via TanStack Query (staleTime: 10 minutes)

**New hook**: `useAlertSummary()` in `hooks.ts`
```typescript
const useAlertSummary = (alertId: string, language: string) => {
  return useQuery({
    queryKey: ['alert-summary', alertId, language],
    queryFn: () => fetchJson<AlertSummaryResponse>(`/ai/alert-summary/${alertId}?language=${language}`),
    enabled: false,  // Only fetches when refetch() is called (lazy)
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
};
```

### 4c. Scenario Simulation Card

**New file**: `apps/frontend/src/components/ScenarioSimulationCard.tsx`

**Placement**: HomeScreen, below `AiRiskInsightsCard`

**Layout**:
```
┌─────────────────────────────────┐
│ 🌧️ What-If Scenarios            │
│                                 │
│ [Light ○] [Heavy ●] [Extreme ○]│  ← Radio-style selector
│                                 │
│ 📍 Connaught Place              │
│   Now: Low (0.15)  →  Heavy: High (0.72)
│   ████████████████░░░░  72%     │
│                                 │
│ 📍 Lajpat Nagar                │
│   Now: Low (0.20)  →  Heavy: Moderate (0.55)
│   ████████████░░░░░░░░  55%     │
│                                 │
│ 💡 Under heavy rain, avoid...   │  ← AI summary
│                                 │
│ ⚠️ Projected estimates only     │  ← Disclaimer
└─────────────────────────────────┘
```

**State**: Local state for selected scenario. Fetches on scenario change.

**New hook**: `useScenarioSimulation()` in `hooks.ts`
```typescript
const useScenarioSimulation = (city: string, scenario: string, locations: Location[]) => {
  return useQuery({
    queryKey: ['scenario-simulation', city, scenario, locations.map(l => `${l.lat},${l.lng}`).sort()],
    queryFn: () => fetchJson<SimulationResponse>('/ai/simulate', {
      method: 'POST',
      body: JSON.stringify({ city, scenario, locations }),
    }),
    staleTime: 30 * 60 * 1000,  // 30 min (scenarios don't change fast)
    enabled: locations.length > 0,
  });
};
```

**Conditional rendering**: Only shows if user has watch areas. Hidden during onboarding.

### 4d. Enhanced FloodHub Forecast Chart

**Modified file**: `apps/frontend/src/components/floodhub/ForecastChart.tsx`

**Enhancements** (all using existing Recharts):
```tsx
// Confidence band — Area component
<Area
  dataKey="upperBound"
  stroke="none"
  fill="#4285F4"
  fillOpacity={0.1}
/>
<Area
  dataKey="lowerBound"
  stroke="none"
  fill="#4285F4"
  fillOpacity={0.1}
/>

// Threshold reference areas
<ReferenceArea y1={0} y2={warningLevel} fill="#22c55e" fillOpacity={0.05} />
<ReferenceArea y1={warningLevel} y2={dangerLevel} fill="#f59e0b" fillOpacity={0.05} />
<ReferenceArea y1={dangerLevel} y2={extremeLevel} fill="#ef4444" fillOpacity={0.05} />

// "Now" indicator
<ReferenceDot x={nowIndex} y={currentLevel} r={6} fill="#4285F4" stroke="white" />
```

**Data transform**: Add `upperBound` and `lowerBound` fields (±10% of predicted level) to forecast data before rendering. Purely frontend calculation.

---

## 5. Rate Limit Budget & Caching Strategy

### Groq Free Tier Limits

| Limit | Hard (Groq) | Soft (FloodSafe) | Buffer |
|-------|-------------|-------------------|--------|
| Requests/minute | 120 | 100 | 17% |
| Requests/day | 2,000 | 1,800 | 10% |
| Tokens/minute | 10,000 | ~8,000 | 20% |
| Tokens/day | 480,000 | ~400,000 | 17% |

### Daily Budget Allocation

| Feature | Est. Daily Requests | Cache Strategy | Cache TTL |
|---------|-------------------|----------------|-----------|
| Risk summaries (existing AiRiskInsightsCard) | ~400 | Per (lat4, lng4, lang) | 1hr |
| **Chatbot conversations** | ~600 | No response cache (conversational) | N/A |
| **Address risk lookup** | ~300 | Per geohash-6 + lang | 1hr |
| **Alert AI summaries** | ~200 | Per alert_id + lang | 1hr |
| **Scenario simulation** | ~100 | Per (city, scenario, locations) | 30min |
| **Reserve buffer** | ~200 | — | — |
| **Total** | **~1,800** | — | — |

### Quota Protection Mechanisms

1. **Lazy loading**: Alert summaries and simulation only fetch on user action (not page load)
2. **Aggressive caching**: 1hr TTL on all non-conversational endpoints
3. **Conversation limits**: Max 10 messages per conversation, max 200 active conversations
4. **Graceful degradation**: When rate-limited, return `rate_limited: true` with no AI text
5. **Frontend retry**: Show "AI service is busy — try again in a few minutes" (no auto-retry)
6. **Shared rate limiter**: All features use single `llama_service` rate tracker

### Cache Architecture

```
┌─────────────────────────────────────┐
│ Frontend (TanStack Query)           │
│ staleTime: 10min (risk, alerts)     │
│ staleTime: 30min (simulation)       │
│ gcTime: 30min                       │
├─────────────────────────────────────┤
│ Backend (In-Memory LRU)             │
│ llama_service: 500 entries, 1hr TTL │
│ ai_chat_service: 200 conversations  │
│ simulation: 50 entries, 30min TTL   │
│ alert summaries: 100 entries, 1hr   │
├─────────────────────────────────────┤
│ Groq API (External)                 │
│ 120 req/min, 2000 req/day           │
└─────────────────────────────────────┘
```

---

## 6. Dependency & Risk Analysis

### No New Dependencies Required

| Need | Existing Solution | Package |
|------|------------------|---------|
| LLM API calls | `llama_service.py` (httpx → Groq/Meta Llama) | `httpx` (already installed) |
| Charts & confidence bands | Recharts Area, ReferenceArea, ReferenceDot | `recharts@3.4.1` (already installed) |
| Geocoding | `search_service.py` (Nominatim + aliases) | `httpx` (already installed) |
| FHI calculation | `fhi_calculator.py` (Open-Meteo/NEA/OWM) | Custom code (already exists) |
| UI primitives | Radix UI + Tailwind CSS | Already installed |
| Portal rendering | React.createPortal (built-in) | React 18 |
| UUID generation | `crypto.randomUUID()` (browser) / `uuid` (Python) | Built-in |

### Risk Mitigation Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Groq quota exhaustion** | Medium | High — all AI features degrade | Lazy loading, aggressive caching, budget allocation, graceful degradation UI |
| **Chat panel overlaps map controls** | Low | Medium — UX confusion | Portal to document.body, z-[180], tested at 375px/768px/1280px |
| **Slow Groq responses (>5s)** | Medium | Medium — poor UX | Typing indicator, 15s timeout, "try again" message |
| **Simulation misleads users** | Low | High — liability risk | Clear "PROJECTED — estimates only" disclaimer, conservative scenarios |
| **Conversation memory leak** | Low | Low — gradual memory growth | 30-min TTL eviction, max 200 conversations, LRU |
| **FHI weather API failure during simulation** | Low | Medium — simulation unavailable | Return current FHI as fallback with "weather data unavailable" flag |
| **Chatbot used for non-flood queries** | High | Low — wasted Groq calls | System prompt restricts to flood/weather/safety topics, polite redirect for off-topic |

### Breaking Change Analysis

| Changed File | Risk Level | What Changes | Backward Compatible? |
|-------------|-----------|--------------|---------------------|
| `main.py` | Low | Add 1 router import + include_router | ✅ Yes — additive only |
| `AlertCard.tsx` | Low | Add optional "Explain" button | ✅ Yes — button only appears if AI enabled |
| `ForecastChart.tsx` | Low | Add Area + ReferenceArea components | ✅ Yes — visual enhancement only |
| `HomeScreen.tsx` | Low | Add ScenarioSimulationCard below existing card | ✅ Yes — new card at end of scroll |
| `App.tsx` or `ResponsiveLayout.tsx` | Low | Add AiChatFab portal | ✅ Yes — portal renders outside layout |
| `hooks.ts` | Low | Add 4 new hooks | ✅ Yes — additive only |
| `types.ts` | Low | Add 4 new interfaces | ✅ Yes — additive only |

**Conclusion: Zero breaking changes. All modifications are additive.**

---

## 7. File Change Map

### New Files (Backend)

```
apps/backend/src/api/ai_chat.py              — New router (4 endpoints)
apps/backend/src/domain/services/ai_chat_service.py — Orchestration service
```

### New Files (Frontend)

```
apps/frontend/src/components/ai-chat/AiChatFab.tsx        — Floating action button
apps/frontend/src/components/ai-chat/AiChatPanel.tsx       — Chat panel container
apps/frontend/src/components/ai-chat/ChatMessage.tsx       — Message bubble component
apps/frontend/src/components/ai-chat/QuickActions.tsx      — Preset action buttons
apps/frontend/src/components/ai-chat/RiskCard.tsx          — Inline risk display
apps/frontend/src/components/ScenarioSimulationCard.tsx    — What-if simulation card
```

### Modified Files (Backend)

```
apps/backend/src/main.py                     — Add ai_chat router import + registration
apps/backend/src/api/hotspots.py             — Add optional `scenario` query param to risk-summary
```

### Modified Files (Frontend)

```
apps/frontend/src/App.tsx (or ResponsiveLayout.tsx) — Add AiChatFab portal
apps/frontend/src/components/AlertCard.tsx          — Add "Explain" button + AI summary section
apps/frontend/src/components/floodhub/ForecastChart.tsx — Add confidence bands + thresholds
apps/frontend/src/components/screens/HomeScreen.tsx — Add ScenarioSimulationCard
apps/frontend/src/lib/api/hooks.ts                 — Add 4 new hooks
apps/frontend/src/types.ts                         — Add 4 new interfaces
```

### Files NOT Changed

```
apps/backend/src/domain/services/llama_service.py  — Reused as-is (no modifications needed)
apps/backend/src/domain/ml/fhi_calculator.py       — Reused as-is (scenario override done in ai_chat_service)
apps/backend/src/core/config.py                    — No new env vars needed (reuses LLAMA_* settings)
apps/backend/requirements.txt                      — No new dependencies
apps/frontend/package.json                         — No new dependencies
```

---

## 8. Testing Plan

### Backend Tests

| Test | What to Verify |
|------|---------------|
| `POST /api/ai/chat` with valid message | Returns reply + conversation_id |
| `POST /api/ai/chat` with conversation_id | Continues conversation (context-aware) |
| `POST /api/ai/chat` when rate-limited | Returns `rate_limited: true`, no error |
| `GET /api/ai/address-risk` with known address | Returns geocoded location + FHI + AI summary |
| `GET /api/ai/address-risk` with unknown address | Returns 404 or empty result |
| `POST /api/ai/simulate` with valid scenario | Returns projections for all locations |
| `POST /api/ai/simulate` with >5 locations | Returns 400 error |
| `GET /api/ai/alert-summary/{id}` | Returns AI summary for alert |
| `GET /api/ai/alert-summary/{bad-id}` | Returns 404 |
| Conversation TTL eviction | Old conversations cleaned up after 30 min |
| Cache hit verification | Second identical request returns cached response |

### Frontend Tests

| Test | What to Verify |
|------|---------------|
| AiChatFab renders on HomeScreen | FAB visible at bottom-right |
| AiChatFab hidden on LoginPage | Not rendered during auth flow |
| Chat panel opens on FAB click | Panel slides up, input focused |
| Chat panel closes on X / outside click | Panel closes, FAB reappears |
| Message sent and reply received | User message appears, typing indicator, bot reply appears |
| Rate-limited response handled | "AI service busy" message shown |
| Quick action buttons work | "Check my area" sends appropriate message |
| Alert "Explain" button appears | Button visible on alert cards |
| Alert summary lazy-loads | Only fetches on button click (network tab verification) |
| Scenario card shows watch areas | Lists user's watch areas with current FHI |
| Scenario selector changes projections | Switching scenario updates projected FHI values |
| ForecastChart has confidence bands | Semi-transparent area visible around forecast line |
| Mobile layout (375px) | Chat panel is full-width, FAB above bottom nav |
| Desktop layout (1280px) | Chat panel is 380px wide, positioned bottom-right |
| Z-index: chat doesn't overlap modals | Open modal → chat panel goes behind it |

### Quality Gates (from CLAUDE.md)

- [ ] `npx tsc --noEmit` passes (no type errors)
- [ ] `npm run build` passes (frontend)
- [ ] No new TypeScript `any` types
- [ ] Console clean (no warnings)
- [ ] Error handling present on all API calls
- [ ] Mobile viewport tested (375px)
- [ ] Z-index conflicts verified

---

## 9. Deferred: Tier 3 Satellite ML

### What DOFA-EuroSAT Could Enable (Future)

Based on analysis of [Bmaina/dofa-eurosat-segmentation](https://github.com/Bmaina/dofa-eurosat-segmentation):

| Capability | Description | Prerequisite |
|-----------|-------------|-------------|
| **Binary flood segmentation** | Fine-tune DOFA for flood/no-flood at 10m resolution | Labeled flood extent masks for South/SE Asian cities |
| **SAR flood mapping** | Use Sentinel-1 radar (penetrates clouds) via wavelength conditioning | SAR preprocessing pipeline + training data |
| **Change detection** | Before/after flood comparison from Sentinel-2 time series | Multi-temporal data pipeline |
| **Flood extent overlay** | GeoTIFF predictions overlaid on MapLibre map | Rasterio → GeoJSON conversion service |

### Why Deferred

1. **Data gap**: DOFA is trained on European EuroSAT data. Tropical/monsoon landscapes (Delhi, Yogyakarta) are underrepresented
2. **Infrastructure**: 140M param model needs GPU. Koyeb free tier has no GPU
3. **Labeling effort**: Need hundreds of labeled flood extent patches for fine-tuning
4. **Latency**: Sentinel-2 has 5-day revisit time — not real-time
5. **Scope**: This is a standalone ML project, not an incremental feature

### Path to Tier 3 (When Ready)

1. Collect labeled flood extent masks from [Groundsource](https://groundsource.google) or manual annotation
2. Fine-tune DOFA binary segmentation head (35M trainable params)
3. Deploy as new endpoint in ml-service (needs GPU instance)
4. Frontend: Add flood extent layer to MapLibre map
5. Estimated effort: 4-8 weeks dedicated ML work

---

## Appendix: Reference Links

| Resource | URL |
|----------|-----|
| StormShield repo | https://github.com/Tanishaaaaaaa/StormShield |
| DOFA-EuroSAT repo | https://github.com/Bmaina/dofa-eurosat-segmentation |
| DOFA pretrained weights | https://huggingface.co/earthflow/DOFA |
| Groq API docs | https://console.groq.com/docs |
| Groq rate limits | https://console.groq.com/docs/rate-limits |
| Meta Llama API | https://llama.meta.com/docs |
| Recharts API | https://recharts.org/en-US/api |
| FloodSafe llama_service | `apps/backend/src/domain/services/llama_service.py` |
| FloodSafe FHI calculator | `apps/backend/src/domain/ml/fhi_calculator.py` |
| FloodSafe AiRiskInsightsCard | `apps/frontend/src/components/AiRiskInsightsCard.tsx` |
| FloodSafe ForecastChart | `apps/frontend/src/components/floodhub/ForecastChart.tsx` |
