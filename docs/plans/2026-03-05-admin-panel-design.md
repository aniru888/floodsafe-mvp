# Design: Admin Panel — PR #13 Review + Report Management Features

> **Date**: 2026-03-05
> **PR**: #13 (`admin-server` branch, commit `a9588a0`)
> **Scope**: Fix critical issues in PR + add admin report creation + full verification workflow
> **Status**: Approved for implementation

---

## 1. Context

PR #13 adds a complete admin panel: backend (20+ endpoints), frontend (6-panel dashboard),
admin auth (env-var credentials), and audit logging. The review identified 4 critical, 10 major,
and 8 minor issues across 16 changed files.

Additionally, two new features are needed:
- **Admin report creation** — create community reports without photos (from field data, government sources)
- **Full verification workflow** — admin verification notes, push notifications, reputation integration

### Existing Infrastructure (reuse, don't rebuild)

| System | Location | Status |
|--------|----------|--------|
| ReputationService | `reputation_service.py:113-595` | Working — `process_report_verification()` handles points, badges, auto-promote |
| Push notifications | `push_notification_service.py:55-104` | Working — `send_push_notification(fcm_token, title, body, data)` via FCM |
| Comment model | `models.py:396-407` | Working — fields: `id, report_id, user_id, content, created_at` |
| Comment API | `api/comments.py` | Working — GET/POST/DELETE with rate limiting (5/min) |
| City bounds | `api/search.py:83-122` | Working — `{min_lat, max_lat, min_lng, max_lng}` for all 5 cities |
| Report model | `models.py:135-189` | Working — 25+ columns including `verified, verified_at, quality_score, media_url` |
| ReportCard.tsx | `components/ReportCard.tsx` | Working — conditional `media_url` rendering, verified badge (green CheckCircle) |
| Verify endpoint | `api/reports.py:756-808` | **BROKEN** — completely unauthenticated, no role check |

---

## 2. PR #13 Required Fixes (Block-Merge)

### 2.1 Admin Auth Security (C1+C2+C3)

**Problem**: Plain-text password `==` comparison, hardcoded default credentials, no rate limiting, auto-creates admin user on first login.

**Fix**:
```
File: apps/backend/src/core/config.py
- ADMIN_EMAIL: str = "admin@floodsafe.app"
- ADMIN_PASSWORD: str = "floodsafe-admin-change-me"
+ ADMIN_EMAIL: str = ""
+ ADMIN_PASSWORD_HASH: str = ""  # bcrypt hash — generate with: python -c "from passlib.hash import bcrypt; print(bcrypt.hash('your-password'))"
+ Add @field_validator that raises ValueError if empty in production
```

```
File: apps/backend/src/api/admin.py (admin_login function)
- Remove auto-creation of admin user (lines 120-132)
- Add: check_rate_limit(f"admin_login:{req.client.host}", max_requests=5, window_seconds=300)
- Replace: if request.password == settings.ADMIN_PASSWORD
+ With: if not verify_password(request.password, settings.ADMIN_PASSWORD_HASH)
- Admin user must be pre-seeded via migration or management command
```

### 2.2 Transaction Safety (M1)

**Problem**: `log_admin_action()` at `admin_service.py:46` calls `db.commit()` internally. Every caller also calls `db.commit()`. Creates hidden coupling — audit entry commits all pending session changes as side effect.

**Fix**: Remove `db.commit()` and `db.refresh(entry)` from `log_admin_action()`. Callers already commit.

### 2.3 Verify Endpoint Security (CRITICAL — found during review)

**Problem**: `POST /reports/{report_id}/verify` at `reports.py:756` has NO authentication dependency. Any anonymous HTTP request can verify any report and trigger reputation point awards. This enables privilege escalation: bulk-verify target user's reports -> inflate reputation -> trigger auto-promotion to `verified_reporter`.

**Fix**:
```python
# reports.py:757 — add admin/moderator role check
from src.api.deps import get_privileged_user

def verify_report(
    report_id: UUID,
    verification: ReportVerificationRequest,
+   current_user: User = Depends(get_privileged_user),  # admin or moderator
    db: Session = Depends(get_db)
):
```

### 2.4 Frontend Fixes (M2-M5)

| Fix | File | Change |
|-----|------|--------|
| UTC timestamps | `AdminDashboard.tsx:299,446,776` | Add `parseUTC()` helper, replace all `new Date(timestamp)` |
| Global CSS | `main.tsx` | Remove `import './styles/admin.css'` — move to `AdminDashboard.tsx` and `AdminLoginScreen.tsx` |
| Orphan dep | `package.json` | Remove `"driver.js": "^1.4.0"` line |
| Reformatting | `App.tsx` | Revert whitespace changes, keep only 2 imports + 2 routes |

