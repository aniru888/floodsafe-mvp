# Landing Page Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate an external marketing landing page into FloodSafe as the public entry point at `/`, with the authenticated app at `/app` and login at `/login`.

**Architecture:** Route-based split using React Router. Landing page is lazy-loaded. Auth-gated FloodSafeApp keeps its internal tab-based navigation unchanged. 8 surgical fixes prevent silent failures identified in the design audit.

**Tech Stack:** React 18, React Router v7, Framer Motion, GSAP, Tailwind CSS v4

**Design doc:** `docs/plans/2026-03-04-landing-page-integration-design.md`

---

## Task 1: Install New Dependencies

**Files:**
- Modify: `apps/frontend/package.json`

**Step 1: Install framer-motion and gsap**

Run:
```bash
cd apps/frontend && npm install framer-motion gsap
```

Expected: Both packages added to `dependencies` in package.json.

**Step 2: Verify no peer dependency conflicts**

Run:
```bash
cd apps/frontend && npm ls --depth=0 2>&1 | grep -i "ERR\|WARN\|peer"
```

Expected: No ERR. Possible WARNs are OK.

**Step 3: Commit**

```bash
git add apps/frontend/package.json apps/frontend/package-lock.json
git commit -m "feat: add framer-motion and gsap dependencies for landing page"
```

---

## Task 2: Clone and Port Landing Page Assets

**Files:**
- Create: `apps/frontend/src/assets/landing/logo.png`
- Create: `apps/frontend/src/assets/landing/logo-meta.png`
- Create: `apps/frontend/src/assets/landing/logo-sl2.png`
- Create: `apps/frontend/src/assets/landing/logo-wa.png`
- Create: `apps/frontend/src/assets/landing/navigate.png`

**Step 1: Clone the external repo temporarily and copy assets**

```bash
cd /tmp && git clone https://github.com/chaterinaolivia/FloodSade-LandingPage.git landing-page-tmp
```

**Step 2: Copy assets to FloodSafe**

```bash
mkdir -p "apps/frontend/src/assets/landing"
cp /tmp/landing-page-tmp/floodsafe-landing/src/assets/logo.png apps/frontend/src/assets/landing/
cp /tmp/landing-page-tmp/floodsafe-landing/src/assets/logo-meta.png apps/frontend/src/assets/landing/
cp /tmp/landing-page-tmp/floodsafe-landing/src/assets/logo-sl2.png apps/frontend/src/assets/landing/
cp /tmp/landing-page-tmp/floodsafe-landing/src/assets/logo-wa.png apps/frontend/src/assets/landing/
cp /tmp/landing-page-tmp/floodsafe-landing/src/assets/navigate.png apps/frontend/src/assets/landing/
```

**Step 3: Commit**

```bash
git add apps/frontend/src/assets/landing/
git commit -m "feat: add landing page image assets"
```

---

## Task 3: Port UI Components (DotGrid, Preloader, TextType, ScrollVelocity)

**Files:**
- Create: `apps/frontend/src/components/landing/DotGrid.tsx`
- Create: `apps/frontend/src/components/landing/Preloader.tsx`
- Create: `apps/frontend/src/components/landing/TextType.tsx`
- Create: `apps/frontend/src/components/landing/ScrollVelocity.tsx`

**Step 1: Copy and port each UI component from the cloned repo**

For each file in `/tmp/landing-page-tmp/floodsafe-landing/src/components/ui/`:

