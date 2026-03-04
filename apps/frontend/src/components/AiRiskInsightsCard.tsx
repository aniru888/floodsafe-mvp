import { useMemo } from 'react';
import { Brain, MapPin, RefreshCw, Sparkles } from 'lucide-react';
import { Badge } from './ui/badge';
import { Skeleton } from './ui/skeleton';
import { cn } from '../lib/utils';
import { useRiskSummary } from '../lib/api/hooks';
import type { WatchArea, DailyRoute } from '../types';
import { useLanguage } from '../contexts/LanguageContext';
import type { AppLanguage } from '../contexts/LanguageContext';

// ============================================================================
// Types
// ============================================================================

interface LocationItem {
    name: string;
    latitude: number;
    longitude: number;
    source: 'watch_area' | 'daily_route';
}

interface AiRiskInsightsCardProps {
    watchAreas: WatchArea[];
    dailyRoutes: DailyRoute[];
    maxItems?: number;
}

// ============================================================================
// Risk level styling map
// ============================================================================

const RISK_STYLES: Record<string, { border: string; badgeBg: string; badgeText: string; label: string }> = {
    low:      { border: 'border-l-emerald-500', badgeBg: 'bg-emerald-50',  badgeText: 'text-emerald-700', label: 'Low' },
    moderate: { border: 'border-l-amber-500',   badgeBg: 'bg-amber-50',    badgeText: 'text-amber-700',   label: 'Moderate' },
    high:     { border: 'border-l-orange-500',   badgeBg: 'bg-orange-50',   badgeText: 'text-orange-700',  label: 'High' },
    extreme:  { border: 'border-l-red-500',      badgeBg: 'bg-red-50',      badgeText: 'text-red-700',     label: 'Extreme' },
};

const DEFAULT_RISK_STYLE = RISK_STYLES['low'];

function getRiskStyle(level: string) {
    return RISK_STYLES[level.toLowerCase()] || DEFAULT_RISK_STYLE;
}

// ============================================================================
// RiskInsightItem — one item per location, fetches independently
// ============================================================================

function RiskInsightItem({ location, language }: { location: LocationItem; language: AppLanguage }) {
    // API only supports en/hi — fall back to English for other languages
    const apiLang = language === 'hi' ? 'hi' : 'en';
    const { data, isLoading, isError, refetch } = useRiskSummary(
        location.latitude,
        location.longitude,
        apiLang,
        location.name
    );

    // Loading skeleton
    if (isLoading) {
        return (
            <div className="border-l-4 border-l-muted rounded-lg bg-muted/30 p-3 space-y-2">
                <div className="flex items-center gap-2">
                    <Skeleton className="h-4 w-4 rounded-full" />
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-5 w-14 rounded-full ml-auto" />
                </div>
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-3/4" />
            </div>
        );
    }

    // Network error / 500
    if (isError) {
        return (
            <div className="border-l-4 border-l-muted rounded-lg bg-muted/30 p-3">
                <div className="flex items-center gap-2 mb-1">
                    <MapPin className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground">{location.name}</span>
                </div>
                <p className="text-sm text-muted-foreground">Could not load insight for {location.name}</p>
                <button
                    onClick={() => refetch()}
                    className="mt-2 flex items-center gap-1 text-xs text-primary hover:text-primary/80 font-medium min-h-[44px]"
                >
                    <RefreshCw className="w-3 h-3" />
                    Retry
                </button>
            </div>
        );
    }

    // Service disabled
    if (data && !data.enabled) {
        return (
            <div className="border-l-4 border-l-muted rounded-lg bg-muted/30 p-3">
                <div className="flex items-center gap-2 mb-1">
                    <MapPin className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground">{location.name}</span>
                </div>
                <p className="text-sm text-muted-foreground italic">
                    AI insights are being set up for your area
                </p>
            </div>
        );
    }

    // Service enabled but summary is null (Groq rate limited / busy)
    if (data && data.enabled && !data.risk_summary) {
        return (
            <div className="border-l-4 border-l-muted rounded-lg bg-muted/30 p-3">
                <div className="flex items-center gap-2 mb-1">
                    <MapPin className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground">{location.name}</span>
                </div>
                <p className="text-sm text-muted-foreground">
                    AI service is busy — try again in a few minutes
                </p>
                <button
                    onClick={() => refetch()}
                    className="mt-2 flex items-center gap-1 text-xs text-primary hover:text-primary/80 font-medium min-h-[44px]"
                >
                    <RefreshCw className="w-3 h-3" />
                    Refresh
                </button>
            </div>
        );
    }

    // Success — show the AI summary
    if (!data) return null;

    const style = getRiskStyle(data.risk_level);

    return (
        <div className={cn('border-l-4 rounded-lg bg-card p-3', style.border)}>
            <div className="flex items-center gap-2 mb-1.5">
                <MapPin className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <span className="text-sm font-medium text-foreground truncate">{location.name}</span>
                <Badge className={cn('ml-auto text-[10px] px-1.5 py-0 border-none', style.badgeBg, style.badgeText)}>
                    {style.label}
                </Badge>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
                {data.risk_summary}
            </p>
            {data.weather_unavailable && (
                <p className="text-xs text-muted-foreground/60 mt-1 italic">
                    Weather data temporarily unavailable
                </p>
            )}
        </div>
    );
}

