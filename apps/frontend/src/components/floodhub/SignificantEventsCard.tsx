/**
 * Significant Events Card - Displays major active flood events from Google FloodHub
 *
 * Shows affected population, area, and linked gauge count.
 * Only rendered when events exist (empty during non-flood periods is normal).
 */

import { AlertTriangle, Users, MapPin, Radio } from 'lucide-react';
import type { FloodHubSignificantEvent } from '../../types';

interface SignificantEventsCardProps {
    events: FloodHubSignificantEvent[];
    onSelectGauge?: (gaugeId: string) => void;
}

function formatPopulation(pop: number): string {
    if (pop >= 1_000_000) return `${(pop / 1_000_000).toFixed(1)}M`;
    if (pop >= 1_000) return `${(pop / 1_000).toFixed(0)}K`;
    return pop.toLocaleString();
}

function formatArea(km2: number): string {
    if (km2 >= 1_000) return `${(km2 / 1_000).toFixed(1)}K km²`;
    return `${km2.toFixed(0)} km²`;
}

function formatEventTime(startTime: string, endTime?: string | null): string {
    const start = new Date(startTime);
    const startStr = start.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

    if (endTime) {
        const end = new Date(endTime);
        const endStr = end.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
        return `${startStr} – ${endStr}`;
    }
    return `${startStr} – ongoing`;
}

export function SignificantEventsCard({ events, onSelectGauge }: SignificantEventsCardProps) {
    if (events.length === 0) return null;

    return (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-4 h-4 text-red-600" />
                <h3 className="text-sm font-semibold text-red-800">
                    Significant Flood Events ({events.length})
                </h3>
            </div>

            <div className="space-y-3">
                {events.map((event, idx) => (
                    <div
                        key={`${event.start_time}-${idx}`}
                        className="bg-white/70 rounded-lg p-3 border border-red-100"
                    >
                        <p className="text-xs font-medium text-red-700 mb-2">
                            {formatEventTime(event.start_time, event.end_time)}
                        </p>

                        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                            {event.affected_population != null && event.affected_population > 0 && (
                                <span className="flex items-center gap-1">
                                    <Users className="w-3 h-3" />
                                    {formatPopulation(event.affected_population)} affected
                                </span>
                            )}
                            {event.area_km2 != null && event.area_km2 > 0 && (
                                <span className="flex items-center gap-1">
                                    <MapPin className="w-3 h-3" />
                                    {formatArea(event.area_km2)}
                                </span>
                            )}
                            {event.gauge_ids.length > 0 && (
                                <span className="flex items-center gap-1">
                                    <Radio className="w-3 h-3" />
                                    {event.gauge_ids.length} gauge{event.gauge_ids.length > 1 ? 's' : ''}
                                </span>
                            )}
                        </div>

                        {/* Quick-link to linked gauges */}
                        {onSelectGauge && event.gauge_ids.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 mt-2">
                                {event.gauge_ids.slice(0, 3).map((gid) => (
                                    <button
                                        key={gid}
                                        onClick={() => onSelectGauge(gid)}
                                        className="text-xs text-red-600 hover:text-red-800 underline underline-offset-2"
                                    >
                                        {gid}
                                    </button>
                                ))}
                                {event.gauge_ids.length > 3 && (
                                    <span className="text-xs text-red-400">
                                        +{event.gauge_ids.length - 3} more
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