### 2.5 Backend Fixes (M7-M8)

| Fix | File | Change |
|-----|------|--------|
| Router business logic | `api/admin.py:186-222` | Move `update_user_role` DB logic into `admin_service.update_user_role()` |
| Sort allowlist | `admin_service.py:113` | `ALLOWED_SORT = {"created_at","username","email","role","points","reputation_score"}` |

### 2.6 Mutation Error Handling (M9)

Add `onError` callbacks to all mutations in `admin-hooks.ts`:
```typescript
onError: (err: Error) => {
    toast.error(err.message || 'Operation failed');
}
```
Requires importing toast from `react-hot-toast` or `sonner` (whichever the project uses).

---

## 3. New Feature: Admin Report Creation

### 3.1 Backend Endpoint

```
POST /api/admin/reports
Auth: get_current_admin_user
```

**Request**:
```json
{
    "description": "Waterlogging reported at MG Road underpass (string, 10-500 chars, required)",
    "latitude": 28.6139,
    "longitude": 77.2090,
    "city": "delhi",
    "water_depth": "knee",
    "vehicle_passability": "large_vehicles",
    "source": "field_observation",
    "admin_notes": "Received via phone call from local volunteer"
}
```

**Validation**:
- `city` must be one of: `delhi|bangalore|yogyakarta|singapore|indore`
- Coordinates must fall within selected city's bounding box (reuse from `search.py:83-122`)
- City bounds should be extracted to a shared `core/city_config.py` (currently duplicated in `search.py`)

**Behavior**:
- Creates Report with `admin_created = True`, `verified = True`, `verified_at = now()`
- Sets `user_id` to admin's user ID
- NO photo required (`media_url = None`)
- NO gamification points awarded (skip the 5-point base award at `reports.py:512`)
- NO ML classifier, NO GPS photo matching, NO OTP verification
- Audit logged via `log_admin_action()`

**Response**: `{ report_id, success, message }`

### 3.2 Model Change

```python
# models.py — Report class (after line 169, before latitude property)
admin_created = Column(Boolean, default=False)  # True for admin-created reports
source = Column(String(50), nullable=True)       # "field_observation"|"government_data"|"phone_report"
```

**Why `admin_created` flag instead of checking `user.role`?** Roles can change. If an admin is later demoted, their reports should still be identifiable as admin-created. The flag is immutable at creation time.

### 3.3 Reputation Guard

```python
# reputation_service.py — process_report_verification(), after line 130
report = self.db.query(Report).filter(Report.id == report_id).first()
if report.admin_created:
    # Admin reports are pre-verified — skip reputation pipeline
    return {"points_earned": 0, "quality_score": report.quality_score or 0, "skipped": "admin_created"}
```

### 3.4 Frontend — Admin Dashboard Create Report Form

In `AdminDashboard.tsx`, add a "Create Report" button in the Reports panel header. Opens a form with:
- Description textarea (required)
- City dropdown (required)
- Latitude/Longitude inputs OR a simplified map picker
- Water depth dropdown (optional)
- Vehicle passability dropdown (optional)
- Source dropdown: Field observation | Government data | Phone report (required)
- Admin notes textarea (optional)

### 3.5 Community Feed Display

In `ReportCard.tsx`, when `report.admin_created === true`:
- Show "Official Report" badge (blue/authoritative) instead of generic "Verified"
- Show source label: "Source: Field observation" (human-readable)
- No photo section rendered (already handled — `media_url` conditional at line 213)

---

## 4. New Feature: Full Verification Workflow

### 4.1 Comment Model Extension

```python
# models.py — Comment class, add after content field (line 402)
comment_type = Column(String(20), default="community")
# Values: "community" (default), "admin_verification", "admin_rejection"
```

**Upsert logic**: When admin verifies/rejects, query for existing admin comment on that report:
```python
existing = db.query(Comment).filter(
    Comment.report_id == report_id,
    Comment.comment_type.in_(["admin_verification", "admin_rejection"])
).first()
if existing:
    existing.content = notes
    existing.comment_type = new_type
    existing.created_at = datetime.utcnow()
else:
    # Create new admin comment
```
This prevents duplicate verification notes if admin re-verifies.

### 4.2 Enhanced Verify Endpoint

Modify `POST /reports/{report_id}/verify` (after adding auth from 2.3):

