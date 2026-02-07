import { X } from 'lucide-react';
import SearchBar from './SearchBar';
import { useCurrentCity } from '../contexts/CityContext';

interface LocationPickerFieldProps {
    label: string;
    value: { lat: number; lng: number; name: string } | null;
    onChange: (location: { lat: number; lng: number; name: string }) => void;
    placeholder?: string;
    error?: string;
    required?: boolean;
}

/**
 * Reusable form field component for location selection.
 * Wraps SearchBar with label, selected location display, and error handling.
 */
export default function LocationPickerField({
    label,
    value,
    onChange,
    placeholder = 'Search for a location...',
    error,
    required = false
}: LocationPickerFieldProps) {
    const cityKey = useCurrentCity();

    const handleLocationSelect = (lat: number, lng: number, name: string) => {
        onChange({ lat, lng, name });
    };

    const handleClear = () => {
        onChange({ lat: 0, lng: 0, name: '' });
    };

    return (
        <div className="space-y-2">
            {/* Label */}
            <label className="text-sm font-medium text-foreground">
                {label}
                {required && <span className="text-red-500 ml-1">*</span>}
            </label>

            {/* Selected Location Badge (if value exists) */}
            {value && value.name && (
                <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-blue-900 truncate">
                            {value.name}
                        </p>
                        <p className="text-xs text-blue-600">
                            {value.lat.toFixed(6)}, {value.lng.toFixed(6)}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={handleClear}
                        className="flex-shrink-0 p-1.5 hover:bg-blue-100 rounded-full transition-colors"
                        aria-label="Clear location"
                    >
                        <X className="h-4 w-4 text-blue-700" />
                    </button>
                </div>
            )}

            {/* SearchBar (only show if no value selected) */}
            {(!value || !value.name) && (
                <SearchBar
                    onLocationSelect={handleLocationSelect}
                    cityKey={cityKey}
                    placeholder={placeholder}
                    className="w-full"
                />
            )}

            {/* Error Message */}
            {error && (
                <p className="text-xs text-red-500 mt-1">
                    {error}
                </p>
            )}
        </div>
    );
}
