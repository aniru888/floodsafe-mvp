import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Search, X, Loader2, MapPin, FileText, User, TrendingUp, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';
import { useUnifiedSearch, useTrendingSearches } from '../lib/api/hooks';
import type { HotspotsResponse } from '../lib/api/hooks';
import type {
    SearchLocationResult,
    SearchReportResult,
    SearchUserResult,
    SearchIntent
} from '../types';

interface SmartSearchBarProps {
    onLocationSelect?: (lat: number, lng: number, name: string) => void;
    onReportSelect?: (report: SearchReportResult) => void;
    onUserSelect?: (user: SearchUserResult) => void;
    placeholder?: string;
    className?: string;
    showTrending?: boolean;
    /** City key for filtering location results. If not provided, searches globally. */
    cityKey?: 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore' | 'indore';
    /** User's current latitude for proximity-sorted results */
    userLat?: number;
    /** User's current longitude for proximity-sorted results */
    userLng?: number;
}

/**
 * Simple fuzzy match: checks if most characters in query appear in target in order.
 * Handles typos like "Vijay Nager" matching "vijay nagar".
 */
function _fuzzyMatch(query: string, target: string): boolean {
    if (!target || target.length < query.length * 0.5) return false;
    let qi = 0;
    for (let ti = 0; ti < target.length && qi < query.length; ti++) {
        if (query[qi] === target[ti]) qi++;
    }
    // Match if >70% of query characters found in order
    return qi >= query.length * 0.7;
}

/** Initial number of results shown per section before "Show more" */
const INITIAL_LOCATIONS = 20;
const INITIAL_REPORTS = 8;
const INITIAL_USERS = 5;

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

