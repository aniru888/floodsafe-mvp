import { X, Calendar, AlertTriangle, Users, Clock, MapPin, ExternalLink, Newspaper, Droplets } from 'lucide-react';

// Custom scrollbar styles - FORCED visible
const scrollbarStyles = `
.custom-scrollbar {
    scrollbar-width: auto !important;
    scrollbar-color: #7c3aed #e5e7eb !important;
    scrollbar-gutter: stable;
}
.custom-scrollbar::-webkit-scrollbar {
    width: 12px !important;
    background: #e5e7eb;
}
.custom-scrollbar::-webkit-scrollbar-track {
    background: #e5e7eb !important;
    border-radius: 6px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
    background: #7c3aed !important;
    border-radius: 6px;
    border: 2px solid #e5e7eb;
    min-height: 50px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: #6d28d9 !important;
}
.custom-scrollbar::-webkit-scrollbar-corner {
    background: #e5e7eb;
}
`;

interface HistoricalFlood {
    id: string;
    date: string;
    districts: string;
    severity: string;
    fatalities: number;
    injured: number;
    displaced: number;
    duration_days: number | null;
    main_cause: string;
    // Enriched fields (available for recent events)
    news_headline?: string;
    news_source?: string;
    news_url?: string;
    specific_areas?: string[];
    impact_summary?: string;
    yamuna_level_m?: number;
}

interface HistoricalFloodsPanelProps {
    floods: HistoricalFlood[];
    onClose: () => void;
    isOpen: boolean;
    cityName?: string;  // Display name of the city (e.g., "Delhi NCR", "Bangalore")
    comingSoonMessage?: string;  // Message when data isn't available for a city
}

const severityColors: Record<string, { bg: string; text: string; border: string }> = {
    minor: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
    moderate: { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200' },
    severe: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
};

function formatDate(dateStr: string): string {
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-IN', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    } catch {
        return dateStr;
    }
}

function getYear(dateStr: string): number {
    try {
        const year = new Date(dateStr).getFullYear();
        // Validate year is reasonable (1900-2100)
        return (year >= 1900 && year <= 2100) ? year : 0;
    } catch {
        return 0;
    }
}

