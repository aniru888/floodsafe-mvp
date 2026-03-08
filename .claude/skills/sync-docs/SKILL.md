---
name: sync-docs
description: Scan codebase for real counts (hotspots, contexts, tables, cities, routers, screens) and compare against FEATURES.md, CLAUDE.md, README.md. Reports drift and optionally applies fixes.
argument-hint: [--apply]
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# Documentation Sync — Drift Detection

Scan the actual codebase for ground truth metrics and compare them against what's documented in FEATURES.md, CLAUDE.md, and README.md. Reports drift and optionally auto-fixes.

**Arguments**: `$ARGUMENTS`
- No args: Report only (safe, read-only)
- `--apply`: Report AND auto-fix all drifted values

---

## Phase 1: Gather Ground Truth from Code

Run ALL of these checks to build a ground truth table. Use parallel tool calls where possible.

### 1. Hotspots per city
For each JSON file in `apps/ml-service/data/`, count entries:
```bash
python -c "import json,glob; [print(f.split('/')[-1].split('\\\\')[-1]+': '+str(len(json.load(open(f))))) for f in glob.glob('apps/ml-service/data/*_waterlogging_hotspots.json')]"
```
Expected files: `delhi_waterlogging_hotspots.json`, `yogyakarta_waterlogging_hotspots.json`, `singapore_waterlogging_hotspots.json`

### 2. React Contexts
```
Glob pattern: apps/frontend/src/contexts/*Context.tsx
```
Count the files. Also note the context names (strip "Context.tsx" suffix).

### 3. Frontend Screens
```
Glob pattern: apps/frontend/src/components/screens/*Screen.tsx
```
Count the files. Note their names.

### 4. Database Models
```
Grep pattern: "class .+\(.*Base.*\):" in apps/backend/src/infrastructure/models.py
```
Count unique class definitions that inherit from Base.

### 5. Backend Routers
```
Glob pattern: apps/backend/src/api/*.py
```
Exclude `__init__.py` and `deps.py`. Count remaining files.

### 6. Supported Cities
```
Grep pattern: "CITY_CODES" in apps/frontend/src/lib/cityUtils.ts
```
Read the CITY_CODES object and extract city keys.

### 7. Alert Sources (External Alert Fetchers)
```
Glob pattern: apps/backend/src/domain/services/external_alerts/*_fetcher.py
```
Exclude `base_fetcher.py`. Count remaining files.

### 8. WebMCP Entities
```
Grep in apps/frontend/src/components/WebMCPProvider.tsx for:
- registerContext → count
- registerTool → count
- registerResource → count
- registerPrompt → count
Total = sum of all
```

### 9. FHI City Calibration
Read `apps/backend/src/domain/services/rainfall.py` and extract the `CITY_CALIBRATION` dictionary. Note per-city keys and their values (especially `precip_threshold_mm`, `intensity_threshold_mm_hr`, `elevation_range`).

### 10. Environment Variables
```bash
# Backend env vars
grep -c "=" apps/backend/.env.example 2>/dev/null || echo "no .env.example"
# Frontend env vars
grep -c "=" apps/frontend/.env.example 2>/dev/null || echo "no .env.example"
```

### 11. FEATURES.md Line Count
```bash
wc -l FEATURES.md
```

### 12. Recent Git Activity
```bash
git log --oneline -20
```
Note any commits since the "Last updated" date in MEMORY.md.

---

## Phase 2: Extract Documented Values

Read these files and extract the CURRENTLY DOCUMENTED values for each metric above:

### FEATURES.md
Read the file and search for:
- `hotspot_counts:` section (lines ~123-127) — per-city hotspot numbers
- `Frontend Contexts (N)` heading — context count
- `Database Models (N)` heading — model count
- `Backend API Files (N)` heading — router count
- `entities (N total)` — WebMCP entity count
- FHI calibration values (appears in both @hotspots and @rainfall sections)
- Roadmap `[ ]` and `[x]` items in Tier 7
- Line count references like "980+ lines"

### README.md
Read and search for:
- Hotspot counts in features table and "Why FloodSafe" paragraph
- "N screens", "N React contexts", "N tables", "N routers", "N+ endpoints"
- City Coverage table with per-city counts
- FEATURES.md line count reference

### CLAUDE.md
Read and search for:
- `Frontend state: "N Contexts (...list...)"` (around line 403)
- WebMCP `switch_city` city list (around line 323)
- MCP Status date
- Hotspot pipeline counts

---

## Phase 3: Diff and Report

Build this comparison table:

```
Documentation Sync Report
==========================================================================================================
  #  │ Metric                │ Code Value      │ Documented      │ Status │ Locations
─────┼───────────────────────┼─────────────────┼─────────────────┼────────┼──────────────────────────────
  1  │ Hotspots (Delhi)      │ <from code>     │ <from docs>     │ ✅/⚠️  │ FEATURES L123, README L45
  2  │ Hotspots (Yogyakarta) │ <from code>     │ <from docs>     │ ✅/⚠️  │ FEATURES L124, README L46
  3  │ Hotspots (Singapore)  │ <from code>     │ <from docs>     │ ✅/⚠️  │ FEATURES L125, README L47
  4  │ Total Hotspots        │ <sum>           │ <from docs>     │ ✅/⚠️  │ README "Why FloodSafe"
  5  │ React Contexts        │ <from code>     │ <from docs>     │ ✅/⚠️  │ CLAUDE L403, FEATURES, README
  6  │ Frontend Screens      │ <from code>     │ <from docs>     │ ✅/⚠️  │ CLAUDE, FEATURES
  7  │ DB Models             │ <from code>     │ <from docs>     │ ✅/⚠️  │ FEATURES, README
  8  │ Backend Routers       │ <from code>     │ <from docs>     │ ✅/⚠️  │ FEATURES, README
  9  │ Supported Cities      │ <from code>     │ <from docs>     │ ✅/⚠️  │ all 3 files
 10  │ Alert Sources         │ <from code>     │ <from docs>     │ ✅/⚠️  │ FEATURES, README
 11  │ WebMCP Entities       │ <from code>     │ <from docs>     │ ✅/⚠️  │ CLAUDE, FEATURES
 12  │ FEATURES.md Lines     │ <from wc>       │ <from docs>     │ ✅/⚠️  │ README
==========================================================================================================
  Drifted: N  │  Current: N  │  Total: 12
```

Status key: ✅ = matches, ⚠️ DRIFT = code differs from docs

Also list any Tier 7 roadmap `[ ]` items that appear to now have matching code (i.e., a feature that was marked incomplete but now has implementation).

---

## Phase 4: Apply Fixes (only if --apply)

**If `$ARGUMENTS` contains `--apply`:**

For each drifted metric:
1. Show: `File: <path>, Line: <N>, Old: "<old value>", New: "<new value>"`
2. Use the Edit tool to replace the old value with the correct one
3. Apply to ALL locations where the value appears (a metric may be documented in multiple files)
4. After all edits, show a summary of changes made

**If `$ARGUMENTS` does NOT contain `--apply`:**

Just display the report with a note:
```
Run `/sync-docs --apply` to auto-fix drifted values.
```

---

## Important Notes

- FEATURES.md has DUPLICATED values (e.g., FHI calibration appears in both @hotspots and @rainfall sections). When applying fixes, update ALL locations.
- MEMORY.md also contains counts — but do NOT auto-edit MEMORY.md (it's managed separately).
- Some values are approximate (e.g., "980+ lines") — flag as drift only if the actual value differs by >5%.
- Context names in CLAUDE.md include the full list in parentheses — when updating the count, also verify the list matches actual context files.
