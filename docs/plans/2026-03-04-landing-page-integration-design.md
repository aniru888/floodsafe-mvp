# Landing Page Integration Design

> **Date**: 2026-03-04
> **Status**: Approved
> **Source**: [FloodSade-LandingPage](https://github.com/chaterinaolivia/FloodSade-LandingPage)

## Summary

Integrate an external landing page (React + Tailwind + Framer Motion + GSAP) into FloodSafe as the public entry point. The app transitions from a single-route architecture (everything at `/`) to a multi-route structure using React Router properly.

## Routing Architecture

### New URL Structure

```
/                  -> LandingPage (public, lazy-loaded)
/login             -> LoginPage (public, wraps existing LoginScreen)
/app               -> FloodSafeApp (auth-gated, tab navigation inside)
/email-verified    -> EmailVerifiedScreen (public, existing - unchanged path)
*                  -> Redirect to /
```

### Key Design Decisions

1. **Tab-based navigation inside `/app` is UNCHANGED.** The internal `setActiveTab('home' | 'map' | 'report' | ...)` system stays. Only the outer shell gets routes.
2. **Context providers wrap everything** (auth state needed on landing page for "Go to Dashboard" button).
3. **`LandingPage` is lazy-loaded** to avoid bloating the authenticated app bundle.
4. **Authenticated users see the landing page** with "Go to Dashboard" instead of "Sign In / Register".

### Route Changes in App.tsx

```tsx
// Before (lines 348-358)
<Route path="/email-verified" element={<EmailVerifiedScreen />} />
<Route path="*" element={<FloodSafeApp />} />

// After
<Route path="/" element={<Suspense fallback={<LoadingSpinner />}><LandingPage /></Suspense>} />
<Route path="/login" element={<LoginPage />} />
<Route path="/email-verified" element={<EmailVerifiedScreen />} />
<Route path="/app" element={<FloodSafeApp />} />
<Route path="*" element={<Navigate to="/" replace />} />
```

## Landing Page Components

### New Files

```
apps/frontend/src/components/screens/LandingPage.tsx       (root component)
apps/frontend/src/components/landing/                      (sub-components)
  +-- Navbar.tsx           (PillNav with auth-aware buttons)
  +-- PillNav.tsx          (animated pill navigation)
  +-- Hero.tsx             (hero section with CTA buttons)
  +-- Features.tsx         (bento grid feature cards)
  +-- HowItWorks.tsx       (process explanation)
  +-- Mission.tsx          (mission statement)
  +-- SupportedBy.tsx      (supporters section)
  +-- TechStack.tsx        (technology stack)
  +-- CTA.tsx              (call-to-action section)
  +-- Footer.tsx           (page footer)
  +-- Preloader.tsx        (3-second loading animation)
  +-- DotGrid.tsx          (interactive dot grid background)
  +-- ScrollVelocity.tsx   (scroll velocity effect)
  +-- TextType.tsx         (typewriter text animation)
```

### Porting Strategy

- **React 19 -> 18**: Minimal changes (mostly type imports)
- **Tailwind v3 -> v4**: Most utilities identical. Custom values via arbitrary syntax or `@theme` in CSS. Custom keyframe animations defined in `index.css`.
- **New dependencies**: `framer-motion` (~30KB gz), `gsap` (~23KB gz)

### Button Wiring

| Button | Location | Action |
|--------|----------|--------|
| Sign In | Navbar | `navigate('/login')` |
| Register | Navbar | `navigate('/login?mode=register')` |
| Go to Dashboard | Navbar (auth'd) | `navigate('/app')` |
| View Live Risk Map | Hero | `navigate('/login')` |
| Get Alerts on WhatsApp | Hero | `window.open('https://wa.me/...')` |
| Join With Us | CTA section | `navigate('/login')` |
| GitHub | CTA section | `window.open(github_url)` |

## Silent Failure Audit & Required Fixes

### Audit Methodology

Three parallel deep dives were conducted:
1. Onboarding flow end-to-end (onboarding wizard, bot tour, localStorage flags)
2. Map/navigation features (GPS, location tracking, map state, sharing)
3. Auth persistence & token flow (tokens, refresh, OAuth, session management)

### What's Safe (No Changes Needed)

- Auth core: token storage, refresh, logout, Firebase, Google OAuth (all route-agnostic)
- Map/GPS/navigation: uses `navigator.geolocation`, not URL (route-agnostic)
- Onboarding bot: uses `registerNavigation(setActiveTab)` callback inside FloodSafeApp (tab-based)
- All API calls: use `API_BASE_URL` from env var (route-agnostic)
- All localStorage flags: path-independent
- Service worker scope: `scope: '/'` covers all sub-paths
- Backend: zero changes needed

### 8 Surgical Fixes (Required)

#### Fix 1: Invite URL Generation (CRITICAL - silent failure)

```
File: apps/frontend/src/components/circles/InviteLinkShare.tsx:14
Before: const inviteUrl = `${window.location.origin}?join=${inviteCode}`;
After:  const inviteUrl = `${window.location.origin}/app?join=${inviteCode}`;
```

**Why**: Without this, shared invite links go to the landing page which has no invite handling. The invite code is silently lost.

#### Fix 2: Landing Page Deep Link Forwarding (CRITICAL - silent failure)

```
File: apps/frontend/src/components/screens/LandingPage.tsx (NEW)
Add useEffect that captures ?join= query param, stores in sessionStorage, redirects to /login
```

**Why**: Old invite links (or direct visits to `/?join=CODE`) must be forwarded. Landing page acts as a safety net.

#### Fix 3: PWA Start URL (CRITICAL - silent failure)

```
File: apps/frontend/vite.config.ts:21
Before: start_url: '/'
After:  start_url: '/app'
```

**Why**: PWA homescreen icon must open the app, not the landing page. Existing installs will update on next SW refresh.

#### Fix 4: Email Verified Redirect (MEDIUM - wrong page)

```
File: apps/frontend/src/components/screens/EmailVerifiedScreen.tsx:47,58
Before: navigate('/', { replace: true })
After:  navigate('/app', { replace: true })
```

**Why**: After email verification, user should go to the app, not the landing page.

#### Fix 5: Post-Login Redirect (HIGH - back-button loop)

```
File: apps/frontend/src/components/screens/LoginPage.tsx (NEW wrapper)
Add: useEffect that navigates to /app with { replace: true } when isAuthenticated becomes true
```

**Why**: Without `replace: true`, browser back from `/app` goes to `/login`, which auto-redirects to `/app`, creating an infinite loop.

#### Fix 6: Post-Logout Redirect (HIGH - URL/content mismatch)

```
Files: apps/frontend/src/components/screens/ProfileScreen.tsx:803
       apps/frontend/src/components/Sidebar.tsx:87
Add: navigate('/login', { replace: true }) after logout()
```

**Why**: Without explicit redirect, user sees LoginScreen at `/app` URL. Back button returns to app without auth.

#### Fix 7: Onboarding Reload (NO CHANGE NEEDED)

```
File: apps/frontend/src/App.tsx:232
Keep: window.location.reload()
```

**Why**: Since FloodSafeApp renders at `/app`, the reload stays at `/app`. The `floodsafe_start_app_tour` localStorage flag is read on remount. No regression.

#### Fix 8: Vercel SPA Rewrites (CRITICAL - 404 on refresh)

```
File: apps/frontend/vercel.json (NEW or update existing)
Add: { "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }
```

**Why**: Without this, refreshing the browser at `/login` or `/app` returns a 404 from Vercel.

### Pre-existing Bugs Found (Optional Fix)

| Bug | File:Line | Issue |
|-----|-----------|-------|
| Alert share URL | `HomeScreen.tsx:376` | Hardcoded `https://floodsafe.app/alert/${id}` - wrong domain, no route handler |
| WhatsApp template URLs | Backend `message_templates.py:92,480` | References `floodsafe.app/help` - wrong domain |

## Auth Gate at /app

FloodSafeApp adds a redirect for unauthenticated access:

```tsx
function FloodSafeApp() {
    const { isAuthenticated, authLoading } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            navigate('/login', { replace: true });
        }
    }, [authLoading, isAuthenticated]);

    if (authLoading) return <LoadingSpinner />;
    if (!isAuthenticated) return null; // redirecting

    // ... rest of existing FloodSafeApp (unchanged)
}
```

## What Stays Unchanged

- Tab-based navigation inside `/app` (setActiveTab)
- All 13 context providers (same pyramid, same order)
- Auth core (tokens, refresh, Firebase, Google OAuth)
- Map/GPS/navigation features
- Onboarding 5-step wizard + bot tour
- All API calls
- All localStorage flags
- Service worker scope (keep `scope: '/'`)
- Backend (zero changes)

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Tailwind v3->v4 class incompatibility | Test each component, use v4 arbitrary syntax where needed |
| Bundle size increase (framer-motion + gsap) | Lazy-load landing page, only loads at `/` |
| Existing PWA installs open to `/` | Change start_url to `/app`, browser updates manifest periodically |
| Old invite links with `/?join=` format | Landing page captures and forwards (Fix 2) |

## Testing Checklist

- [ ] New user: Landing -> Sign In -> Register -> Onboarding -> App
- [ ] Returning user: Landing -> Dashboard button -> App
- [ ] PWA install: Homescreen icon opens `/app`
- [ ] Email verification: Click email link -> `/email-verified` -> auto-redirect to `/app`
- [ ] Safety Circle invite: Share link -> recipient opens -> login -> join circle
- [ ] Old invite link format (`/?join=CODE`) -> forwarded to app
- [ ] Logout: Redirects to `/login`
- [ ] Browser back from `/app` -> does NOT loop through `/login`
- [ ] Page refresh at `/app` -> does NOT 404
- [ ] Page refresh at `/login` -> does NOT 404
- [ ] Onboarding complete -> app tour starts correctly
- [ ] Landing page: Preloader + DotGrid + all sections render
- [ ] Landing page: Mobile responsive
- [ ] `npx tsc --noEmit` passes
- [ ] `npm run build` passes
