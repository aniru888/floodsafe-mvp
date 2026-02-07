import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, MapPin, Loader2, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';
import { useLocationSearch, useTrendingSearches } from '../lib/api/hooks';
import { isWithinCityBounds, getCityConfig, type CityKey } from '../lib/map/cityConfigs';
import type { SearchLocationResult } from '../types';

interface SearchBarProps {
    onLocationSelect: (lat: number, lng: number, name: string) => void;
    cityKey: CityKey;
    placeholder?: string;
    className?: string;
}

/**
 * Custom hook for debouncing a value
 */
function useDebounce<T>(value: T, delay: number): T {
    const [debouncedValue, setDebouncedValue] = useState<T>(value);

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        return () => {
            clearTimeout(handler);
        };
    }, [value, delay]);

    return debouncedValue;
}

export default function SearchBar({
    onLocationSelect,
    cityKey,
    placeholder = 'Search for a location...',
    className = ''
}: SearchBarProps) {
    const [query, setQuery] = useState('');
    const [isOpen, setIsOpen] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(-1);
    const inputRef = useRef<HTMLInputElement>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // Debounce the search query (30ms for fast response)
    const debouncedQuery = useDebounce(query, 30);

    // Use the new backend location search with city filtering
    const { data: results, isLoading, isFetching } = useLocationSearch(
        debouncedQuery,
        10,
        cityKey,  // Filter by selected city
        debouncedQuery.length >= 2
    );

    // Get trending searches
    const { data: trending } = useTrendingSearches(5);

    const cityConfig = getCityConfig(cityKey);

    // Filter results to only include locations within city bounds
    const filteredResults = (results || []).filter((result: SearchLocationResult) => {
        return isWithinCityBounds(result.lng, result.lat, cityKey);
    });

    // Handle click outside to close dropdown
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false);
                setSelectedIndex(-1);
            }
        }

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // Open dropdown when we have results
    useEffect(() => {
        if (debouncedQuery.length >= 3) {
            setIsOpen(true);
        }
    }, [debouncedQuery]);

    // Reset selected index when results change
    useEffect(() => {
        setSelectedIndex(-1);
    }, [filteredResults]);

    // Handle keyboard navigation
    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
        if (!isOpen) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setSelectedIndex(prev =>
                    prev < filteredResults.length - 1 ? prev + 1 : prev
                );
                break;
            case 'ArrowUp':
                e.preventDefault();
                setSelectedIndex(prev => prev > 0 ? prev - 1 : -1);
                break;
            case 'Enter':
                e.preventDefault();
                if (selectedIndex >= 0 && filteredResults[selectedIndex]) {
                    handleSelect(filteredResults[selectedIndex]);
                }
                break;
            case 'Escape':
                e.preventDefault();
                setIsOpen(false);
                setSelectedIndex(-1);
                inputRef.current?.blur();
                break;
        }
    }, [isOpen, selectedIndex, filteredResults]);

    // Handle selection of a result
    const handleSelect = (result: SearchLocationResult) => {
        // Clear the search and close dropdown
        setQuery(result.formatted_name);
        setIsOpen(false);
        setSelectedIndex(-1);

        // Notify parent component
        onLocationSelect(result.lat, result.lng, result.formatted_name);
        toast.success(`Location set: ${result.formatted_name}`, { duration: 2000 });
    };

    // Handle trending click
    const handleTrendingClick = (term: string) => {
        setQuery(term);
        inputRef.current?.focus();
    };

    // Clear search
    const handleClear = () => {
        setQuery('');
        setIsOpen(false);
        setSelectedIndex(-1);
        inputRef.current?.focus();
    };

    const showLoading = isLoading || isFetching;
    const showNoResults = !showLoading && debouncedQuery.length >= 2 && filteredResults.length === 0 && results && results.length > 0;
    const showEmptySearch = !showLoading && debouncedQuery.length >= 2 && (!results || results.length === 0);
    const showTrendingSection = query.length === 0 && (trending?.trending?.length ?? 0) > 0;

    return (
        <div ref={containerRef} className={`relative ${className}`}>
            {/* Search Input */}
            <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    {showLoading ? (
                        <Loader2 className="h-5 w-5 text-muted-foreground/60 animate-spin" />
                    ) : (
                        <Search className="h-5 w-5 text-muted-foreground/60" />
                    )}
                </div>
                <input
                    ref={inputRef}
                    id="location-search"
                    name="location-search"
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={() => {
                        if (debouncedQuery.length >= 3) {
                            setIsOpen(true);
                        }
                    }}
                    placeholder={placeholder}
                    className="w-full pl-11 pr-11 py-3 text-sm font-normal bg-card border border-border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent placeholder:text-muted-foreground transition-all font-sans"
                    autoComplete="off"
                    spellCheck="false"
                />
                {query && (
                    <button
                        type="button"
                        onClick={handleClear}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center hover:opacity-70 transition-opacity"
                    >
                        <X className="h-5 w-5 text-muted-foreground/60" />
                    </button>
                )}
            </div>

            {/* Dropdown Results */}
            {isOpen && (debouncedQuery.length >= 2 || showTrendingSection) && (
                <div
                    ref={dropdownRef}
                    className="absolute z-50 w-full mt-1 bg-card border border-border rounded-lg shadow-lg overflow-hidden max-h-80 sm:max-h-96 flex flex-col font-sans"
                >
                    {/* Dropdown Header with Close Button */}
                    <div className="px-3 py-2 bg-muted border-b border-border flex items-center justify-between flex-shrink-0">
                        <span className="text-xs font-medium text-muted-foreground tracking-wide">
                            {filteredResults.length > 0 ? 'Search Results' : showTrendingSection ? 'Suggestions' : 'Search'}
                        </span>
                        <button
                            type="button"
                            onClick={() => setIsOpen(false)}
                            className="p-1 hover:bg-muted rounded transition-colors"
                            aria-label="Close suggestions"
                        >
                            <X className="h-4 w-4 text-muted-foreground" />
                        </button>
                    </div>

                    {/* Scrollable Content */}
                    <div className="overflow-y-auto flex-1">
                        {/* Results List */}
                        {filteredResults.length > 0 && (
                            <ul>
                                {filteredResults.map((result: SearchLocationResult, index: number) => (
                                    <li key={`${result.lat}-${result.lng}-${index}`}>
                                        <button
                                            type="button"
                                            onClick={() => handleSelect(result)}
                                            className={`w-full px-4 py-3 flex items-start gap-3 text-left hover:bg-accent transition-colors ${
                                                selectedIndex === index ? 'bg-primary/10' : ''
                                            }`}
                                        >
                                            <MapPin className="h-5 w-5 text-primary mt-0.5 flex-shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium text-foreground truncate">
                                                    {result.formatted_name}
                                                </p>
                                                <p className="text-xs text-muted-foreground truncate mt-0.5">
                                                    {result.display_name}
                                                </p>
                                            </div>
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        )}

                        {/* No results in city */}
                        {showNoResults && (
                            <div className="px-4 py-3 text-sm text-muted-foreground">
                                <p>No results found in {cityConfig.displayName}.</p>
                                <p className="text-xs mt-1">
                                    Results are filtered to the current city area.
                                </p>
                            </div>
                        )}

                        {/* No results at all */}
                        {showEmptySearch && (
                            <div className="px-4 py-3 text-sm text-muted-foreground">
                                No locations found for "{debouncedQuery}".
                            </div>
                        )}

                        {/* Loading state */}
                        {showLoading && (
                            <div className="px-4 py-3 flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="h-5 w-5 animate-spin" />
                                Searching...
                            </div>
                        )}

                        {/* Trending Searches (Empty State) */}
                        {showTrendingSection && (
                            <div>
                                <div className="px-4 py-2 text-xs font-semibold text-muted-foreground uppercase bg-muted flex items-center gap-2">
                                    <TrendingUp className="h-4 w-4" />
                                    Trending Searches
                                </div>
                                <div className="px-4 py-3 flex flex-wrap gap-2">
                                    {trending?.trending?.map((term: string, index: number) => (
                                        <button
                                            key={index}
                                            type="button"
                                            onClick={() => handleTrendingClick(term)}
                                            className="px-3 py-1.5 text-sm bg-muted hover:bg-accent text-foreground rounded-full transition-colors"
                                        >
                                            {term}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Footer */}
                    <div className="px-4 py-2 bg-muted border-t border-border flex-shrink-0">
                        <p className="text-xs text-muted-foreground/60">
                            Showing results in {cityConfig.displayName} • Powered by backend search
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}
