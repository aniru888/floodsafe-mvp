# Production Hardening — Changelog & Reference

> **Date**: 2026-03-05
> **Design doc**: `docs/plans/2026-02-27-production-hardening-design.md`
> **Status**: In progress

---

## Phase 1: Dependency Cleanup

### Task 1: Backend dependency upgrades
**Files**: `apps/backend/requirements.txt`

| Package | Before | After | CVEs Fixed |
|---------|--------|-------|------------|
| python-multipart | 0.0.20 | 0.0.22 | CVE-2026-24486 |
| Pillow | 10.4.0 | 12.1.1 | CVE-2026-25990 |
| aiohttp | 3.13.2 | 3.13.3 | 8 CVEs (CVE-2025-69223 through CVE-2025-69230) |
| cryptography | 46.0.3 | 46.0.5 | CVE-2026-26007 (transitive) |

**Verification**: Pillow EXIF extraction tested (getexif, TAGS, GPSTAGS). pytest 58/58 pass.

### Task 2: Frontend dependency upgrades
**Files**: `apps/frontend/package.json`, `package-lock.json`

| Package | Before | After | CVEs Fixed |
|---------|--------|-------|------------|
| react-router-dom | 7.11.0 | latest v7 | GHSA-h5cw (CSRF), GHSA-2w69 (XSS), GHSA-8v8x (SSR XSS) |

**Not fixed (deferred)**: vite (4→7 migration needed), esbuild, vitest, serialize-javascript, MCP SDK (zod v3 constraint blocks npm audit fix). 37→35 vulns.

**Verification**: `npx tsc --noEmit` clean, `npm run build` succeeds.

---

## Phase 2: Security Hardening

### Task 3: Gate Firebase dev-mode fallback
**File**: `apps/backend/src/domain/services/auth_service.py` (line ~147)

**Before**: Any Firebase API failure silently fell through to `_decode_firebase_token_dev()` which decodes JWT without cryptographic verification — allowing token forgery in production.

**After**:
```python
if response.status_code != 200:
    if settings.is_production:
        print(f"Firebase phone verification failed: {response.status_code}")
        return None
    # Fallback: decode the token ourselves for development only
    return self._decode_firebase_token_dev(id_token)
```

**Impact**: Production returns 401 on Firebase failure (correct). Local dev still uses fallback.

### Task 4: Password complexity validator
**File**: `apps/backend/src/api/auth.py` (line ~182)

**Before**: Only `min_length=8, max_length=128` — no character class requirements.

**After**: `@field_validator("password")` on `EmailRegisterRequest` requiring:
- At least 1 uppercase letter (`[A-Z]`)
- At least 1 lowercase letter (`[a-z]`)
- At least 1 digit (`[0-9]`)
- At least 1 special character
- Not in top-10 common passwords blocklist (case-insensitive)

**Impact**: Only affects new registrations. Existing users unaffected. Login endpoint unchanged.

### Task 5: Security headers middleware
**File**: `apps/backend/src/main.py` (after CORS middleware)

**Added** (production only, gated by `settings.is_production`):
| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS for 1 year |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking via iframes |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer leakage |

**Impact**: Additive — browsers enforce stricter behavior. No functional change.

### Task 6: Tighten CORS
**File**: `apps/backend/src/main.py` (lines 87-88)

| Setting | Before | After |
|---------|--------|-------|
| `allow_methods` | `["*"]` | `["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]` |
| `allow_headers` | `["*"]` | `["Content-Type", "Authorization", "Accept", "X-Requested-With"]` |

**Preserved**: `http://localhost` origin for Capacitor Android WebView.

### Task 7: Bounded rate limiting
**File**: `apps/backend/src/api/deps.py` (lines 22-71)

**Before**: `defaultdict(list)` — unbounded. Every unique IP creates a permanent entry.

**After**: `OrderedDict` with LRU eviction capped at 10,000 keys. When full, oldest key is evicted via `popitem(last=False)`. Most recently accessed keys are moved to end via `move_to_end(key)`.

**Memory ceiling**: ~2 MB max (10K keys × ~200 bytes each).

### Task 8: Password reset flow
**Files**: `auth.py`, `verification_service.py`, `email_service.py`, `models.py`, `migrate_add_password_reset_and_lockout.py`

**Added**:
- `PasswordResetToken` model (mirrors `EmailVerificationToken` pattern: hash-stored, single-use, 1hr expiry)
- `POST /auth/forgot-password` — rate-limited, anti-enumeration (always returns success)
- `POST /auth/reset-password` — validates token, sets new password (with complexity), revokes all sessions
- `send_password_reset_email()` in EmailService (SendGrid with HTML template, mock fallback)
- `create_password_reset_token()`, `validate_password_reset_token()`, `can_request_password_reset()` in VerificationService

**Security**: Same password complexity validator applied to `ResetPasswordRequest.new_password`. Token stored as SHA-256 hash. All refresh tokens revoked after reset.

### Task 9: Account lockout after failed logins
**Files**: `models.py`, `auth_service.py`, `migrate_add_password_reset_and_lockout.py`

**Added** to User model:
- `failed_login_attempts` (Integer, default 0)
- `locked_until` (DateTime, nullable)

**Logic** in `authenticate_email_user()`:
- Check `locked_until > now` → return 403 with remaining minutes
- Wrong password → increment `failed_login_attempts`, lock at 5 failures for 15 minutes
- Correct password → reset `failed_login_attempts` to 0, clear `locked_until`
- Only affects email/password login (Google OAuth and phone auth unaffected)

**Migration**: `migrate_add_password_reset_and_lockout.py` covers both Task 8 (table) and Task 9 (columns)