1. Copy the file to `apps/frontend/src/components/landing/`
2. Update imports:
   - `from '../../utils/cn'` → `from '../../lib/utils'` (FloodSafe's existing `cn` utility)
   - Asset paths: `from '../../assets/...'` → `from '../../assets/landing/...'`
3. React 19 → 18 changes:
   - If using `React.use()` → replace with `useEffect`/`useState`
   - If using `useFormStatus` → not expected in UI components
   - Most components should work as-is since React 18 and 19 share the same JSX syntax

**Step 2: Add custom keyframe animations to globals.css**

Check each component for Tailwind arbitrary animations like `animate-[dash_20s_linear_infinite]`. If present, add the keyframe to `apps/frontend/src/styles/globals.css`:

```css
@keyframes dash {
  to { stroke-dashoffset: -100; }
}
```

**Step 3: Verify TypeScript compiles**

Run:
```bash
cd apps/frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: No errors from new files.

**Step 4: Commit**

```bash
git add apps/frontend/src/components/landing/DotGrid.tsx apps/frontend/src/components/landing/Preloader.tsx apps/frontend/src/components/landing/TextType.tsx apps/frontend/src/components/landing/ScrollVelocity.tsx apps/frontend/src/styles/globals.css
git commit -m "feat: port landing page UI components (DotGrid, Preloader, TextType, ScrollVelocity)"
```

---

## Task 4: Port Layout Components (Navbar, PillNav, Footer)

**Files:**
- Create: `apps/frontend/src/components/landing/Navbar.tsx`
- Create: `apps/frontend/src/components/landing/PillNav.tsx`
- Create: `apps/frontend/src/components/landing/Footer.tsx`

**Step 1: Copy and port each layout component**

Same import fixes as Task 3. Additional changes for Navbar:

1. Import `useNavigate` from `react-router-dom` and `useAuth` from `../../contexts/AuthContext`
2. Replace the hardcoded nav items array. Change "Sign In" and "Register" items:
   - If `isAuthenticated`: show "Dashboard" item that calls `navigate('/app')`
   - If `!isAuthenticated`: show "Sign In" → `navigate('/login')` and "Register" → `navigate('/login?mode=register')`
3. Wire the logo click to `navigate('/')` (return to landing page top)

**Step 2: Verify TypeScript compiles**

Run:
```bash
cd apps/frontend && npx tsc --noEmit 2>&1 | head -30
```

**Step 3: Commit**

```bash
git add apps/frontend/src/components/landing/Navbar.tsx apps/frontend/src/components/landing/PillNav.tsx apps/frontend/src/components/landing/Footer.tsx
git commit -m "feat: port landing page layout components (Navbar, PillNav, Footer)"
```

---

## Task 5: Port Section Components (Hero, Features, HowItWorks, Mission, SupportedBy, TechStack, CTA)

**Files:**
- Create: `apps/frontend/src/components/landing/Hero.tsx`
- Create: `apps/frontend/src/components/landing/Features.tsx`
- Create: `apps/frontend/src/components/landing/HowItWorks.tsx`
- Create: `apps/frontend/src/components/landing/Mission.tsx`
- Create: `apps/frontend/src/components/landing/SupportedBy.tsx`
- Create: `apps/frontend/src/components/landing/TechStack.tsx`
- Create: `apps/frontend/src/components/landing/CTA.tsx`

**Step 1: Copy and port each section component**

Same import fixes as Tasks 3-4. Additional wiring:

**Hero.tsx:**
- Import `useNavigate` from `react-router-dom`
- "View Live Risk Map" button: `onClick={() => navigate('/login')}`
- "Get Alerts on WhatsApp" button: `onClick={() => window.open('https://wa.me/...', '_blank')}`

**CTA.tsx:**
- Import `useNavigate` from `react-router-dom`
- "Join With Us" button: `onClick={() => navigate('/login')}`
- GitHub button: keep `window.open(...)` as-is

**Other sections** (Features, HowItWorks, Mission, SupportedBy, TechStack):
- No routing changes needed — purely display components
- Fix imports and Tailwind classes only

**Step 2: Verify TypeScript compiles**

Run:
```bash
cd apps/frontend && npx tsc --noEmit 2>&1 | head -30
```

**Step 3: Commit**

```bash
git add apps/frontend/src/components/landing/Hero.tsx apps/frontend/src/components/landing/Features.tsx apps/frontend/src/components/landing/HowItWorks.tsx apps/frontend/src/components/landing/Mission.tsx apps/frontend/src/components/landing/SupportedBy.tsx apps/frontend/src/components/landing/TechStack.tsx apps/frontend/src/components/landing/CTA.tsx
git commit -m "feat: port landing page section components (Hero, Features, HowItWorks, Mission, SupportedBy, TechStack, CTA)"
```

---

## Task 6: Create LandingPage Root Component

**Files:**
- Create: `apps/frontend/src/components/screens/LandingPage.tsx`

**Step 1: Create the root landing page component**

Based on the external repo's `App.tsx`, create `LandingPage.tsx` that:
1. Imports all landing sub-components
2. Has the 3-second Preloader with `AnimatePresence`
3. Has the DotGrid background
4. Renders all sections in order: Navbar → Hero → SupportedBy → HowItWorks → Features → TechStack → CTA → Mission → Footer
5. **CRITICAL: Deep link forwarding** — add a `useEffect` that captures `?join=CODE` from the URL and forwards it:

```tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { useAuth } from '../../contexts/AuthContext';

// Import all landing page sub-components
import { Navbar } from '../landing/Navbar';
import { Hero } from '../landing/Hero';
import { SupportedBy } from '../landing/SupportedBy';
import { HowItWorks } from '../landing/HowItWorks';
import { Features } from '../landing/Features';
import { TechStack } from '../landing/TechStack';
import { CTA } from '../landing/CTA';
import { Mission } from '../landing/Mission';
import { Footer } from '../landing/Footer';
import { Preloader } from '../landing/Preloader';
import { DotGrid } from '../landing/DotGrid';

export default function LandingPage() {
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    // Deep link forwarding: capture ?join=CODE and forward to /app
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const joinCode = params.get('join');
        if (joinCode) {
            sessionStorage.setItem('pendingInviteCode', joinCode);
            navigate('/login', { replace: true });
        }
    }, [navigate]);

    useEffect(() => {
        const timer = setTimeout(() => setLoading(false), 3000);
        return () => clearTimeout(timer);
    }, []);

    return (
        <div className="relative min-h-screen text-slate-900 overflow-x-hidden selection:bg-blue-200 selection:text-blue-900">
            <AnimatePresence>
                {loading && <Preloader />}
            </AnimatePresence>

            <div style={{ overflow: loading ? 'hidden' : 'auto', height: loading ? '100vh' : 'auto' }}>
                <DotGrid dotSize={2} gap={15} proximity={120} shockRadius={250} />
                <Navbar />
                <main>
                    <Hero />
                    <SupportedBy />
                    <HowItWorks />
                    <Features />
                    <TechStack />
                    <CTA />
                    <Mission />
                </main>
                <Footer />
            </div>
        </div>
    );
}
```

**Step 2: Verify TypeScript compiles**

Run:
```bash
cd apps/frontend && npx tsc --noEmit 2>&1 | head -30
```

**Step 3: Commit**

```bash
git add apps/frontend/src/components/screens/LandingPage.tsx
git commit -m "feat: create LandingPage root component with deep link forwarding"
```

---

## Task 7: Create LoginPage Wrapper (Post-Login Redirect)

**Files:**
- Create: `apps/frontend/src/components/screens/LoginPage.tsx`

**Step 1: Create LoginPage wrapper**

This thin wrapper renders the existing `LoginScreen` and handles post-login redirect:

```tsx
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { LoginScreen } from './LoginScreen';
import { useAuth } from '../../contexts/AuthContext';
import { Toaster } from '../ui/sonner';

