import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { Trash2, Plus, MapPin } from 'lucide-react';

interface WatchArea {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  radius_meters: number;
}

export function AlertsScreen() {
  const [watchAreas, setWatchAreas] = useState<WatchArea[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  
  // Form State
  const [name, setName] = useState('');
  const [currentLocation, setCurrentLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchWatchAreas();
    
    // Get location
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setCurrentLocation({
            lat: position.coords.latitude,
            lng: position.coords.longitude
          });
        }
      );
    }
  }, []);

  const fetchWatchAreas = async () => {
    try {
      const { data } = await api.get('/watch-areas/');
      setWatchAreas(data);
    } catch (error) {
      console.error('Failed to fetch watch areas', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentLocation) {
      alert("Location needed for watch area");
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/watch-areas/', {
        name,
        latitude: currentLocation.lat,
        longitude: currentLocation.lng,
        radius_meters: 500 // Default 500m
      });
      setShowAddForm(false);
      setName('');
      fetchWatchAreas();
    } catch {
      alert("Failed to create watch area");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this alert zone?")) return;
    try {
      await api.delete(`/watch-areas/${id}`);
      setWatchAreas(watchAreas.filter(wa => wa.id !== id));
    } catch {
      alert("Failed to delete");
    }
  };

  if (loading) return <div className="flex justify-center p-8">Loading...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Watch Areas</h2>
          <p className="text-muted-foreground">Get notified when flood risk rises in these zones.</p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          Add Area
        </button>
      </div>

      {showAddForm && (
        <div className="bg-card border rounded-xl p-6 animate-in fade-in slide-in-from-top-2">
          <h3 className="font-semibold mb-4">Add New Watch Area</h3>
          <form onSubmit={handleAdd} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Area Name (e.g. Home, Office)</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="My Home"
                required
              />
            </div>
            
            <div className="flex items-center gap-2 text-sm text-muted-foreground bg-muted/50 p-3 rounded-md">
              <MapPin className="h-4 w-4" />
              {currentLocation 
                ? `Current Location: ${currentLocation.lat.toFixed(4)}, ${currentLocation.lng.toFixed(4)}`
                : "Waiting for GPS..."}
            </div>

            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 text-sm hover:bg-muted rounded-md"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !currentLocation}
                className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm disabled:opacity-50"
              >
                {submitting ? "Saving..." : "Save Area"}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {watchAreas.length === 0 && !showAddForm ? (
          <div className="col-span-2 text-center py-12 text-muted-foreground border-2 border-dashed rounded-xl">
            No watch areas defined yet. Add one to get started!
          </div>
        ) : (
          watchAreas.map((area) => (
            <div key={area.id} className="bg-card border rounded-xl p-4 flex items-center justify-between shadow-sm">
              <div className="flex items-center gap-4">
                <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                  <MapPin className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="font-semibold">{area.name}</h4>
                  <p className="text-xs text-muted-foreground">Radius: {area.radius_meters}m</p>
                </div>
              </div>
              <button
                onClick={() => handleDelete(area.id)}
                className="p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-full transition-colors"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
