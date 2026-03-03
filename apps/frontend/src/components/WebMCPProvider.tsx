import { useCallback } from 'react';
import '@mcp-b/global';
import { useWebMCP, useWebMCPContext, useWebMCPResource, useWebMCPPrompt } from '@mcp-b/react-webmcp';
import { z } from 'zod';
import { useQueryClient } from '@tanstack/react-query';
import { Capacitor } from '@capacitor/core';
import { useAuth } from '../contexts/AuthContext';
import { useCityContext } from '../contexts/CityContext';
import { useLocationTracking } from '../contexts/LocationTrackingContext';
import { useLanguage } from '../contexts/LanguageContext';
import { CITIES, type CityKey } from '../lib/map/cityConfigs';
import { API_BASE_URL } from '../lib/api/config';

// ─── Module-level Zod schemas (stable references — prevent re-registration) ──

const SearchInput = {
  query: z.string().min(2).describe('Search query (min 2 chars)'),
  city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore']).optional().describe('City filter'),
  limit: z.number().min(1).max(20).default(5).describe('Max results'),
};

const CacheInput = {
  query_key: z.string().describe('TanStack Query key as JSON, e.g. \'["reports"]\' or \'["hotspots","delhi",false]\''),
};

const SwitchCityInput = {
  city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore']).describe('Target city'),
};

// ─── WebMCP Provider ─────────────────────────────────────────────────────────
// Leaf component that registers all FloodSafe tools, contexts, resources, and
// prompts with the WebMCP bridge. Renders nothing (pure side-effect provider).
// Always mounted — no sensitive data on FloodSafe. Enables AI debugging in production.

