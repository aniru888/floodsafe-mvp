---
name: health
description: Check health of all production services — frontend (Vercel), backend + domain-specific (Koyeb), ML service, key API endpoints, per-city integrations
argument-hint: [all|quick|endpoints|koyeb|city]
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, WebFetch
---

# Production Health Dashboard

Check the health of all FloodSafe production services and integrations.

**Arguments**: `$ARGUMENTS` (default: `all`)
- `quick` — Just 3 core health endpoints (fastest, <10s)
- `all` — Everything: core + subsystems + per-city + Koyeb infra
- `endpoints` — Core + domain-specific + per-city endpoints
- `koyeb` — Koyeb service + domain status only
- `city` — Per-city integration checks only

**Service URLs**:
- Frontend: `https://frontend-lime-psi-83.vercel.app`
- Backend: `https://floodsafe-backend-floodsafe-dda84554.koyeb.app`
- ML Service: `https://floodsafe-ml-floodsafe-9b7acbea.koyeb.app`

---

## Step 1: Core Health (ALL scopes)

Run these 3 checks in parallel using separate Bash calls:

```bash
# Frontend (Vercel)
curl -s -o /dev/null -w "%{http_code} %{time_total}s" https://frontend-lime-psi-83.vercel.app
```

```bash
# Backend API (Koyeb)
curl -s -o /dev/null -w "%{http_code} %{time_total}s" https://floodsafe-backend-floodsafe-dda84554.koyeb.app/health
```

```bash
# ML Service (Koyeb) — 45s timeout for cold start
curl -s -o /dev/null -w "%{http_code} %{time_total}s" --max-time 45 https://floodsafe-ml-floodsafe-9b7acbea.koyeb.app/v1/predictions/health
```

**If scope is `quick`**: Stop here and report results. Skip to Step 6.

---

## Step 2: Domain-Specific Health (scope: `all` or `endpoints`)

Run these checks in parallel:

```bash
# Hotspot service + ML classifier status
curl -s -w "\n%{http_code} %{time_total}s" "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/hotspots/health"
```

```bash
# Weather API + FHI calculator status
curl -s -w "\n%{http_code} %{time_total}s" "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/rainfall/health"
```

```bash
# Routing service status
curl -s -w "\n%{http_code} %{time_total}s" "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/routes/health"
```

```bash
# ML service model info
curl -s -w "\n%{http_code} %{time_total}s" "https://floodsafe-ml-floodsafe-9b7acbea.koyeb.app/v1/predictions/models/info"
```

```bash
# ML hotspot service health
curl -s -w "\n%{http_code} %{time_total}s" "https://floodsafe-ml-floodsafe-9b7acbea.koyeb.app/v1/hotspots/health"
```

---

## Step 3: Database Connectivity (scope: `all` or `endpoints`)

Test DB is reachable via a lightweight query that exercises SQLAlchemy + PostGIS:

```bash
curl -s -w "\n%{http_code} %{time_total}s" "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/external-alerts/sources?city=delhi"
```

If this returns 200 with source data, the database is healthy. Parse the response to note how many alert sources are active.

---

## Step 4: Per-City Integration Checks (scope: `all`, `endpoints`, or `city`)

Run these in parallel. **IMPORTANT**: FloodHub uses UPPERCASE city codes (`DEL`, `BLR`, `YGY`, `SIN`). Other endpoints use lowercase.

```bash
# Delhi — FloodHub (deepest integration, should have active gauge)
curl -s -w "\n%{http_code}" "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/floodhub/status?city=DEL"
```

```bash
# Delhi — Hotspots (90 expected)
curl -s -w "\n%{http_code}" "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/hotspots/?city=delhi&limit=1"
```

```bash
# Singapore — Hotspots (60 expected, uses NEA weather)
curl -s -w "\n%{http_code}" "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/hotspots/?city=singapore&limit=1"
```

