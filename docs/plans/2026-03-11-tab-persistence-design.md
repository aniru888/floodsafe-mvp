# Tab Persistence: City Preference + Route Navigation

> **Date**: 2026-03-11
> **Status**: Approved
> **Scope**: Fix two bugs caused by React component unmount on tab switch

---

## Problem Statement

Two bugs share the same root cause — the `switch/case` rendering in `App.tsx:247` unmounts and remounts screen components on tab switch:

1. **City preference reverts**: User changes city to Indore via HomeScreen dropdown, switches tab, returns — HomeScreen shows Delhi data again in "Recent Updates" section
2. **Route navigation lost**: User starts safe route navigation, switches to another tab, returns — route and turn-by-turn guidance are gone

## Root Cause Analysis

### Bug 1: Stale City Preference

**Data flow (broken)**:
```
User changes city → syncCityToUser() → PATCH backend ✓ + setCityState() ✓
                  → AuthContext user.city_preference NOT refreshed ✗
User switches tab → HomeScreen unmounts
User returns → HomeScreen remounts → cityFilter inits from stale user.city_preference → wrong city
```

**Files involved**:
- `CityContext.tsx:67-88` — `syncCityToUser` updates backend + CityContext state, but doesn't refresh AuthContext
- `HomeScreen.tsx:73-76` — `cityFilter` useState initializer reads from `user?.city_preference` (AuthContext, stale)
- `HomeScreen.tsx:83-87` — useEffect watches `user?.city_preference` which never changes within a session
- `AuthContext.tsx:406-411` — `refreshUser()` exists but is never called after city sync

### Bug 2: Route Navigation Lost

**Root cause**: `FloodAtlasScreen.tsx:236` wraps its content in a **nested `<NavigationProvider>`**, shadowing the app-level provider at `App.tsx:347`. When the tab unmounts, the inner provider's state (active route, GPS position, turn instructions) is destroyed.

**Files involved**:
- `FloodAtlasScreen.tsx:233-239` — Nested `<NavigationProvider>` wrapper
- `App.tsx:347` — App-level `<NavigationProvider>` (exists but is shadowed)
- `NavigationContext.tsx:59-370` — Provider with route state, GPS watcher, hotspot alerts

---

## Solution: Approach 2 — Lift State Up

Fix each bug at its proper layer. No new files. No new dependencies.

### Fix 1: City Preference (3 changes)

**1a. HomeScreen: Init `cityFilter` from CityContext, not AuthContext**

```tsx
// BEFORE (HomeScreen.tsx:73-76):
const [cityFilter, setCityFilter] = useState<CityFilter>(() => {
    return (user?.city_preference as CityFilter) || 'all';
});

// AFTER:
const [cityFilter, setCityFilter] = useState<CityFilter>(currentCity);
```

**1b. HomeScreen: Watch CityContext instead of AuthContext**

```tsx
// BEFORE (HomeScreen.tsx:83-87):
useEffect(() => {
    if (user?.city_preference) {
        setCityFilter(user.city_preference as CityFilter);
    }
}, [user?.city_preference]);

// AFTER:
useEffect(() => {
    setCityFilter(currentCity);
}, [currentCity]);
```

**1c. CityContext: Refresh AuthContext user after successful sync**

```tsx
// CityContext.tsx — add refreshUser to useAuth destructuring
const { user, refreshUser } = useAuth();

// In syncCityToUser, after successful PATCH:
setCityState(newCity);
await refreshUser(); // Keeps AuthContext.user.city_preference in sync
```

### Fix 2: Route Navigation (1 change)

**2a. Remove nested NavigationProvider from FloodAtlasScreen**

```tsx
// BEFORE (FloodAtlasScreen.tsx:233-239):
export function FloodAtlasScreen(props: FloodAtlasScreenProps) {
    return (
        <NavigationProvider>
            <FloodAtlasContent {...props} />
        </NavigationProvider>
    );
}

// AFTER:
export function FloodAtlasScreen(props: FloodAtlasScreenProps) {
    return <FloodAtlasContent {...props} />;
}
```

The app-level `NavigationProvider` at `App.tsx:347` persists across tab switches. All `useNavigation()` consumers (MapComponent, LiveNavigationPanel, NavigationPanel) are children of this provider.

**Route restoration flow**:
```
Navigation active → NavigationContext stores route (app-level, persists)
User switches tab → FloodAtlasScreen unmounts, context survives
User returns → FloodAtlasScreen remounts → reads navState from context
  → passes navigationRoutes to MapComponent (lines 167-184)
  → MapComponent creates new map → useEffect draws route (line 1145+)
  → LiveNavigationPanel renders (line 159, checks navState.isNavigating)
```

---

## Dependency Verification

| Concern | Verified |
|---------|----------|
| CityContext already imports `useAuth` | Yes (line 4) — just add `refreshUser` to destructuring |
| App-level NavigationProvider has CityContext + VoiceGuidance | Yes — provider order: CityProvider > VoiceGuidanceProvider > NavigationProvider |
| All `useNavigation()` consumers inside app-level provider | Yes — MapComponent, LiveNavigationPanel, NavigationPanel, FloodAtlasContent |
| GPS watcher persists across tab switches | Yes — `watchIdRef` in app-level provider stays alive |
| No new API overhead from removing nested provider | Correct — app-level provider already runs `useHotspots` |
| `cityFilter` default changes from `'all'` to current city | Acceptable — user has an explicit city preference |
| `refreshUser()` exists in AuthContext | Yes (line 406-411), already exposed in context value |

---

## Files Changed

| File | Change | Lines | Risk |
|------|--------|-------|------|
| `HomeScreen.tsx` | Init `cityFilter` from CityContext | 73-76 | Low |
| `HomeScreen.tsx` | Watch `currentCity` in useEffect | 83-87 | Low |
| `CityContext.tsx` | Add `refreshUser` destructuring + call after sync | 23, 83 | Low |
| `FloodAtlasScreen.tsx` | Remove nested `<NavigationProvider>` | 233-239 | Medium |

**Total: 4 edits across 3 files. No new files. No new dependencies.**

---

## Testing Plan

| Test | Expected Result |
|------|-----------------|
| `npx tsc --noEmit` | No type errors |
| `npm run build` | Clean build |
| Change city to Indore → switch tab → return | HomeScreen filter shows Indore, Recent Updates filtered to Indore |
| Change city → refresh browser | City persists (DB sync verified) |
| Start navigation → switch to alerts tab → return | Route line visible on map, LiveNavigationPanel active |
| Start navigation → switch tab → return → stop navigation | Clean stop, route clears, panel hides |
| Fresh login with city_preference=indore in DB | HomeScreen opens with Indore filter |

---

## Rejected Alternatives

**Keep Tabs Mounted (CSS visibility)**: Higher memory, MapLibre rendering issues when hidden, inactive screens still run effects.

**Hybrid (keep only map mounted)**: Special-case logic, inconsistent pattern across tabs.
