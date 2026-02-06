import { useState } from 'react';
import { Navigation, Loader2 } from 'lucide-react';
import { api } from '../../lib/api';

type RouteGeometry = {
  type: 'LineString';
  coordinates: [number, number][];
};

type RouteResponse = {
  geometry: RouteGeometry;
  duration: number;
  distance: number;
  risk_score: number;
  alerts: string[];
};

interface NavigationPanelProps {
  currentLocation: { lat: number; lng: number } | null;
  onRouteCalculated: (routes: GeoJSON.FeatureCollection<GeoJSON.LineString>) => void;
}

export function NavigationPanel({ currentLocation, onRouteCalculated }: NavigationPanelProps) {
  const [destination, setDestination] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleCalculate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentLocation) {
      setError('Current location not found');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // 1. Geocode destination (using basic OSM Nominatim for prototype)
      // In production, use a proper geocoding service
      const geocodeRes = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(destination)}`);
      const geocodeData = (await geocodeRes.json()) as Array<{ lat: string; lon: string }>;
      
      if (!geocodeData || geocodeData.length === 0) {
        throw new Error('Destination not found');
      }

      const destLat = parseFloat(geocodeData[0].lat);
      const destLng = parseFloat(geocodeData[0].lon);

      // 2. Calculate safe route via backend
      const { data } = await api.post<RouteResponse[]>('/routes/calculate', {
        origin: [currentLocation.lng, currentLocation.lat],
        destination: [destLng, destLat],
        mode: 'driving'
      });

      if (data && data.length > 0) {
        const safest =
          data.reduce<RouteResponse>((best, next) => (next.risk_score < best.risk_score ? next : best), data[0]);
        const fastest =
          data.reduce<RouteResponse>((best, next) => (next.duration < best.duration ? next : best), data[0]);

        onRouteCalculated({
          type: 'FeatureCollection',
          features: [
            {
              type: 'Feature',
              properties: {
                route_type: 'fastest',
                duration: fastest.duration,
                distance: fastest.distance,
                risk_score: fastest.risk_score,
              },
              geometry: fastest.geometry,
            },
            {
              type: 'Feature',
              properties: {
                route_type: 'safest',
                duration: safest.duration,
                distance: safest.distance,
                risk_score: safest.risk_score,
              },
              geometry: safest.geometry,
            },
          ],
        });
      } else {
        setError('No safe route found');
      }
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Routing failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="absolute top-4 right-4 z-10 w-80 bg-background/95 backdrop-blur shadow-lg border rounded-xl p-4">
      <h3 className="font-semibold flex items-center gap-2 mb-3">
        <Navigation className="h-4 w-4 text-blue-500" />
        Safe Navigation
      </h3>
      
      <form onSubmit={handleCalculate} className="space-y-3">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Destination</label>
          <input
            type="text"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            placeholder="Search destination..."
            className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            required
          />
        </div>

        {error && <p className="text-xs text-red-500">{error}</p>}

        <button
          type="submit"
          disabled={loading || !currentLocation}
          className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2 rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Find Safe Route'}
        </button>
      </form>
    </div>
  );
}
