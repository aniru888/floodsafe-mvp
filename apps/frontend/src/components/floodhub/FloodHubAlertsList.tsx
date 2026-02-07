/**
 * FloodHub Alerts List - Displays gauge cards with current flood status
 */

import { MapPin, Clock, ChevronRight } from 'lucide-react';
import type { FloodHubGauge, FloodHubSeverity } from '../../types';

interface FloodHubAlertsListProps {
    gauges: FloodHubGauge[];
    selectedGaugeId: string | null;
    onSelectGauge: (gaugeId: string | null) => void;
}

const severityStyles: Record<FloodHubSeverity, {
    dot: string;
    badge: string;
    label: string;
}> = {
    EXTREME: {
        dot: 'bg-red-500',
        badge: 'bg-red-100 text-red-800 border-red-200',
        label: 'Extreme',
    },
    SEVERE: {
        dot: 'bg-orange-500',
        badge: 'bg-orange-100 text-orange-800 border-orange-200',
        label: 'Severe',
    },
    ABOVE_NORMAL: {
        dot: 'bg-yellow-500',
        badge: 'bg-yellow-100 text-yellow-800 border-yellow-200',
        label: 'Above Normal',
    },
    NO_FLOODING: {
        dot: 'bg-green-500',
        badge: 'bg-green-100 text-green-800 border-green-200',
        label: 'Normal',
    },
    UNKNOWN: {
        dot: 'bg-gray-400',
        badge: 'bg-gray-100 text-gray-600 border-gray-200',
        label: 'Unknown',
    },
};

function GaugeCard({
    gauge,
    isSelected,
    onSelect,
}: {
    gauge: FloodHubGauge;
    isSelected: boolean;
    onSelect: () => void;
}) {
    const style = severityStyles[gauge.severity];
    const issuedDate = gauge.issued_time ? new Date(gauge.issued_time) : null;
    const issuedTime = issuedDate && !isNaN(issuedDate.getTime())
        ? issuedDate.toLocaleString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
            day: 'numeric',
            month: 'short',
        })
        : 'Unknown';

    return (
        <button
            onClick={onSelect}
            className={`w-full p-3 rounded-xl border text-left transition-all ${
                isSelected
                    ? 'border-primary bg-primary/5 ring-1 ring-primary/20'
                    : 'border-border bg-card hover:border-border/80 hover:bg-muted'
            }`}
        >
            <div className="flex items-start gap-3">
                {/* Severity indicator dot */}
                <div className={`w-3 h-3 rounded-full mt-1 ${style.dot}`} />

                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                        <h4 className="font-medium text-foreground truncate">
                            {gauge.site_name}
                        </h4>
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${style.badge}`}>
                            {style.label}
                        </span>
                    </div>

                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                            <MapPin className="w-3 h-3" />
                            {gauge.river}
                        </span>
                        <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {issuedTime}
                        </span>
                    </div>
                </div>

                <ChevronRight className={`w-4 h-4 text-muted-foreground ${isSelected ? 'text-primary' : ''}`} />
            </div>
        </button>
    );
}

export function FloodHubAlertsList({ gauges, selectedGaugeId, onSelectGauge }: FloodHubAlertsListProps) {
    // Sort gauges by severity (most severe first)
    const severityOrder: FloodHubSeverity[] = ['EXTREME', 'SEVERE', 'ABOVE_NORMAL', 'UNKNOWN', 'NO_FLOODING'];
    const sortedGauges = [...gauges].sort((a, b) => {
        return severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity);
    });

    // Filter to only show gauges with active flooding (exclude NO_FLOODING for alert display)
    const activeAlerts = sortedGauges.filter(g => g.severity !== 'NO_FLOODING');
    const normalGauges = sortedGauges.filter(g => g.severity === 'NO_FLOODING');

    if (gauges.length === 0) {
        return (
            <div className="text-center py-8 text-muted-foreground">
                <p>No gauge data available</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Active Alerts Section */}
            {activeAlerts.length > 0 && (
                <div>
                    <h3 className="text-sm font-medium text-foreground mb-2">
                        Active Alerts ({activeAlerts.length})
                    </h3>
                    <div className="space-y-2">
                        {activeAlerts.map((gauge) => (
                            <GaugeCard
                                key={gauge.gauge_id}
                                gauge={gauge}
                                isSelected={selectedGaugeId === gauge.gauge_id}
                                onSelect={() => onSelectGauge(
                                    selectedGaugeId === gauge.gauge_id ? null : gauge.gauge_id
                                )}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* All Clear Message */}
            {activeAlerts.length === 0 && (
                <div className="text-center py-4 bg-green-50 rounded-xl border border-green-200">
                    <p className="text-green-700 font-medium">No Active Flood Alerts</p>
                    <p className="text-sm text-green-600 mt-1">
                        All monitoring stations report normal water levels
                    </p>
                </div>
            )}

            {/* Normal Gauges (collapsed by default) */}
            {normalGauges.length > 0 && (
                <details className="group">
                    <summary className="text-sm font-medium text-muted-foreground cursor-pointer hover:text-foreground py-2">
                        Normal Stations ({normalGauges.length})
                    </summary>
                    <div className="space-y-2 mt-2">
                        {normalGauges.map((gauge) => (
                            <GaugeCard
                                key={gauge.gauge_id}
                                gauge={gauge}
                                isSelected={selectedGaugeId === gauge.gauge_id}
                                onSelect={() => onSelectGauge(
                                    selectedGaugeId === gauge.gauge_id ? null : gauge.gauge_id
                                )}
                            />
                        ))}
                    </div>
                </details>
            )}
        </div>
    );
}
