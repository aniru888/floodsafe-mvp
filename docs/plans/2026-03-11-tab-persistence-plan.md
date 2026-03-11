# Tab Persistence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix city preference reverting and route navigation disappearing when switching tabs.

**Architecture:** Remove stale state sources — HomeScreen reads city from CityContext (canonical), CityContext refreshes AuthContext after sync. Remove nested NavigationProvider so route state persists at app level.

**Tech Stack:** React 18 contexts, TypeScript, MapLibre GL JS

**Design doc:** `docs/plans/2026-03-11-tab-persistence-design.md`

---

### Task 1: Fix HomeScreen cityFilter initialization

**Files:**
- Modify: `apps/frontend/src/components/screens/HomeScreen.tsx:73-76`

**Step 1: Change cityFilter initializer to read from CityContext**

Replace lines 73-76:
```tsx
// BEFORE:
const [cityFilter, setCityFilter] = useState<CityFilter>(() => {
    // Initialize with user's city preference, fallback to 'all'
    return (user?.city_preference as CityFilter) || 'all';
});

// AFTER:
const [cityFilter, setCityFilter] = useState<CityFilter>(currentCity);
```

`currentCity` is already available from line 70: `const { city: currentCity, setCity, syncCityToUser } = useCityContext();`

**Step 2: Verify no type error**

Run: `cd apps/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors (both `CityFilter` and `CityKey` are string unions, `CityKey` is a subset of `CityFilter`)

---

### Task 2: Fix HomeScreen useEffect to watch CityContext

**Files:**
- Modify: `apps/frontend/src/components/screens/HomeScreen.tsx:82-87`

**Step 1: Change useEffect dependency from AuthContext to CityContext**

Replace lines 82-87:
```tsx
// BEFORE:
// Update city filter when user's city preference changes
useEffect(() => {
    if (user?.city_preference) {
        setCityFilter(user.city_preference as CityFilter);
    }
}, [user?.city_preference]);

// AFTER:
// Update city filter when CityContext city changes
useEffect(() => {
    setCityFilter(currentCity);
}, [currentCity]);
```

Note: No `if` guard needed — `currentCity` always has a value (CityContext guarantees a valid CityKey).

**Step 2: Verify no type error**

Run: `cd apps/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

---

### Task 3: CityContext — refresh AuthContext after sync

**Files:**
- Modify: `apps/frontend/src/contexts/CityContext.tsx:23, 82-83`

**Step 1: Add `refreshUser` to useAuth destructuring**

Line 23, change:
```tsx
// BEFORE:
const { user } = useAuth();

// AFTER:
const { user, refreshUser } = useAuth();
```

**Step 2: Call refreshUser after successful backend sync**

Lines 82-83, change:
```tsx
// BEFORE:
// Update local state after successful API call
setCityState(newCity);

// AFTER:
// Update local state after successful API call
setCityState(newCity);
// Refresh AuthContext user so user.city_preference stays in sync
await refreshUser();
```

**Step 3: Verify no type error**

Run: `cd apps/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors — `refreshUser` is already typed as `() => Promise<void>` in AuthContext interface (line 73)

**Step 4: Commit city preference fix**

```bash
cd apps/frontend
git add src/components/screens/HomeScreen.tsx src/contexts/CityContext.tsx
git commit -m "fix: city preference — read from CityContext, refresh AuthContext after sync

HomeScreen cityFilter now initializes from CityContext (canonical source)
instead of stale AuthContext user.city_preference. CityContext calls
refreshUser() after successful backend sync to keep AuthContext in sync."
```

---

### Task 4: Remove nested NavigationProvider from FloodAtlasScreen

**Files:**
- Modify: `apps/frontend/src/components/screens/FloodAtlasScreen.tsx:233-239`

**Step 1: Remove the nested provider wrapper**

Replace lines 233-239:
```tsx
// BEFORE:
// Main component with providers
export function FloodAtlasScreen(props: FloodAtlasScreenProps) {
    return (
        <NavigationProvider>
            <FloodAtlasContent {...props} />
        </NavigationProvider>
    );
}

// AFTER:
// Main component — uses app-level NavigationProvider (App.tsx:347)
export function FloodAtlasScreen(props: FloodAtlasScreenProps) {
    return <FloodAtlasContent {...props} />;
}
```

**Step 2: Clean up unused import**

Check if `NavigationProvider` is still used elsewhere in the file. If line 9 has:
```tsx
import { NavigationProvider, useNavigation } from '../../contexts/NavigationContext';
```
Change to:
```tsx
import { useNavigation } from '../../contexts/NavigationContext';
```
(Only if `NavigationProvider` has no other references in the file — `useNavigation` is still used at line 34.)

**Step 3: Verify no type error**

Run: `cd apps/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

**Step 4: Commit route persistence fix**

```bash
cd apps/frontend
git add src/components/screens/FloodAtlasScreen.tsx
git commit -m "fix: route navigation persists across tab switches

Remove nested NavigationProvider that shadowed app-level provider.
Route state now lives in App.tsx NavigationProvider, surviving tab switches.
Map visual restores via existing useEffect on remount."
```

---

### Task 5: Build verification

**Step 1: Full TypeScript check**

Run: `cd apps/frontend && npx tsc --noEmit`
Expected: Clean — zero errors

**Step 2: Production build**

Run: `cd apps/frontend && npm run build`
Expected: Clean build, no warnings related to changed files

**Step 3: Verify no unused imports or variables**

Check build output for warnings about `NavigationProvider` unused import. If present, fix in FloodAtlasScreen.tsx.

---

### Task 6: Manual verification checklist

> Use `superpowers:verification-before-completion` before claiming done.

Run dev server: `cd apps/frontend && npm run dev`

**City preference tests:**
- [ ] Open app → go to Home → change city dropdown to Indore
- [ ] Verify: Recent Updates section shows Indore-area content
- [ ] Switch to Map tab → switch back to Home tab
- [ ] Verify: City filter still shows Indore (not reverted to Delhi)
- [ ] Refresh browser (F5)
- [ ] Verify: City preference persists as Indore after reload

**Route navigation tests:**
- [ ] Go to Map tab → plan a route → start navigation
- [ ] Verify: Route line visible, LiveNavigationPanel showing
- [ ] Switch to Home tab
- [ ] Switch back to Map tab
- [ ] Verify: Route line redrawn on map, LiveNavigationPanel active
- [ ] Stop navigation
- [ ] Verify: Route clears, panel hides cleanly