```python
# After reputation processing, add:

# 1. Create/update admin verification comment
if verification.notes:
    comment_type = "admin_verification" if verification.verified else "admin_rejection"
    _upsert_admin_comment(db, report_id, current_user.id, verification.notes, comment_type)

# 2. Push notification (verified only; rejection only if notes provided)
if report.user_id and report.user_id != current_user.id:
    user = db.query(User).filter(User.id == report.user_id).first()
    if user and user.fcm_token:
        if verification.verified:
            await send_push_notification(
                user.fcm_token,
                "Report Verified!",
                f"Your flood report was verified by the FloodSafe team. +{result.get('points_earned', 0)} points!",
                data={"report_id": str(report_id), "type": "verification"}
            )
        elif verification.notes:  # Rejection push ONLY if admin wrote a reason
            await send_push_notification(
                user.fcm_token,
                "Report Update",
                "Your flood report was reviewed. Tap for details.",
                data={"report_id": str(report_id), "type": "review"}
            )
```

**Why no push on silent rejection?** Rejections without explanation are discouraging. If admin doesn't explain why, the user just sees the -5 point change in their profile — gentler feedback loop that doesn't actively discourage future reporting.

### 4.3 Verification Request Schema Update

```python
# reports.py or admin.py — extend the verification request
class ReportVerificationRequest(BaseModel):
    verified: bool
    quality_score: int = Field(0, ge=0, le=100)
    notes: Optional[str] = Field(None, max_length=500)  # NEW — admin verification notes
```

### 4.4 Admin Dashboard — Verification Queue

Enhance the Reports panel in `AdminDashboard.tsx`:

**Filter tabs**: `Pending Review` (default) | `Verified` | `Rejected` | `All`
- Pending = `verified=false, archived_at=null`
- Verified = `verified=true`
- Rejected = has `admin_rejection` comment type (need backend support)

**Report card in admin panel shows**:
- Description, timestamp (UTC-corrected), city
- Photo thumbnail (if exists)
- Current vote score (upvotes - downvotes)
- Water depth / vehicle passability badges

**Actions per report**:
- **Verify**: Opens modal with quality score slider (0-100) + notes textarea. Submits to verify endpoint.
- **Reject**: Opens modal with required reason textarea. Submits to verify endpoint with `verified=false`.
- **Archive**: Existing archive endpoint
- **Delete**: Existing delete endpoint with reason

**No auto-advance** — YAGNI. Admin clicks next report manually.

### 4.5 Frontend — Admin Notes in ReportCard

In `ReportCard.tsx`, after the existing comment section:
- Query comments for the report (already done via `useComments`)
- Filter for `comment_type === "admin_verification"` or `"admin_rejection"`
- Render admin notes in a distinct callout:
  - Verified: green border, "FloodSafe Team: [notes]"
  - Rejected: amber border, "Review Note: [notes]"
- Regular community comments render as before (no change)

---

## 5. Migration Plan

### 5.1 Prerequisite: Verify PR Migration Chain

Before adding new migrations, verify:
```bash
cd apps/backend && alembic history
```
Confirm that `654d12e73e2f` (initial schema) exists and `3eae32b88127` chains correctly.

Check if `tour_completed_at`, `verified_reporter_since`, `moderator_since` already exist in production:
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'users'
AND column_name IN ('tour_completed_at', 'verified_reporter_since', 'moderator_since');
```
If they exist, the PR's migration will fail. Fix: add `IF NOT EXISTS` guards or remove those lines from the migration.

### 5.2 New Migration (chains after PR's migration)

```
Revision: XXXXX
Down revision: 3eae32b88127

upgrade():
    # Report: admin_created flag + source field
    op.add_column('reports', sa.Column('admin_created', sa.Boolean(), default=False, server_default='false'))
    op.add_column('reports', sa.Column('source', sa.String(50), nullable=True))

    # Comment: type field for admin notes
    op.add_column('comments', sa.Column('comment_type', sa.String(20), server_default='community'))

downgrade():
    op.drop_column('comments', 'comment_type')
    op.drop_column('reports', 'source')
    op.drop_column('reports', 'admin_created')