export function LoginPage() {
    const { isAuthenticated, isLoading } = useAuth();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    // Redirect to /app if already authenticated (prevents back-button loop with replace:true)
    useEffect(() => {
        if (!isLoading && isAuthenticated) {
            navigate('/app', { replace: true });
        }
    }, [isAuthenticated, isLoading, navigate]);

    // Show LoginScreen (pass mode from query param if present)
    return (
        <>
            <LoginScreen />
            <Toaster position="top-center" />
        </>
    );
}
```

**Step 2: Verify TypeScript compiles**

Run:
```bash
cd apps/frontend && npx tsc --noEmit 2>&1 | head -30
```

**Step 3: Commit**

```bash
git add apps/frontend/src/components/screens/LoginPage.tsx
git commit -m "feat: create LoginPage wrapper with post-login redirect"
```

---

## Task 8: Update App.tsx Routes (Core Migration)

**Files:**
- Modify: `apps/frontend/src/App.tsx` (lines 1-3, 97-224, 348-358)

**Step 1: Add imports for new components and React.lazy**

At top of App.tsx, add:
```tsx
import { Suspense, lazy } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { LoginPage } from './components/screens/LoginPage';

const LandingPage = lazy(() => import('./components/screens/LandingPage'));
```

**Step 2: Add auth redirect to FloodSafeApp**

In the `FloodSafeApp` function (line 97), add redirect logic for unauthenticated users. Replace the current auth gate (lines 216-224) with a `useNavigate` + `useEffect` redirect:

```tsx
function FloodSafeApp() {
    const { isAuthenticated, isLoading: authLoading, user } = useAuth();
    const { registerNavigation, startTour } = useOnboardingBot();
    const navigate = useNavigate();
    // ... existing state declarations ...

    // Redirect unauthenticated users to /login
    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            navigate('/login', { replace: true });
        }
    }, [authLoading, isAuthenticated, navigate]);

    // ... existing useEffects ...

    // Show loading screen while checking auth
    if (authLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-cyan-50">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                    <p className="text-gray-600">Loading FloodSafe...</p>
                </div>
            </div>
        );
    }

    // Don't render if not authenticated (redirect effect will fire)
    if (!isAuthenticated) {
        return null;
    }

    // Show onboarding if profile not complete (UNCHANGED)
    if (user && !user.profile_complete) {
        return (
            <>
                <OnboardingScreen onComplete={() => {
                    window.location.reload();
                }} />
                <Toaster position="top-center" />
            </>
        );
    }

    // ... rest of FloodSafeApp unchanged ...