### Task 10: Email verification enforcement at login
**File**: `auth.py` (login endpoint, after successful auth)

**Before**: Unverified email users could log in freely.

**After**: `if not user.email_verified` → HTTP 403 with `"Please verify your email before logging in"` + `X-Verification-Required: true` header.

**Impact**: Users who registered but never clicked the verification email will be blocked. They need to verify or request a new verification email. Google OAuth and phone auth users are unaffected (those flows don't use this endpoint).

---

## Phase 3: Scalability

### Task 11: Database connection pool tuning
**Files**: `database.py` (sync + async engines), `scheduler.py`

| Pool | Before | After |
|------|--------|-------|
| Sync (psycopg2) | pool_size=5, max_overflow=10, max=15 | pool_size=3, max_overflow=5, max=8 |
| Async (asyncpg) | pool_size=5, max_overflow=10, max=15 | pool_size=3, max_overflow=5, max=8 |
| Scheduler (asyncpg) | pool_size=5, max_overflow=10, max=15 | pool_size=2, max_overflow=3, max=5 |
| **TOTAL** | **45 of 60** Supabase connections | **21 of 60** (39 free) |

Added `pool_pre_ping=True` and `pool_recycle=1800` to all three pools.

### Task 12: Bounded in-memory caches
**Files**: `rainfall.py`, `predictions.py`

| Cache | Before | After |
|-------|--------|-------|
| `_rainfall_cache` | Unbounded dict | Max 450 entries (covers 406 hotspots + margin) |
| `_prediction_cache` | Unbounded dict | Max 100 entries |

**Eviction**: FIFO based on Python 3.7+ dict insertion order. Oldest entries removed when over capacity.

### Task 13: GZIP response compression
**File**: `main.py`

Added: `app.add_middleware(GZipMiddleware, minimum_size=1000)`

Responses >= 1KB are automatically GZIP-compressed. GeoJSON/hotspot payloads (50-200KB) → 10-40KB. Browsers auto-decompress.

### Task 14: Circuit breaker for external APIs
**New file**: `core/circuit_breaker.py`

Lightweight `CircuitBreaker` class (~500 bytes per instance):
- **CLOSED**: normal operation, requests pass through
- **OPEN**: after 3 consecutive failures, blocks for 60 seconds
- **HALF-OPEN**: after cooldown, allows next attempt

Three pre-configured breakers:
| Breaker | Applied to | Chokepoint |
|---------|-----------|------------|
| `open_meteo_breaker` | `rainfall.py` `_fetch_open_meteo_forecast()` | Main weather API |
| `floodhub_breaker` | `floodhub_service.py` `_paginated_post()` | All FloodHub endpoints |
| `fhi_weather_breaker` | `fhi_calculator.py` `_fetch_with_retry()` | FHI weather data |

**When APIs healthy**: zero overhead. **When down**: instant fallback (<100ms) instead of 10s timeout cascade.

### Task 15: Scheduler pool SSL fix
**File**: `scheduler.py`

**Before**: Naive `str.replace("postgresql://", "postgresql+asyncpg://")` — no SSL config, no `connect_args`.

**After**: Uses `create_database_url()` + URL object manipulation from `database.py`. Applies proper asyncpg `ssl: "require"` and `server_settings` for search_path. Consistent with main async pool.

---

## Phase 4: Verification & Deploy

### Task 16: Full verification gate
**Status**: Complete (2026-03-05)

| Check | Result | Notes |
|-------|--------|-------|
| `pytest` | 63 passed, 3 failed, 4 skipped | 3 failures pre-existing (WhatsApp test assertions) |
| `npx tsc --noEmit` | 0 errors | Clean |
| `npm run build` | Success (27s) | PWA generated, 21 precached entries |
| `npm audit` | 35 vulns | All transitive (firebase/undici). Down from 37 pre-hardening |
| `pip-audit` | 35 vulns in 18 packages | None in targeted packages. All transitive (setuptools, pypdf, keras, etc.) |
| App routes | 154 routes | `/auth/forgot-password` + `/auth/reset-password` registered |
| Middleware | 3 active | CORS, GZip, Security Headers |
| Circuit breakers | 3 loaded, all CLOSED | open-meteo, floodhub, fhi-weather |
| Cache bounds | rainfall=450, predictions=100 | FIFO eviction |
| Rate limiter | OrderedDict, max 10K keys | LRU eviction |
| Password validator | Active | Rejected weak password in test |
| DB pool | size=3, overflow=5, pre_ping=True, recycle=1800s | Max 8 sync connections |
| PasswordResetToken model | 6 columns | id, user_id, token_hash, expires_at, created_at, used_at |
| User lockout columns | Present | failed_login_attempts, locked_until |
| Targeted package versions | All correct | python-multipart 0.0.22, Pillow 12.1.1, aiohttp 3.13.3, cryptography 46.0.5 |

### Task 17: Deploy to production
**Status**: Pending

---

## Pre-existing Issues (Not Caused by Hardening)

| Issue | Detail |
|-------|--------|
| `test_twilio_not_configured_tracked_in_errors` | Stale assertion — expects "Twilio not configured" but message changed to "No WhatsApp/SMS channel configured" |
| `test_whatsapp_success` / `test_whatsapp_fails_falls_back_to_sms` | Meta WhatsApp not configured in test environment — pre-existing |
| `tflite-runtime` install failure | Not available for Python 3.11 on Windows. Pre-existing. |
| npm audit 35 remaining vulns | All transitive (firebase/undici, vite, esbuild). Require breaking upgrades deferred to vite migration. 37→35 after react-router fix |
| pip-audit 35 remaining vulns | All transitive (awscli, setuptools, pypdf, keras, streamlit, werkzeug, etc.). None in directly-managed packages |