export default function HistoricalFloodsPanel({
    floods,
    onClose,
    isOpen,
    cityName = 'Delhi NCR',
    comingSoonMessage
}: HistoricalFloodsPanelProps) {
    if (!isOpen) return null;

    // Check if this is a "coming soon" scenario (no data for the city)
    const isComingSoon = floods.length === 0 && comingSoonMessage;

    // Sort by date descending (most recent first) - handle invalid dates
    const sortedFloods = [...floods].sort((a, b) => {
        const timeA = new Date(a.date).getTime();
        const timeB = new Date(b.date).getTime();
        if (isNaN(timeA) || isNaN(timeB)) return 0;
        return timeB - timeA;
    });

    // Group by decade - skip invalid years
    const groupedByDecade: Record<string, HistoricalFlood[]> = {};
    sortedFloods.forEach(flood => {
        const year = getYear(flood.date);
        if (year === 0) return; // Skip invalid dates
        const decade = `${Math.floor(year / 10) * 10}s`;
        if (!groupedByDecade[decade]) {
            groupedByDecade[decade] = [];
        }
        groupedByDecade[decade].push(flood);
    });

    // Calculate statistics - filter out invalid years
    const totalFatalities = floods.reduce((sum, f) => sum + (f.fatalities || 0), 0);
    const severeCount = floods.filter(f => f.severity === 'severe').length;
    const validYears = floods.map(f => getYear(f.date)).filter(y => y > 0);
    const yearRange = validYears.length > 0
        ? `${Math.min(...validYears)} - ${Math.max(...validYears)}`
        : 'N/A';

    return (
        <div
            className="fixed inset-0 flex items-center justify-center bg-black/40 backdrop-blur-sm"
            style={{ zIndex: 9999 }}
            onClick={onClose}
        >
            {/* Inject scrollbar styles */}
            <style>{scrollbarStyles}</style>
            <div
                className="bg-card rounded-xl shadow-2xl flex flex-col overflow-hidden"
                style={{
                    width: '90vw',
                    maxWidth: '420px',
                    height: '85vh',
                    maxHeight: '700px',
                    margin: '16px'
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div
                    className="flex items-center justify-between p-3 border-b rounded-t-xl"
                    style={{ background: 'linear-gradient(to right, #7c3aed, #4f46e5)' }}
                >
                    <div className="flex items-center gap-2">
                        <div className="p-1.5 rounded-lg" style={{ backgroundColor: 'rgba(255,255,255,0.2)' }}>
                            <Calendar className="w-4 h-4" style={{ color: 'white' }} />
                        </div>
                        <div>
                            <h2 className="text-base font-bold" style={{ color: 'white' }}>Historical Floods</h2>
                            <p className="text-xs" style={{ color: 'rgba(255,255,255,0.8)' }}>{cityName} • {isComingSoon ? 'Coming Soon' : yearRange}</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="rounded-md p-1.5 hover:bg-white/20 transition-colors"
                        style={{ color: 'white' }}
                        aria-label="Close"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Statistics Bar */}
                <div className="grid grid-cols-3 gap-2 p-3 bg-muted border-b">
                    <div className="text-center">
                        <div className="text-xl font-bold text-foreground">{floods.length}</div>
                        <div className="text-[10px] text-muted-foreground">Events</div>
                    </div>
                    <div className="text-center">
                        <div className="text-xl font-bold text-red-600">{totalFatalities}</div>
                        <div className="text-[10px] text-muted-foreground">Fatalities</div>
                    </div>
                    <div className="text-center">
                        <div className="text-xl font-bold text-orange-600">{severeCount}</div>
                        <div className="text-[10px] text-muted-foreground">Severe</div>
                    </div>
                </div>

                {/* Source Attribution */}
                <div className="px-3 py-1.5 bg-primary/10 border-b text-[10px] text-primary">
                    <strong>Source:</strong> IFI-Impacts • IIT-Delhi •
                    <a href="https://zenodo.org/records/11275211" target="_blank" rel="noopener noreferrer" className="underline ml-1">
                        Zenodo
                    </a>
                </div>

                {/* Scrollable Event List with visible scrollbar */}
                <div
                    className="custom-scrollbar flex-1"
                    style={{
                        minHeight: 0,
                        overflowY: 'scroll',
                        scrollbarWidth: 'auto',
                        scrollbarColor: '#7c3aed #e5e7eb',
                        paddingRight: '4px'
                    }}
                >
                    <div className="p-3 pr-1 space-y-3">
                    {isComingSoon ? (
                        <div className="text-center py-12 text-muted-foreground">
                            <Calendar className="w-16 h-16 mx-auto mb-4 text-purple-200" />
                            <p className="font-semibold text-lg text-foreground mb-2">Coming Soon!</p>
                            <p className="text-sm text-muted-foreground mb-4">{comingSoonMessage}</p>
                            <div className="bg-purple-50 rounded-lg p-4 max-w-sm mx-auto border border-purple-100">
                                <p className="text-xs text-purple-700">
                                    Historical flood data is currently available for <strong>Delhi NCR</strong> only.
                                    We're working on adding data for more cities.
                                </p>
                            </div>
                        </div>
                    ) : Object.keys(groupedByDecade).length === 0 ? (
                        <div className="text-center py-12 text-muted-foreground">
                            <Calendar className="w-12 h-12 mx-auto mb-3 text-muted-foreground/60" />
                            <p className="font-medium">No historical flood data available</p>
                            <p className="text-sm mt-1">Data may still be loading.</p>
                        </div>
                    ) : Object.entries(groupedByDecade)
                        .sort((a, b) => b[0].localeCompare(a[0]))
                        .map(([decade, events]) => (
                            <div key={decade}>
                                <div className="sticky top-0 bg-card py-1 mb-2">
                                    <span className="text-sm font-semibold text-muted-foreground bg-muted px-3 py-1 rounded-full">
                                        {decade}
                                    </span>
                                </div>
                                <div className="space-y-2">
                                    {events.map((flood) => {
                                        const colors = severityColors[flood.severity] || severityColors.minor;
                                        const hasEnrichedData = flood.news_headline || flood.impact_summary;
                                        return (
                                            <div
                                                key={flood.id}
                                                className={`p-3 rounded-lg border ${colors.border} ${colors.bg}`}
                                            >
                                                {/* Header: Date + Severity + Fatalities */}
                                                <div className="flex items-center gap-2 mb-2">
                                                    <span className="font-semibold text-foreground">
                                                        {formatDate(flood.date)}
                                                    </span>
                                                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors.text} ${colors.bg} border ${colors.border}`}>
                                                        {flood.severity}
                                                    </span>
                                                    {flood.fatalities > 0 && (
                                                        <span className="text-xs text-red-600 font-medium">
                                                            {flood.fatalities} deaths
                                                        </span>
                                                    )}
                                                </div>

                                                {/* News Headline (enriched) */}
                                                {flood.news_headline && (
                                                    <div className="mb-2">
                                                        <p className="text-sm font-medium text-foreground italic border-l-2 border-purple-400 pl-2">
                                                            "{flood.news_headline}"
                                                        </p>
                                                        {flood.news_source && (
                                                            <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                                                                <Newspaper className="w-3 h-3" />
                                                                <span>{flood.news_source}</span>
                                                                {flood.news_url && (
                                                                    <a
                                                                        href={flood.news_url}
                                                                        target="_blank"
                                                                        rel="noopener noreferrer"
                                                                        className="text-purple-600 hover:text-purple-800 flex items-center gap-0.5 ml-1"
                                                                        onClick={(e) => e.stopPropagation()}
                                                                    >
                                                                        <ExternalLink className="w-3 h-3" />
                                                                    </a>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}

                                                {/* Cause (if no headline) */}
                                                {!flood.news_headline && (
                                                    <p className="text-sm text-muted-foreground mb-2">
                                                        <strong>Cause:</strong> {flood.main_cause || 'Not specified'}
                                                    </p>
                                                )}

                                                {/* Impact Summary (enriched) */}
                                                {flood.impact_summary && (
                                                    <p className="text-xs text-muted-foreground mb-2 bg-card/50 rounded p-1.5">
                                                        {flood.impact_summary}
                                                    </p>
                                                )}

                                                {/* Specific Areas (enriched) */}
                                                {flood.specific_areas && flood.specific_areas.length > 0 && (
                                                    <div className="flex flex-wrap gap-1 mb-2">
                                                        <MapPin className="w-3 h-3 text-muted-foreground/60 mt-0.5" />
                                                        {flood.specific_areas.slice(0, 4).map((area, idx) => (
                                                            <span
                                                                key={idx}
                                                                className="text-xs px-1.5 py-0.5 bg-card/70 rounded text-muted-foreground border border-border"
                                                            >
                                                                {area}
                                                            </span>
                                                        ))}
                                                        {flood.specific_areas.length > 4 && (
                                                            <span className="text-xs text-muted-foreground/60">
                                                                +{flood.specific_areas.length - 4} more
                                                            </span>
                                                        )}
                                                    </div>
                                                )}

                                                {/* Stats Row */}
                                                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                                                    {flood.displaced > 0 && (
                                                        <span className="flex items-center gap-1">
                                                            <Users className="w-3 h-3" />
                                                            {flood.displaced.toLocaleString()} displaced
                                                        </span>
                                                    )}
                                                    {flood.injured > 0 && (
                                                        <span className="flex items-center gap-1">
                                                            <AlertTriangle className="w-3 h-3" />
                                                            {flood.injured} injured
                                                        </span>
                                                    )}
                                                    {flood.yamuna_level_m && (
                                                        <span className="flex items-center gap-1 text-blue-600 font-medium">
                                                            <Droplets className="w-3 h-3" />
                                                            Yamuna: {flood.yamuna_level_m}m
                                                        </span>
                                                    )}
                                                    {flood.duration_days && flood.duration_days > 1 && (
                                                        <span className="flex items-center gap-1">
                                                            <Clock className="w-3 h-3" />
                                                            {flood.duration_days} days
                                                        </span>
                                                    )}
                                                    {/* Show districts only for non-enriched entries */}
                                                    {!hasEnrichedData && flood.districts && flood.districts !== 'nan' && (
                                                        <span className="flex items-center gap-1">
                                                            <MapPin className="w-3 h-3" />
                                                            {flood.districts.split(',').slice(0, 3).join(', ')}
                                                            {flood.districts.split(',').length > 3 && '...'}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Footer */}
                <div className="p-2 border-t bg-muted rounded-b-xl">
                    <p className="text-[10px] text-muted-foreground/60 text-center">
                        Events shown as timeline (no GPS data available)
                    </p>
                </div>
            </div>
        </div>
    );
}
