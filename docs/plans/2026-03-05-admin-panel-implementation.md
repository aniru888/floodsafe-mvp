# Admin Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical security issues in PR #13, add admin report creation (no photo), and implement a full verification workflow with admin notes, push notifications, and reputation integration.

**Architecture:** All changes build on top of PR #13's `admin-server` branch (commit `a9588a0`). Backend follows existing layered architecture: `api/` -> `domain/services/` -> `infrastructure/`. Frontend uses TanStack Query hooks + sonner toasts. Admin auth is separate from Firebase (env-var credentials + JWT).

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React 18, TypeScript, TanStack Query, sonner, FCM push

**Design doc:** `docs/plans/2026-03-05-admin-panel-design.md`

**Branch:** Work on `admin-server` branch (PR #13). All changes are modifications to existing PR files.

---

## Prerequisites

Before starting, merge `admin-server` into your working branch:

```bash
git fetch origin admin-server
git checkout admin-server
git merge origin/admin-server
```

Verify the branch has the admin files:
```bash
ls apps/backend/src/api/admin.py apps/backend/src/domain/services/admin_service.py
ls apps/frontend/src/components/screens/AdminDashboard.tsx
```

---

### Task 1: Fix Admin Auth Security (C1+C2+C3)

**Files:**
- Modify: `apps/backend/src/core/config.py:144-148`
- Modify: `apps/backend/src/api/admin.py:95-144`
- Test: `apps/backend/tests/test_admin.py`

**Step 1: Write failing tests for auth security**

Add to `apps/backend/tests/test_admin.py`:

```python
class TestAdminAuthSecurity:
    """Tests for admin login security hardening."""

    def test_admin_login_rejects_empty_credentials_config(self, client_no_db):
        """When ADMIN_EMAIL or ADMIN_PASSWORD_HASH are empty, login should fail."""
        response = client_no_db.post("/api/admin/login", json={
            "email": "",
            "password": "anything"
        })
        assert response.status_code in [401, 503]

    def test_admin_login_rate_limited(self, client_no_db):
        """After 5 failed attempts, should return 429."""
        for i in range(6):
            response = client_no_db.post("/api/admin/login", json={
                "email": "wrong@example.com",
                "password": "wrong"
            })
        # 6th attempt should be rate limited (or 500 if no DB, but rate limit fires first)
        assert response.status_code in [429, 500]
```

**Step 2: Run tests to verify they fail**

```bash
cd apps/backend && python -m pytest tests/test_admin.py::TestAdminAuthSecurity -v
```

Expected: FAIL — rate limiting not implemented on admin login yet.

**Step 3: Fix config.py — empty defaults + validator**

In `apps/backend/src/core/config.py`, replace lines 147-148:

```python
    # Admin Panel Credentials (set via environment variables in production)
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD_HASH: str = ""  # bcrypt hash of admin password
```

**Step 4: Fix admin.py — secure login endpoint**

Replace the `admin_login` function in `apps/backend/src/api/admin.py` (lines ~95-144):

```python
@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest, req: Request, db: Session = Depends(get_db)):
    """
    Admin login with pre-configured credentials.
    Uses ADMIN_EMAIL and ADMIN_PASSWORD_HASH environment variables.
    Returns JWT tokens for admin API access.
    """
    from src.api.deps import check_rate_limit

    # Rate limit: 5 attempts per 5 minutes per IP
    check_rate_limit(f"admin_login:{req.client.host}", max_requests=5, window_seconds=300)

    # Reject if admin not configured
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD_HASH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin panel not configured",
        )

    # Validate email
    if request.email != settings.ADMIN_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )

    # Validate password against bcrypt hash
    if not verify_password(request.password, settings.ADMIN_PASSWORD_HASH):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )

    # Look up admin user (must be pre-seeded — no auto-creation)
    admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin user not found. Run admin seed migration.",
        )

    # Ensure admin role
    if admin_user.role != "admin":
        admin_user.role = "admin"
        db.commit()

    # Generate tokens
    access_token = create_access_token(data={"sub": str(admin_user.id)})
    refresh_token_str, _ = create_refresh_token(str(admin_user.id))

    return AdminLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": str(admin_user.id),
            "username": admin_user.username,
            "email": admin_user.email,
            "role": admin_user.role,
        },
    )
```

Also add the `Request` import at top of file if not present:
```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
```

**Step 5: Run tests to verify they pass**

```bash
cd apps/backend && python -m pytest tests/test_admin.py -v
```

Expected: All auth security tests PASS.

**Step 6: Commit**

```bash
cd apps/backend
git add src/core/config.py src/api/admin.py tests/test_admin.py
git commit -m "fix(admin): secure login — hashed password, rate limiting, no auto-create"
```

---

### Task 2: Fix Transaction Safety (M1)

**Files:**
- Modify: `apps/backend/src/domain/services/admin_service.py:27-48`

**Step 1: Write failing test**

Add to `apps/backend/tests/test_admin.py`:

```python
class TestAdminServiceTransactions:
    """Tests for transaction safety in admin service."""

    def test_log_admin_action_does_not_commit(self):
        """log_admin_action should not call db.commit() — caller manages transaction."""
        import inspect
        from src.domain.services import admin_service
        source = inspect.getsource(admin_service.log_admin_action)
        assert "db.commit()" not in source, "log_admin_action should not commit — caller manages transaction"
        assert "db.refresh(" not in source, "log_admin_action should not refresh — unnecessary round-trip"
```

**Step 2: Run test to verify it fails**

```bash
cd apps/backend && python -m pytest tests/test_admin.py::TestAdminServiceTransactions -v
```

Expected: FAIL — `db.commit()` is currently in the function.

**Step 3: Remove commit from log_admin_action**

In `apps/backend/src/domain/services/admin_service.py`, replace the `log_admin_action` function body. Remove the `db.commit()` and `db.refresh(entry)` lines:

```python
def log_admin_action(
    db: Session,
    admin_id: UUID,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AdminAuditLog:
    """Create an audit log entry for an admin action.
    NOTE: Does NOT commit. Caller must commit the transaction."""
    entry = AdminAuditLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry
```

**Step 4: Run tests**

```bash
cd apps/backend && python -m pytest tests/test_admin.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/domain/services/admin_service.py tests/test_admin.py
git commit -m "fix(admin): remove db.commit from log_admin_action — caller manages transaction"
```

---

### Task 3: Fix Verify Endpoint Security

**Files:**
- Modify: `apps/backend/src/api/reports.py:756-760`
- Test: `apps/backend/tests/test_admin.py`

**Step 1: Write failing test**

```python
class TestVerifyEndpointSecurity:
    """Tests for report verification endpoint security."""

    def test_verify_requires_authentication(self, client_no_db):
        """POST /reports/{id}/verify should require authentication."""
        import uuid
        fake_id = str(uuid.uuid4())
        response = client_no_db.post(f"/api/reports/{fake_id}/verify", json={
            "verified": True,
            "quality_score": 50
        })
        # Should be 401 (no token) or 403 (not authorized), NOT 404/500
        assert response.status_code in [401, 403], \
            f"Verify endpoint should require auth, got {response.status_code}"
```

**Step 2: Run test to verify it fails**

```bash
cd apps/backend && python -m pytest tests/test_admin.py::TestVerifyEndpointSecurity -v
```

Expected: FAIL — currently returns 404 or 500 (no auth check).

**Step 3: Add auth dependency to verify endpoint**

In `apps/backend/src/api/reports.py`, modify the verify_report function signature (around line 757):

```python
from src.api.deps import get_current_verified_user

@router.post("/{report_id}/verify")
def verify_report(
    report_id: UUID,
    verification: ReportVerificationRequest,
    current_user: User = Depends(get_current_verified_user),  # admin, moderator, or verified_reporter
    db: Session = Depends(get_db)
):
```

Add the import at the top of the file if not present:
```python
from src.api.deps import get_current_user, get_current_verified_user
from src.infrastructure.models import User
```

**Step 4: Run tests**

```bash
cd apps/backend && python -m pytest tests/test_admin.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/api/reports.py tests/test_admin.py
git commit -m "fix(security): require auth on report verification endpoint"
```

---

### Task 4: Backend Fixes — Sort Allowlist + Move Router Logic

**Files:**
- Modify: `apps/backend/src/domain/services/admin_service.py:110-117`
- Modify: `apps/backend/src/api/admin.py:186-222`

**Step 1: Write failing test for sort allowlist**

```python
class TestAdminServiceSafety:
    """Tests for admin service safety measures."""

    def test_sort_allowlist_blocks_invalid_fields(self):
        """list_users_filtered should reject invalid sort fields."""
        import inspect
        from src.domain.services import admin_service
        source = inspect.getsource(admin_service.list_users_filtered)
        assert "ALLOWED_SORT" in source or "allowed_sort" in source, \
            "list_users_filtered must use a sort field allowlist"
```

**Step 2: Run test to verify it fails**

```bash
cd apps/backend && python -m pytest tests/test_admin.py::TestAdminServiceSafety -v
```

**Step 3: Add sort allowlist**

In `apps/backend/src/domain/services/admin_service.py`, at the top of `list_users_filtered` (around line 110):

```python
ALLOWED_SORT_FIELDS = {"created_at", "username", "email", "role", "points", "reputation_score"}

def list_users_filtered(
    db: Session,
    role: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    per_page: int = 20,
) -> Dict[str, Any]:
    """List users with optional filtering, searching, and pagination."""
    # Validate sort field against allowlist
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = "created_at"

    query = db.query(User)
    # ... rest of function unchanged
```

**Step 4: Move update_user_role logic to service layer**

Add to `apps/backend/src/domain/services/admin_service.py`:

```python
def update_user_role(
    db: Session, user_id: UUID, admin_id: UUID, new_role: str, reason: str
) -> Dict[str, Any]:
    """Change a user's role with audit trail."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}

    old_role = user.role
    user.role = new_role

    # Timestamps for role transitions
    if new_role == "verified_reporter":
        user.verified_reporter_since = user.verified_reporter_since or datetime.utcnow()
    elif new_role == "moderator":
        user.moderator_since = user.moderator_since or datetime.utcnow()

    role_entry = RoleHistory(
        user_id=user_id,
        old_role=old_role,
        new_role=new_role,
        changed_by=admin_id,
        reason=reason,
    )
    db.add(role_entry)

    log_admin_action(
        db, admin_id, "change_role", "user", str(user_id),
        json.dumps({"old": old_role, "new": new_role, "reason": reason})
    )

    db.commit()
    return {"success": True, "old_role": old_role, "new_role": new_role}
```

Then simplify `apps/backend/src/api/admin.py` `update_user_role` endpoint:

```python
@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    role_update: RoleUpdateRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Change a user's role with audit trail."""
    result = admin_service.update_user_role(
        db, user_id, admin.id, role_update.new_role, role_update.reason
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
```

**Step 5: Run tests**

```bash
cd apps/backend && python -m pytest tests/test_admin.py -v
```

**Step 6: Commit**

```bash
git add src/domain/services/admin_service.py src/api/admin.py tests/test_admin.py
git commit -m "fix(admin): sort allowlist + move update_user_role to service layer"
```

---

### Task 5: Model Changes + Migration

**Files:**
- Modify: `apps/backend/src/infrastructure/models.py:169` (Report) and `:402` (Comment)
- Create: `apps/backend/alembic/versions/XXXXX_admin_report_features.py`

**Step 1: Verify migration chain**

```bash
cd apps/backend && python -m alembic history 2>&1 || echo "Alembic history check failed — verify manually"
```

**Step 2: Add columns to Report model**

In `apps/backend/src/infrastructure/models.py`, inside the `Report` class, after `archived_at` (line 169):

```python
    # Admin report fields
    admin_created = Column(Boolean, default=False)  # True for admin-created reports
    source = Column(String(50), nullable=True)       # "field_observation"|"government_data"|"phone_report"
```

**Step 3: Add column to Comment model**

In `apps/backend/src/infrastructure/models.py`, inside the `Comment` class, after `created_at` (line 403):

```python
    comment_type = Column(String(20), default="community")  # "community"|"admin_verification"|"admin_rejection"
```

**Step 4: Create migration**

```bash
cd apps/backend && python -m alembic revision --autogenerate -m "add admin report and comment type fields"
```

If autogenerate doesn't work (common without DB connection), create manually:

```python
# apps/backend/alembic/versions/XXXXX_add_admin_report_and_comment_type_fields.py
"""add admin report and comment type fields

Revision ID: <auto>
Revises: 3eae32b88127
"""
from alembic import op
import sqlalchemy as sa

revision = '<generate>'
down_revision = '3eae32b88127'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('reports', sa.Column('admin_created', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('reports', sa.Column('source', sa.String(length=50), nullable=True))
    op.add_column('comments', sa.Column('comment_type', sa.String(length=20), server_default='community', nullable=True))

def downgrade() -> None:
    op.drop_column('comments', 'comment_type')
    op.drop_column('reports', 'source')
    op.drop_column('reports', 'admin_created')
```

**Step 5: Verify type check passes**

```bash
cd apps/backend && python -c "from src.infrastructure.models import Report, Comment; print('Report.admin_created:', hasattr(Report, 'admin_created')); print('Comment.comment_type:', hasattr(Comment, 'comment_type'))"
```

Expected: Both True.

**Step 6: Commit**

```bash
git add src/infrastructure/models.py alembic/versions/
git commit -m "feat(models): add admin_created, source on Report + comment_type on Comment"
```

---

### Task 6: Admin Report Creation — Backend

**Files:**
- Modify: `apps/backend/src/domain/services/admin_service.py`
- Modify: `apps/backend/src/api/admin.py`
- Test: `apps/backend/tests/test_admin.py`

**Step 1: Write failing test**

```python
class TestAdminReportCreation:
    """Tests for admin report creation endpoint."""

    def test_admin_create_report_in_schema(self, client_no_db):
        """POST /api/admin/reports should be registered."""
        response = client_no_db.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})
        assert "/api/admin/reports" in paths, "Admin create report endpoint not registered"
        assert "post" in paths["/api/admin/reports"], "Should accept POST"

    def test_admin_create_report_requires_auth(self, client_no_db):
        """POST /api/admin/reports should require admin auth."""
        response = client_no_db.post("/api/admin/reports", json={
            "description": "Test flood report",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "city": "delhi",
            "source": "field_observation"
        })
        assert response.status_code in [401, 403, 500]
```

**Step 2: Run test to verify it fails**

```bash
cd apps/backend && python -m pytest tests/test_admin.py::TestAdminReportCreation -v
```

**Step 3: Add request model to admin.py**

In `apps/backend/src/api/admin.py`, add to the request/response models section:

```python
class AdminCreateReportRequest(BaseModel):
    """Admin request to create a report without photo."""
    description: str = Field(..., min_length=10, max_length=500)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    city: str = Field(..., pattern="^(delhi|bangalore|yogyakarta|singapore|indore)$")
    water_depth: Optional[str] = Field(None, pattern="^(ankle|knee|waist|chest)$")
    vehicle_passability: Optional[str] = Field(None, pattern="^(all|large_vehicles|none)$")
    source: str = Field("field_observation", pattern="^(field_observation|government_data|phone_report)$")
    admin_notes: Optional[str] = Field(None, max_length=500)
```

**Step 4: Add city bounds validation to admin_service.py**

In `apps/backend/src/domain/services/admin_service.py`, add at the top (after imports):

```python
from src.infrastructure.models import Report
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

# City bounding boxes for coordinate validation
CITY_BOUNDS = {
    "delhi": {"min_lat": 28.40, "max_lat": 28.88, "min_lng": 76.84, "max_lng": 77.35},
    "bangalore": {"min_lat": 12.75, "max_lat": 13.20, "min_lng": 77.35, "max_lng": 77.80},
    "yogyakarta": {"min_lat": -7.95, "max_lat": -7.65, "min_lng": 110.30, "max_lng": 110.50},
    "singapore": {"min_lat": 1.15, "max_lat": 1.47, "min_lng": 103.60, "max_lng": 104.05},
    "indore": {"min_lat": 22.52, "max_lat": 22.85, "min_lng": 75.72, "max_lng": 75.97},
}


def validate_city_bounds(lat: float, lng: float, city: str) -> bool:
    """Validate that coordinates fall within the city's bounding box."""
    bounds = CITY_BOUNDS.get(city)
    if not bounds:
        return False
    return (bounds["min_lat"] <= lat <= bounds["max_lat"] and
            bounds["min_lng"] <= lng <= bounds["max_lng"])


def admin_create_report(
    db: Session, admin_id: UUID, data: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a report as admin — no photo required, auto-verified."""
    # Validate coordinates within city bounds
    if not validate_city_bounds(data["latitude"], data["longitude"], data["city"]):
        return {"error": f"Coordinates ({data['latitude']}, {data['longitude']}) are outside {data['city']} bounds"}

    # Create PostGIS point
    point = from_shape(Point(data["longitude"], data["latitude"]), srid=4326)

    report = Report(
        user_id=admin_id,
        description=data["description"],
        location=point,
        media_url=None,  # No photo required
        verified=True,
        verified_at=datetime.utcnow(),
        admin_created=True,
        source=data.get("source", "field_observation"),
        water_depth=data.get("water_depth"),
        vehicle_passability=data.get("vehicle_passability"),
        quality_score=75.0,  # Admin reports get a default quality score
    )
    db.add(report)

    log_admin_action(
        db, admin_id, "create_report", "report", None,
        json.dumps({"city": data["city"], "source": data.get("source"), "description": data["description"][:100]})
    )

    db.commit()
    db.refresh(report)
    return {"success": True, "report_id": str(report.id), "message": "Admin report created"}
```

**Step 5: Add endpoint to admin.py**

In `apps/backend/src/api/admin.py`, add a new endpoint in the REPORT MODERATION section:

```python
@router.post("/reports")
async def admin_create_report(
    req: AdminCreateReportRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Create a report as admin without photo requirement."""
    result = admin_service.admin_create_report(db, admin.id, req.model_dump())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
```

**Step 6: Run tests**

```bash
cd apps/backend && python -m pytest tests/test_admin.py -v
```

**Step 7: Commit**

```bash
git add src/api/admin.py src/domain/services/admin_service.py tests/test_admin.py
git commit -m "feat(admin): add admin report creation endpoint — no photo, auto-verified"
```

---

### Task 7: Reputation Guard for Admin Reports

**Files:**
- Modify: `apps/backend/src/domain/services/reputation_service.py:122-155`
- Test: `apps/backend/tests/test_admin.py`

**Step 1: Write failing test**

```python
class TestReputationGuard:
    """Tests for reputation pipeline admin_created guard."""

    def test_reputation_service_has_admin_guard(self):
        """process_report_verification should skip for admin_created reports."""
        import inspect
        from src.domain.services.reputation_service import ReputationService
        source = inspect.getsource(ReputationService.process_report_verification)
        assert "admin_created" in source, \
            "process_report_verification must check admin_created flag"
```

**Step 2: Run test to verify it fails**

```bash
cd apps/backend && python -m pytest tests/test_admin.py::TestReputationGuard -v
```

**Step 3: Add guard to reputation_service.py**

In `apps/backend/src/domain/services/reputation_service.py`, inside `process_report_verification` method (around line 130, after fetching the report):

Find the line that fetches the report (e.g., `report = self.db.query(Report)...`) and add after it:

```python
        # Skip reputation pipeline for admin-created reports
        if report.admin_created:
            return {
                "points_earned": 0,
                "quality_score": report.quality_score or 0,
                "skipped": "admin_created",
            }
```

**Step 4: Run tests**

```bash
cd apps/backend && python -m pytest tests/test_admin.py -v
```

**Step 5: Commit**

```bash
git add src/domain/services/reputation_service.py tests/test_admin.py
git commit -m "feat(reputation): skip pipeline for admin-created reports"
```

---

### Task 8: Enhanced Verify Endpoint — Notes + Push

**Files:**
- Modify: `apps/backend/src/api/reports.py:756-808`
- Modify: `apps/backend/src/domain/services/admin_service.py`

**Step 1: Add notes field to ReportVerificationRequest**

Find `ReportVerificationRequest` in `apps/backend/src/api/reports.py` and add:

```python
class ReportVerificationRequest(BaseModel):
    verified: bool
    quality_score: int = 0
    notes: Optional[str] = Field(None, max_length=500)  # Admin verification notes
```

Add `Optional` to imports if not present: `from typing import Optional`

**Step 2: Add upsert_admin_comment to admin_service.py**

```python
def upsert_admin_comment(
    db: Session, report_id: UUID, admin_id: UUID, notes: str, comment_type: str
) -> Comment:
    """Create or update an admin verification comment on a report."""
    existing = db.query(Comment).filter(
        Comment.report_id == report_id,
        Comment.comment_type.in_(["admin_verification", "admin_rejection"])
    ).first()

    if existing:
        existing.content = notes
        existing.comment_type = comment_type
        existing.created_at = datetime.utcnow()
        return existing
    else:
        comment = Comment(
            report_id=report_id,
            user_id=admin_id,
            content=notes,
            comment_type=comment_type,
        )
        db.add(comment)
        return comment
```

**Step 3: Enhance verify endpoint with notes + push**

Replace the verify_report function body in `apps/backend/src/api/reports.py` (keep the new auth signature from Task 3):

```python
@router.post("/{report_id}/verify")
async def verify_report(
    report_id: UUID,
    verification: ReportVerificationRequest,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    """Verify or reject a report with quality scoring, admin notes, and push notification."""
    try:
        report = db.query(models.Report).filter(models.Report.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        if report.verified and verification.verified:
            return {
                'message': 'Report already verified',
                'report_id': str(report_id),
                'verified': True,
                'quality_score': report.quality_score
            }

        # Process verification through reputation service
        reputation_service = ReputationService(db)
        result = reputation_service.process_report_verification(
            report_id=report_id,
            verified=verification.verified,
            quality_score=verification.quality_score
        )

        # Create/update admin verification comment
        if verification.notes:
            from src.domain.services.admin_service import upsert_admin_comment
            comment_type = "admin_verification" if verification.verified else "admin_rejection"
            upsert_admin_comment(db, report_id, current_user.id, verification.notes, comment_type)
            db.commit()

        # Push notification to report author
        if report.user_id and report.user_id != current_user.id:
            author = db.query(models.User).filter(models.User.id == report.user_id).first()
            if author and hasattr(author, 'fcm_token') and author.fcm_token:
                from src.domain.services.push_notification_service import send_push_notification
                if verification.verified:
                    await send_push_notification(
                        author.fcm_token,
                        "Report Verified!",
                        f"Your flood report was verified by the FloodSafe team. +{result.get('points_earned', 0)} points!",
                        data={"report_id": str(report_id), "type": "verification"}
                    )
                elif verification.notes:  # Rejection push only if admin wrote a reason
                    await send_push_notification(
                        author.fcm_token,
                        "Report Update",
                        "Your flood report was reviewed. Tap for details.",
                        data={"report_id": str(report_id), "type": "review"}
                    )

        return {
            'message': 'Report verified' if verification.verified else 'Report rejected',
            'report_id': str(report_id),
            'verified': verification.verified,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying report: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to verify report")
```

**Note**: The endpoint must be `async def` (not `def`) to use `await send_push_notification()`.

**Step 4: Run tests**

```bash
cd apps/backend && python -m pytest tests/ -v
```

**Step 5: Commit**

```bash
git add src/api/reports.py src/domain/services/admin_service.py
git commit -m "feat(verify): add admin notes, push notifications to verification flow"
```

---

### Task 9: Frontend Fixes — CSS, UTC, driver.js, onError

**Files:**
- Modify: `apps/frontend/src/main.tsx`
- Modify: `apps/frontend/src/components/screens/AdminDashboard.tsx`
- Modify: `apps/frontend/src/components/screens/AdminLoginScreen.tsx`
- Modify: `apps/frontend/src/lib/api/admin-hooks.ts`
- Modify: `apps/frontend/package.json`

**Step 1: Move CSS import from main.tsx to admin components**

In `apps/frontend/src/main.tsx`, remove:
```typescript
- import './styles/admin.css'
```

In `apps/frontend/src/components/screens/AdminDashboard.tsx`, add at top:
```typescript
import '../../styles/admin.css';
```

In `apps/frontend/src/components/screens/AdminLoginScreen.tsx`, add at top:
```typescript
import '../../styles/admin.css';
```

**Step 2: Fix UTC timestamps in AdminDashboard.tsx**

Add this helper at the top of `AdminDashboard.tsx` (after imports):

```typescript
/** Parse backend timestamps (stored without 'Z' suffix) as UTC */
const parseUTC = (ts: string | null): Date | null => {
    if (!ts) return null;
    if (!ts.endsWith('Z') && !ts.includes('+')) return new Date(ts + 'Z');
    return new Date(ts);
};
```

Then replace all `new Date(someTimestamp)` with `parseUTC(someTimestamp)` throughout the file. Search for:
- `new Date(user.created_at)` -> `parseUTC(user.created_at)`
- `new Date(report.timestamp)` -> `parseUTC(report.timestamp)`
- `new Date(entry.created_at)` -> `parseUTC(entry.created_at)`

Handle null: `parseUTC(ts)?.toLocaleDateString() ?? 'N/A'`

**Step 3: Add onError to all mutations in admin-hooks.ts**

Add import at top of `apps/frontend/src/lib/api/admin-hooks.ts`:
```typescript
import { toast } from 'sonner';
```

Then add `onError` to every `useMutation` call. Example pattern:

```typescript
export function useAdminBanUser() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (args: { userId: string; reason: string }) =>
            adminFetch(`/users/${args.userId}/ban`, {
                method: 'PATCH',
                body: JSON.stringify({ reason: args.reason }),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['admin', 'users'] });
            toast.success('User banned successfully');
        },
        onError: (err: Error) => {
            toast.error(err.message || 'Failed to ban user');
        },
    });
}
```

Apply the same `onError` pattern to ALL mutations:
- `useAdminBanUser`
- `useAdminUnbanUser`
- `useAdminDeleteUser`
- `useAdminUpdateRole`
- `useAdminVerifyReport`
- `useAdminArchiveReport`
- `useAdminDeleteReport`
- `useAdminCreateBadge`
- `useAdminUpdateBadge`
- `useAdminAwardBadge`
- `useAdminPromoteAmbassador`

**Step 4: Remove driver.js from package.json**

In `apps/frontend/package.json`, remove the line:
```
        "driver.js": "^1.4.0",
```

Then run:
```bash
cd apps/frontend && npm install
```

**Step 5: Verify build**

```bash
cd apps/frontend && npx tsc --noEmit && npm run build
```

Expected: No errors.

**Step 6: Commit**

```bash
cd apps/frontend
git add src/main.tsx src/components/screens/AdminDashboard.tsx src/components/screens/AdminLoginScreen.tsx src/lib/api/admin-hooks.ts package.json package-lock.json
git commit -m "fix(admin-frontend): lazy CSS, UTC timestamps, onError handlers, remove driver.js"
```

---

### Task 10: Frontend — Admin Create Report Form

**Files:**
- Modify: `apps/frontend/src/components/screens/AdminDashboard.tsx`
- Modify: `apps/frontend/src/lib/api/admin-hooks.ts`

**Step 1: Add hook in admin-hooks.ts**

```typescript
export interface AdminCreateReportRequest {
    description: string;
    latitude: number;
    longitude: number;
    city: string;
    water_depth?: string;
    vehicle_passability?: string;
    source: string;
    admin_notes?: string;
}

export function useAdminCreateReport() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (data: AdminCreateReportRequest) =>
            adminFetch('/reports', {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['admin', 'reports'] });
            toast.success('Report created successfully');
        },
        onError: (err: Error) => {
            toast.error(err.message || 'Failed to create report');
        },
    });
}
```

**Step 2: Add Create Report form to AdminDashboard.tsx**

In the Reports panel section of `AdminDashboard.tsx`, add a "Create Report" button that toggles a form. The form should include:

```typescript
const [showCreateReport, setShowCreateReport] = useState(false);
const [newReport, setNewReport] = useState<AdminCreateReportRequest>({
    description: '',
    latitude: 0,
    longitude: 0,
    city: 'delhi',
    source: 'field_observation',
});
const createReportMutation = useAdminCreateReport();
```

Form JSX (inside the reports panel, before the reports list):

```tsx
{showCreateReport && (
    <div className="admin-card" style={{ marginBottom: '1rem' }}>
        <h4>Create Official Report</h4>
        <div style={{ display: 'grid', gap: '0.75rem' }}>
            <textarea
                className="admin-input"
                placeholder="Description (10-500 chars)"
                value={newReport.description}
                onChange={e => setNewReport(p => ({ ...p, description: e.target.value }))}
                rows={3}
            />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem' }}>
                <select
                    className="admin-input"
                    value={newReport.city}
                    onChange={e => setNewReport(p => ({ ...p, city: e.target.value }))}
                >
                    <option value="delhi">Delhi</option>
                    <option value="bangalore">Bangalore</option>
                    <option value="yogyakarta">Yogyakarta</option>
                    <option value="singapore">Singapore</option>
                    <option value="indore">Indore</option>
                </select>
                <input
                    className="admin-input"
                    type="number"
                    step="0.0001"
                    placeholder="Latitude"
                    value={newReport.latitude || ''}
                    onChange={e => setNewReport(p => ({ ...p, latitude: parseFloat(e.target.value) || 0 }))}
                />
                <input
                    className="admin-input"
                    type="number"
                    step="0.0001"
                    placeholder="Longitude"
                    value={newReport.longitude || ''}
                    onChange={e => setNewReport(p => ({ ...p, longitude: parseFloat(e.target.value) || 0 }))}
                />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem' }}>
                <select
                    className="admin-input"
                    value={newReport.source}
                    onChange={e => setNewReport(p => ({ ...p, source: e.target.value }))}
                >
                    <option value="field_observation">Field Observation</option>
                    <option value="government_data">Government Data</option>
                    <option value="phone_report">Phone Report</option>
                </select>
                <select
                    className="admin-input"
                    value={newReport.water_depth || ''}
                    onChange={e => setNewReport(p => ({ ...p, water_depth: e.target.value || undefined }))}
                >
                    <option value="">Water Depth (optional)</option>
                    <option value="ankle">Ankle</option>
                    <option value="knee">Knee</option>
                    <option value="waist">Waist</option>
                    <option value="chest">Chest</option>
                </select>
                <select
                    className="admin-input"
                    value={newReport.vehicle_passability || ''}
                    onChange={e => setNewReport(p => ({ ...p, vehicle_passability: e.target.value || undefined }))}
                >
                    <option value="">Passability (optional)</option>
                    <option value="all">All Vehicles</option>
                    <option value="large_vehicles">Large Only</option>
                    <option value="none">None</option>
                </select>
            </div>
            <textarea
                className="admin-input"
                placeholder="Admin notes (optional)"
                value={newReport.admin_notes || ''}
                onChange={e => setNewReport(p => ({ ...p, admin_notes: e.target.value || undefined }))}
                rows={2}
            />
            <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                    className="admin-btn admin-btn-primary"
                    disabled={createReportMutation.isPending || newReport.description.length < 10}
                    onClick={() => createReportMutation.mutate(newReport, {
                        onSuccess: () => setShowCreateReport(false),
                    })}
                >
                    {createReportMutation.isPending ? 'Creating...' : 'Create Report'}
                </button>
                <button
                    className="admin-btn"
                    onClick={() => setShowCreateReport(false)}
                >
                    Cancel
                </button>
            </div>
        </div>
    </div>
)}
```

**Step 3: Verify build**

```bash
cd apps/frontend && npx tsc --noEmit && npm run build
```

**Step 4: Commit**

```bash
git add src/components/screens/AdminDashboard.tsx src/lib/api/admin-hooks.ts
git commit -m "feat(admin): add create report form — no photo, city-validated, auto-verified"
```

---

### Task 11: Frontend — Official Report Badge + Admin Notes in ReportCard

**Files:**
- Modify: `apps/frontend/src/components/ReportCard.tsx`

**Step 1: Add admin_created and source to report type**

Find the Report interface/type in the frontend (likely in `types.ts` or inline in hooks). Add:

```typescript
admin_created?: boolean;
source?: string;
```

**Step 2: Modify ReportCard verified badge section**

In `apps/frontend/src/components/ReportCard.tsx`, find the verified badge rendering (around line 142-160). Wrap it with an admin_created check:

```tsx
{report.admin_created ? (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">
        <Shield className="w-3.5 h-3.5" />
        Official Report
        {report.source && (
            <span className="text-blue-500 ml-1">
                ({report.source === 'field_observation' ? 'Field' :
                  report.source === 'government_data' ? 'Govt' : 'Phone'})
            </span>
        )}
    </span>
) : report.verified ? (
    // ... existing verified badge (green CheckCircle)
) : (
    // ... existing unverified badge (yellow AlertTriangle)
)}
```

Add `Shield` to the lucide-react import at top of file:
```typescript
import { Shield, CheckCircle, AlertTriangle, /* ... existing imports */ } from 'lucide-react';
```

**Step 3: Add admin notes display**

After the existing comment section in ReportCard, add rendering for admin verification notes. The existing `useComments` hook returns all comments — filter by type:

```tsx
{/* Admin verification notes — render distinctly */}
{comments?.filter((c: any) => c.comment_type === 'admin_verification' || c.comment_type === 'admin_rejection').map((note: any) => (
    <div
        key={note.id}
        className={`mt-2 p-2 rounded-lg text-sm border-l-4 ${
            note.comment_type === 'admin_verification'
                ? 'border-green-500 bg-green-50 text-green-800'
                : 'border-amber-500 bg-amber-50 text-amber-800'
        }`}
    >
        <span className="font-medium">FloodSafe Team:</span> {note.content}
    </div>
))}
```

**Note**: This requires that the comments API returns `comment_type` in its response. Check `apps/backend/src/api/comments.py` — the `CommentResponse` schema may need `comment_type: str` added.

**Step 4: Verify build**

```bash
cd apps/frontend && npx tsc --noEmit && npm run build
```

**Step 5: Commit**

```bash
git add src/components/ReportCard.tsx
git commit -m "feat(ui): Official Report badge + admin verification notes in ReportCard"
```

---

### Task 12: Frontend — Verification Queue in Admin Dashboard

**Files:**
- Modify: `apps/frontend/src/components/screens/AdminDashboard.tsx`
- Modify: `apps/frontend/src/lib/api/admin-hooks.ts`

**Step 1: Add verify/reject hooks**

In `admin-hooks.ts`, add:

```typescript
export function useAdminVerifyReportWithNotes() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (args: { reportId: string; verified: boolean; quality_score: number; notes?: string }) =>
            adminFetch(`/reports/${args.reportId}/verify`, {
                method: 'PATCH',
                body: JSON.stringify({
                    verified: args.verified,
                    quality_score: args.quality_score,
                    notes: args.notes,
                }),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['admin', 'reports'] });
            toast.success('Report verification updated');
        },
        onError: (err: Error) => {
            toast.error(err.message || 'Failed to update verification');
        },
    });
}
```

**Note**: This calls the main `/api/reports/{id}/verify` endpoint (not the admin-prefixed one). The admin-hooks `adminFetch` adds admin prefix by default, so this hook needs to use the base `fetch` or a separate non-prefixed call. Adjust `adminFetch` or create a specific function:

```typescript
async function apiBaseFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const token = getAdminToken();
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            ...options?.headers,
        },
    });
    // ... same error handling as adminFetch
}
```

Then use: `apiBaseFetch(`/reports/${args.reportId}/verify`, ...)`

**Step 2: Add filter tabs to Reports panel**

In the reports section of `AdminDashboard.tsx`, add tab state:

```typescript
const [reportFilter, setReportFilter] = useState<'pending' | 'verified' | 'rejected' | 'all'>('pending');
```

Map filter to API query param:
```typescript
const reportStatus = reportFilter === 'pending' ? 'unverified'
    : reportFilter === 'verified' ? 'verified'
    : reportFilter === 'rejected' ? 'archived'  // approximate — rejected filter needs backend support
    : undefined;
```

Add tab buttons above the reports list:

```tsx
<div className="admin-tabs" style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
    {(['pending', 'verified', 'rejected', 'all'] as const).map(tab => (
        <button
            key={tab}
            className={`admin-btn ${reportFilter === tab ? 'admin-btn-primary' : ''}`}
            onClick={() => setReportFilter(tab)}
        >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
        </button>
    ))}
</div>
```

**Step 3: Add verify/reject action buttons per report**

Replace the existing `prompt()`/`confirm()` patterns for verify/reject with proper inline forms:

```tsx
{/* Verify button with quality score + notes */}
<button
    className="admin-btn admin-btn-primary"
    onClick={() => {
        const quality = prompt('Quality score (0-100):', '75');
        const notes = prompt('Verification notes (optional):');
        if (quality !== null) {
            verifyMutation.mutate({
                reportId: report.id,
                verified: true,
                quality_score: parseInt(quality) || 75,
                notes: notes || undefined,
            });
        }
    }}
>
    Verify
</button>
<button
    className="admin-btn"
    style={{ background: '#ef4444', color: 'white' }}
    onClick={() => {
        const reason = prompt('Rejection reason (required):');
        if (reason && reason.length >= 5) {
            verifyMutation.mutate({
                reportId: report.id,
                verified: false,
                quality_score: 0,
                notes: reason,
            });
        }
    }}
>
    Reject
</button>
```

**Note**: Using `prompt()` for now (deferred: replace with Radix modals in future PR per design doc section 6).

**Step 4: Verify build**

```bash
cd apps/frontend && npx tsc --noEmit && npm run build
```

**Step 5: Commit**

```bash
git add src/components/screens/AdminDashboard.tsx src/lib/api/admin-hooks.ts
git commit -m "feat(admin): verification queue with filter tabs, verify/reject with notes"
```

---

### Task 13: Final Verification

**Step 1: Run all backend tests**

```bash
cd apps/backend && python -m pytest tests/ -v
```

Expected: All pass.

**Step 2: Run frontend type check + build**

```bash
cd apps/frontend && npx tsc --noEmit && npm run build
```

Expected: No errors.

**Step 3: Verify no new `any` types**

```bash
cd apps/frontend && grep -rn ": any\|as any" src/components/screens/AdminDashboard.tsx src/lib/api/admin-hooks.ts src/components/ReportCard.tsx | head -20
```

Expected: Minimal or zero `any` usage.

**Step 4: Check for console warnings**

Start dev server and visit `/admin`:
```bash
cd apps/frontend && npm run dev
```
Open browser at `http://localhost:5175/admin` — check console for warnings.

**Step 5: Verify admin.css is NOT loaded on main pages**

Visit `http://localhost:5175/` — check Network tab, confirm `admin.css` is NOT fetched.
Visit `http://localhost:5175/admin` — confirm `admin.css` IS loaded.

**Step 6: Final commit if any cleanup needed**

```bash
git add -A && git commit -m "chore: final cleanup for admin panel PR"
```