export default function SmartSearchBar({
    onLocationSelect,
    onReportSelect,
    onUserSelect,
    placeholder = 'Search locations, reports, or users...',
    className = '',
    showTrending = true,
    cityKey,
    userLat,
    userLng
}: SmartSearchBarProps) {
    const [query, setQuery] = useState('');
    const [isOpen, setIsOpen] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(-1);
    const [showAllLocations, setShowAllLocations] = useState(false);
    const [showAllReports, setShowAllReports] = useState(false);
    const [showAllUsers, setShowAllUsers] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // Debounce the search query (300ms to avoid hammering the geocoding APIs)
    const debouncedQuery = useDebounce(query, 300);

    // Use the unified search hook with city filtering and proximity
    const { data: searchResults, isLoading, isFetching } = useUnifiedSearch({
        query: debouncedQuery,
        city: cityKey,
        lat: userLat,
        lng: userLng,
        limit: 30,
        enabled: debouncedQuery.length >= 2
    });

    // Get trending searches for empty state
    const { data: trending } = useTrendingSearches(5);

    // Instant local hotspot matching from TanStack Query cache (no API call)
    const queryClient = useQueryClient();
    const localHotspotMatches = useMemo(() => {
        if (query.length < 2) return [];
        const queryLower = query.toLowerCase();

        // Read cached hotspot data (already loaded by map screen)
        const cachedHotspots = queryClient.getQueryData<HotspotsResponse>(
            ['hotspots', cityKey, false]
        );
        if (!cachedHotspots?.features) return [];

        return cachedHotspots.features
            .filter(f => {
                const name = f.properties.name?.toLowerCase() || '';
                const desc = f.properties.description?.toLowerCase() || '';
                const zone = f.properties.zone?.toLowerCase() || '';
                // Match if query is a prefix, substring, or fuzzy match
                return name.includes(queryLower) ||
                    desc.includes(queryLower) ||
                    zone.includes(queryLower) ||
                    // Simple typo tolerance: check if >60% of query chars appear in name
                    (queryLower.length >= 4 && _fuzzyMatch(queryLower, name));
            })
            .slice(0, 5)
            .map(f => ({
                type: 'location' as const,
                display_name: `${f.properties.name} — ${f.properties.zone || 'Hotspot'}`,
                lat: f.geometry.coordinates[1],
                lng: f.geometry.coordinates[0],
                address: {},
                importance: 1.0, // Highest importance — local hotspots are most relevant
                formatted_name: f.properties.name,
            }));
    }, [query, cityKey, queryClient]);

    // Deduplicate locations by formatted_name + coordinates to avoid duplicate key warnings
    // Merge local hotspot matches (instant) at the top, then API results
    const deduplicatedLocations = useMemo(() => {
        const apiLocations = searchResults?.locations
            ? searchResults.locations.filter((loc, index, self) =>
                index === self.findIndex((l) =>
                    l.formatted_name === loc.formatted_name &&
                    Math.abs((l.lat || 0) - (loc.lat || 0)) < 0.001 &&
                    Math.abs((l.lng || 0) - (loc.lng || 0)) < 0.001
                )
            )
            : [];

        // Merge: local hotspot matches first, then API results (deduped)
        const merged = [...localHotspotMatches];
        for (const loc of apiLocations) {
            const isDuplicate = merged.some(
                m => Math.abs((m.lat || 0) - (loc.lat || 0)) < 0.001 &&
                     Math.abs((m.lng || 0) - (loc.lng || 0)) < 0.001
            );
            if (!isDuplicate) merged.push(loc);
        }
        return merged;
    }, [searchResults?.locations, localHotspotMatches]);

    // Flatten all results for keyboard navigation
    const allResults = [
        ...deduplicatedLocations,
        ...(searchResults?.reports || []),
        ...(searchResults?.users || [])
    ];

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

    // Open dropdown only when typing (not on mount)
    useEffect(() => {
        if (debouncedQuery.length >= 2) {
            setIsOpen(true);
        }
    }, [debouncedQuery]);

    // Reset selected index and collapse sections when results change
    useEffect(() => {
        setSelectedIndex(-1);
        setShowAllLocations(false);
        setShowAllReports(false);
        setShowAllUsers(false);
    }, [searchResults]);

    // Handle keyboard navigation
    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
        if (!isOpen) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setSelectedIndex(prev =>
                    prev < allResults.length - 1 ? prev + 1 : prev
                );
                break;
            case 'ArrowUp':
                e.preventDefault();
                setSelectedIndex(prev => prev > 0 ? prev - 1 : -1);
                break;
            case 'Enter':
                e.preventDefault();
                if (selectedIndex >= 0 && allResults[selectedIndex]) {
                    handleSelect(allResults[selectedIndex]);
                }
                break;
            case 'Escape':
                e.preventDefault();
                setIsOpen(false);
                setSelectedIndex(-1);
                inputRef.current?.blur();
                break;
        }
    }, [isOpen, selectedIndex, allResults]);

    // Handle selection of a result
    const handleSelect = (result: SearchLocationResult | SearchReportResult | SearchUserResult) => {
        console.log('[SmartSearchBar] Selected:', result);

        if (result.type === 'location') {
            const loc = result as SearchLocationResult;
            // Add null checks for lat/lng
            if (onLocationSelect && loc.lat !== undefined && loc.lng !== undefined) {
                onLocationSelect(loc.lat, loc.lng, loc.formatted_name || loc.display_name);
                setQuery(loc.formatted_name || loc.display_name);
                toast.success(`Location set: ${loc.formatted_name || loc.display_name}`, { duration: 2000 });
            } else {
                console.warn('[SmartSearchBar] Location missing lat/lng:', loc);
                toast.error('Invalid location data');
            }
        } else if (result.type === 'report' && onReportSelect) {
            onReportSelect(result as SearchReportResult);
            setQuery(result.description.substring(0, 50));
            toast.info('Report selected', { duration: 2000 });
        } else if (result.type === 'user' && onUserSelect) {
            onUserSelect(result as SearchUserResult);
            setQuery(result.username);
            toast.info(`Viewing @${result.username}`, { duration: 2000 });
        }

        setIsOpen(false);
        setSelectedIndex(-1);
    };

    // Clear search
    const handleClear = () => {
        setQuery('');
        setIsOpen(false);
        setSelectedIndex(-1);
        inputRef.current?.focus();
    };

    // Handle trending click
    const handleTrendingClick = (term: string) => {
        setQuery(term);
        inputRef.current?.focus();
    };

    const showLoading = isLoading || isFetching;
    const showResults = debouncedQuery.length >= 2 && searchResults;
    const showTrendingSection = query.length === 0 && showTrending && trending;
    const hasResults = deduplicatedLocations.length +
                      (searchResults?.reports.length || 0) +
                      (searchResults?.users.length || 0) > 0;

    // Get intent badge
    const getIntentBadge = (intent: SearchIntent) => {
        const badges = {
            location: { icon: MapPin, label: 'Location', color: 'text-primary bg-primary/10' },
            report: { icon: FileText, label: 'Report', color: 'text-orange-600 bg-orange-50' },
            user: { icon: User, label: 'User', color: 'text-purple-600 bg-purple-50' },
            mixed: { icon: Sparkles, label: 'Smart', color: 'text-green-600 bg-green-50' },
            empty: { icon: Search, label: 'Search', color: 'text-muted-foreground bg-muted' }
        };
        return badges[intent] || badges.empty;
    };

    const intentBadge = searchResults ? getIntentBadge(searchResults.intent) : null;

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
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={() => {
                        // Only show dropdown if there's already a query
                        if (query.length >= 2) {
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
            {isOpen && (
                <div className="absolute z-50 w-full mt-1 bg-card border border-border rounded-lg shadow-lg overflow-hidden max-h-[32rem] flex flex-col font-sans">

                    {/* Dropdown Header with Close Button */}
                    <div className="px-3 py-2 bg-muted border-b border-border flex items-center justify-between flex-shrink-0">
                        <span className="text-xs font-medium text-muted-foreground tracking-wide">
                            {showResults ? 'Search Results' : 'Suggestions'}
                        </span>
                        <button
                            type="button"
                            onClick={() => setIsOpen(false)}
                            className="p-1 hover:bg-accent rounded transition-colors"
                            aria-label="Close suggestions"
                        >
                            <X className="h-4 w-4 text-muted-foreground" />
                        </button>
                    </div>

                    {/* Scrollable Content */}
                    <div className="overflow-y-auto flex-1">
                        {/* Intent Badge */}
                        {intentBadge && showResults && (
                            <div className="px-4 py-2 bg-muted border-b border-border flex items-center gap-2">
                                <intentBadge.icon className={`h-4 w-4 ${intentBadge.color.split(' ')[0]}`} />
                                <span className={`text-xs font-medium px-2 py-0.5 rounded ${intentBadge.color}`}>
                                    {intentBadge.label} Search
                                </span>
                            </div>
                        )}

                    {/* Locations */}
                    {showResults && deduplicatedLocations.length > 0 && (
                        <div>
                            <div className="px-4 py-2 text-xs font-semibold text-muted-foreground uppercase bg-muted flex items-center justify-between">
                                <span>Locations</span>
                                <span className="text-xs font-normal text-muted-foreground/60 normal-case">
                                    {deduplicatedLocations.length} results
                                </span>
                            </div>
                            {(showAllLocations ? deduplicatedLocations : deduplicatedLocations.slice(0, INITIAL_LOCATIONS)).map((location, index) => (
                                <button
                                    key={`loc-${index}-${location.lat?.toFixed(4) || 'na'}-${location.lng?.toFixed(4) || 'na'}`}
                                    type="button"
                                    onClick={() => handleSelect(location)}
                                    className={`w-full px-4 py-3 flex items-start gap-3 text-left hover:bg-muted transition-colors ${
                                        selectedIndex === index ? 'bg-primary/10' : ''
                                    }`}
                                >
                                    <MapPin className="h-5 w-5 text-primary mt-0.5 flex-shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-foreground truncate">
                                            {location.formatted_name}
                                        </p>
                                        <p className="text-xs text-muted-foreground truncate mt-0.5">
                                            {location.display_name}
                                        </p>
                                    </div>
                                </button>
                            ))}
                            {!showAllLocations && deduplicatedLocations.length > INITIAL_LOCATIONS && (
                                <button
                                    type="button"
                                    onClick={() => setShowAllLocations(true)}
                                    className="w-full px-4 py-2 text-xs text-primary hover:bg-primary/10 transition-colors text-center font-medium"
                                >
                                    Show all {deduplicatedLocations.length} locations
                                </button>
                            )}
                        </div>
                    )}

                    {/* Reports */}
                    {showResults && searchResults.reports.length > 0 && (
                        <div>
                            <div className="px-4 py-2 text-xs font-semibold text-muted-foreground uppercase bg-muted border-t border-border flex items-center justify-between">
                                <span>Flood Reports</span>
                                <span className="text-xs font-normal text-muted-foreground/60 normal-case">
                                    {searchResults.reports.length} results
                                </span>
                            </div>
                            {(showAllReports ? searchResults.reports : searchResults.reports.slice(0, INITIAL_REPORTS)).map((report, index) => {
                                const visibleLocations = showAllLocations ? deduplicatedLocations.length : Math.min(deduplicatedLocations.length, INITIAL_LOCATIONS);
                                const resultIndex = visibleLocations + index;
                                return (
                                    <button
                                        key={`report-${report.id}`}
                                        type="button"
                                        onClick={() => handleSelect(report)}
                                        className={`w-full px-4 py-3 flex items-start gap-3 text-left hover:bg-muted transition-colors ${
                                            selectedIndex === resultIndex ? 'bg-primary/10' : ''
                                        }`}
                                    >
                                        <FileText className="h-5 w-5 text-orange-500 mt-0.5 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm text-foreground">
                                                {report.highlight}
                                            </p>
                                            <div className="flex items-center gap-2 mt-1">
                                                {report.verified && (
                                                    <span className="text-xs px-1.5 py-0.5 bg-green-100 text-green-700 rounded">
                                                        Verified
                                                    </span>
                                                )}
                                                {report.water_depth && (
                                                    <span className="text-xs text-muted-foreground">
                                                        {report.water_depth} deep
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </button>
                                );
                            })}
                            {!showAllReports && searchResults.reports.length > INITIAL_REPORTS && (
                                <button
                                    type="button"
                                    onClick={() => setShowAllReports(true)}
                                    className="w-full px-4 py-2 text-xs text-orange-600 hover:bg-orange-50 transition-colors text-center font-medium"
                                >
                                    Show all {searchResults.reports.length} reports
                                </button>
                            )}
                        </div>
                    )}

                    {/* Users */}
                    {showResults && searchResults.users.length > 0 && (
                        <div>
                            <div className="px-4 py-2 text-xs font-semibold text-muted-foreground uppercase bg-muted border-t border-border flex items-center justify-between">
                                <span>Users</span>
                                <span className="text-xs font-normal text-muted-foreground/60 normal-case">
                                    {searchResults.users.length} results
                                </span>
                            </div>
                            {(showAllUsers ? searchResults.users : searchResults.users.slice(0, INITIAL_USERS)).map((user, index) => {
                                const visibleLocations = showAllLocations ? deduplicatedLocations.length : Math.min(deduplicatedLocations.length, INITIAL_LOCATIONS);
                                const visibleReports = showAllReports ? searchResults.reports.length : Math.min(searchResults.reports.length, INITIAL_REPORTS);
                                const resultIndex = visibleLocations + visibleReports + index;
                                return (
                                    <button
                                        key={`user-${user.id}`}
                                        type="button"
                                        onClick={() => handleSelect(user)}
                                        className={`w-full px-4 py-3 flex items-start gap-3 text-left hover:bg-muted transition-colors ${
                                            selectedIndex === resultIndex ? 'bg-primary/10' : ''
                                        }`}
                                    >
                                        <User className="h-5 w-5 text-purple-500 mt-0.5 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-foreground">
                                                @{user.username}
                                            </p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <span className="text-xs text-muted-foreground">
                                                    Level {user.level} • {user.points} pts
                                                </span>
                                                {user.reports_count > 0 && (
                                                    <span className="text-xs text-muted-foreground">
                                                        • {user.reports_count} reports
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </button>
                                );
                            })}
                            {!showAllUsers && searchResults.users.length > INITIAL_USERS && (
                                <button
                                    type="button"
                                    onClick={() => setShowAllUsers(true)}
                                    className="w-full px-4 py-2 text-xs text-purple-600 hover:bg-purple-50 transition-colors text-center font-medium"
                                >
                                    Show all {searchResults.users.length} users
                                </button>
                            )}
                        </div>
                    )}

                    {/* No Results */}
                    {showResults && !hasResults && (
                        <div className="px-4 py-8 text-center">
                            <Search className="h-12 w-12 text-muted-foreground/60 mx-auto mb-3" />
                            <p className="text-sm text-muted-foreground">
                                No results for "{debouncedQuery}"
                            </p>
                            <p className="text-xs text-muted-foreground/60 mt-1">
                                Try different keywords or check spelling
                            </p>
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
                                {trending.trending.map((term, index) => (
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

                    {/* Loading State */}
                    {showLoading && (
                        <div className="px-4 py-3 flex items-center gap-2 text-sm text-muted-foreground">
                            <Loader2 className="h-5 w-5 animate-spin" />
                            Searching...
                        </div>
                    )}

                    {/* Search Tips */}
                    {showResults && searchResults.suggestions && searchResults.suggestions.length > 0 && (
                        <div className="px-4 py-3 bg-primary/10 border-t border-border">
                            {searchResults.suggestions.map((suggestion, index) => (
                                <div key={index} className="text-xs text-primary">
                                    {suggestion.text}
                                </div>
                            ))}
                        </div>
                    )}
                    </div>
                </div>
            )}
        </div>
    );
}
