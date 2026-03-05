# Multi-Admin Invite Codes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable multiple admins via invite codes, replace single-env-var auth with DB-based multi-admin login.

**Architecture:** New `AdminInvite` model + 4 endpoints (CRUD invites + register). Login refactored to two-tier (DB-first, env-var fallback). Frontend: register screen, invite management in System tab, admin link in ProfileScreen.

**Tech Stack:** FastAPI, SQLAlchemy, bcrypt, React, TanStack Query, Lucide icons.

**Design doc:** `docs/plans/2026-03-05-multi-admin-invites-design.md`

---

### Task 1: AdminInvite Model

**Files:**
- Modify: `apps/backend/src/infrastructure/models.py` (after line 633, after AdminAuditLog)
- Modify: `apps/backend/src/api/admin.py:16` (add AdminInvite to import)

**Step 1: Add AdminInvite model**

Insert after `AdminAuditLog` class (line 633) in `models.py`:

```python
class AdminInvite(Base):
    """Invite codes for multi-admin onboarding."""
    __tablename__ = "admin_invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(64), unique=True, nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    email_hint = Column(String(255), nullable=True)
    used_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Step 2: Add import in admin.py**

Update line 16 of `admin.py`:
```python
from src.infrastructure.models import User, Badge, AdminInvite
```

**Step 3: Commit**

```bash
git add apps/backend/src/infrastructure/models.py apps/backend/src/api/admin.py
git commit -m "feat(models): add AdminInvite model for multi-admin invite codes"
```

---

### Task 2: Alembic Migration

**Files:**
- Create: `apps/backend/alembic/versions/b2c3d4e5f6a7_add_admin_invites_table.py`

**Step 1: Create migration file**

```python
"""Add admin_invites table for multi-admin support.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'admin_invites',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('email_hint', sa.String(255), nullable=True),
        sa.Column('used_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('admin_invites')
```

**Step 2: Commit**

```bash
git add apps/backend/alembic/versions/b2c3d4e5f6a7_add_admin_invites_table.py
git commit -m "migration: add admin_invites table"
```

---

### Task 3: Two-Tier Login Refactor

**Files:**
- Modify: `apps/backend/src/api/admin.py:113-174` (admin_login function)

**Step 1: Rewrite admin_login to two-tier auth**

Replace the `admin_login` function (lines 113-174) with:

```python
@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest, req: Request, db: Session = Depends(get_db)):
    """
    Admin login with two-tier auth:
    1. DB-based: user.role == 'admin' + user.password_hash
    2. Env-var fallback: ADMIN_EMAIL + ADMIN_PASSWORD_HASH (bootstrap)
    """
    from src.api.deps import check_rate_limit

    check_rate_limit(f"admin_login:{req.client.host}", max_requests=5, window_seconds=300)

    admin_user = None

    # Tier 1: DB-based admin auth
    user = db.query(User).filter(User.email == request.email).first()
    if user and user.role == "admin" and user.password_hash:
        if verify_password(request.password, user.password_hash):
            admin_user = user

    # Tier 2: Env-var fallback (bootstrap / recovery)
    if not admin_user:
        if (settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD_HASH
                and request.email == settings.ADMIN_EMAIL
                and verify_password(request.password, settings.ADMIN_PASSWORD_HASH)):
            admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
            if admin_user and admin_user.role != "admin":
                admin_user.role = "admin"
                db.commit()

    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )

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

**Step 2: Verify existing login still works**

Run: `cd apps/backend && python -m pytest tests/test_admin.py -v -k login 2>&1 | tail -20`

**Step 3: Commit**

```bash
git add apps/backend/src/api/admin.py
git commit -m "feat(admin): two-tier login — DB-based auth with env-var fallback"
```

---

### Task 4: Invite CRUD Endpoints

**Files:**
- Modify: `apps/backend/src/api/admin.py` (add after audit-log endpoint, before EOF)

**Step 1: Add Pydantic models for invites**

Add after `AdminCreateReportRequest` (line 107):

```python
class CreateInviteRequest(BaseModel):
    """Request to create an admin invite."""
    email_hint: Optional[str] = Field(None, description="Restrict invite to this email")


class CreateInviteResponse(BaseModel):
    """Response with generated invite link."""
    code: str
    invite_url: str
    email_hint: Optional[str]
    expires_at: str


class InviteListItem(BaseModel):
    """Invite item for listing."""
    id: str
    code: str
    email_hint: Optional[str]
    created_by_username: str
    used_by_username: Optional[str]
    expires_at: str
    created_at: str
    is_expired: bool
    is_used: bool
```

**Step 2: Add invite endpoints**

Add after the audit-log endpoint (after line 514):

```python
# =============================================================================
# ADMIN INVITES
# =============================================================================

@router.post("/invites", response_model=CreateInviteResponse)
async def create_invite(
    request: CreateInviteRequest,
    req: Request,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Generate a one-time admin invite code (48h expiry)."""
    import secrets
    from datetime import timedelta

    code = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=48)

    invite = AdminInvite(
        code=code,
        created_by=admin.id,
        email_hint=request.email_hint,
        expires_at=expires_at,
    )
    db.add(invite)

    admin_service.log_admin_action(
        db, admin.id, admin.username, "create_invite",
        target_type="invite", target_id=code,
        details=json.dumps({"email_hint": request.email_hint}),
        ip_address=req.client.host if req.client else None,
    )
    db.commit()

    frontend_url = settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else "https://floodsafe.live"
    invite_url = f"{frontend_url}/admin/register?code={code}"

    return CreateInviteResponse(
        code=code,
        invite_url=invite_url,
        email_hint=request.email_hint,
        expires_at=expires_at.isoformat(),
    )