```

**Step 3: Update the Routes block**

Replace lines 348-358 in the `App` default export:

```tsx
<Routes>
    {/* Public routes */}
    <Route path="/" element={
        <Suspense fallback={
            <div className="min-h-screen flex items-center justify-center">
                <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
            </div>
        }>
            <LandingPage />
        </Suspense>
    } />
    <Route path="/login" element={<LoginPage />} />
    <Route path="/email-verified" element={
        <>
            <EmailVerifiedScreen />
            <Toaster position="top-center" />
        </>
    } />

    {/* Authenticated app */}
    <Route path="/app" element={<FloodSafeApp />} />

    {/* Catch-all redirect */}
    <Route path="*" element={<Navigate to="/" replace />} />
</Routes>
```

**Step 4: Remove the old LoginScreen import if now unused directly**

The `LoginScreen` import at line 9 is still needed — `LoginPage` imports it. But the direct usage in FloodSafeApp (lines 218-223) is removed. Keep the import.

**Step 5: Verify TypeScript compiles**

Run:
```bash
cd apps/frontend && npx tsc --noEmit 2>&1 | head -30
```

**Step 6: Commit**

```bash
git add apps/frontend/src/App.tsx
git commit -m "feat: migrate to route-based architecture (/, /login, /app)"
```

---

## Task 9: Apply Surgical Fix — Email Verified Redirect

**Files:**
- Modify: `apps/frontend/src/components/screens/EmailVerifiedScreen.tsx` (lines 47, 58)

**Step 1: Update redirect targets**

Change line 47:
```tsx
// Before
navigate('/', { replace: true });
// After
navigate('/app', { replace: true });
```

Change line 58:
```tsx
// Before
navigate('/', { replace: true });
// After
navigate('/app', { replace: true });
```

Line 62 (`navigate('/login', ...)`) is already correct for the new structure.

**Step 2: Commit**

```bash
git add apps/frontend/src/components/screens/EmailVerifiedScreen.tsx
git commit -m "fix: redirect email verification to /app instead of /"
```

---

## Task 10: Apply Surgical Fix — Invite URL Generation

**Files:**
- Modify: `apps/frontend/src/components/circles/InviteLinkShare.tsx` (line 14)

**Step 1: Update invite URL to include /app path**

Change line 14:
```tsx
// Before
const inviteUrl = `${window.location.origin}?join=${inviteCode}`;
// After
const inviteUrl = `${window.location.origin}/app?join=${inviteCode}`;
```

**Step 2: Commit**

```bash
git add apps/frontend/src/components/circles/InviteLinkShare.tsx
git commit -m "fix: update Safety Circle invite URL to use /app path"
```

---

## Task 11: Apply Surgical Fix — Post-Logout Redirect

**Files:**
- Modify: `apps/frontend/src/components/Sidebar.tsx` (line 87)
- Modify: `apps/frontend/src/components/screens/ProfileScreen.tsx` (lines 76, 801-808)

**Step 1: Update Sidebar logout**

Add `useNavigate` import and redirect after logout. In `Sidebar.tsx`:

```tsx
// Add import
import { useNavigate } from 'react-router-dom';

