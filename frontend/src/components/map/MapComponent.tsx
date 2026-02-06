import { useCallback, useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Protocol } from 'pmtiles';
import MapLegend, { type MapLegendLayerKey, type MapLegendLayerVisibility } from './MapLegend';
import { api } from '../../lib/api';

export interface Report {
  id: number;
  latitude: number;
  longitude: number;
  water_level: number;
  description?: string;
  image_url?: string;
  created_at: string;
}

interface MapComponentProps {
  className?: string;
  initialCenter?: [number, number]; // [lng, lat]
  initialZoom?: number;
  reports?: Report[];
  route?: GeoJSON.LineString | GeoJSON.FeatureCollection<GeoJSON.LineString> | null;
  currentLocation?: { lat: number; lng: number } | null;
}

const DELHI_COORDINATES: [number, number] = [77.1025, 28.7041];

const DEFAULT_SENSORS: GeoJSON.FeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [77.209, 28.6139] },
      properties: { id: 's-1', name: 'Connaught Place Sensor', status: 'active' },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [77.230, 28.6400] },
      properties: { id: 's-2', name: 'ITO Sensor', status: 'warning' },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [77.1025, 28.7041] },
      properties: { id: 's-3', name: 'North Delhi Sensor', status: 'active' },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [77.2890, 28.5700] },
      properties: { id: 's-4', name: 'South Delhi Sensor', status: 'critical' },
    },
  ],
};

const escapeHtml = (value: string) =>
  value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

const getString = (value: unknown): string | null => (typeof value === 'string' ? value : null);
const getNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
};
const getBoolean = (value: unknown): boolean | null => (typeof value === 'boolean' ? value : null);

const normalizeLevel = (value: unknown): string | null => {
  const raw = getString(value);
  if (!raw) return null;
  return raw.trim().toLowerCase();
};

const getRiskLevelAndColor = (probability: number): { risk_level: string; risk_color: string } => {
  if (probability < 0.25) return { risk_level: 'low', risk_color: '#22c55e' };
  if (probability < 0.5) return { risk_level: 'moderate', risk_color: '#eab308' };
  if (probability < 0.75) return { risk_level: 'high', risk_color: '#f97316' };
  return { risk_level: 'extreme', risk_color: '#ef4444' };
};

const getFhiLevelAndColor = (score: number): { fhi_level: string; fhi_color: string } => {
  if (score < 0.2) return { fhi_level: 'low', fhi_color: '#22c55e' };
  if (score < 0.4) return { fhi_level: 'moderate', fhi_color: '#eab308' };
  if (score < 0.7) return { fhi_level: 'high', fhi_color: '#f97316' };
  return { fhi_level: 'extreme', fhi_color: '#ef4444' };
};

const severityToBaseProbability = (severity: string | null): number => {
  const s = severity?.toLowerCase() ?? '';
  if (s.includes('extreme') || s.includes('critical') || s.includes('severe')) return 0.85;
  if (s.includes('high')) return 0.65;
  if (s.includes('low')) return 0.25;
  if (s.includes('moderate') || s.includes('medium')) return 0.45;
  return 0.45;
};

const normalizeProbability = (value: number | null): number | null => {
  if (value === null) return null;
  if (value > 1 && value <= 100) return clamp01(value / 100);
  return clamp01(value);
};

const normalizeHotspots = (fc: GeoJSON.FeatureCollection): GeoJSON.FeatureCollection => {
  return {
    ...fc,
    features: fc.features.map((feature) => {
      const rawProps = feature.properties;
      const props: Record<string, unknown> =
        rawProps && typeof rawProps === 'object' ? (rawProps as Record<string, unknown>) : {};

      const parseFhiObject = (): Record<string, unknown> | null => {
        const raw = props.fhi;
        if (!raw) return null;
        if (typeof raw === 'string') {
          try {
            const parsed = JSON.parse(raw) as unknown;
            if (parsed && typeof parsed === 'object') return parsed as Record<string, unknown>;
          } catch {
            return null;
          }
          return null;
        }
        if (raw && typeof raw === 'object') return raw as Record<string, unknown>;
        return null;
      };

      const fhiObj = parseFhiObject();

      const id = getNumber(props.id) ?? 0;
      const name = getString(props.name) ?? 'Unknown';
      const zone = getString(props.zone) ?? 'unknown';
      const description = getString(props.description) ?? '';

      const source = normalizeLevel(props.source) ?? 'mcd_reports';
      const verified = getBoolean(props.verified) ?? (source === 'mcd_reports');
      const osmId = getNumber(props.osm_id);

      const historicalSeverity = getString(props.historical_severity) ?? getString(props.severity_history) ?? 'unknown';

      const riskProb =
        normalizeProbability(getNumber(props.risk_probability)) ??
        normalizeProbability(getNumber(props.adjusted_prob)) ??
        normalizeProbability(getNumber(props.xgboost_prob)) ??
        normalizeProbability(getNumber(props.risk_score)) ??
        severityToBaseProbability(historicalSeverity);

      const { risk_level, risk_color } = getRiskLevelAndColor(riskProb);

      const fhiScore =
        normalizeProbability(getNumber(props.fhi_score)) ?? (fhiObj ? normalizeProbability(getNumber(fhiObj.fhi_score)) : null);
      const fhiDerived = fhiScore !== null ? getFhiLevelAndColor(fhiScore) : null;
      const fhi_level =
        normalizeLevel(props.fhi_level) ??
        (fhiObj ? normalizeLevel(fhiObj.fhi_level) : null) ??
        fhiDerived?.fhi_level;
      const fhi_color =
        getString(props.fhi_color) ??
        (fhiObj ? getString(fhiObj.fhi_color) : null) ??
        fhiDerived?.fhi_color;
      const elevation_m = getNumber(props.elevation_m) ?? (fhiObj ? getNumber(fhiObj.elevation_m) : null);

      const nextProps: Record<string, unknown> = {
        ...props,
        id,
        name,
        zone,
        description,
        risk_probability: riskProb,
        risk_level,
        risk_color,
        historical_severity: historicalSeverity,
        source,
        verified,
        osm_id: osmId ?? undefined,
        fhi_score: fhiScore ?? undefined,
        fhi_level: fhi_level ?? undefined,
        fhi_color: fhi_color ?? undefined,
        elevation_m: elevation_m ?? undefined,
      };

      return {
        ...feature,
        properties: nextProps,
      };
    }),
  };
};

