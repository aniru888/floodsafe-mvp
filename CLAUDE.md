# FloodSafe Development Guide

> Nonprofit flood monitoring platform for social good.
> AI assistants: Read this FIRST before any work.

---

## TOP PRIORITY RULES (NON-NEGOTIABLE)

**These rules override all other instructions. Violation is unacceptable.**

1. **NEVER TAKE SHORTCUTS** - Every feature requires full systems-level thinking. No "quick fixes" that skip proper architecture.

2. **NEVER MAKE ASSUMPTIONS** - Ask questions when unclear. Verify requirements before implementing. Don't guess user intent.

3. **ALWAYS EXPLORE FIRST** - Use explore agents before any implementation. Understand existing code patterns before writing new code.

4. **COMPLETE END-TO-END** - No partial implementations. No "TODO later" comments. Every feature must work fully when marked complete.

5. **TEST EVERYTHING** - Type safety (`npx tsc --noEmit`), build (`npm run build`), console clean, E2E verification. All gates must pass.

6. **NO JARGON-LOADED UI** - Keep user interfaces simple and clear. Avoid technical terms. The close button should be a simple X, not buried in complex patterns.

7. **FRONTEND DEV SERVER IS PORT 5175** - The frontend runs on `http://localhost:5175`, NOT 5173. Never confuse this.

8. **CHECK DEPENDENCIES BEFORE CREATING** - Before creating new functions/files, search if similar functionality exists. Reuse existing code. Never duplicate.

9. **ASK QUESTIONS WHENEVER NEEDED** - Don't proceed with ambiguity. Clarify scope, requirements, and acceptance criteria. Better to ask than assume wrong.

10. **BE PATIENT - DON'T RUSH TO FINISH** - Don't jump to conclusions. Don't mark things complete prematurely. Take time to do it right.

11. **VERIFY BEFORE CLAIMING COMPLETE** - "It should work" is not verification. TEST IT. PROVE IT. Be skeptical of your own work.

12. **USE SUBAGENTS PRODUCTIVELY** - Use explore agents for unfamiliar code (3+ files). Use specialized agents for their domains. Use verifier/code-reviewer after implementation.

13. **DOCUMENT IMPORTANT FINDINGS** - Add significant discoveries to REALISATIONS.md. Record gotchas, edge cases, and non-obvious behaviors.

14. **NO SILENT FALLBACKS - REPORT FAILURES** - When something fails, STOP and report the error to the user. Never silently fall back to a degraded mode. The user needs to know what broke so they can fix the root cause, not have problems hidden behind workarounds.

---

## LARGE DATA FILE HANDLING (MANDATORY)

**CRITICAL: NEVER attempt to read entire training data files. This WILL exhaust context and cause failure.**

### Dangerous File Types
| Type | Example | Trap |
|------|---------|------|
| `.npz` | `hotspot_training_data.npz` | metadata field can be 90K+ chars |
| `.csv` | `India_Flood_Inventory_v3.csv` | 1000+ rows |
| `.json` | Large GeoJSON files | Feature arrays with 100+ elements |

### Safe Inspection Patterns

**1. NPZ files** - Use Python one-liner (NEVER use Read tool):
```bash
python -c "import numpy as np; d = np.load('file.npz'); print([(k, d[k].shape, d[k].dtype) for k in d.keys()])"
```

**2. CSV files** - Read first 10-20 lines only:
```
Use Read tool with limit: 15
```

**3. JSON files** - Get count first, then sample ONE element:
```bash
python -c "import json; d=json.load(open('file.json')); print(f'Type: {type(d).__name__}, Len: {len(d)}')"
```