// In component body (line ~20)
const navigate = useNavigate();

// Change line 87
onClick={async () => {
    await logout();
    navigate('/login', { replace: true });
}}
```

**Step 2: Update ProfileScreen logout**

In `ProfileScreen.tsx`, add `useNavigate` import and update logout handler:

```tsx
// Add import (at top)
import { useNavigate } from 'react-router-dom';

// In component body (after line 76)
const navigate = useNavigate();

// Change lines 801-808
onClick={async () => {
    try {
        await logout();
        navigate('/login', { replace: true });
        toast.success('Logged out successfully');
    } catch (error) {
        toast.error('Failed to logout');
    }
}}
```

**Step 3: Verify TypeScript compiles**

Run:
```bash
cd apps/frontend && npx tsc --noEmit 2>&1 | head -30
```

**Step 4: Commit**

```bash
git add apps/frontend/src/components/Sidebar.tsx apps/frontend/src/components/screens/ProfileScreen.tsx
git commit -m "fix: add explicit /login redirect after logout"
```

---

## Task 12: Apply Surgical Fix — PWA Start URL

**Files:**
- Modify: `apps/frontend/vite.config.ts` (line 21)

**Step 1: Update start_url**

Change line 21:
```tsx
// Before
start_url: '/',
// After
start_url: '/app',
```

Keep `scope: '/'` unchanged — the service worker should cover all paths.

**Step 2: Commit**

```bash
git add apps/frontend/vite.config.ts
git commit -m "fix: update PWA start_url to /app for homescreen shortcut"
```

---

## Task 13: Apply Surgical Fix — Vercel SPA Rewrites

**Files:**
- Modify: `apps/frontend/vercel.json`

**Step 1: Add SPA catch-all rewrite**

Update `vercel.json` to serve `index.html` for all client-side routes:

```json
{
  "framework": "vite",
  "installCommand": "npm install",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "rewrites": [
    { "source": "/architecture.html", "destination": "/architecture.html" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

The specific `/architecture.html` rule goes FIRST (Vercel evaluates in order), so it still serves the static file. Everything else falls through to `index.html`.

**Step 2: Commit**

```bash
git add apps/frontend/vercel.json
git commit -m "fix: add SPA rewrite rule for client-side routing"
```

---

## Task 14: Add Landing Page Styles to globals.css

**Files:**
- Modify: `apps/frontend/src/styles/globals.css`

**Step 1: Add any custom keyframes and landing-page-specific styles**

After porting components, check for custom animations used in the landing page (like `animate-[dash_...]`, `animate-ping`, etc.). Add any missing `@keyframes` to `globals.css`.

Also ensure `selection:bg-blue-200` and `selection:text-blue-900` work in Tailwind v4 (may need `::selection` in CSS).

**Step 2: Rebuild CSS**

Run:
```bash
cd apps/frontend && npx @tailwindcss/cli -i src/styles/globals.css -o src/index.css
```

**Step 3: Commit**

```bash
git add apps/frontend/src/styles/globals.css apps/frontend/src/index.css
git commit -m "feat: add landing page keyframe animations and styles"
```

---

## Task 15: Full Build Verification

**Files:** None (verification only)

**Step 1: TypeScript type check**

Run:
```bash
cd apps/frontend && npx tsc --noEmit
```

Expected: 0 errors.

**Step 2: Build**

Run:
```bash
cd apps/frontend && npm run build
```

Expected: Build succeeds. Check bundle sizes — landing page chunk should be separate (lazy-loaded).

**Step 3: Local dev test**

Run:
```bash
cd apps/frontend && npm run dev
```

Then test in browser at `http://localhost:5175`:
- [ ] `/` shows landing page with Preloader → sections → Footer
- [ ] Navbar "Sign In" goes to `/login`
- [ ] `/login` shows existing LoginScreen
- [ ] Authenticated user at `/` sees "Go to Dashboard" in navbar
- [ ] `/app` shows the main FloodSafe app (if authenticated) or redirects to `/login`
- [ ] Browser back from `/app` does NOT loop through `/login`
- [ ] `/?join=TESTCODE` stores code and redirects to `/login`
- [ ] After login, invite code is processed (check sessionStorage)
- [ ] Logout redirects to `/login`
- [ ] `/email-verified?success=true` redirects to `/app` after countdown
- [ ] Page refresh at `/app` does NOT 404
- [ ] Page refresh at `/login` does NOT 404
- [ ] Mobile responsive: landing page sections stack vertically

**Step 4: Commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address build/runtime issues from landing page integration"
```

---

## Task 16: Clean Up Temp Clone

**Step 1: Remove temporary clone**

```bash
rm -rf /tmp/landing-page-tmp
```

---

## Summary of All Files Changed

### New Files (16)
```
apps/frontend/src/components/screens/LandingPage.tsx
apps/frontend/src/components/screens/LoginPage.tsx
apps/frontend/src/components/landing/Navbar.tsx
apps/frontend/src/components/landing/PillNav.tsx
apps/frontend/src/components/landing/Footer.tsx
apps/frontend/src/components/landing/Hero.tsx
apps/frontend/src/components/landing/Features.tsx
apps/frontend/src/components/landing/HowItWorks.tsx
apps/frontend/src/components/landing/Mission.tsx
apps/frontend/src/components/landing/SupportedBy.tsx
apps/frontend/src/components/landing/TechStack.tsx
apps/frontend/src/components/landing/CTA.tsx
apps/frontend/src/components/landing/Preloader.tsx
apps/frontend/src/components/landing/DotGrid.tsx
apps/frontend/src/components/landing/TextType.tsx
apps/frontend/src/components/landing/ScrollVelocity.tsx
```

### Modified Files (8)
```
apps/frontend/package.json                          (new deps)
apps/frontend/src/App.tsx                           (routes + auth redirect)
apps/frontend/src/components/screens/EmailVerifiedScreen.tsx  (redirect target)
apps/frontend/src/components/circles/InviteLinkShare.tsx      (invite URL)
apps/frontend/src/components/Sidebar.tsx             (logout redirect)
apps/frontend/src/components/screens/ProfileScreen.tsx  (logout redirect)
apps/frontend/vite.config.ts                         (PWA start_url)
apps/frontend/vercel.json                            (SPA rewrites)
```

### Asset Files (5)
```
apps/frontend/src/assets/landing/logo.png
apps/frontend/src/assets/landing/logo-meta.png
apps/frontend/src/assets/landing/logo-sl2.png
apps/frontend/src/assets/landing/logo-wa.png
apps/frontend/src/assets/landing/navigate.png
```
