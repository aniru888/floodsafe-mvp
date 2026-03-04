# Production Hardening Design — Dependencies, Security, Scalability

> **Date**: 2026-02-27
> **Approach**: Phased batches (Dependencies → Security → Scalability → Verification)
> **Status**: Design phase — audit refreshed 2026-03-05

---

## Verified Infrastructure (Exact Numbers)

| Resource | Platform | Plan | Exact Specs | Source |
|----------|----------|------|-------------|--------|
| **Backend** | Koyeb | **Free** | 1 shared vCPU, **512 MB RAM**, 2.5 GB disk, max 1 instance, scale-to-zero, region: Frankfurt | `koyeb services describe` output |
| **ML Service** | Koyeb | **Free** | **PAUSED since Jan 6, 2026** — no active service | `koyeb apps list` output |
| **Frontend** | Vercel | **Hobby (Free)** | **100 GB/month bandwidth**, 6000 min/month build, 1 concurrent build, **141 MB deploy** (137 MB = PMTiles) | `vercel project ls` + `vercel inspect` |
| **Database** | Supabase | **Free (Nano)** | **60 max direct connections**, 500 MB database, 1 GB file storage, 5 GB egress, 50K MAU auth | [Supabase docs](https://supabase.com/docs/guides/troubleshooting/how-to-change-max-database-connections-_BQ8P5) |

### Database Connection Pools (Verified from Code)

| Pool | File:Line | pool_size | max_overflow | Max | pool_pre_ping | pool_recycle |
|------|-----------|-----------|-------------|-----|---------------|-------------|
| Sync (psycopg2) | `database.py:89` | 5 (default) | 10 (default) | 15 | No | None |
| Async (asyncpg) | `database.py:109` | 5 (default) | 10 (default) | 15 | No | None |
| Scheduler (asyncpg) | `scheduler.py` (own engine) | 5 (explicit) | 10 (explicit) | 15 | Yes | None |
| **TOTAL** | | | | **45 of 60** | | |

### Bandwidth Estimates (Calculated, Not Guessed)

- Vercel: **100 GB/month**
- First visit: ~3-5 MB (JS+CSS+HTML+initial API; PMTiles stream on demand)
- Return visits: ~100-500 KB (SW-cached assets, just API calls)
- **Max first-time visitors**: ~20,000-33,000/month (100GB / 3-5MB)
- **Max return visitors**: 200,000-1,000,000/month (100GB / 100-500KB)

---

## PHASE 1: Dependency Cleanup

### 1A: Backend — Packages VERIFIED as Actually Used

| # | Package | Current | Target | CVEs | Used Where (verified) | Breaking? |
|---|---------|---------|--------|------|-----------------------|-----------|
| 1 | **aiohttp** | 3.13.2 | 3.13.3 | 8 CVEs | 8 alert fetchers in `external_alerts/` (telegram, pub, gdacs, rss, cwc, twitter, imd, gdelt) | No — patch |
| 2 | **cryptography** | 46.0.3 | 46.0.5 | 1 CVE | Transitive (Firebase Admin SDK, python-jose). Not directly imported. | No — patch |
| 3 | **python-multipart** | 0.0.20 | 0.0.22 | 1 CVE | `reports.py:302-314` (Form+File), `ml.py:15,66` (File), `webhook.py:308-312` (Form for Twilio) | No — patch |
| 4 | **Pillow** | 10.4.0 | 12.1.1 | 1 CVE | `core/utils.py:1-2` (EXIF GPS extraction from photos), `ml-service/scripts/` (testing) | **YES — major jump 10→12**. Must test Image.open, EXIF read, resize. PIL API is stable but verify. |
| 5 | **urllib3** | 2.6.2 | 2.6.3 | 1 CVE | Transitive (requests). Not directly imported. | No — patch |
| 6 | **werkzeug** | 3.1.4 | 3.1.6 | 2 CVEs | Transitive (Flask, which is transitive of something else). Not directly imported. | No — patch |
| 7 | **filelock** | 3.20.0 | 3.20.3 | 2 CVEs | Transitive (torch/huggingface model caching). Not directly imported. | No — patch |
| 8 | **geopandas** | 1.1.1 | 1.1.2 | 1 CVE | Transitive. Not directly imported in backend src. | No — patch |
| 9 | **pyasn1** | 0.6.1 | 0.6.2 | 1 CVE | Transitive (crypto). Not directly imported. | No — patch |
| 10 | **wheel** | 0.45.1 | 0.46.2 | 1 CVE | Build tool only. Not runtime. | No |
| 11 | **setuptools** | 65.5.0 | 78.1.1 | 3 CVEs | Build tool only. Not runtime. | No — build tool |
| 12 | **flask** | 3.1.2 | 3.1.3 | 1 CVE | Not directly imported. Not in requirements.txt. Transitive only. | No — patch |

**NEW since Feb 27 audit (discovered 2026-03-05 refresh):**

| # | Package | Current | Target | CVEs | Used Where | Breaking? |
|---|---------|---------|--------|------|-----------------------|-----------|
| 13 | **awscli** | 1.43.0 | 1.44.38 | 1 (GHSA-747p) | Transitive. Not directly used in app. | No — patch |
| 14 | **keras** | 3.12.0 | 3.12.1 | 2 CVEs (CVE-2026-0897, CVE-2026-1669) | ML service uses `tensorflow.keras`. Standalone keras is transitive. | No — patch, transitive |
| 15 | **nbconvert** | 7.16.6 | 7.17.0 | 1 CVE (CVE-2025-53000) | Transitive (Jupyter). Not used in production. | No — dev tool |
| 16 | **nltk** | 3.9.2 | 3.9.3 | 1 CVE (CVE-2025-14009) | Not imported in `apps/backend/src/`. Transitive only. | No — patch |
| 17 | **pip** | 24.0 | 26.0 | 2 CVEs (CVE-2025-8869, CVE-2026-1703) | Package manager. Not runtime. | No — build tool |
| 18 | **pypdf** | 6.4.0 | 6.7.5 | 9 CVEs (CVE-2026-22690 through CVE-2026-28804) | Not imported anywhere. Transitive only. | No — transitive |
| 19 | **streamlit** | 1.32.0 | 1.37.0 | 1 (PYSEC-2024-153) | Not in requirements.txt. Transitive only. | No — transitive |
| 20 | **yt-dlp** | 2025.12.8 | 2026.2.21 | 1 CVE (CVE-2026-26331) | CLI tool in optional data collection script. Not a pip dependency. | No — optional |

**NOT fixable / shielded (no action needed):**

| Package | Why No Action |
|---------|-------------|
| **js2py** 0.74 (no fix) | Not imported. Transitive only. Shielded by parent package. |
| **ecdsa** 0.19.1 (no fix) | Not imported. Transitive from python-jose[cryptography]. Shielded. |

### 1B: Frontend — Packages VERIFIED

| # | Package | Current | Fix | Used Where (verified) | Breaking? |
|---|---------|---------|-----|-----------------------|-----------|
| 1 | **react-router-dom** | 7.11.0 | 7.12.1+ via `npm audit fix` | `main.tsx:3,9` (BrowserRouter), `App.tsx:3,303,305` (Routes) | No — patch within v7 |
| 2 | **@modelcontextprotocol/sdk** | 1.25.2 | patch via `npm audit fix` | Transitive via @mcp-b/react-webmcp. Not directly imported. | No — patch |
| 3 | **rollup** | 3.29.5 | patch via `npm audit fix` | Transitive via vite. Build tool only. | No — patch |
| 4 | **minimatch** | various | patch via `npm audit fix` | Transitive via eslint, vitest. Build/lint tooling. | No — patch |
| 5 | **hono** | 4.11.9 | 4.11.10+ via `npm audit fix` | NOT imported in frontend src. Transitive via MCP SDK. | No — patch |
| 6 | **ajv** | 6.12.6 / 8.17.1 | patch via `npm audit fix` | NOT imported in frontend src. Transitive via eslint, workbox, MCP SDK. | No — patch |
| 7 | **undici** | 6.19.7 | patch via `npm audit fix` | NOT imported in frontend src. Transitive via firebase. | No — patch |

**NEW since Feb 27 audit (discovered 2026-03-05 refresh):**

| # | Package | Current | Fix | Used Where | Breaking? |
|---|---------|---------|-----|------------|-----------|
| 8 | **serialize-javascript** | <=7.0.2 | `npm audit fix --force` (installs vite-plugin-pwa@0.19.8) | Transitive via @rollup/plugin-terser → workbox-build → vite-plugin-pwa. NOT directly imported. | **YES — vite-plugin-pwa breaking change**. Requires separate migration. |
| 9 | **undici** (expanded) | 6.19.7 | patch via `npm audit fix` | Now 3 CVEs (was 1): GHSA-c76h (random values), GHSA-g9mf (decompression bomb), GHSA-cxrh (bad cert DoS). Transitive via firebase. | No — patch |

**NOT fixable now (deferred — requires vite 4→7 and/or plugin migrations):**

| Package | Current | Fix Requires | Why Deferred |
|---------|---------|-------------|-------------|
| **vite** | 4.5.14 | vite 7.3.1 | 3 major version jump. Breaking build config, plugin compat, dev server changes. Dedicated migration needed. |
| **esbuild** | 0.18.20 | Tied to vite | Upgrades with vite. |
| **vitest** | 1.6.1 | Tied to vite | Test runner API changes with major vite upgrade. |
| **serialize-javascript** | <=7.0.2 | vite-plugin-pwa 0.19.8 | Breaking change to PWA plugin config. Tied to vite migration. |

**Safe to remove (not used):**

| Package | Evidence |
|---------|----------|
| **lodash** | 0 imports in `apps/frontend/src/`. `_.unset` and `_.omit` (vulnerable functions) never called. Transitive via recharts — can't remove from node_modules, but not a direct dependency risk. |

### Phase 1 Verification Gate

```
Backend:
  ✓ pip-audit — 0 fixable CVEs remaining
  ✓ pytest — all existing tests pass
  ✓ uvicorn starts without import errors
  ✓ /health endpoint responds
  ✓ Report photo upload works (Pillow EXIF test after major upgrade)
  ✓ External alerts fetching works (aiohttp test)

Frontend:
  ✓ npm audit — only deferred vite/esbuild/vitest issues remain
  ✓ npx tsc --noEmit — 0 type errors
  ✓ npm run build — production build succeeds
  ✓ All navigation flows work (react-router test)
```

---

## PHASE 2: Security Hardening

### 2A: Critical Fixes

#### Fix 1: Gate Firebase dev-mode fallback

| Aspect | Verified Detail |
|--------|----------------|
| **File** | `apps/backend/src/domain/services/auth_service.py` |
| **Problem location** | Lines 147-150 (trigger) + Lines 173-203 (fallback function) |
| **Exact code** | `if response.status_code != 200: return self._decode_firebase_token_dev(id_token)` |
| **Issue** | Fallback triggers on ANY Firebase API failure (network error, invalid key, timeout). Comment says "development only" but **NO environment check** (`settings.DEBUG`, `settings.is_production`, etc.). Decodes JWT payload without cryptographic verification → anyone can forge a phone number. |
| **Change** | Add guard at line 147: `if response.status_code != 200: if not getattr(settings, 'DEBUG', False): raise HTTPException(401, "Phone verification failed"); return self._decode_firebase_token_dev(id_token)` |
| **Impact on current working** | **Production**: Firebase API calls succeed (FIREBASE_PROJECT_ID is set on Koyeb) → fallback never triggers → zero change. **Local dev without Firebase**: Still works via fallback. **Production if Firebase goes down**: Returns 401 instead of silently accepting forged tokens (correct behavior). |
| **Verification** | Deploy → phone login works. Kill Firebase config → returns 401 (not fake acceptance). Local dev → fallback still works. |

#### Fix 2: Password complexity

| Aspect | Verified Detail |
|--------|----------------|
| **File** | `apps/backend/src/api/auth.py` |
| **Problem location** | Line 184: `password: str = Field(..., min_length=8, max_length=128)` |
| **Exact code** | Pydantic Field with length only. No `pattern=`, no `@validator`, no regex. |
| **Change** | Add `@field_validator('password')` requiring: 1 uppercase (`[A-Z]`), 1 lowercase (`[a-z]`), 1 digit (`[0-9]`), 1 special char (`[!@#$%^&*(),.?":{}|<>]`). Also block top-10 common passwords. |
| **Impact on current working** | **Existing users**: Unaffected — validation only runs at registration (line 194-244). No retroactive password checking. **New registrations**: Must meet complexity requirements. **Login endpoint**: Unchanged (line 247-281 does NOT re-validate password format). |
| **Verification** | Register with "aaaaaaaa" → 422 error. Register with "Test1ng!" → succeeds. Existing accounts still log in. |

#### Fix 3: Per-account lockout

| Aspect | Verified Detail |
|--------|----------------|
| **File** | `apps/backend/src/infrastructure/models.py` (lines 11-75, User model) + `auth_service.py` (lines 307-343, `authenticate_email_user`) |
| **Problem location** | `authenticate_email_user` at line 340-341 returns `None` on failure with no tracking. No `failed_login_attempts` or `locked_until` fields in User model. |
| **Exact code** | `if not verify_password(password, user.password_hash): return None` — fails silently, no counter. |
| **Change** | Add to User model: `failed_login_attempts: int = Column(Integer, default=0)`, `locked_until: datetime = Column(DateTime, nullable=True)`. In `authenticate_email_user`: check `locked_until` before password verify, increment `failed_login_attempts` on failure, lock for 15 min after 5 failures, reset counter on success. |
| **Impact on current working** | **DB migration required**: 2 new nullable columns with defaults (non-breaking ALTER TABLE). Existing users get `failed_login_attempts=0, locked_until=NULL`. Only affects email/password login (Google OAuth at line 30-66 and phone auth at line 68-170 don't use passwords). |
| **Verification** | 5 wrong passwords → 6th returns 403 with lockout duration. Wait 15 min → login works. Google/phone login unaffected. Check DB: `failed_login_attempts` increments correctly. |

#### Fix 4: Security headers

| Aspect | Verified Detail |
|--------|----------------|
| **File** | `apps/backend/src/main.py` |
| **Problem location** | Lines 81-89 — ONLY middleware is CORSMiddleware. Zero security headers. |
| **Exact finding** | Grepped entire `main.py`: no `Strict-Transport-Security`, no `X-Content-Type-Options`, no `X-Frame-Options`, no `Content-Security-Policy`, no `Referrer-Policy`. Completely absent. |
| **Change** | Add custom middleware (after CORS) that sets on every response: `Strict-Transport-Security: max-age=31536000; includeSubDomains` (HTTPS enforcement), `X-Content-Type-Options: nosniff` (prevent MIME sniffing), `X-Frame-Options: DENY` (prevent clickjacking), `Referrer-Policy: strict-origin-when-cross-origin`. Only active when `"localhost" not in str(settings.DATABASE_URL)` (production check already used at line 52). |
| **Impact on current working** | **Production (Koyeb+Vercel)**: Already serves over HTTPS. Headers tell browsers to enforce it. No behavioral change for users. **Local dev**: Headers skipped (localhost check). No impact. |
| **Verification** | `curl -I https://floodsafe-backend-...koyeb.app/health` → headers present. `curl -I http://localhost:8000/health` → headers absent. |

#### Fix 5: Tighten CORS

| Aspect | Verified Detail |
|--------|----------------|
| **File** | `apps/backend/src/main.py:83-89` + `core/config.py:19-24` |
| **Exact code** | `allow_methods=["*"], allow_headers=["*"]`. Origins: `["http://localhost:5175", "http://localhost:8000", "http://localhost", "https://frontend-lime-psi-83.vercel.app"]` |
| **Change** | Replace `allow_methods=["*"]` with `["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]`. Replace `allow_headers=["*"]` with `["Content-Type", "Authorization", "Accept", "X-Requested-With"]`. Change `"http://localhost"` to `"http://localhost:5175"` (remove bare localhost). |
| **Impact on current working** | Must verify no endpoint uses unusual methods (TRACE, CONNECT) or custom headers beyond Content-Type/Authorization/Accept. All standard REST+Bearer flows are covered. Capacitor WebView at `http://localhost` (no port) will be blocked — need to test if Capacitor actually sends this origin or a specific port. |
| **Verification** | Frontend loads correctly. API calls succeed. OPTIONS preflight returns correct headers. Test from unauthorized origin → blocked. |

### 2B: High Priority Fixes

#### Fix 6: Bounded rate limiting

| Aspect | Verified Detail |
|--------|----------------|
| **File** | `apps/backend/src/api/deps.py:18-65` |
| **Exact code** | `_rate_limit_store: dict[str, list[datetime]] = defaultdict(list)` — global dict, sliding window, cleans old entries on read (line 54-55). Limits: Google 10/60s, Phone 5/60s, Email login 5/60s. |
| **Problem** | Unbounded dict (never evicts keys, only timestamps). Lost on restart. Single-instance only. |
| **Change** | Add `maxsize=10000` key eviction (LRU). Keep in-memory (no Redis on free tier), but add bounded growth. The DB-backed rate limiting from Phase 2 original design is removed — Koyeb free tier is max 1 instance, so in-memory IS sufficient. Just needs bounding. |
| **Impact** | Same rate limits, same behavior. Dict capped at 10,000 keys. On restart, limits reset (acceptable for 1-instance free tier). |

#### Fix 7: Password reset flow

| Aspect | Verified Detail |
|--------|----------------|
| **Verified absence** | Grepped `auth.py` and `auth_service.py` for `forgot`, `reset_password`, `password_reset` — **0 results**. No endpoint exists. No token model exists. |
| **Change** | Add `POST /auth/forgot-password` (generates single-use token, 1-hour expiry, sends email via SendGrid). Add `POST /auth/reset-password` (validates token, sets new bcrypt hash). Reuse `EmailVerificationToken` pattern from `verification_service.py` (lines 1-190). Add `ForgotPasswordScreen.tsx` in frontend. |
| **Impact** | **Additive only** — new endpoints, new screen. No existing flows modified. Uses existing SendGrid infrastructure. |

#### Fix 8: Email verification enforcement at login

| Aspect | Verified Detail |
|--------|----------------|
| **File** | `auth_service.py:340-343` (returns user without checking `email_verified`) + `auth.py:247-281` (login endpoint, no verification check) |
| **Exact code** | `authenticate_email_user` → `if not verify_password(...): return None` → `return user` — no `email_verified` check anywhere in the chain. |
| **Change** | In `login_email` endpoint (auth.py ~line 270): after successful auth, check `if not user.email_verified: raise HTTPException(403, "Please verify your email first")`. Return the email in the error detail so frontend can show "Check your inbox" message with resend option. |
| **Impact** | Users who registered but never verified email will be blocked from login. This is the CORRECT behavior (verification exists but wasn't enforced). May affect users who registered during the window where verification was added but not enforced — they'll need to verify or request a new verification email. |

### Phase 2 Verification Gate

```
✓ Phone login works (production Firebase verification — fallback gated)
✓ Email registration enforces password complexity (weak passwords rejected)
✓ Account lockout after 5 failed attempts (DB fields exist, counter works)
✓ Security headers present in production responses (curl -I check)
✓ CORS rejects unauthorized origins/methods (browser test)
✓ Rate limiting bounded at 10K keys (memory stays flat)
✓ Password reset flow works end-to-end (email sent, reset succeeds)
✓ Unverified email users get 403 with helpful message
✓ All Phase 1 checks still pass (no regression)
```

---

## PHASE 3: Scalability

### 3A: Database Connection Pool Tuning

| Aspect | Verified Detail |
|--------|----------------|
| **Files** | `database.py:89` (sync), `database.py:109` (async), `scheduler.py` (own engine) |
| **Current state** | 3 pools × 15 max = **45 of 60 Supabase connections** consumed. No `pool_pre_ping`, no `pool_recycle`. |
| **Change** | Sync: `pool_size=3, max_overflow=5` (8 max). Async: `pool_size=3, max_overflow=5` (8 max). Scheduler: `pool_size=2, max_overflow=3` (5 max). Add `pool_pre_ping=True, pool_recycle=1800` on ALL three. **Total: 21 max** (down from 45). |
| **Why these numbers** | 1 uvicorn worker = async event loop = rarely needs >3-5 concurrent DB connections. Current defaults (15 per pool) are massive overkill for single-process server. 21 total leaves 39 free for Dashboard/migrations/tools. |
| **Impact** | Fewer idle connections (saves Supabase resources). Stale connections detected (pre_ping). 30-min recycle prevents Supabase idle timeout kills. No behavior change for users. |

### 3B: Multi-Worker — REMOVED

| Aspect | Detail |
|--------|--------|
| **Why removed** | **512 MB RAM**. Each Python worker = ~120 MB base. 2 workers = 240 MB + caches + transient = OOM risk. Single uvicorn worker is correct for 512 MB. Async I/O handles concurrency via event loop. |
| **If more capacity needed** | Upgrade Koyeb plan (not free tier), not more workers in 512 MB. |

### 3C: Bounded In-Memory Caches

| Aspect | Verified Detail |
|--------|----------------|
| **Files** | `api/rainfall.py:19-20` (`_cache = {}`), `api/predictions.py:20-22` (`_cache = {}`) |
| **Current state** | Unbounded Python dicts. Every unique (lat,lng) creates entry living for 1 hour. No maxsize, no eviction. |
| **Change** | Max 450 entries for weather (covers 406 hotspots across 5 cities + margin). Max 100 for predictions. LRU eviction when full. Total cache budget: ~3 MB. |
| **Why 400** | 90 (Delhi) + 200 (Bangalore) + 19 (Yogyakarta) + 60 (Singapore) + 37 (Indore) = **406 hotspots**. 450 covers all with 44 spare for user searches. |
| **Impact** | Memory flat at ~3 MB forever. Currently: unbounded growth → eventual OOM on 512 MB instance. |

### 3D: Response Compression (GZIPMiddleware)

| Aspect | Detail |
|--------|--------|
| **File** | `apps/backend/src/main.py` |
| **Change** | `app.add_middleware(GZIPMiddleware, minimum_size=1000)`. Built-in FastAPI middleware. |
| **Impact** | GeoJSON responses (50-200 KB) → 10-40 KB. ~1 KB buffer per response, negligible RAM. Browsers auto-decompress. Mobile loads 3-5x faster. |

### 3E: External API Circuit Breaker

| Aspect | Detail |
|--------|--------|
| **Files** | `fhi_service.py`, `rainfall.py`, `floodhub_service.py` |
| **Change** | Lightweight class (~500 bytes): after 3 consecutive failures → 60-second cooldown → return cached/fallback data. No new dependencies. |
| **Impact** | When APIs healthy: zero change. When down: instant fallback instead of 10-second timeout cascade. |

### 3F: Scheduler pool SSL fix

| Aspect | Verified Detail |
|--------|----------------|
| **File** | `scheduler.py` — creates own async engine with naive `str.replace("postgresql://", "postgresql+asyncpg://")` |
| **Problem** | Does NOT call `get_connect_args()` from `database.py`. No SSL config applied. Supabase requires SSL. |
| **Change** | Import and use `create_database_url()` and `get_connect_args()` from `database.py`. |
| **Impact** | Scheduler connections become SSL-secured and consistent with other pools. May fix intermittent scheduler errors. |

### Phase 3 Verification Gate

```
✓ pg_stat_activity shows ≤ 21 connections at peak (down from 45)
✓ Supabase dashboard accessible while app runs (39 connections free)
✓ Memory stable after 1 hour: under 400 MB of 512 MB
✓ Cache sizes: weather ≤ 450, predictions ≤ 100
✓ Gzip: curl with Accept-Encoding shows compressed responses
✓ Circuit breaker: mock failure → fallback in <100ms
✓ Scheduler SSL: connections use SSL
✓ All Phase 1 + Phase 2 checks still pass
```

### Revised Capacity After All Phases

| Metric | Current (verified) | After Changes | Calculation |
|--------|-------------------|---------------|-------------|
| DB connection headroom | 15 of 60 free (45 used) | 39 of 60 free (21 used) | 3+5 + 3+5 + 2+3 = 21 |
| Backend steady-state memory | Unbounded (OOM risk) | ~134 MB | 120MB Python + 2.3MB weather (450 entries) + 0.5MB predictions + misc |
| Backend memory headroom | Unknown (shrinking) | ~379 MB free of 512 MB | 512 - 133 = 379 |
| Concurrent requests (async) | ~50-100/sec | ~50-100/sec (unchanged) | Single worker, limited by CPU |
| Monthly first-time visitors | ~20K-33K | ~25K-40K | Gzip saves ~30% on API responses |
| External API failure | 10+ sec timeout | <100ms fallback | Circuit breaker |

---

## PHASE 4: Full E2E Verification (Testing Only)

| Check | Command / Method | Pass Criteria |
|-------|-----------------|---------------|
| pip-audit | `pip-audit` | 0 fixable CVEs |
| npm audit | `npm audit` | Only deferred vite/esbuild/vitest |
| TypeScript | `npx tsc --noEmit` | 0 errors |
| Frontend build | `npm run build` | Succeeds |
| Backend tests | `pytest` | All pass |
| Email register | Manual | Complexity enforced, verification email sent |
| Email login | Manual | Works, lockout after 5 failures, unverified blocked |
| Google OAuth | Manual | Works unchanged |
| Phone OTP | Manual | Works unchanged, dev fallback gated |
| Password reset | Manual | Email sent, reset works, old password invalid |
| Security headers | `curl -I` | HSTS, X-Content-Type, X-Frame present |
| CORS | Browser DevTools | Rejects unauthorized origins |
| DB connections | `pg_stat_activity` | ≤ 21 total |
| Memory | Koyeb dashboard | Stable under 400 MB after 1 hour |
| Gzip | `curl --compressed` | 3-5x smaller responses |
| Circuit breaker | Mock test | Fallback on external API failure |
| Deploy frontend | `npx vercel --prod` | Builds, serves correctly |
| Deploy backend | Koyeb redeploy | Health check passes |

---

## Appendix: Vulnerability Sources

### npm audit (refreshed 2026-03-05) — 37 vulnerabilities (1 low, 19 moderate, 17 high)

**Fixable via `npm audit fix`:**
- react-router 7.0.0-7.12.0: CSRF (GHSA-h5cw-625j-3rxh), XSS Open Redirects (GHSA-2w69-qvjg-hvjx), SSR XSS (GHSA-8v8x-cx79-35w7)
- @modelcontextprotocol/sdk 1.10.0-1.25.3: Cross-client data leak (GHSA-345p-7cg4-v4c7)
- minimatch various: ReDoS (GHSA-3ppc-4f35-3m26, GHSA-7r86-cg39-jmmj, GHSA-23c5-xmqv-rm74)
- rollup 3.29.5/4.x: Path Traversal file write (GHSA-mw96-cpmx-2vgc)
- lodash 4.0.0-4.17.21: Prototype Pollution (GHSA-xxjr-mmjv-4gpg)
- hono <4.11.10: Timing attack in basicAuth/bearerAuth (GHSA-gq3j-xvxp-8hrf)
- ajv <6.14.0 / <8.18.0: ReDoS with $data option (GHSA-2g4f-4pwh-qvx6)
- undici <=6.22.0: 3 CVEs — random values (GHSA-c76h), decompression bomb (GHSA-g9mf), bad cert DoS (GHSA-cxrh)

**Deferred (requires breaking upgrades):**
- vite <=6.1.6: 3 moderate vulns (requires vite 4→7 migration)
- esbuild <=0.24.2: Dev server request leak (GHSA-67mh-4wv8-2f99) (tied to vite)
- vitest: tied to vite
- serialize-javascript <=7.0.2: RCE via RegExp.flags (GHSA-5c6j-r48x-rmvq) (requires vite-plugin-pwa 0.19.8 — breaking change)

### pip-audit (refreshed 2026-03-05) — 46 vulnerabilities in 22 packages

**Directly used packages (ACTION REQUIRED):**
- aiohttp 3.13.2: CVE-2025-69223 through CVE-2025-69230 (8 CVEs, fix: 3.13.3)
- cryptography 46.0.3: CVE-2026-26007 (fix: 46.0.5)
- python-multipart 0.0.20: CVE-2026-24486 (fix: 0.0.22)
- Pillow 10.4.0: CVE-2026-25990 (fix: 12.1.1) ⚠️ major version jump

**Transitive packages (fix when convenient):**
- urllib3 2.6.2: CVE-2026-21441 (fix: 2.6.3)
- werkzeug 3.1.4: CVE-2026-21860, CVE-2026-27199 (fix: 3.1.6)
- filelock 3.20.0: CVE-2025-68146, CVE-2026-22701 (fix: 3.20.3)
- flask 3.1.2: CVE-2026-27205 (fix: 3.1.3)
- geopandas 1.1.1: CVE-2025-69662 (fix: 1.1.2)
- pyasn1 0.6.1: CVE-2026-23490 (fix: 0.6.2)
- setuptools 65.5.0: PYSEC-2022-43012, PYSEC-2025-49, CVE-2024-6345 (fix: 78.1.1)
- wheel 0.45.1: CVE-2026-24049 (fix: 0.46.2)

**New since Feb 27 (transitive, not directly used):**
- awscli 1.43.0: GHSA-747p-wmpv-9c78 (fix: 1.44.38)
- keras 3.12.0: CVE-2026-0897, CVE-2026-1669 (fix: 3.12.1)
- nbconvert 7.16.6: CVE-2025-53000 (fix: 7.17.0)
- nltk 3.9.2: CVE-2025-14009 (fix: 3.9.3)
- pip 24.0: CVE-2025-8869, CVE-2026-1703 (fix: 26.0)
- pypdf 6.4.0: 9 CVEs (CVE-2026-22690 through CVE-2026-28804, fix: 6.7.5)
- streamlit 1.32.0: PYSEC-2024-153 (fix: 1.37.0)
- yt-dlp 2025.12.8: CVE-2026-26331 (fix: 2026.2.21)

### No fix available (transitive, not directly used)
- ecdsa 0.19.1: CVE-2024-23342 (transitive via python-jose)
- js2py 0.74: CVE-2024-28397 (transitive, not imported)