```

### 5.3 Admin User Pre-Seeding

Since auto-creation is removed (Section 2.1), admin user must be seeded:
```sql
-- Run via Supabase MCP after migration
INSERT INTO users (id, username, email, role, auth_provider, password_hash, email_verified, profile_complete, city_preference)
VALUES (
    gen_random_uuid(),
    'floodsafe_admin',
    '<ADMIN_EMAIL from env>',
    'admin',
    'local',
    '<bcrypt hash of ADMIN_PASSWORD>',
    true,
    true,
    'delhi'
) ON CONFLICT (email) DO UPDATE SET role = 'admin';
```

---

## 6. Deferred Items (Post-Merge Tech Debt)

| Item | Reason for Deferral | Tracking |
|------|---------------------|----------|
| Same-origin XSS (C4) | Needs subdomain infrastructure (`admin.floodsafe.live`) | Future issue |
| Admin routes inside app providers (M6) | Requires App.tsx provider tree restructure | Future PR |
| `prompt()`/`confirm()` -> Radix modals (M10) | Functional as-is, UX polish | Future PR |
| Mobile admin nav (m7) | Internal tool, desktop-only acceptable for v1 | Future PR |
| Response models on admin endpoints (m4) | No data leaks currently | Future PR |
| Photo URL validation in admin (m2) | Low risk (React auto-escapes) | Future PR |
| `unban` restores to `user` role (m3) | Intentional safety default | Document only |
| Dead `useAdminAnalyticsCities` hook (m6) | Harmless dead code | Cleanup PR |
| City bounds extraction to shared config | Currently duplicated in `search.py` | Future refactor |

---

## 7. File Change Map

```
BACKEND — PR FIXES
  MODIFY  apps/backend/src/core/config.py                    (~10 lines)
  MODIFY  apps/backend/src/api/admin.py                      (~50 lines)
  MODIFY  apps/backend/src/domain/services/admin_service.py   (~40 lines)
  MODIFY  apps/backend/src/api/reports.py                     (~5 lines)

BACKEND — NEW FEATURES
  MODIFY  apps/backend/src/infrastructure/models.py           (~5 lines — 3 columns)
  MODIFY  apps/backend/src/api/admin.py                      (~60 lines — create report endpoint)
  MODIFY  apps/backend/src/domain/services/admin_service.py   (~80 lines — create report + upsert comment)
  MODIFY  apps/backend/src/domain/services/reputation_service.py (~5 lines — admin_created guard)
  MODIFY  apps/backend/src/api/reports.py                     (~30 lines — push + notes in verify)
  NEW     apps/backend/alembic/versions/XXXXX_admin_features.py (~20 lines)

FRONTEND — PR FIXES
  MODIFY  apps/frontend/src/components/screens/AdminDashboard.tsx (~20 lines — UTC + onError)
  MODIFY  apps/frontend/src/lib/api/admin-hooks.ts            (~30 lines — onError handlers)
  MODIFY  apps/frontend/src/main.tsx                          (~1 line — remove CSS import)
  MODIFY  apps/frontend/src/App.tsx                           (revert whitespace, keep routes)
  MODIFY  apps/frontend/package.json                          (~1 line — remove driver.js)

FRONTEND — NEW FEATURES
  MODIFY  apps/frontend/src/components/screens/AdminDashboard.tsx (~300 lines — create form + queue)
  MODIFY  apps/frontend/src/lib/api/admin-hooks.ts            (~60 lines — new hooks)
  MODIFY  apps/frontend/src/components/ReportCard.tsx          (~30 lines — Official badge + notes)
  MODIFY  apps/frontend/src/styles/admin.css                  (~40 lines — verification queue styles)

TOTAL: ~16 files modified, ~1 new file, ~800 lines changed
```

---

## 8. Testing Checklist

### Backend
- [ ] Admin login rejects default/empty credentials
- [ ] Admin login rate-limited (6th attempt within 5min returns 429)
- [ ] Admin report creation validates city bounds
- [ ] Admin report creation sets `admin_created=true`, `verified=true`
- [ ] Admin-created reports skip reputation pipeline
- [ ] Verify endpoint requires admin/moderator auth (401 without token)
- [ ] Verify endpoint creates/updates admin comment
- [ ] Verify endpoint sends push to report author (verified)
- [ ] Verify endpoint does NOT push on silent rejection
- [ ] `log_admin_action` does not commit (caller commits)
- [ ] Migration applies cleanly, downgrade works

### Frontend
- [ ] AdminDashboard timestamps display correctly (UTC)
- [ ] admin.css only loads on /admin routes (check network tab)
- [ ] Create Report form validates required fields
- [ ] Verification queue filters work (pending/verified/rejected)
- [ ] Mutation errors show toast notification
- [ ] ReportCard shows "Official Report" for admin-created reports
- [ ] Admin verification notes render distinctly in ReportCard
- [ ] No driver.js in production bundle

### E2E
- [ ] Full flow: admin login -> create report -> appears in community feed with Official badge
- [ ] Full flow: admin login -> verify user report -> user gets push -> reputation updated
- [ ] Regular user cannot access /api/admin/* endpoints
- [ ] Regular user cannot access /reports/{id}/verify endpoint
