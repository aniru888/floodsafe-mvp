import { useState } from 'react';
import { Info } from 'lucide-react';
import { toast } from 'sonner';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import SearchBar from './SearchBar';
import { useCreateWatchArea } from '../lib/api/hooks';
import { useAuth } from '../contexts/AuthContext';
import { useCityContext } from '../contexts/CityContext';

interface AddWatchAreaDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

interface SelectedLocation {
    lat: number;
    lng: number;
    name: string;
}

export default function AddWatchAreaDialog({ open, onOpenChange }: AddWatchAreaDialogProps) {
    const { user } = useAuth();
    const { city: selectedCity } = useCityContext();
    const createArea = useCreateWatchArea();

    const [name, setName] = useState('');
    const [location, setLocation] = useState<SelectedLocation | null>(null);
    const [radius, setRadius] = useState(1000);
    const [errors, setErrors] = useState<{ name?: string; location?: string }>({});

    const handleLocationSelect = (lat: number, lng: number, locationName: string) => {
        setLocation({ lat, lng, name: locationName });
        setErrors((prev) => ({ ...prev, location: undefined }));
    };

    const formatRadius = (meters: number) => {
        if (meters < 1000) return `${meters} m`;
        return `${(meters / 1000).toFixed(1)} km`;
    };

    const validateForm = () => {
        const newErrors: { name?: string; location?: string } = {};

        if (!name.trim()) {
            newErrors.name = 'Area name is required';
        } else if (name.trim().length < 3) {
            newErrors.name = 'Area name must be at least 3 characters';
        } else if (name.trim().length > 100) {
            newErrors.name = 'Area name must be less than 100 characters';
        }

        if (!location) {
            newErrors.location = 'Please select a location';
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = () => {
        if (!validateForm() || !user || !location) {
            return;
        }

        createArea.mutate(
            {
                user_id: user.id,
                name: name.trim(),
                latitude: location.lat,
                longitude: location.lng,
                radius: radius,
            },
            {
                onSuccess: () => {
                    toast.success('Watch area added!');
                    onOpenChange(false);
                    // Reset form
                    setName('');
                    setLocation(null);
                    setRadius(1000);
                    setErrors({});
                },
                onError: (error) => {
                    console.error('Failed to add watch area:', error);
                    toast.error('Failed to add watch area');
                },
            }
        );
    };

    const handleClose = () => {
        onOpenChange(false);
        // Reset form after dialog animation completes
        setTimeout(() => {
            setName('');
            setLocation(null);
            setRadius(1000);
            setErrors({});
        }, 200);
    };

    const isSubmitting = createArea.isPending;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Add Watch Area</DialogTitle>
                    <DialogDescription>
                        Get flood alerts for this area
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                    {/* Area Name Field */}
                    <div>
                        <label htmlFor="area-name" className="block text-sm font-medium text-foreground mb-1.5">
                            Area Name <span className="text-red-500">*</span>
                        </label>
                        <input
                            id="area-name"
                            type="text"
                            value={name}
                            onChange={(e) => {
                                setName(e.target.value);
                                setErrors((prev) => ({ ...prev, name: undefined }));
                            }}
                            placeholder="e.g., Home, Office, Parents' House"
                            className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent ${
                                errors.name ? 'border-red-300 bg-red-50' : 'border-border'
                            }`}
                            maxLength={100}
                        />
                        {errors.name && (
                            <p className="mt-1 text-xs text-red-600">{errors.name}</p>
                        )}
                    </div>

                    {/* Location Field */}
                    <div>
                        <label htmlFor="location-search" className="block text-sm font-medium text-foreground mb-1.5">
                            Location <span className="text-red-500">*</span>
                        </label>
                        <SearchBar
                            onLocationSelect={handleLocationSelect}
                            cityKey={selectedCity}
                            placeholder="Search for location..."
                            className="w-full"
                        />
                        {location && (
                            <div className="mt-2 flex items-center gap-2 p-2 bg-primary/10 border border-primary/20 rounded-md">
                                <div className="flex-1 min-w-0">
                                    <p className="text-xs font-medium text-foreground truncate">
                                        {location.name}
                                    </p>
                                    <p className="text-xs text-primary mt-0.5">
                                        {location.lat.toFixed(5)}, {location.lng.toFixed(5)}
                                    </p>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setLocation(null);
                                    }}
                                    className="text-primary hover:text-primary/80 text-xs font-medium"
                                >
                                    Change
                                </button>
                            </div>
                        )}
                        {errors.location && (
                            <p className="mt-1 text-xs text-red-600">{errors.location}</p>
                        )}
                    </div>

                    {/* Monitoring Radius Field */}
                    <div>
                        <label htmlFor="radius-slider" className="block text-sm font-medium text-foreground mb-1.5">
                            Monitoring Radius
                        </label>
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <span className="text-xs text-muted-foreground">100 m</span>
                                <span className="text-sm font-semibold text-primary">{formatRadius(radius)}</span>
                                <span className="text-xs text-muted-foreground">10 km</span>
                            </div>
                            <input
                                id="radius-slider"
                                type="range"
                                min="100"
                                max="10000"
                                step="100"
                                value={radius}
                                onChange={(e) => setRadius(parseInt(e.target.value))}
                                className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                                style={{
                                    background: `linear-gradient(to right, rgb(59 130 246) 0%, rgb(59 130 246) ${
                                        ((radius - 100) / (10000 - 100)) * 100
                                    }%, rgb(229 231 235) ${((radius - 100) / (10000 - 100)) * 100}%, rgb(229 231 235) 100%)`,
                                }}
                            />
                        </div>
                    </div>

                    {/* Info Box */}
                    <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-lg">
                        <Info className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                        <p className="text-xs text-blue-700">
                            You'll receive alerts for floods within {formatRadius(radius)} of your selected location.
                        </p>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={handleClose} disabled={isSubmitting}>
                        Cancel
                    </Button>
                    <Button onClick={handleSubmit} disabled={isSubmitting}>
                        {isSubmitting ? 'Adding...' : 'Add Area'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
