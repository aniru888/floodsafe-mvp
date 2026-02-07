import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from './ui/dialog';
import SearchBar from './SearchBar';
import { Button } from './ui/button';
import { useCreateDailyRoute } from '../lib/api/hooks';
import { useAuth } from '../contexts/AuthContext';
import { useCityContext } from '../contexts/CityContext';
import { toast } from 'sonner';
import { Car, PersonStanding, Train, RefreshCw } from 'lucide-react';
import { cn } from '../lib/utils';

interface AddDailyRouteDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

type TransportMode = 'driving' | 'walking' | 'metro' | 'combined';

interface LocationData {
    lat: number;
    lng: number;
    name: string;
}

export default function AddDailyRouteDialog({ open, onOpenChange }: AddDailyRouteDialogProps) {
    const { user } = useAuth();
    const { city: cityKey } = useCityContext();
    const createRoute = useCreateDailyRoute();

    // Form state
    const [name, setName] = useState('');
    const [origin, setOrigin] = useState<LocationData | null>(null);
    const [destination, setDestination] = useState<LocationData | null>(null);
    const [mode, setMode] = useState<TransportMode>('driving');
    const [notify, setNotify] = useState(true);

    // Transport mode options
    const modes = [
        { value: 'driving' as TransportMode, icon: Car, label: 'Driving' },
        { value: 'walking' as TransportMode, icon: PersonStanding, label: 'Walking' },
        { value: 'metro' as TransportMode, icon: Train, label: 'Metro' },
        { value: 'combined' as TransportMode, icon: RefreshCw, label: 'All' }
    ];

    // Handle origin selection from SearchBar
    const handleOriginSelect = (lat: number, lng: number, locationName: string) => {
        setOrigin({ lat, lng, name: locationName });
    };

    // Handle destination selection from SearchBar
    const handleDestinationSelect = (lat: number, lng: number, locationName: string) => {
        setDestination({ lat, lng, name: locationName });
    };

    // Validate and submit form
    const handleSubmit = () => {
        // Validation
        if (!name.trim()) {
            toast.error('Please enter a route name');
            return;
        }

        if (name.trim().length < 3 || name.trim().length > 100) {
            toast.error('Route name must be between 3 and 100 characters');
            return;
        }

        if (!origin) {
            toast.error('Please select a starting point');
            return;
        }

        if (!destination) {
            toast.error('Please select a destination');
            return;
        }

        if (!user) {
            toast.error('You must be logged in to add a route');
            return;
        }

        // Submit to backend
        createRoute.mutate({
            user_id: user.id,
            name: name.trim(),
            origin_latitude: origin.lat,
            origin_longitude: origin.lng,
            destination_latitude: destination.lat,
            destination_longitude: destination.lng,
            transport_mode: mode,
            notify_on_flood: notify
        }, {
            onSuccess: () => {
                toast.success('Route added!');
                resetForm();
                onOpenChange(false);
            },
            onError: (error) => {
                console.error('Failed to add route:', error);
                toast.error('Failed to add route. Please try again.');
            }
        });
    };

    // Reset form to initial state
    const resetForm = () => {
        setName('');
        setOrigin(null);
        setDestination(null);
        setMode('driving');
        setNotify(true);
    };

    // Reset form when dialog closes
    const handleOpenChange = (newOpen: boolean) => {
        if (!newOpen) {
            resetForm();
        }
        onOpenChange(newOpen);
    };

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Add Daily Route</DialogTitle>
                    <DialogDescription>
                        Set up a daily commute route to receive flood alerts when it's affected.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* Route Name */}
                    <div className="space-y-2">
                        <label htmlFor="route-name" className="text-sm font-medium text-foreground">
                            Route Name <span className="text-red-500">*</span>
                        </label>
                        <input
                            id="route-name"
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="e.g., Work Commute, School Run"
                            className="w-full px-3 py-2 text-sm border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                            maxLength={100}
                        />
                        <p className="text-xs text-muted-foreground">
                            {name.length}/100 characters
                        </p>
                    </div>

                    {/* Starting Point */}
                    <div className="space-y-2">
                        <label htmlFor="origin-search" className="text-sm font-medium text-foreground">
                            Starting Point <span className="text-red-500">*</span>
                        </label>
                        <SearchBar
                            onLocationSelect={handleOriginSelect}
                            cityKey={cityKey}
                            placeholder="Search for origin..."
                            className="relative"
                        />
                        {origin && (
                            <p className="text-xs text-green-600 flex items-center gap-1">
                                <span className="inline-block w-2 h-2 bg-green-600 rounded-full"></span>
                                {origin.name}
                            </p>
                        )}
                    </div>

                    {/* Destination */}
                    <div className="space-y-2">
                        <label htmlFor="destination-search" className="text-sm font-medium text-foreground">
                            Destination <span className="text-red-500">*</span>
                        </label>
                        <SearchBar
                            onLocationSelect={handleDestinationSelect}
                            cityKey={cityKey}
                            placeholder="Search for destination..."
                            className="relative"
                        />
                        {destination && (
                            <p className="text-xs text-green-600 flex items-center gap-1">
                                <span className="inline-block w-2 h-2 bg-green-600 rounded-full"></span>
                                {destination.name}
                            </p>
                        )}
                    </div>

                    {/* Transport Mode */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-foreground">
                            Transport Mode
                        </label>
                        <div className="grid grid-cols-4 gap-2">
                            {modes.map(({ value, icon: Icon, label }) => (
                                <button
                                    key={value}
                                    type="button"
                                    onClick={() => setMode(value)}
                                    className={cn(
                                        "flex flex-col items-center gap-1.5 p-3 rounded-lg border transition-all",
                                        mode === value
                                            ? "bg-purple-50 border-purple-500 text-purple-700 shadow-sm"
                                            : "bg-card border-border text-muted-foreground hover:bg-muted hover:border-border"
                                    )}
                                >
                                    <Icon className="w-5 h-5" />
                                    <span className="text-xs font-medium">{label}</span>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Notification Toggle */}
                    <div className="flex items-center gap-3 p-3 bg-muted rounded-lg">
                        <input
                            id="notify-checkbox"
                            type="checkbox"
                            checked={notify}
                            onChange={(e) => setNotify(e.target.checked)}
                            className="w-4 h-4 text-purple-600 border-border rounded focus:ring-ring cursor-pointer"
                        />
                        <label htmlFor="notify-checkbox" className="text-sm text-foreground cursor-pointer flex-1">
                            Notify me about floods on this route
                        </label>
                    </div>
                </div>

                <DialogFooter>
                    <Button
                        type="button"
                        variant="outline"
                        onClick={() => handleOpenChange(false)}
                        disabled={createRoute.isPending}
                    >
                        Cancel
                    </Button>
                    <Button
                        type="button"
                        onClick={handleSubmit}
                        disabled={createRoute.isPending}
                        className="bg-purple-600 hover:bg-purple-700"
                    >
                        {createRoute.isPending ? 'Adding...' : 'Add Route'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