export function WebMCPProvider() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const { city, setCity } = useCityContext();
  const { state: locState } = useLocationTracking();
  const { language } = useLanguage();
  const queryClient = useQueryClient();

  // ─── Contexts (2) ───────────────────────────────────────────────────

  useWebMCPContext(
    'context_app_state',
    'FloodSafe state: city, auth, user profile, push notification permission',
    () => ({
      city,
      city_display: CITIES[city]?.displayName,
      is_authenticated: isAuthenticated,
      auth_loading: authLoading,
      user_id: user?.id ?? null,
      username: user?.username ?? null,
      level: user?.level ?? 0,
      points: user?.points ?? 0,
      profile_complete: user?.profile_complete ?? false,
      language,
      available_cities: Object.keys(CITIES),
      notification_permission: 'Notification' in window ? Notification.permission : 'unsupported',
    })
  );

  useWebMCPContext(
    'context_location',
    'GPS position and nearby flood hotspot proximity data',
    () => ({
      is_tracking: locState.isTracking,
      is_enabled: locState.isEnabled,
      position: locState.currentPosition,
      nearby_hotspots: locState.nearbyHotspots.map(h => ({
        id: h.id, name: h.name, fhi_level: h.fhi_level, distance_m: h.distanceMeters,
      })),
    })
  );

  // ─── Tools (3) ──────────────────────────────────────────────────────

  useWebMCP({
    name: 'search_locations',
    description: 'Search locations via FloodSafe unified search API. Returns geocoded results.',
    inputSchema: SearchInput,
    annotations: { readOnlyHint: true, idempotentHint: true, openWorldHint: true },
    handler: useCallback(async (input: { query: string; city?: string; limit?: number }) => {
      const params = new URLSearchParams({
        q: input.query,
        limit: String(input.limit ?? 5),
        city: input.city || city,
      });
      const res = await fetch(`${API_BASE_URL}/search/locations/?${params}`);
      if (!res.ok) throw new Error(`Search failed: ${res.status} ${res.statusText}`);
      const results = await res.json();
      return { count: results.length, results: results.slice(0, 10) };
    }, [city]),
  });

  useWebMCP({
    name: 'get_query_cache',
    description: 'Inspect any TanStack Query cache entry. Use to verify data freshness or debug loading issues. Common keys: ["reports"], ["hotspots","<city>",false], ["unified-alerts","<city>","all"], ["floodhub-status","<city>"], ["gamification","badges","me"]',
    inputSchema: CacheInput,
    annotations: { readOnlyHint: true, idempotentHint: true },
    handler: useCallback((input: { query_key: string }) => {
      let key: unknown[];
      try {
        key = JSON.parse(input.query_key);
        if (!Array.isArray(key)) key = [input.query_key];
      } catch {
        key = [input.query_key];
      }

      const state = queryClient.getQueryState(key);
      if (!state) return { found: false, state: 'not_found', preview: 'No cache entry' };

      const data = queryClient.getQueryData(key);
      const json = JSON.stringify(data, null, 2);
      return {
        found: true,
        state: state.fetchStatus === 'fetching' ? 'fetching' : state.isInvalidated ? 'stale' : 'fresh',
        fetch_status: state.fetchStatus,
        updated_at: state.dataUpdatedAt ? new Date(state.dataUpdatedAt).toISOString() : null,
        preview: json.length > 2000 ? json.slice(0, 2000) + '...[truncated]' : json,
      };
    }, [queryClient]),
  });

  useWebMCP({
    name: 'switch_city',
    description: 'Switch FloodSafe active city. Changes map, alerts, hotspots, FloodHub data.',
    inputSchema: SwitchCityInput,
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: true },
    handler: useCallback((input: { city: string }) => {
      const prev = city;
      setCity(input.city as CityKey);
      return { previous: prev, current: input.city, success: true };
    }, [city, setCity]),
  });

  // ─── Resources (5) ─────────────────────────────────────────────────

  useWebMCPResource({
    uri: 'floodsafe://config',
    name: 'App Configuration',
    description: 'FloodSafe config: API URL, city list, bounds, feature flags',
    mimeType: 'application/json',
    read: useCallback(async () => ({
      contents: [{
        uri: 'floodsafe://config',
        mimeType: 'application/json',
        text: JSON.stringify({
          api_base_url: API_BASE_URL,
          dev_mode: import.meta.env.DEV,
          current_city: city,
          cities: Object.entries(CITIES).map(([k, c]) => ({
            key: k, name: c.displayName, center: c.center,
            has_metro: 'metro' in c, has_flood_tiles: !!c.pmtiles?.flood,
          })),
          pwa_installed: window.matchMedia('(display-mode: standalone)').matches,
        }, null, 2),
      }],
    }), [city]),
  });

  useWebMCPResource({
    uri: 'floodsafe://alerts/{city}',
    name: 'City Alerts',
    description: 'Unified flood alerts for a city (IMD, GDACS, community, FloodHub)',
    mimeType: 'application/json',
    read: useCallback(async (uri: { toString(): string }) => {
      const match = uri.toString().match(/alerts\/(.+)/);
      const c = match?.[1] || city;
      const data = queryClient.getQueryData(['unified-alerts', c, 'all']) || [];
      return { contents: [{ uri: uri.toString(), mimeType: 'application/json', text: JSON.stringify(data, null, 2) }] };
    }, [city, queryClient]),
  });

  useWebMCPResource({
    uri: 'floodsafe://hotspots/{city}',
    name: 'Flood Hotspots',
    description: 'Waterlogging hotspots with FHI risk levels for a city',
    mimeType: 'application/json',
    read: useCallback(async (uri: { toString(): string }) => {
      const match = uri.toString().match(/hotspots\/(.+)/);
      const c = match?.[1] || city;
      const data = queryClient.getQueryData(['hotspots', c, false]) || [];
      return { contents: [{ uri: uri.toString(), mimeType: 'application/json', text: JSON.stringify(data, null, 2) }] };
    }, [city, queryClient]),
  });

  useWebMCPResource({
    uri: 'floodsafe://reports',
    name: 'Flood Reports',
    description: 'Recent community flood reports with verification status',
    mimeType: 'application/json',
    read: useCallback(async (uri: { toString(): string }) => {
      const data = queryClient.getQueryData(['reports']) || [];
      return { contents: [{ uri: uri.toString(), mimeType: 'application/json', text: JSON.stringify(data, null, 2) }] };
    }, [queryClient]),
  });

  useWebMCPResource({
    uri: 'floodsafe://floodhub/{city}',
    name: 'FloodHub Data',
    description: 'Google Flood Forecasting status and gauges for a city',
    mimeType: 'application/json',
    read: useCallback(async (uri: { toString(): string }) => {
      const match = uri.toString().match(/floodhub\/(.+)/);
      const c = match?.[1] || city;
      const status = queryClient.getQueryData(['floodhub-status', c]);
      const gauges = queryClient.getQueryData(['floodhub-gauges', c]);
      return { contents: [{ uri: uri.toString(), mimeType: 'application/json', text: JSON.stringify({ status, gauges }, null, 2) }] };
    }, [city, queryClient]),
  });

  useWebMCPResource({
    uri: 'floodsafe://push-status',
    name: 'Push Notification Status',
    description: 'FCM push notification diagnostics: permission, VAPID key, service worker, platform',
    mimeType: 'application/json',
    read: useCallback(async (uri: { toString(): string }) => {
      const swRegistrations = await navigator.serviceWorker?.getRegistrations().catch(() => []);
      const hasFirebaseSW = swRegistrations?.some(
        r => r.active?.scriptURL.includes('firebase-messaging-sw')
      ) ?? false;

      return {
        contents: [{
          uri: uri.toString(),
          mimeType: 'application/json',
          text: JSON.stringify({
            permission: 'Notification' in window ? Notification.permission : 'unsupported',
            vapid_key_configured: !!import.meta.env.VITE_FIREBASE_VAPID_KEY,
            service_worker_active: !!navigator.serviceWorker?.controller,
            firebase_messaging_sw_registered: hasFirebaseSW,
            is_native_platform: Capacitor.isNativePlatform(),
            total_sw_registrations: swRegistrations?.length ?? 0,
          }, null, 2),
        }],
      };
    }, []),
  });

  // ─── Prompts (5) ───────────────────────────────────────────────────

  useWebMCPPrompt({
    name: 'analyze-flood-risk',
    description: 'Structured analysis of current flood risk for a city',
    argsSchema: { city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore']).describe('City to analyze') },
    get: useCallback(async (args: { city: string }) => ({
      messages: [{
        role: 'user' as const,
        content: { type: 'text' as const, text: [
          `Analyze flood risk for ${args.city}:`,
          '1. Read floodsafe://config for feature availability',
          `2. Read floodsafe://hotspots/${args.city} for risk levels`,
          `3. Read floodsafe://floodhub/${args.city} for gauge status`,
          `4. Read floodsafe://alerts/${args.city} for active alerts`,
          '5. Produce report: overall risk, top dangerous areas, recommendations',
        ].join('\n') },
      }],
    }), []),
  });

  useWebMCPPrompt({
    name: 'debug-ui-state',
    description: 'Gather all app state for debugging (auth, city, cache, console errors)',
    get: useCallback(async () => ({
      messages: [{
        role: 'user' as const,
        content: { type: 'text' as const, text: [
          'Debug FloodSafe UI state:',
          '1. Call context_app_state for auth/city',
          '2. Call context_location for GPS state',
          '3. Call get_query_cache for: ["reports"], ["unified-alerts","<city>","all"], ["hotspots","<city>",false], ["floodhub-status","<city>"]',
          '4. Use list_console_messages for errors',
          '5. Use take_screenshot for visual state',
          '6. Report: auth state, data loading status, errors, visual issues',
        ].join('\n') },
      }],
    }), []),
  });

  useWebMCPPrompt({
    name: 'verify-yogyakarta',
    description: 'End-to-end verification of Yogyakarta city integration',
    get: useCallback(async () => ({
      messages: [{
        role: 'user' as const,
        content: { type: 'text' as const, text: [
          'Verify Yogyakarta integration:',
          '1. Call context_app_state → note current city',
          '2. Call switch_city(yogyakarta)',
          '3. Wait 2s, call context_app_state → confirm switch',
          '4. get_query_cache(["hotspots","yogyakarta",false]) → verify data loads',
          '5. get_query_cache(["historicalFloods","yogyakarta"]) → verify history',
          '6. Read floodsafe://config → verify Yogyakarta has no metro, no flood tiles',
          '7. take_screenshot → verify map shows Yogyakarta (center ~110.37, -7.80)',
          '8. search_locations(query="malioboro", city="yogyakarta") → verify search works',
          '9. list_console_messages → verify no JS errors',
          'Expected: city switches, map centers on Yogyakarta, search returns Indonesian results',
        ].join('\n') },
      }],
    }), []),
  });

  useWebMCPPrompt({
    name: 'verify-push-notifications',
    description: 'End-to-end verification of push notification pipeline',
    get: useCallback(async () => ({
      messages: [{
        role: 'user' as const,
        content: { type: 'text' as const, text: [
          'Verify push notification pipeline:',
          '1. Call context_app_state → confirm authenticated, get user_id + notification_permission',
          '2. Read floodsafe://push-status → check permission, VAPID, SW, Firebase SW',
          '3. If permission != "granted": STOP — user must grant permission manually',
          '4. list_network_requests → find POST /api/push/register-token with status 200',
          '5. list_console_messages → check NO "Failed to register FCM token" errors',
          '6. list_console_messages → check NO "VITE_FIREBASE_VAPID_KEY not set" warnings',
          '7. get_query_cache(["reports"]) → verify reports data loaded (push triggers on report creation)',
          '8. take_screenshot → capture visual state',
          'Expected: permission=granted, VAPID configured, SW active, token registered (200), no errors',
          'If any check fails, report which step failed and the error details',
        ].join('\n') },
      }],
    }), []),
  });

  useWebMCPPrompt({
    name: 'verify-full-e2e',
    description: 'Comprehensive E2E verification of all FloodSafe features for a city',
    argsSchema: { city: z.enum(['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore']).default('delhi').describe('City to test') },
    get: useCallback(async (args: { city: string }) => ({
      messages: [{
        role: 'user' as const,
        content: { type: 'text' as const, text: [
          `Full E2E verification for ${args.city}:`,
          '',
          '── Auth ──',
          '1. Call context_app_state → confirm authenticated, profile_complete, notification_permission',
          '',
          '── Data Loading ──',
          `2. get_query_cache(["hotspots","${args.city}",false]) → verify hotspots loaded`,
          `3. get_query_cache(["unified-alerts","${args.city}","all"]) → verify alerts loaded`,
          '4. get_query_cache(["reports"]) → verify reports loaded',
          `5. Read floodsafe://floodhub/${args.city} → verify FloodHub data`,
          '',
          '── Push Notifications ──',
          '6. Read floodsafe://push-status → check permission, VAPID, SW',
          '7. list_network_requests → find POST /api/push/register-token',
          '',
          '── City Features ──',
          `8. Read floodsafe://config → verify ${args.city} features`,
          `9. search_locations(query="main road", city="${args.city}") → verify search`,
          '',
          '── Health ──',
          '10. list_console_messages → check for JS errors (filter type=error)',
          '11. take_screenshot → capture visual state',
          '',
          'Report: PASS/FAIL for each section with specific failures listed.',
        ].join('\n') },
      }],
    }), []),
  });

  return null; // Renders nothing — pure side-effect provider
}