@router.get("/invites")
async def list_invites(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """List all admin invites (active and used)."""
    invites = db.query(AdminInvite).order_by(AdminInvite.created_at.desc()).all()

    result = []
    for inv in invites:
        creator = db.query(User).filter(User.id == inv.created_by).first() if inv.created_by else None
        redeemer = db.query(User).filter(User.id == inv.used_by).first() if inv.used_by else None
        result.append({
            "id": str(inv.id),
            "code": inv.code,
            "email_hint": inv.email_hint,
            "created_by_username": creator.username if creator else "unknown",
            "used_by_username": redeemer.username if redeemer else None,
            "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
            "is_expired": inv.expires_at < datetime.utcnow() if inv.expires_at else True,
            "is_used": inv.used_by is not None,
        })

    return result


@router.delete("/invites/{code}")
async def revoke_invite(
    code: str,
    req: Request,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Revoke an unused invite code."""
    invite = db.query(AdminInvite).filter(AdminInvite.code == code).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.used_by:
        raise HTTPException(status_code=400, detail="Cannot revoke — invite already used")

    db.delete(invite)
    admin_service.log_admin_action(
        db, admin.id, admin.username, "revoke_invite",
        target_type="invite", target_id=code,
        ip_address=req.client.host if req.client else None,
    )
    db.commit()

    return {"status": "revoked"}
```

**Step 3: Commit**

```bash
git add apps/backend/src/api/admin.py
git commit -m "feat(admin): invite CRUD — create, list, revoke invite codes"
```

---

### Task 5: Register Endpoint (Public, Code-Gated)

**Files:**
- Modify: `apps/backend/src/api/admin.py` (add after invite endpoints)

**Step 1: Add register Pydantic model**

Add with other models (after `InviteListItem`):

```python
class AdminRegisterRequest(BaseModel):
    """Request to register as admin via invite code."""
    code: str = Field(..., min_length=10)
    email: str = Field(..., description="Must match existing FloodSafe account")
    password: str = Field(..., min_length=8, max_length=128)
```

**Step 2: Add register endpoint**

Add after revoke_invite:

```python
@router.post("/register")
async def register_admin(
    request: AdminRegisterRequest,
    req: Request,
    db: Session = Depends(get_db),
):
    """
    Redeem an invite code to become an admin.
    Public endpoint — no auth required, but needs valid invite code.
    Rate limited: 5 attempts per 5 min per IP.
    """
    from src.api.deps import check_rate_limit

    check_rate_limit(f"admin_register:{req.client.host}", max_requests=5, window_seconds=300)

    # Validate invite code
    invite = db.query(AdminInvite).filter(AdminInvite.code == request.code).first()
    if not invite or invite.used_by is not None:
        raise HTTPException(status_code=400, detail="Invalid or already-used invite code")
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite code has expired")

    # Check email hint restriction
    if invite.email_hint and invite.email_hint.lower() != request.email.lower():
        raise HTTPException(status_code=400, detail="This invite is restricted to a different email")

    # Find existing user
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=400,
            detail="No FloodSafe account found with this email. Please sign up first.",
        )

    # Set admin role + password
    user.role = "admin"
    user.password_hash = hash_password(request.password)

    # Mark invite as used
    invite.used_by = user.id

    admin_service.log_admin_action(
        db, user.id, user.username, "admin_registered",
        target_type="invite", target_id=invite.code,
        details=json.dumps({"email": request.email}),
        ip_address=req.client.host if req.client else None,
    )
    db.commit()

    return {"status": "ok", "message": "Admin access granted. You can now log in at /admin/login."}
```

**Step 3: Add `from datetime import datetime` if missing**

Check top of admin.py — `datetime` is used but may not be imported. Add if needed:
```python
from datetime import datetime
```

**Step 4: Commit**

```bash
git add apps/backend/src/api/admin.py
git commit -m "feat(admin): register endpoint — redeem invite to become admin"
```

---

### Task 6: Frontend — Admin Hooks for Invites

**Files:**
- Modify: `apps/frontend/src/lib/api/admin-hooks.ts` (add types + hooks at end)

**Step 1: Add invite types**

Add after `AnalyticsData` interface (line 197):

```typescript
export interface AdminInvite {
    id: string;
    code: string;
    email_hint: string | null;
    created_by_username: string;
    used_by_username: string | null;
    expires_at: string;
    created_at: string;
    is_expired: boolean;
    is_used: boolean;
}

export interface CreateInviteResponse {
    code: string;
    invite_url: string;
    email_hint: string | null;
    expires_at: string;
}
```

**Step 2: Add invite hooks**

Add after `useAdminAuditLog` (after line 547):

```typescript
// ============================================================================
// INVITES
// ============================================================================

export function useAdminInvites() {
    return useQuery<AdminInvite[]>({
        queryKey: ['admin', 'invites'],
        queryFn: () => adminFetch('/invites'),
        staleTime: 15_000,
        enabled: isAdminAuthenticated(),
    });
}

export function useAdminCreateInvite() {
    const qc = useQueryClient();
    return useMutation<CreateInviteResponse, Error, { email_hint?: string }>({
        mutationFn: (data) =>
            adminFetch('/invites', {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['admin', 'invites'] });
            toast.success('Invite created');
        },
        onError: (err) => { toast.error(err.message || 'Failed to create invite'); },
    });
}

export function useAdminRevokeInvite() {
    const qc = useQueryClient();
    return useMutation<unknown, Error, string>({
        mutationFn: (code) =>
            adminFetch(`/invites/${code}`, { method: 'DELETE' }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['admin', 'invites'] });
            toast.success('Invite revoked');
        },
        onError: (err) => { toast.error(err.message || 'Failed to revoke invite'); },
    });
}

export function useAdminRegister() {
    return useMutation({
        mutationFn: async (data: { code: string; email: string; password: string }) => {
            const response = await fetch(`${API_BASE_URL}/admin/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({ detail: 'Registration failed' }));
                throw new Error(err.detail || 'Registration failed');
            }
            return response.json();
        },
    });
}
```

**Step 3: Commit**

```bash
git add apps/frontend/src/lib/api/admin-hooks.ts
git commit -m "feat(admin): frontend hooks for invite CRUD + register"
```

---

### Task 7: Frontend — AdminRegisterScreen

**Files:**
- Create: `apps/frontend/src/components/screens/AdminRegisterScreen.tsx`
- Modify: `apps/frontend/src/App.tsx` (add route + lazy import)

**Step 1: Create AdminRegisterScreen**

New file — same styling as AdminLoginScreen (uses admin.css classes). Shows:
- "You've been invited" header
- Email input (must match existing account)
- Password + confirm password inputs
- Info note: "This also sets a password for your FloodSafe account"
- Submit → calls `useAdminRegister` → redirects to `/admin/login`
- Error states for invalid/expired/used codes

**Step 2: Add route in App.tsx**

Add lazy import (after line 42):
```typescript
const AdminRegisterScreen = lazy(() => import('./components/screens/AdminRegisterScreen').then(m => ({ default: m.AdminRegisterScreen })));
```

Add route (after line 386, after `/admin/login` route):
```tsx
<Route path="/admin/register" element={
    <Suspense fallback={
        <div className="min-h-screen flex items-center justify-center" style={{ background: '#0f172a' }}>
            <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
        </div>
    }>
        <AdminRegisterScreen />
    </Suspense>
} />
```

**Step 3: Commit**

```bash
git add apps/frontend/src/components/screens/AdminRegisterScreen.tsx apps/frontend/src/App.tsx
git commit -m "feat(admin): register screen for invite code redemption"
```

---

### Task 8: Frontend — Invite Management in SystemPanel

**Files:**
- Modify: `apps/frontend/src/components/screens/AdminDashboard.tsx` (SystemPanel function, line 873)

**Step 1: Add invite imports**

Update imports at top of AdminDashboard.tsx (line 18-29) to add:
```typescript
useAdminInvites, useAdminCreateInvite, useAdminRevokeInvite,
type AdminInvite as AdminInviteType,
```

Also add `Link2, Copy, UserPlus2` to lucide-react imports if not present.

**Step 2: Add invite management section to SystemPanel**

Insert after the Health Check card (after line 908, before the Audit Log card):

- "Admin Invites" card with:
  - "Create Invite" button (optional email hint input)
  - Table: Code (truncated), Email Hint, Created By, Status (Active/Used/Expired), Expires, Actions
  - Copy invite link button
  - Revoke button for active unused invites
  - Visual indicators: green=active, gray=used, red=expired

**Step 3: Commit**

```bash
git add apps/frontend/src/components/screens/AdminDashboard.tsx
git commit -m "feat(admin): invite management UI in System tab"
```

---

### Task 9: Frontend — Admin Link in ProfileScreen

**Files:**
- Modify: `apps/frontend/src/components/screens/ProfileScreen.tsx`

**Step 1: Add admin panel link**

Find the section near line 235 where the admin role badge is shown. Add after the user info section (around line 244), conditionally rendered:

```tsx
{user.role === "admin" && (
    <a
        href="/admin"
        className="flex items-center gap-2 px-3 py-2 mt-3 rounded-lg bg-purple-50 text-purple-700 text-sm font-medium hover:bg-purple-100 transition-colors"
    >
        <ShieldCheck className="w-4 h-4" />
        Admin Panel
    </a>
)}
```

This shows an "Admin Panel" link with the purple Shield icon, only visible to admin-role users.

**Step 2: Verify build**

Run: `cd apps/frontend && npx tsc --noEmit && npm run build`

**Step 3: Commit**

```bash
git add apps/frontend/src/components/screens/ProfileScreen.tsx
git commit -m "feat(profile): admin panel link visible to admin-role users"
```

---

### Task 10: Deploy Migration + Backend + Frontend

**Step 1: Apply migration to production DB**

Either:
- (a) Use temporary migration endpoint pattern (proven earlier today), or
- (b) Run via Supabase Management API if PAT is valid

The SQL is simple:
```sql
CREATE TABLE IF NOT EXISTS admin_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) UNIQUE NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    email_hint VARCHAR(255),
    used_by UUID REFERENCES users(id) ON DELETE SET NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_admin_invites_code ON admin_invites(code);
```

**Step 2: Push + deploy backend**

```bash
git push origin master
./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend
```

**Step 3: Deploy frontend**

```bash
cd apps/frontend && npx vercel --prod
```

**Step 4: Verify**

- Login at `/admin/login` with existing credentials (env var fallback)
- System tab → generate invite
- Open invite link in incognito → register form works
- Log in as new admin → dashboard loads
- Check ProfileScreen shows admin link

---

### Task Summary

| Task | Description | Files |
|------|------------|-------|
| 1 | AdminInvite model | models.py, admin.py import |
| 2 | Alembic migration | new migration file |
| 3 | Two-tier login refactor | admin.py login endpoint |
| 4 | Invite CRUD endpoints | admin.py (3 endpoints) |
| 5 | Register endpoint | admin.py (public, code-gated) |
| 6 | Frontend hooks | admin-hooks.ts |
| 7 | AdminRegisterScreen | new screen + App.tsx route |
| 8 | Invite management UI | AdminDashboard.tsx SystemPanel |
| 9 | Admin link in profile | ProfileScreen.tsx |
| 10 | Deploy + verify | migration, Koyeb, Vercel |