// ============================================================================
// AiRiskInsightsCard — main card
// ============================================================================

export function AiRiskInsightsCard({ watchAreas, dailyRoutes, maxItems = 3 }: AiRiskInsightsCardProps) {
    const { language } = useLanguage();

    // Build location list: watch areas first, then fill remaining slots with route destinations
    const locations: LocationItem[] = useMemo(() => {
        const items: LocationItem[] = [];

        // Priority 1: Watch areas
        for (const wa of watchAreas) {
            if (items.length >= maxItems) break;
            items.push({
                name: wa.name,
                latitude: wa.latitude,
                longitude: wa.longitude,
                source: 'watch_area',
            });
        }

        // Priority 2: Daily route destinations (fill remaining slots)
        for (const route of dailyRoutes) {
            if (items.length >= maxItems) break;
            // Avoid duplicates — skip if a watch area is already at same location (within ~100m)
            const isDuplicate = items.some(item =>
                Math.abs(item.latitude - route.destination_latitude) < 0.001 &&
                Math.abs(item.longitude - route.destination_longitude) < 0.001
            );
            if (!isDuplicate) {
                items.push({
                    name: route.name,
                    latitude: route.destination_latitude,
                    longitude: route.destination_longitude,
                    source: 'daily_route',
                });
            }
        }

        return items;
    }, [watchAreas, dailyRoutes, maxItems]);

    // Empty state — no watch areas and no daily routes
    if (locations.length === 0) {
        return (
            <div className="bg-card text-card-foreground rounded-xl border shadow-sm p-4">
                <div className="flex items-center gap-2 mb-3">
                    <div className="w-8 h-8 rounded-lg bg-violet-100 flex items-center justify-center">
                        <Brain className="w-4 h-4 text-violet-600" />
                    </div>
                    <h3 className="font-semibold text-foreground text-sm">AI Risk Insights</h3>
                </div>
                <p className="text-sm text-muted-foreground">
                    Set up watch areas in your profile to get personalized AI risk insights for your locations.
                </p>
            </div>
        );
    }

    return (
        <div className="bg-card text-card-foreground rounded-xl border shadow-sm overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 border-b flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-violet-100 flex items-center justify-center flex-shrink-0">
                    <Brain className="w-4 h-4 text-violet-600" />
                </div>
                <h3 className="font-semibold text-foreground text-sm">AI Risk Insights</h3>

                <div className="ml-auto">
                    <Badge className="bg-violet-50 text-violet-600 border-none text-[10px] px-1.5 py-0">
                        <Sparkles className="w-3 h-3" />
                        AI
                    </Badge>
                </div>
            </div>

            {/* Items */}
            <div className="p-3 space-y-2">
                {locations.map((loc) => (
                    <RiskInsightItem
                        key={`${loc.source}-${loc.latitude}-${loc.longitude}`}
                        location={loc}
                        language={language}
                    />
                ))}
            </div>
        </div>
    );
}