export function MapComponent({ 
  className = "h-full w-full",
  initialCenter = DELHI_COORDINATES,
  initialZoom = 11,
  reports = [],
  route = null,
  currentLocation = null
}: MapComponentProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [mapStyleReady, setMapStyleReady] = useState(false);
  const [hotspotsData, setHotspotsData] = useState<GeoJSON.FeatureCollection | null>(null);
  const fhiCacheRef = useRef(new Map<string, {
    fhi_score: number;
    fhi_level: string;
    fhi_color: string;
    elevation_m: number;
    components: Record<string, number>;
    monsoon_modifier: number;
    rain_gated: boolean;
    correction_factor: number;
    precip_prob_max: number;
  }>());
  const [layerVisibility, setLayerVisibility] = useState<MapLegendLayerVisibility>({
    hotspots: true,
    sensors: true,
    reports: true,
    route: true,
    floodAreas: true,
    metroLines: true,
    metroStations: true,
  });

  const fetchFhiForLocation = useCallback(async (lat: number, lng: number) => {
    const cacheKey = `${lat.toFixed(4)},${lng.toFixed(4)}`;
    const cached = fhiCacheRef.current.get(cacheKey);
    if (cached) return cached;

    const ELEVATION_URL = 'https://api.open-meteo.com/v1/elevation';
    const FORECAST_URL = 'https://api.open-meteo.com/v1/forecast';

    const elevationReq = fetch(`${ELEVATION_URL}?latitude=${lat}&longitude=${lng}`);
    const forecastReq = fetch(
      `${FORECAST_URL}?latitude=${lat}&longitude=${lng}` +
        `&hourly=precipitation,soil_moisture_0_to_7cm,surface_pressure` +
        `&daily=precipitation_probability_max` +
        `&forecast_days=3&timezone=auto`,
    );

    const [elevationRes, forecastRes] = await Promise.all([elevationReq, forecastReq]);
    if (!elevationRes.ok || !forecastRes.ok) {
      throw new Error('Failed to fetch FHI inputs');
    }

    const elevationJson = (await elevationRes.json()) as unknown;
    const forecastJson = (await forecastRes.json()) as unknown;

    const elevationList =
      elevationJson && typeof elevationJson === 'object'
        ? (elevationJson as Record<string, unknown>).elevation
        : undefined;
    const elevation_m =
      Array.isArray(elevationList) && typeof elevationList[0] === 'number' ? elevationList[0] : 220.0;

    const hourly =
      forecastJson && typeof forecastJson === 'object'
        ? (forecastJson as Record<string, unknown>).hourly
        : undefined;
    const daily =
      forecastJson && typeof forecastJson === 'object' ? (forecastJson as Record<string, unknown>).daily : undefined;

    const hourlyObj = hourly && typeof hourly === 'object' ? (hourly as Record<string, unknown>) : {};
    const dailyObj = daily && typeof daily === 'object' ? (daily as Record<string, unknown>) : {};

    const precipitation = Array.isArray(hourlyObj.precipitation) ? hourlyObj.precipitation : [];
    const soilMoisture = Array.isArray(hourlyObj.soil_moisture_0_to_7cm) ? hourlyObj.soil_moisture_0_to_7cm : [];
    const surfacePressure = Array.isArray(hourlyObj.surface_pressure) ? hourlyObj.surface_pressure : [];

    const precipValues = precipitation.map((v) => (typeof v === 'number' && Number.isFinite(v) ? v : 0));
    const soilValues = soilMoisture.map((v) => (typeof v === 'number' && Number.isFinite(v) ? v : 0.2));
    const pressureValues = surfacePressure.map((v) => (typeof v === 'number' && Number.isFinite(v) ? v : 1013));

    const sum = (arr: number[], start: number, end: number) => arr.slice(start, end).reduce((a, b) => a + b, 0);
    const precip_24h = sum(precipValues, 0, 24);
    const precip_48h = sum(precipValues, 24, 48);
    const precip_72h = sum(precipValues, 48, 72);
    const precip_3d_raw = precip_24h + precip_48h + precip_72h;

    const probValues = Array.isArray(dailyObj.precipitation_probability_max) ? dailyObj.precipitation_probability_max : [];
    const precip_prob_max = Math.max(
      ...probValues
        .map((v) => (typeof v === 'number' && Number.isFinite(v) ? v : null))
        .filter((v): v is number => v !== null),
      50,
    );

    const BASE_PRECIP_CORRECTION = 1.5;
    const PROB_BOOST_MULTIPLIER = 0.5;
    const MIN_RAIN_THRESHOLD_MM = 5.0;
    const LOW_FHI_CAP = 0.15;
    const PRECIP_THRESHOLD_MM = 64.4;
    const INTENSITY_THRESHOLD_MM_H = 50.0;
    const SOIL_SATURATION_MAX = 0.5;
    const ANTECEDENT_THRESHOLD_MM = 150.0;
    const PRESSURE_BASELINE_HPA = 1013;
    const URBAN_SATURATION_THRESHOLD_MM = 50.0;
    const DELHI_ELEV_MIN = 190;
    const DELHI_ELEV_MAX = 320;

    const probBoost = 1 + (precip_prob_max / 100) * PROB_BOOST_MULTIPLIER;
    const correction_factor = BASE_PRECIP_CORRECTION * probBoost;

    const P = Math.min(
      1,
      0.5 * ((precip_24h * correction_factor) / PRECIP_THRESHOLD_MM) +
        0.3 * ((precip_48h * correction_factor) / PRECIP_THRESHOLD_MM) +
        0.2 * ((precip_72h * correction_factor) / PRECIP_THRESHOLD_MM),
    );

    const hourlyMax = precipValues.slice(0, 24).reduce((m, v) => (v > m ? v : m), 0);
    const I = Math.min(1, (hourlyMax * correction_factor) / INTENSITY_THRESHOLD_MM_H);

    const antecedentProxy = Math.min(1, precip_3d_raw / URBAN_SATURATION_THRESHOLD_MM);
    const soilAvg = soilValues.slice(0, 24).reduce((a, b) => a + b, 0) / Math.max(1, soilValues.slice(0, 24).length);
    const soilNorm = Math.min(1, soilAvg / SOIL_SATURATION_MAX);
    const S = 0.7 * antecedentProxy + 0.3 * soilNorm;

    const A = Math.min(1, (precip_3d_raw * correction_factor) / ANTECEDENT_THRESHOLD_MM);

    const pressureAvg =
      pressureValues.slice(0, 24).reduce((a, b) => a + b, 0) / Math.max(1, pressureValues.slice(0, 24).length);
    const R = Math.min(1, Math.max(0, (PRESSURE_BASELINE_HPA - pressureAvg) / 30.0));

    const elevClamped = Math.max(DELHI_ELEV_MIN, Math.min(DELHI_ELEV_MAX, elevation_m));
    const E = 1 - (elevClamped - DELHI_ELEV_MIN) / (DELHI_ELEV_MAX - DELHI_ELEV_MIN);

    const nowMonth = new Date().getMonth() + 1;
    const monsoon_modifier = [6, 7, 8, 9].includes(nowMonth) ? 1.2 : 1.0;

    const fhi_raw = (0.35 * P + 0.18 * I + 0.12 * S + 0.12 * A + 0.08 * R + 0.15 * E) * monsoon_modifier;
    let fhi_score = clamp01(fhi_raw);

    let rain_gated = false;
    if (precip_3d_raw < MIN_RAIN_THRESHOLD_MM) {
      fhi_score = Math.min(fhi_score, LOW_FHI_CAP);
      rain_gated = true;
    }

    const { fhi_level, fhi_color } = getFhiLevelAndColor(fhi_score);

    const result = {
      fhi_score: Math.round(fhi_score * 1000) / 1000,
      fhi_level,
      fhi_color,
      elevation_m: Math.round(elevation_m * 10) / 10,
      components: {
        P: Math.round(P * 1000) / 1000,
        I: Math.round(I * 1000) / 1000,
        S: Math.round(S * 1000) / 1000,
        A: Math.round(A * 1000) / 1000,
        R: Math.round(R * 1000) / 1000,
        E: Math.round(E * 1000) / 1000,
      },
      monsoon_modifier,
      rain_gated,
      correction_factor: Math.round(correction_factor * 100) / 100,
      precip_prob_max: Math.round(precip_prob_max),
    };

    fhiCacheRef.current.set(cacheKey, result);
    return result;
  }, []);

  // Initialize Map
  useEffect(() => {
    if (map.current || !mapContainer.current) return;

    // Initialize PMTiles protocol
    const protocol = new Protocol();
    maplibregl.addProtocol('pmtiles', protocol.tile);

    // Construct style programmatically to ensure valid URLs and fallback
    const styleSpec: maplibregl.StyleSpecification = {
      version: 8,
      sources: {
        'osm': {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '&copy; OpenStreetMap Contributors'
        },
        'flood-tiles': {
          type: 'vector',
          url: `pmtiles://${window.location.origin}/delhi-tiles.pmtiles`
        }
      },
      layers: [
        {
          id: 'osm',
          type: 'raster',
          source: 'osm',
          minzoom: 0,
          maxzoom: 19
        },
        {
          id: 'flood-layer',
          type: 'fill',
          source: 'flood-tiles',
          'source-layer': 'flood',
          paint: {
            'fill-color': '#519EA2',
            'fill-opacity': 0.6
          }
        }
      ]
    };

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: styleSpec,
      center: initialCenter,
      zoom: initialZoom,
      attributionControl: { compact: true },
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'bottom-right');
    
    map.current.addControl(
      new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: true
      }),
      'bottom-right'
    );

    map.current.on('load', () => {
      setIsLoaded(true);
    });

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, [initialCenter, initialZoom]);

  // Track when map style is fully ready (Legacy Logic)
  useEffect(() => {
    if (!map.current || !isLoaded) {
      setMapStyleReady(false);
      return;
    }

    const checkStyleReady = () => {
      try {
        if (!map.current?.isStyleLoaded() || !map.current?.getStyle()?.sources) return false;
        return true;
      } catch {
        return false;
      }
    };

    // Check immediately
    if (checkStyleReady()) {
      setMapStyleReady(true);
      return;
    }

    const onStyleLoad = () => {
      if (checkStyleReady()) {
        setMapStyleReady(true);
        map.current?.off('styledata', onStyleLoad);
      }
    };

    map.current.on('styledata', onStyleLoad);

    return () => {
      map.current?.off('styledata', onStyleLoad);
    };
  }, [isLoaded]);

  // Fetch hotspots
  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      const delaysMs = [0, 500, 1500, 3000, 6000];

      for (let attempt = 0; attempt < delaysMs.length; attempt += 1) {
        const delay = delaysMs[attempt];
        if (delay > 0) {
          await new Promise((resolve) => setTimeout(resolve, delay));
        }

        try {
          const res = await api.get<GeoJSON.FeatureCollection>('/hotspots/');
          if (cancelled) return;
          setHotspotsData(normalizeHotspots(res.data));
          return;
        } catch (err) {
          if (attempt === delaysMs.length - 1) {
            console.error('Failed to load hotspots:', err);
          }
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  // Update Layers when style is ready
  useEffect(() => {
    if (!map.current || !isLoaded || !mapStyleReady) return;

    const currentMap = map.current;
    const setVisibility = (layerId: string, isVisible: boolean) => {
      if (!currentMap.getLayer(layerId)) return;
      currentMap.setLayoutProperty(layerId, 'visibility', isVisible ? 'visible' : 'none');
    };

    const getPointCoordinates = (feature: maplibregl.MapGeoJSONFeature): [number, number] | null => {
      const geometry = feature.geometry;
      if (!geometry || geometry.type !== 'Point') return null;
      const coordinates = geometry.coordinates;
      if (!Array.isArray(coordinates) || coordinates.length < 2) return null;
      const [lng, lat] = coordinates;
      if (typeof lng !== 'number' || typeof lat !== 'number') return null;
      return [lng, lat];
    };

    // 1. Add Hotspots Source & Layer
    if (hotspotsData) {
      if (!currentMap.getSource('hotspots')) {
        currentMap.addSource('hotspots', {
          type: 'geojson',
          data: hotspotsData
        });

        // Add hotspot layer (heatmap/circles)
        currentMap.addLayer({
          id: 'hotspots-layer',
          type: 'circle',
          source: 'hotspots',
          paint: {
            'circle-radius': 15,
            'circle-color': ['coalesce', ['get', 'fhi_color'], ['get', 'risk_color'], '#eab308'],
            'circle-opacity': 0.6,
            'circle-stroke-width': 2,
            'circle-stroke-color': '#ffffff'
          }
        });
        setVisibility('hotspots-layer', layerVisibility.hotspots);

        // Add popup for hotspots
        currentMap.on('click', 'hotspots-layer', (e) => {
           if (!e.features || e.features.length === 0) return;
           const feature = e.features[0];
           const props = feature.properties as unknown as Record<string, unknown> | null;
           if (!props) return;
           const coordinates = getPointCoordinates(feature);
           if (!coordinates) return;

           const parseFhiFromProps = (): {
             fhi_score: number | null;
             fhi_level: string | null;
             fhi_color: string | null;
             elevation_m: number | null;
           } => {
             const fhiObj = (() => {
               const raw = props.fhi;
               if (!raw) return null;
               if (typeof raw === 'string') {
                 try {
                   const parsed = JSON.parse(raw) as unknown;
                   if (parsed && typeof parsed === 'object') return parsed as Record<string, unknown>;
                 } catch {
                   return null;
                 }
                 return null;
               }
               if (raw && typeof raw === 'object') return raw as Record<string, unknown>;
               return null;
             })();

             const fhi_score =
               normalizeProbability(getNumber(props.fhi_score)) ??
               (fhiObj ? normalizeProbability(getNumber(fhiObj.fhi_score)) : null);
             const derived = fhi_score !== null ? getFhiLevelAndColor(fhi_score) : null;
             const fhi_level =
               normalizeLevel(props.fhi_level) ??
               (fhiObj ? normalizeLevel(fhiObj.fhi_level) : null) ??
               derived?.fhi_level ??
               null;
             const fhi_color =
               getString(props.fhi_color) ??
               (fhiObj ? getString(fhiObj.fhi_color) : null) ??
               derived?.fhi_color ??
               null;
             const elevation_m = getNumber(props.elevation_m) ?? (fhiObj ? getNumber(fhiObj.elevation_m) : null);

             return { fhi_score, fhi_level, fhi_color, elevation_m };
           };

           const parseRiskFromProps = (): {
             risk_probability: number;
             risk_level: string;
             risk_color: string;
             rainfall_24h_mm: number | null;
           } => {
             const risk_probability =
               normalizeProbability(getNumber(props.risk_probability)) ??
               normalizeProbability(getNumber(props.adjusted_prob)) ??
               normalizeProbability(getNumber(props.xgboost_prob)) ??
               normalizeProbability(getNumber(props.risk_score)) ??
               severityToBaseProbability(getString(props.historical_severity) ?? getString(props.severity_history) ?? getString(props.severity));
             const mapped = getRiskLevelAndColor(risk_probability);
             const risk_level = normalizeLevel(props.risk_level) ?? mapped.risk_level;
             const risk_color = getString(props.risk_color) ?? mapped.risk_color;
             const rainfall_24h_mm = getNumber(props.rainfall_24h_mm) ?? getNumber(props.rainfall_factor);
             return { risk_probability, risk_level, risk_color, rainfall_24h_mm };
           };

           const buildPopupHtml = (data: {
             name: string;
             description: string;
             id: number | null;
             zone: string | null;
             source: string | null;
             verified: boolean | null;
             osm_id: number | null;
             historical_severity: string | null;
             risk_probability: number;
             risk_level: string;
             risk_color: string;
             rainfall_24h_mm: number | null;
             fhi_score: number | null;
             fhi_level: string | null;
             fhi_color: string | null;
             elevation_m: number | null;
             fhi_loading: boolean;
           }) => {
             const riskPct = Math.round(data.risk_probability * 100);
             const fhiPct = data.fhi_score !== null ? Math.round(data.fhi_score * 100) : null;
             const primaryColor = data.fhi_color ?? data.risk_color;

             return `
               <div class="p-3 min-w-[200px]" style="max-width: min(360px, calc(100vw - 32px))">
                 <div class="flex items-center gap-2 mb-2">
                   <div class="w-3 h-3 rounded-full" style="background-color: ${primaryColor}"></div>
                   <h3 class="font-bold text-sm">Waterlogging Hotspot</h3>
                 </div>
                 <p class="text-sm font-medium text-gray-800 mb-2">${escapeHtml(data.name)}</p>

                 ${
                   data.fhi_score !== null
                     ? `
                 <div class="text-xs space-y-1 text-gray-600 pt-2 pb-2">
                   <div class="flex items-center justify-between mb-1">
                     <span class="text-gray-500 flex items-center gap-1">
                       <span class="w-2 h-2 rounded-full animate-pulse" style="background-color: ${data.fhi_color ?? '#9ca3af'}"></span>
                       Live Flood Risk
                     </span>
                     <span class="px-2 py-0.5 rounded text-xs font-bold" style="background-color: ${(data.fhi_color ?? '#9ca3af')}20; color: ${data.fhi_color ?? '#9ca3af'}">
                       ${(data.fhi_level ?? 'N/A').toUpperCase()}
                     </span>
                   </div>
                   <div class="flex items-center gap-2">
                     <div class="flex-1 bg-gray-200 rounded-full h-2.5">
                       <div class="h-2.5 rounded-full transition-all" style="width: ${fhiPct}%; background-color: ${data.fhi_color ?? '#9ca3af'}"></div>
                     </div>
                     <span class="text-sm font-bold" style="color: ${data.fhi_color ?? '#9ca3af'}">
                       ${fhiPct}%
                     </span>
                   </div>
                   ${data.elevation_m !== null ? `<div class="text-xs text-gray-400 mt-1">Elevation: ${data.elevation_m.toFixed(1)}m</div>` : ''}
                   ${
                     data.verified !== null
                       ? `<div class="text-xs mt-1 ${data.verified ? 'text-green-600' : 'text-amber-600'}">${data.verified ? '✓ Verified' : '⚠ ML Predicted (OSM)'}</div>`
                       : ''
                   }
                   <p class="text-gray-400 text-[10px] italic mt-1">Based on current weather conditions</p>
                 </div>
                 `
                     : data.fhi_loading
                       ? `
                 <div class="text-xs text-gray-500 pt-2 pb-2">
                   <div class="flex items-center justify-between">
                     <span class="text-gray-500 flex items-center gap-1">
                       <span class="w-2 h-2 rounded-full animate-pulse bg-gray-300"></span>
                       Live Flood Risk
                     </span>
                     <span class="text-[10px] text-gray-400">Loading…</span>
                   </div>
                 </div>
                 `
                       : ''
                 }

                 <div class="text-xs space-y-1 text-gray-500 ${data.fhi_score !== null || data.fhi_loading ? 'mt-2 pt-2 border-t border-gray-200' : 'pt-2'}">
                   <div class="flex justify-between items-center">
                     <span class="text-gray-400">Base Risk (ML)</span>
                     <span class="px-1.5 py-0.5 rounded text-[10px] font-medium" style="background-color: ${data.risk_color}15; color: ${data.risk_color}">
                       ${data.risk_level.toUpperCase()}
                     </span>
                   </div>
                   <div class="flex items-center gap-2">
                     <div class="flex-1 bg-gray-100 rounded-full h-1.5">
                       <div class="h-1.5 rounded-full transition-all" style="width: ${riskPct}%; background-color: ${data.risk_color}"></div>
                     </div>
                     <span class="text-xs" style="color: ${data.risk_color}">${riskPct}%</span>
                   </div>
                   ${data.rainfall_24h_mm !== null ? `<p class="text-gray-400 text-[10px] italic">Rainfall (24h): ${data.rainfall_24h_mm.toFixed(1)}mm</p>` : `<p class="text-gray-300 text-[9px] italic">Terrain & land cover baseline</p>`}
                 </div>

                 <div class="text-xs text-gray-500 mt-2 pt-2 border-t space-y-1">
                   ${data.id !== null ? `<div><strong>ID:</strong> ${data.id}</div>` : ''}
                   ${data.zone ? `<div><strong>Zone:</strong> ${escapeHtml(data.zone)}</div>` : ''}
                   ${data.source ? `<div><strong>Source:</strong> ${escapeHtml(data.source)}</div>` : ''}
                   ${data.osm_id !== null ? `<div><strong>OSM ID:</strong> ${data.osm_id}</div>` : ''}
                   ${data.historical_severity ? `<div><strong>Historical:</strong> ${escapeHtml(data.historical_severity)}</div>` : ''}
                 </div>

                 ${data.description ? `<p class="text-xs text-gray-600 mt-2">${escapeHtml(data.description)}</p>` : ''}
               </div>
             `;
           };

           const name = getString(props.name) ?? 'Unknown Location';
           const description = getString(props.description) ?? '';
           const id = getNumber(props.id);
           const zone = getString(props.zone);
           const source = normalizeLevel(props.source) ?? getString(props.source);
           const verified = getBoolean(props.verified);
           const osm_id = getNumber(props.osm_id);
           const historical_severity = getString(props.historical_severity) ?? getString(props.severity_history) ?? getString(props.severity);

           const risk = parseRiskFromProps();
           const fhi = parseFhiFromProps();

           const popup = new maplibregl.Popup({ offset: 15 })
             .setLngLat(coordinates)
             .setHTML(
               buildPopupHtml({
                 name,
                 description,
                 id,
                 zone,
                 source,
                 verified,
                 osm_id,
                 historical_severity,
                 ...risk,
                 ...fhi,
                 fhi_loading: fhi.fhi_score === null,
               }),
             )
             .addTo(currentMap);

           if (fhi.fhi_score === null) {
             const [lng, lat] = coordinates;
             void fetchFhiForLocation(lat, lng)
               .then((fhiResult) => {
                 popup.setHTML(
                   buildPopupHtml({
                     name,
                     description,
                     id,
                     zone,
                     source,
                     verified,
                     osm_id,
                     historical_severity,
                     ...risk,
                     ...fhiResult,
                     fhi_loading: false,
                   }),
                 );
               })
               .catch(() => {
                 popup.setHTML(
                   buildPopupHtml({
                     name,
                     description,
                     id,
                     zone,
                     source,
                     verified,
                     osm_id,
                     historical_severity,
                     ...risk,
                     ...fhi,
                     fhi_loading: false,
                   }),
                 );
               });
           }
        });

        // Cursor pointer
        currentMap.on('mouseenter', 'hotspots-layer', () => {
          currentMap.getCanvas().style.cursor = 'pointer';
        });
        currentMap.on('mouseleave', 'hotspots-layer', () => {
          currentMap.getCanvas().style.cursor = '';
        });
      } else {
        (currentMap.getSource('hotspots') as maplibregl.GeoJSONSource).setData(hotspotsData);
      }
    }

    // 2. Add Reports Source & Layer
    if (!currentMap.getSource('reports')) {
      currentMap.addSource('reports', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: []
        }
      });

      currentMap.addLayer({
        id: 'reports-circles',
        type: 'circle',
        source: 'reports',
        paint: {
          'circle-radius': 8,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
          'circle-color': [
            'match',
            ['get', 'water_level'],
            0, '#3b82f6', // None/Info - Blue
            1, '#eab308', // Low - Yellow
            2, '#f97316', // Medium - Orange
            3, '#ef4444', // High - Red
            '#3b82f6'     // Default
          ]
        }
      });
      setVisibility('reports-circles', layerVisibility.reports);

      // Add click handler for popups
      currentMap.on('click', 'reports-circles', (e) => {
        if (!e.features || e.features.length === 0) return;
        
        const feature = e.features[0];
        const coordinates = getPointCoordinates(feature);
        if (!coordinates) return;
        const props = feature.properties;

        if (!props) return;

        const description = `
          <div class="p-2 min-w-[200px]">
            <h3 class="font-bold text-sm mb-1">Flood Report</h3>
            ${props.image_url ? `<img src="http://localhost:8000${props.image_url}" class="w-full h-32 object-cover rounded-md mb-2" />` : ''}
            <p class="text-xs text-gray-600 mb-1">${props.description || 'No description provided'}</p>
            <div class="flex items-center gap-1 mt-2">
              <span class="text-xs px-2 py-0.5 rounded-full ${
                props.water_level === 3 ? 'bg-red-100 text-red-700' :
                props.water_level === 2 ? 'bg-orange-100 text-orange-700' :
                props.water_level === 1 ? 'bg-yellow-100 text-yellow-700' :
                'bg-blue-100 text-blue-700'
              }">
                Severity: ${['None', 'Low', 'Medium', 'High'][props.water_level] || 'Unknown'}
              </span>
            </div>
            <p class="text-[10px] text-gray-400 mt-1">${new Date(props.created_at).toLocaleString()}</p>
          </div>
        `;

        new maplibregl.Popup()
          .setLngLat(coordinates)
          .setHTML(description)
          .addTo(currentMap);
      });

      // Change cursor on hover
      currentMap.on('mouseenter', 'reports-circles', () => {
        currentMap.getCanvas().style.cursor = 'pointer';
      });
      currentMap.on('mouseleave', 'reports-circles', () => {
        currentMap.getCanvas().style.cursor = '';
      });
    }

    // Update Reports Data
    if (reports && currentMap.getSource('reports')) {
       const geojson: GeoJSON.FeatureCollection = {
        type: 'FeatureCollection',
        features: reports.map(report => ({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [report.longitude, report.latitude]
          },
          properties: {
            id: report.id,
            water_level: report.water_level,
            description: report.description,
            image_url: report.image_url,
            created_at: report.created_at
          }
        }))
      };
      (currentMap.getSource('reports') as maplibregl.GeoJSONSource).setData(geojson);
    }

    // 3. Add Route Source & Layer
    if (!currentMap.getSource('route')) {
      currentMap.addSource('route', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: []
        }
      });

      currentMap.addLayer({
        id: 'route-fastest',
        type: 'line',
        source: 'route',
        filter: ['==', ['get', 'route_type'], 'fastest'],
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': '#3b82f6',
          'line-width': 5,
          'line-opacity': 0.85,
          'line-offset': 2
        }
      });

      currentMap.addLayer({
        id: 'route-safest',
        type: 'line',
        source: 'route',
        filter: ['==', ['get', 'route_type'], 'safest'],
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': '#22c55e',
          'line-width': 5,
          'line-opacity': 0.85,
          'line-offset': -2
        }
      });

      setVisibility('route-fastest', layerVisibility.route);
      setVisibility('route-safest', layerVisibility.route);
    }

    // 4. Metro Lines
    if (!currentMap.getSource('metro-lines')) {
        currentMap.addSource('metro-lines', {
            type: 'geojson',
            data: '/delhi-metro-lines.geojson'
        });
        currentMap.addLayer({
            id: 'metro-lines',
            type: 'line',
            source: 'metro-lines',
            layout: {
                'line-join': 'round',
                'line-cap': 'round'
            },
            paint: {
                'line-color': ['get', 'colour'], // Note: 'colour' (British) in GeoJSON
                'line-width': 3,
                'line-opacity': 0.7
            }
        });
        setVisibility('metro-lines', layerVisibility.metroLines);
    }

    // 5. Metro Stations
    if (!currentMap.getSource('metro-stations')) {
        currentMap.addSource('metro-stations', {
            type: 'geojson',
            data: '/delhi-metro-stations.geojson'
        });
        currentMap.addLayer({
            id: 'metro-stations',
            type: 'circle',
            source: 'metro-stations',
            paint: {
                'circle-radius': 5,
                'circle-color': '#ffffff',
                'circle-stroke-width': 2,
                'circle-stroke-color': ['get', 'color'] // Note: 'color' (American) in GeoJSON
            }
        });
        setVisibility('metro-stations', layerVisibility.metroStations);

        currentMap.on('click', 'metro-stations', (e) => {
            if (!e.features || e.features.length === 0) return;
            const feature = e.features[0];
            const props = feature.properties;
            if (!props) return;

            const coordinates = getPointCoordinates(feature);
            if (!coordinates) return;
            const name = typeof props.name === 'string' ? props.name : 'Metro Station';
            const rawLine = typeof props.line === 'string' ? props.line : '';
            const cleanedLine = rawLine.trim();
            const lineLabel = cleanedLine
              ? cleanedLine.toLowerCase().endsWith(' line')
                ? cleanedLine
                : `${cleanedLine} Line`
              : '';
            new maplibregl.Popup()
                .setLngLat(coordinates)
                .setHTML(`
                    <div class="p-2">
                        <h3 class="font-bold text-sm">${escapeHtml(name)}</h3>
                        ${lineLabel ? `<p class="text-xs text-gray-600">${escapeHtml(lineLabel)}</p>` : ''}
                    </div>
                `)
                .addTo(currentMap);
        });
        
        currentMap.on('mouseenter', 'metro-stations', () => {
            currentMap.getCanvas().style.cursor = 'pointer';
        });
        currentMap.on('mouseleave', 'metro-stations', () => {
            currentMap.getCanvas().style.cursor = '';
        });
    }

    // 6. Sensors (Placeholder for Future Implementation)
    // Legend mentions: Active (Green), Warning (Orange), Critical (Red)
    if (!currentMap.getSource('sensors')) {
        currentMap.addSource('sensors', {
            type: 'geojson',
            data: DEFAULT_SENSORS
        });
        currentMap.addLayer({
            id: 'sensors-layer',
            type: 'circle',
            source: 'sensors',
            paint: {
                'circle-radius': 6,
                'circle-color': [
                    'match',
                    ['get', 'status'],
                    'active', '#22c55e',
                    'warning', '#f97316',
                    'critical', '#ef4444',
                    '#9ca3af'
                ],
                'circle-stroke-width': 1,
                'circle-stroke-color': '#ffffff'
            }
        });
        setVisibility('sensors-layer', layerVisibility.sensors);

        currentMap.on('click', 'sensors-layer', (e) => {
          if (!e.features || e.features.length === 0) return;
          const feature = e.features[0];
          const props = feature.properties as unknown as Record<string, unknown> | null;
          if (!props) return;
          const coordinates = getPointCoordinates(feature);
          if (!coordinates) return;

          const name = getString(props.name) ?? 'Sensor';
          const status = normalizeLevel(props.status) ?? 'unknown';
          const color =
            status === 'active' ? '#22c55e' : status === 'warning' ? '#f97316' : status === 'critical' ? '#ef4444' : '#9ca3af';

          new maplibregl.Popup({ offset: 12 })
            .setLngLat(coordinates)
            .setHTML(`
              <div class="p-2 min-w-[200px]">
                <div class="flex items-center gap-2 mb-1">
                  <div class="w-2.5 h-2.5 rounded-full" style="background-color: ${color}"></div>
                  <h3 class="font-bold text-sm">Sensor</h3>
                </div>
                <p class="text-xs text-gray-800 font-medium">${escapeHtml(name)}</p>
                <p class="text-xs text-gray-600">Status: ${escapeHtml(status)}</p>
              </div>
            `)
            .addTo(currentMap);
        });

        currentMap.on('mouseenter', 'sensors-layer', () => {
          currentMap.getCanvas().style.cursor = 'pointer';
        });
        currentMap.on('mouseleave', 'sensors-layer', () => {
          currentMap.getCanvas().style.cursor = '';
        });
    }

    if (!currentMap.getSource('user-location')) {
      currentMap.addSource('user-location', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      currentMap.addLayer({
        id: 'user-location',
        type: 'circle',
        source: 'user-location',
        paint: {
          'circle-radius': 6,
          'circle-color': '#3b82f6',
          'circle-opacity': 0.95,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
        },
      });
    }

    // Update Route Data
    if (currentMap.getSource('route')) {
      const toFeatureCollection = (): GeoJSON.FeatureCollection<GeoJSON.LineString> => {
        if (!route) return { type: 'FeatureCollection', features: [] };
        if ((route as GeoJSON.FeatureCollection).type === 'FeatureCollection') {
          return route as GeoJSON.FeatureCollection<GeoJSON.LineString>;
        }

        const line = route as GeoJSON.LineString;
        return {
          type: 'FeatureCollection',
          features: [
            { type: 'Feature', properties: { route_type: 'fastest' }, geometry: line },
            { type: 'Feature', properties: { route_type: 'safest' }, geometry: line },
          ],
        };
      };

      const fc = toFeatureCollection();
      (currentMap.getSource('route') as maplibregl.GeoJSONSource).setData(fc);

      const lineCoordinates = fc.features.flatMap((f) => (f.geometry?.coordinates ?? [])) as GeoJSON.Position[];
      if (lineCoordinates.length > 0) {
        const toLngLat = (pos: GeoJSON.Position): [number, number] | null => {
          const [lng, lat] = pos;
          if (typeof lng !== 'number' || typeof lat !== 'number') return null;
          return [lng, lat];
        };

        const first = toLngLat(lineCoordinates[0]);
        if (!first) return;

        const bounds = new maplibregl.LngLatBounds(first, first);
        for (const coord of lineCoordinates.slice(1)) {
          const lngLat = toLngLat(coord);
          if (lngLat) bounds.extend(lngLat);
        }

        currentMap.fitBounds(bounds, { padding: 50 });
      } 
    }

    if (currentMap.getSource('user-location')) {
      const next = currentLocation
        ? {
            type: 'FeatureCollection' as const,
            features: [
              {
                type: 'Feature' as const,
                geometry: {
                  type: 'Point' as const,
                  coordinates: [currentLocation.lng, currentLocation.lat],
                },
                properties: {},
              },
            ],
          }
        : { type: 'FeatureCollection' as const, features: [] };

      (currentMap.getSource('user-location') as maplibregl.GeoJSONSource).setData(next);
    }

  }, [currentLocation, fetchFhiForLocation, isLoaded, mapStyleReady, hotspotsData, reports, route, layerVisibility]);

  useEffect(() => {
    if (!map.current || !isLoaded || !mapStyleReady) return;

    const currentMap = map.current;
    const setVisibility = (layerId: string, isVisible: boolean) => {
      if (!currentMap.getLayer(layerId)) return;
      currentMap.setLayoutProperty(layerId, 'visibility', isVisible ? 'visible' : 'none');
    };

    setVisibility('flood-layer', layerVisibility.floodAreas);
    setVisibility('hotspots-layer', layerVisibility.hotspots);
    setVisibility('sensors-layer', layerVisibility.sensors);
    setVisibility('reports-circles', layerVisibility.reports);
    setVisibility('route-fastest', layerVisibility.route);
    setVisibility('route-safest', layerVisibility.route);
    setVisibility('metro-lines', layerVisibility.metroLines);
    setVisibility('metro-stations', layerVisibility.metroStations);
  }, [isLoaded, mapStyleReady, layerVisibility]);

  return (
    <div className="relative h-full w-full">
        <div ref={mapContainer} className={className} style={{ width: '100%', height: '100%', minHeight: '500px' }} />
        <MapLegend
          className="absolute bottom-8 left-4 z-50 w-64 max-w-[calc(100%-2rem)]"
          layerVisibility={layerVisibility}
          onToggleLayer={(layer: MapLegendLayerKey) => {
            setLayerVisibility((prev) => ({ ...prev, [layer]: !prev[layer] }));
          }}
        />
    </div>
  );
}