### Red Flags (STOP IMMEDIATELY)
- About to read a data file WITHOUT `limit` parameter
- Planning to read entire .npz file (binary - won't work anyway)
- Second read of same large file "to see more examples"
- Accessing `np.load()['metadata']` directly (often 90K+ chars!)

### Use @data Skill
For data inspection, invoke: `@data path/to/file.npz`
This automatically applies safe patterns. See `.claude/commands/data.md`.

---

## Quick Reference

| Component | Location | Tech |
|-----------|----------|------|
| Backend API | `apps/backend/` | FastAPI, SQLAlchemy, PostGIS |
| Frontend | `apps/frontend/` | React 18, TypeScript, Vite, PWA |
| ML Service | `apps/ml-service/` | PyTorch, GEE, XGBoost |
| IoT Ingestion | `apps/iot-ingestion/` | FastAPI (port 8001, raw SQL) |
| ESP32 Firmware | `apps/esp32-firmware/` | Arduino (XIAO ESP32S3) |

> **For domain feature documentation, see [FEATURES.md](./FEATURES.md).**

## Production Deployment URLs

| Service | URL | Platform |
|---------|-----|----------|
| **Frontend** | https://frontend-lime-psi-83.vercel.app | Vercel |
| **Backend API** | https://floodsafe-backend-floodsafe-dda84554.koyeb.app | Koyeb |
| **ML Service** | https://floodsafe-ml-floodsafe-9b7acbea.koyeb.app | Koyeb |
| **Database** | Supabase (project: `udblirsscaghsepuxxqv`) | Supabase |

### Health Check Commands
```bash
# Backend health
curl https://floodsafe-backend-floodsafe-dda84554.koyeb.app/health

# ML service health (may take 30s to wake from sleep)
curl https://floodsafe-ml-floodsafe-9b7acbea.koyeb.app/health

# Koyeb CLI status
./koyeb-cli-extracted/koyeb.exe services list
```

### Deployment Commands (IMPORTANT)

**Vercel (Frontend)**: Git integration is NOT connected. Must deploy manually:
```bash
cd apps/frontend && npx vercel --prod
```

**Koyeb (Backend)**: Redeploy from CLI:
```bash
./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend
```

**Note**: `git push` does NOT trigger auto-deploy on either platform. Always run the deployment commands above after pushing code changes.

## Commands
```bash
# Full stack (Docker)
docker-compose up

# Local dev (requires DB + ML service)
docker-compose up -d db ml-service  # Start database and ML service

# Frontend dev
cd apps/frontend && npm run dev

# Backend dev (LOCAL - use localhost in .env)
cd apps/backend && python -m uvicorn src.main:app --reload

# Tests
cd apps/frontend && npm run build && npx tsc --noEmit
cd apps/backend && pytest

# Visual Testing (Playwright)
cd apps/frontend && npm run screenshot
```

### Environment Setup
- **Docker**: Uses `DATABASE_URL=postgresql://user:password@db:5432/floodsafe`
- **Local dev**: Change `.env` to `DATABASE_URL=postgresql://user:password@localhost:5432/floodsafe`

---

## Subagent Strategy

### When to Use Subagents
**ALWAYS prefer subagents for:**
- Exploring unfamiliar code areas (3+ files to check)
- Parallel verification tasks
- Multi-domain features (frontend + backend)

**Use direct tools for:**
- Single file edits
- Quick lookups (known file paths)
- Running build/test commands

### Subagent Types

| Agent | Scope | When to Use |
|-------|-------|-------------|
| `explore` | Codebase research | FIRST step for any task |
| `frontend-ui` | React/TypeScript | UI features, component fixes, visual testing |
| `backend-api` | FastAPI/Python | API endpoints, services |
| `maps-geo` | MapLibre, PostGIS | Map features, spatial queries |
| `ml-data` | ML pipelines | GEE, predictions, model training |
| `verifier` | E2E verification | After implementation, test flows |
| `code-reviewer` | Quality check | After completing code changes |
| `planner` | Architecture | Complex multi-file features |

### Prefer Serena for Code Analysis

**Use Serena MCP tools instead of Explore agents when:**
- Looking up specific symbols/functions (`find_symbol`)
- Tracing function calls and references (`find_referencing_symbols`)
- Understanding file structure (`get_symbols_overview`)
- Refactoring across files (`rename_symbol`, `replace_symbol_body`)

**Serena saves tokens** by returning only relevant code, not entire files.

**Example - Finding how reports are created:**
```
# Instead of launching Explore agent to read entire files:
mcp__serena__find_symbol(name_path="create_report", include_body=True)
mcp__serena__find_referencing_symbols(name_path="create_report", ...)
```

---

## MCP Servers (Model Context Protocol)

MCP servers extend Claude's capabilities with external tools and integrations. These are configured in `~/.claude/plugins/` and enabled in `~/.claude/settings.json`.

### Active MCPs (Use These)

| MCP | Purpose | When to Use | Loading |
|-----|---------|-------------|---------|
| **Supabase** | Database management, SQL execution | Production DB, schema changes | Always |
| **Context7** | Library documentation lookup | API docs (MapLibre, TanStack, FastAPI) | Always |
| **Firebase** | Firebase Auth/Config management | Auth configuration, SDK config | Always |
| **Serena** | Code intelligence, symbol analysis | Refactoring, symbol navigation | Always |
| **Koyeb** | Backend deployment management | Deploy/redeploy backend services | Always |
| **Chrome DevTools** | Low-level browser debugging | Network requests, performance | Deferred |
| **Claude-in-Chrome** | Browser automation | E2E testing, visual verification | Deferred |

### MCP Tool Reference

#### Supabase (CRITICAL for Deployment)
```
supabase: list_projects        # List all projects
supabase: execute_sql          # Run raw SQL
supabase: apply_migration      # Apply tracked migrations
supabase: list_tables          # Verify tables
supabase: get_project_url      # Get API URL
supabase: get_publishable_keys # Get API keys
supabase: get_advisors         # Security/performance checks
```

#### Context7 (Documentation Lookup)
```
# Step 1: Find library ID
mcp__context7__resolve-library-id
# Step 2: Query docs
mcp__context7__query-docs
```
**Example**: Looking up MapLibre GL JS API
```
1. resolve-library-id: query="MapLibre GL JS", libraryName="maplibre-gl"
2. query-docs: libraryId="/maplibre/maplibre-gl-js", query="add GeoJSON layer"
```

#### Serena (Code Intelligence) - USE PROACTIVELY

**Activation**: Run `mcp__serena__activate_project` with path `C:\Users\Anirudh Mohan\Desktop\FloodSafe`

```
find_symbol           # Find symbol definitions (use name_path like "MyClass/method")
find_referencing_symbols  # Find all references to a symbol
get_symbols_overview  # Get file/project symbols (use FIRST for new files)
rename_symbol         # Safe refactoring across entire codebase
replace_symbol_body   # Replace entire function/method body
insert_after_symbol   # Add new code after a symbol
insert_before_symbol  # Add new code before a symbol
search_for_pattern    # Regex search across codebase
```

**Workflow**: `get_symbols_overview` → `find_symbol(include_body=True)` → `find_referencing_symbols` → `replace_symbol_body` or `replace_content`
**Prefer over grep/read** for: understanding files, refactoring, tracing dependencies, editing code

### MCP Status (Jan 2026)

✅ **Working**: Serena, Context7, Chrome DevTools
❌ **Not connected**: Claude-in-Chrome (needs browser extension)
🔲 **Untested**: Supabase, Firebase, Koyeb (deferred plugins)
❌ **Removed**: LSP/Pyright (use Serena instead)

### Serena Known Issues (Windows)

| Issue | Workaround |
|-------|-----------|
| `list_dir(".")` fails with Windows NUL path error | Use subpath like `apps/backend/src` instead of `"."` |
| `find_symbol` without `relative_path` scans data dirs | **Always** pass `relative_path` — unscoped scans hit `__MACOSX` artifacts in `ml-service/data/` |
| `search_for_pattern` can return 90K+ chars | Scope with `relative_path` and/or `restrict_search_to_code_files: true` |
| Large repos slow without scoping | Pass `relative_path` to ALL Serena calls for speed and accuracy |

### MCP Configuration Notes
- **Serena**: `.serena/project.yml` (python + typescript). Auto-activated via `.mcp.json`.
- **Koyeb**: Token in `.env` via `${KOYEB_TOKEN}`. **Chrome DevTools / Claude-in-Chrome**: Deferred (loaded on demand).
- **Context7**: `resolve-library-id` → `query-docs`.

### Best Practices

1. **Database Work**: Use Supabase MCP for production, direct SQL for local dev
2. **Docs Lookup**: Use Context7 instead of web search for library APIs
3. **E2E Testing**: Use Claude-in-Chrome for browser automation
4. **Refactoring**: Use Serena for safe symbol renaming across codebase
5. **Deployment**: Use `/deploy` skill for gated deployments

### Installed Plugins

**✅ Active**: superpowers (v4.1.1), frontend-design, feature-dev, code-review, claude-md-management, claude-code-setup, code-simplifier, explanatory-output-style, vercel (v1.0.0), supabase, context7, firebase, serena
**❌ Non-functional**: pyright-lsp, typescript-lsp (use Serena instead)
**❌ Disabled**: figma (needs MCP), github (needs Copilot), jdtls-lsp (no Java), greptile

---

## WebMCP Bridge (AI Agent Interface)

**Status**: Active in production. Enables Claude Code browser automation.

### Architecture
- **Packages**: `@mcp-b/react-webmcp` v1.1.1 + `@mcp-b/global` v1.5.0
- **Component**: `WebMCPProvider.tsx` (272 lines, renders null — pure side-effect)
- **Mount**: `App.tsx` root level (inside LocationTrackingProvider)
- **Protocol**: postMessage API (browser window events)
- **Contexts consumed**: AuthContext, CityContext, LocationTrackingContext, TanStack Query

### Registered Entities (13 total)

**Contexts (2)**:
| Name | Description |
|------|-------------|
| `context_app_state` | City, auth status, user profile, gamification points |
| `context_location` | GPS position, nearby hotspots with FHI, tracking state |

**Tools (3)**:
| Name | Input | Destructive? |
|------|-------|-------------|
| `search_locations` | `{query, city?, limit?}` | No (read-only) |
| `get_query_cache` | `{query_key}` (JSON format) | No (read-only) |
| `switch_city` | `{city: delhi\|bangalore\|yogyakarta}` | Yes |

**Resources (5)** — All return JSON:
| URI | Description |
|-----|-------------|
| `floodsafe://config` | API URL, city list, bounds, feature flags |
| `floodsafe://alerts/{city}` | Unified flood alerts (IMD, GDACS, community, FloodHub) |
| `floodsafe://hotspots/{city}` | Waterlogging hotspots with FHI risk levels |
| `floodsafe://reports` | Recent community flood reports |
| `floodsafe://floodhub/{city}` | Google Flood Forecasting status + gauges |

**Prompts (3)** — Orchestrate tools for complex tasks:
| Name | Description |
|------|-------------|
| `analyze-flood-risk` | Full risk analysis for a city (reads config, hotspots, floodhub, alerts) |
| `debug-ui-state` | Gather all app state for debugging (auth, city, cache, console) |
| `verify-yogyakarta` | E2E Yogyakarta integration check |

### Common Cache Keys (for `get_query_cache`)
```
["reports"]
["hotspots","<city>",false]
["unified-alerts","<city>","all"]
["floodhub-status","<city>"]
["gamification","badges","me"]
```

---

## Skills (Slash Commands)

### Project Skills (`.claude/skills/`)

| Skill | Purpose | Invocation |
|-------|---------|------------|
| `/deploy` | Deploy frontend (Vercel) + backend (Koyeb) with quality gates | User-only |
| `/preflight` | Run all quality gates (tsc, build, lint, pytest) | User-only |
| `/verify-ui` | Claude-in-Chrome visual verification of all screens | User-only |
| `/screenshot` | Playwright screenshot capture for UI debugging | User-only |
| `/code-reference-finder` | Find code examples and patterns | User-only |

Legacy commands in `.claude/commands/` also still work (e.g., `/test`, `/data`, `/explore`).

### Plugin Skills (use proactively)

| Plugin | Key Skills | When to Use |
|--------|-----------|-------------|
| **superpowers** | `brainstorming`, `verification-before-completion`, `debugging`, `TDD`, `code-review` | Before creative work, before claiming done, when stuck |
| **feature-dev** | `feature-dev` | Guided multi-step feature development |
| **frontend-design** | `frontend-design` | Generating production-grade UI from descriptions |
| **code-review** | `code-review` | After major implementations |
| **code-simplifier** | `code-simplifier` | Refactoring for clarity |
| **vercel** | `deploy`, `logs` | Vercel deployment management |

**Decision tree**: Use `superpowers:brainstorming` for open-ended design → `feature-dev` for structured implementation → `code-review` after completion → `superpowers:verification-before-completion` before marking done.

---

## Hooks (Automatic Quality Enforcement)

Configured in `.claude/settings.local.json` under `"hooks"`:

| Hook | Event | What It Does |
|------|-------|-------------|
| Sensitive file protection | PreToolUse (Edit\|Write) | Blocks edits to `.env`, `credentials`, `secrets`, `.pem`, `.key` files |

**Hook script**: `.claude/hooks/protect-sensitive-files.js`
**To disable**: Remove the `"hooks"` section from `.claude/settings.local.json`

---

## Architecture Rules

### Backend (Python)
- **Layers**: `api/` → `domain/services/` → `infrastructure/`
- **Models**: Pydantic v2 with `from_attributes=True`
- **Database**: SQLAlchemy 2.0, UUID PKs, PostGIS (SRID 4326)
- **Never**: DB queries in routers, business logic in models

### Frontend (React/TS)
- **State**: 7 Contexts (Auth, City, User, Navigation, LocationTracking, VoiceGuidance, InstallPrompt) + TanStack Query (server)
- **API**: Use `fetchJson`/`uploadFile` from `lib/api/client.ts`
- **Components**: `screens/` (12 screens) for pages, `ui/` for primitives, `floodhub/` for FloodHub tab
- **Styling**: Tailwind CSS + Radix UI
- **PWA**: Workbox service worker, offline caching, install banner

#### Frontend Layout Rules (MANDATORY)

**1. Dynamic Sizing Over Hardcoded Values**
- NEVER use hardcoded pixel values for heights/widths that depend on viewport or content
- USE: `h-full`, `min-h-screen`, `flex-1`, `calc()`, CSS Grid with `fr` units
- AVOID: `h-[500px]`, `w-[800px]` unless truly fixed design requirement
- Components must adapt to their container, not assume fixed dimensions

**2. Relative Positioning Awareness**
- Before adding/modifying positioned elements, MAP the existing positioning context:
  - What elements use `relative`, `absolute`, `fixed`, `sticky`?
  - What are their parent containers?
  - What z-index values exist in the hierarchy?
- Document positioning decisions in comments when non-obvious

**3. Overlap Prevention Checklist**
Before any frontend change, verify:
- [ ] New element doesn't overlap existing fixed/absolute elements
- [ ] Z-index doesn't conflict with modals, navbars, or overlays
- [ ] Mobile viewport doesn't cause content to overflow or hide
- [ ] Scroll behavior remains correct (no double scrollbars)

**4. Systematic Layout Thinking**
- Think in layout hierarchy: Viewport → Page → Section → Component → Element
- Each level should handle its own spacing/positioning
- Parent components control layout flow, children fill allocated space
- Test at multiple viewport sizes (mobile 375px, tablet 768px, desktop 1280px)

**Anti-Patterns**: `h-[calc(100vh-200px)]` (magic numbers), `absolute` without `relative` parent, hardcoded pixel widths/heights.
**Good**: `flex flex-col h-full` + `flex-1 overflow-auto`, explicit `relative` positioning context.

### Common Gotchas (IMPORTANT)

#### Timestamps (UTC)
Backend stores UTC timestamps WITHOUT 'Z' suffix. Frontend must parse as UTC:
```typescript
const parseUTCTimestamp = (timestamp: string) => {
    if (!timestamp.endsWith('Z') && !timestamp.includes('+')) {
        return new Date(timestamp + 'Z');
    }
    return new Date(timestamp);
};
```

#### Query Invalidation
After mutations, invalidate queries to refresh data:
```typescript
queryClient.invalidateQueries({ queryKey: ['reports'] });
```

#### GeoJSON Coordinates
Always `[longitude, latitude]` order (not lat/lng).

#### CSS Stacking Context & Fixed Positioning
**CRITICAL**: Parent `transform`/`filter`/`perspective` breaks `position: fixed` — makes it relative to parent, not viewport. Z-index of 9999 inside a stacking context can still appear behind elements outside it.
**Solution**: Render fixed overlays via Portal to document root. Debug with `getBoundingClientRect()`.

#### Docker Named Volumes vs Local Files
**CRITICAL**: ML models trained locally won't appear in Docker named volumes (`ml_models:/app/models`).
**Fix**: Use bind mount (`./apps/ml-service/models:/app/models`) or `docker cp`.

#### Pydantic-Settings v2 and List Types
**CRITICAL**: `List[str]` fields fail to parse non-JSON env vars. Pydantic-settings JSON-parses BEFORE validators run.
**Fix**: Use `Annotated[List[str], NoDecode]` from `pydantic_settings` to disable pre-parsing, then add `field_validator(mode="before")`.
**Wrong Fix**: `Union[str, List[str]]` — doesn't address root cause. See [GitHub #7749](https://github.com/pydantic/pydantic/issues/7749).

---

## Development Philosophy

### Core Principle: NEVER TAKE SHORTCUTS

Every feature must be approached with systems-level thinking:

1. **UNDERSTAND** - What components are involved? How do they interact?
2. **PLAN** - Identify ALL affected files, consider edge cases
3. **IMPLEMENT** - Handle errors, use proper TypeScript types (never `any`)
4. **VERIFY** - Test E2E, check console for warnings

### Anti-Patterns (FORBIDDEN)

| Don't | Do Instead |
|-------|------------|
| Fix only the symptom | Trace root cause through system |
| Skip planning for "simple" tasks | Plan even small changes |
| Use `any` TypeScript type | Define proper interfaces |
| Ignore console warnings | Fix all warnings |
| Test only happy path | Test edge cases and errors |

### Quality Gates (NON-NEGOTIABLE)

| Gate | Command |
|------|---------|
| Type Safety | `npx tsc --noEmit` |
| Build | `npm run build` |
| Console Clean | Check browser console |

---

## Domain Contexts

> **All domain contexts (20+ features) are documented in [FEATURES.md](./FEATURES.md).**
> Key domains: @reports, @auth, @community, @alerts, @hotspots, @routing, @gamification,
> @rainfall, @floodhub, @external-alerts, @smart-search, @live-navigation, @pwa,
> @whatsapp, @iot-ingestion, @esp32-firmware, @ml-predictions, @saved-routes, @profiles, @e2e-testing

---

## Google Flood Forecasting API (FloodHub)

**Status**: Code complete. Waiting for API key activation from Google pilot program.

### API Reference
- **Base URL**: `https://floodforecasting.googleapis.com/v1`
- **Auth**: API key as query parameter `?key=KEY` (NOT header)
- **Region**: `regionCode: "IN"` (country-level), Delhi filtered locally by bounding box
- **Env var**: `GOOGLE_FLOODHUB_API_KEY` in `apps/backend/.env`

### Correct Endpoints (CRITICAL — old code was wrong)
| Operation | Method | Endpoint |
|-----------|--------|----------|
| Search gauges | POST | `/v1/gauges:searchGaugesByArea` + `{"regionCode":"IN"}` |
| Flood status | POST | `/v1/floodStatus:searchLatestFloodStatusByArea` |
| Forecasts | GET | `/v1/gauges:queryGaugeForecasts?gaugeIds=X&issuedTimeStart=Y` |
| Gauge models | GET | `/v1/gaugeModels:batchGet?names=gaugeModels/X` (max 50/req) |
| Inundation | GET | `/v1/serializedPolygons/{id}` (returns KML → convert to GeoJSON) |
| Events | POST | `/v1/significantEvents:search` |

### Backend Files
- **Service**: `apps/backend/src/domain/services/floodhub_service.py` (785 lines)
- **Router**: `apps/backend/src/api/floodhub.py` (5 endpoints: status, gauges, forecast, inundation, events)
- **Cache TTLs**: gauges 10min, forecasts 15min, models 60min, inundation 30min, events 15min

### Frontend Files
- **Types**: `FloodHubGauge`, `FloodHubForecast`, `FloodHubSignificantEvent` in `types.ts`
- **Hooks**: `useFloodHubStatus`, `useFloodHubGauges`, `useFloodHubForecast`, `useFloodHubEvents`, `useFloodHubInundation` in `hooks.ts`
- **Components**: `floodhub/FloodHubTab.tsx` → Header, SignificantEventsCard, AlertsList, ForecastChart, Footer

### Remaining Work (deferred until API key active)
1. **InundationLayer** — MapLibre GeoJSON fill layer in `MapComponent.tsx` (hook exists, layer not wired)
2. **E2E testing** with live API data
3. **Deploy** — Koyeb backend (add env var), Vercel frontend

### Key API Facts
- Pagination: `nextPageToken` pattern, max 500 gauges for forecasts, 50 for models
- Inundation maps: KML format → converted via stdlib `xml.etree.ElementTree` (no extra deps)
- Gauge location: `gauge.location.latitude` (NOT `gaugeLocation`)
- Reference notebook: `Google_Flood_Forecasting_API_Usage_Example.ipynb` in project root

---

## Safety Rules

### Never Modify Without Reading First
- `infrastructure/models.py` - Database schema
- `auth_service.py`, `AuthContext.tsx` - Auth flows
- `token-storage.ts` - Token handling
- `core/config.py` - Environment config

### Database Changes Require
1. Migration script in `scripts/migrate_*.py`
2. Test on dev database
3. Rollback procedure documented

### No Secrets in Code
- Use `.env` files (check `.env.example`)
- Never commit credentials

---

## Testing Requirements

### Quality Gates
```bash
# Type safety & build
cd apps/frontend && npx tsc --noEmit
cd apps/frontend && npm run build

# Backend tests
cd apps/backend && pytest

# Hotspots spatial differentiation
python apps/backend/verify_hotspot_spatial.py  # Verify 62 unique locations

# Visual testing (Playwright)
cd apps/frontend && npm run screenshot  # Requires auth

# E2E Full Test (creates account, tests all flows)
cd apps/frontend && npx tsx scripts/e2e-full-test.ts
```

### Test Accounts
```yaml
# E2E Test Account (auto-created by e2e-full-test.ts)
email: e2e_test_<timestamp>@floodsafe.test
password: TestPassword123!
city: Delhi
watch_area: Connaught Place
```

### Before Marking Complete
- [ ] `npx tsc --noEmit` passes (no type errors)
- [ ] `npm run build` passes (frontend)
- [ ] No new TypeScript `any` types
- [ ] Error handling present
- [ ] Console clean (no warnings)
- [ ] Use `/preflight` skill for all quality gates
- [ ] Use `superpowers:verification-before-completion` before claiming done
- [ ] Use `code-review:code-review` after major implementations

---

## Roadmap

> **Full roadmap with completion status in [FEATURES.md](./FEATURES.md).**
> Summary: Tiers 1, 4, 5, 6 COMPLETE. Tier 2-3 mostly complete. Tier 7 (Scale) planned.