```bash
# Yogyakarta — Hotspots (19 expected)
curl -s -w "\n%{http_code}" "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/hotspots/?city=yogyakarta&limit=1"
```

```bash
# Bangalore — Alerts (no dedicated hotspots file, test alerts)
curl -s -w "\n%{http_code}" "https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/external-alerts/sources?city=bangalore"
```

**Freshness check**: Parse `last_updated` from the external-alerts/sources response. If any source's `last_updated` is >2 hours old, flag as STALE with a warning.

**FloodHub note**: Only Delhi has an active gauge. Bangalore, Yogyakarta, and Singapore return empty — this is expected (mark as info, not error).

---

## Step 5: Koyeb Infrastructure (scope: `all` or `koyeb`)

```bash
./koyeb-cli-extracted/koyeb.exe services list
```

```bash
./koyeb-cli-extracted/koyeb.exe domains list
```

**CRITICAL CHECK**: If any domain status is NOT "ACTIVE", immediately warn:
```
WARNING: Domain status is NOT ACTIVE — possible TLS cert expiry!
Fix: ./koyeb-cli-extracted/koyeb.exe domains refresh 0c47ca00
See MEMORY.md gotcha #32 for details.
```

This check would have caught the Koyeb TLS cert incident proactively.

---

## Step 6: Report

Format the results as a dashboard:

```
FloodSafe Health Dashboard
══════════════════════════════════════════════════════════════
 CORE SERVICES
  Frontend (Vercel)     │ ✅ 200 │ 0.23s │
  Backend API (Koyeb)   │ ✅ 200 │ 0.15s │
  ML Service (Koyeb)    │ ⏳ 200 │ 28.4s │ Cold start
──────────────────────────────────────────────────────────────
 BACKEND SUBSYSTEMS
  Hotspot Service       │ ✅ 200 │ 0.31s │ Classifier loaded
  Rainfall/FHI          │ ✅ 200 │ 0.09s │ Weather APIs OK
  Routing               │ ✅ 200 │ 0.12s │
  Database              │ ✅ 200 │ 0.22s │ via alerts/sources
──────────────────────────────────────────────────────────────
 ML SERVICE MODELS
  Predictions           │ ✅ 200 │ 0.44s │ 2 models loaded
  Hotspots ML           │ ✅ 200 │ 0.33s │ XGBoost ready
──────────────────────────────────────────────────────────────
 PER-CITY STATUS
  Delhi       │ ✅ FloodHub (1 gauge) │ ✅ Hotspots (90)
  Bangalore   │ ℹ️ No FloodHub gauge   │ ✅ Alerts OK
  Yogyakarta  │ ℹ️ No FloodHub gauge   │ ✅ Hotspots (19)
  Singapore   │ ℹ️ No FloodHub gauge   │ ✅ Hotspots (60)
──────────────────────────────────────────────────────────────
 INFRASTRUCTURE
  Koyeb Domain          │ ✅ ACTIVE │
══════════════════════════════════════════════════════════════
 Overall: ✅ All services healthy (N/N checks passed)
```

**Status codes**:
- ✅ = HTTP 2xx, response time <5s
- ⏳ = HTTP 2xx but slow (>5s) — likely cold start, note this
- ⚠️ = Degraded (stale data, partial failure, domain not ACTIVE)
- ❌ = HTTP 4xx/5xx, timeout, or unreachable
- ℹ️ = Expected limitation (e.g., no FloodHub for non-Delhi cities)

**If any check is ❌ or ⚠️**, add a "Recommended Actions" section at the bottom with specific fix commands.

**Common failure patterns**:
- Backend 503 + CORS error → Koyeb TLS cert expired → `domains refresh 0c47ca00`
- ML service timeout → Cold start, retry in 30s
- FloodHub 401/403 → API key issue, check GOOGLE_FLOODHUB_API_KEY env var
- Hotspots 500 → Check ML service is awake first (dependency)
