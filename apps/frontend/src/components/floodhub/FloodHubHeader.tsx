/**
 * FloodHub Header - Status banner showing overall flood risk level
 */

import { Waves, AlertTriangle, CheckCircle, HelpCircle } from 'lucide-react';
import type { FloodHubStatus, FloodHubSeverity } from '../../types';

interface FloodHubHeaderProps {
    status: FloodHubStatus;
    city?: string;
}

const severityConfig: Record<FloodHubSeverity, {
    label: string;
    bgColor: string;
    textColor: string;
    borderColor: string;
    icon: typeof AlertTriangle;
}> = {
    EXTREME: {
        label: 'Extreme Risk',
        bgColor: 'bg-red-50',
        textColor: 'text-red-700',
        borderColor: 'border-red-200',
        icon: AlertTriangle,
    },
    SEVERE: {
        label: 'Severe Risk',
        bgColor: 'bg-orange-50',
        textColor: 'text-orange-700',
        borderColor: 'border-orange-200',
        icon: AlertTriangle,
    },
    ABOVE_NORMAL: {
        label: 'Elevated Risk',
        bgColor: 'bg-yellow-50',
        textColor: 'text-yellow-700',
        borderColor: 'border-yellow-200',
        icon: AlertTriangle,
    },
    NO_FLOODING: {
        label: 'Normal Conditions',
        bgColor: 'bg-green-50',
        textColor: 'text-green-700',
        borderColor: 'border-green-200',
        icon: CheckCircle,
    },
    UNKNOWN: {
        label: 'Status Unknown',
        bgColor: 'bg-gray-50',
        textColor: 'text-gray-600',
        borderColor: 'border-gray-200',
        icon: HelpCircle,
    },
};

export function FloodHubHeader({ status, city }: FloodHubHeaderProps) {
    const severity = status.overall_severity || 'UNKNOWN';
    const config = severityConfig[severity];
    const Icon = config.icon;

    // City-specific header label
    const headerLabel = city?.toLowerCase() === 'delhi' ? 'Yamuna River Status' : 'Flood Monitoring Status';

    // Format last updated time
    const lastUpdated = status.last_updated
        ? new Date(status.last_updated).toLocaleString('en-IN', {
            day: 'numeric',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit',
        })
        : 'Unknown';

    return (
        <div className={`rounded-xl border p-4 ${config.bgColor} ${config.borderColor}`}>
            <div className="flex items-start gap-3">
                <div className={`p-2 rounded-full ${config.bgColor}`}>
                    <Icon className={`w-5 h-5 ${config.textColor}`} />
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <Waves className={`w-4 h-4 ${config.textColor}`} />
                        <h3 className={`font-semibold ${config.textColor}`}>
                            {headerLabel}
                        </h3>
                    </div>
                    <p className={`text-lg font-bold mt-1 ${config.textColor}`}>
                        {config.label}
                    </p>
                    <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                        {status.gauge_count !== undefined && (
                            <span>{status.gauge_count} monitoring stations</span>
                        )}
                        <span>Updated: {lastUpdated}</span>
                    </div>
                </div>
            </div>

            {/* Severity breakdown if available */}
            {status.alerts_by_severity && Object.keys(status.alerts_by_severity).length > 0 && (
                <div className="mt-3 pt-3 border-t border-border/50">
                    <div className="flex flex-wrap gap-2">
                        {Object.entries(status.alerts_by_severity)
                            .filter(([, count]) => count > 0)
                            .map(([sev, count]) => {
                                const sevConfig = severityConfig[sev as FloodHubSeverity] || severityConfig.UNKNOWN;
                                return (
                                    <span
                                        key={sev}
                                        className={`px-2 py-1 rounded-full text-xs font-medium ${sevConfig.bgColor} ${sevConfig.textColor} border ${sevConfig.borderColor}`}
                                    >
                                        {count} {sev.replace('_', ' ').toLowerCase()}
                                    </span>
                                );
                            })}
                    </div>
                </div>
            )}
        </div>
    );
}
