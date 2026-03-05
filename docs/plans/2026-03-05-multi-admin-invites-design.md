# Multi-Admin Support with Invite Codes

> Date: 2026-03-05
> Status: Approved
> Scope: Backend + Frontend

## Problem

Single admin via env vars (ADMIN_EMAIL + ADMIN_PASSWORD_HASH). No way to add more admins without infrastructure access. No admin link in the main app.

## Design

### Database

New table `admin_invites`:

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| code | VARCHAR(64) | Unique, indexed. `secrets.token_urlsafe(32)` |
| created_by | UUID FK -> users | Admin who generated it |
| email_hint | VARCHAR (nullable) | If set, only this email can redeem |
| used_by | UUID FK -> users (nullable) | Set on redemption |
| expires_at | DateTime | created_at + 48h |
| created_at | DateTime | |

No changes to `users` table — reuses existing `password_hash` and `role` columns.

### Login Flow (two-tier)

```
1. Find user by email in DB
2. If user.role == "admin" AND user.password_hash exists -> verify against password_hash
3. Else if email == ADMIN_EMAIL env var -> verify against ADMIN_PASSWORD_HASH env var (bootstrap)
4. Else -> reject
```

Env var fallback stays permanently for bootstrap (first admin / recovery).

### Backend Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | /admin/invites | Admin | Generate invite code, return link |
| GET | /admin/invites | Admin | List active/used invites |
| DELETE | /admin/invites/{code} | Admin | Revoke unused invite |
| POST | /admin/register | Public (valid code) | Redeem invite: set role=admin + password_hash |

### Frontend

- **AdminRegisterScreen** (`/admin/register?code=XXX`): Email + password form, validates invite code
- **AdminDashboard System tab**: Invite management section (generate, list, revoke)
- **ProfileScreen**: "Admin Panel" link with Shield icon, visible only when `user.role === "admin"`

### Security

- Codes: `secrets.token_urlsafe(32)` (256-bit entropy)
- Single-use: `used_by` set on redemption, cannot reuse
- 48h expiry enforced on redemption
- Rate limit on register: 5/5min/IP
- Password minimum: 8 chars
- All actions audit-logged (create invite, redeem, revoke)

### Edge Cases

- **Google OAuth admin (no password_hash)**: Env var fallback handles login. Can also redeem self-invite to set password_hash.
- **Invited Google OAuth user**: Register endpoint sets password_hash. Note shown: "This also sets a password for your FloodSafe account."
- **Revoke admin access**: Use existing "Change Role" in Users tab (demote admin -> user)
- **Expired/used code**: Return clear error message, don't reveal which

### Migration

Add `admin_invites` table via Alembic migration with `server_default` where needed.
