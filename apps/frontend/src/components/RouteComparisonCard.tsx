import React from 'react';
import { Clock, Shield, AlertTriangle, Droplets, Radio, Brain, Check, ChevronDown, ChevronUp, MapPin } from 'lucide-react';
import { RouteComparisonResponse } from '../types';

interface RouteComparisonCardProps {
    comparison: RouteComparisonResponse;
    onSelectNormal: () => void;
    onSelectFloodSafe: () => void;
    selectedRoute: 'normal' | 'floodsafe' | null;
}

export function RouteComparisonCard({
    comparison,
    onSelectNormal,
    onSelectFloodSafe,
    selectedRoute,
}: RouteComparisonCardProps) {
    const [showDetails, setShowDetails] = React.useState(false);

    const {
        normal_route,
        floodsafe_route,
        time_penalty_seconds,
        flood_zones_avoided,
        risk_breakdown,
        stuck_time_estimate,
        net_time_saved,
        recommendation,
        hotspot_analysis,
    } = comparison;

    const formatDuration = (seconds: number | undefined): string => {
        if (!seconds) return 'N/A';
        const minutes = Math.round(seconds / 60);
        if (minutes < 60) return `${minutes} min`;
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return `${hours}h ${mins}m`;
    };

    const formatDistance = (meters: number | undefined): string => {
        if (!meters) return 'N/A';
        if (meters < 1000) return `${Math.round(meters)}m`;
        return `${(meters / 1000).toFixed(1)} km`;
    };

    const penaltyMinutes = Math.round(time_penalty_seconds / 60);
    const isStrongRecommendation = recommendation.startsWith('STRONGLY');
    const hasSevereFlooding = ['waist', 'impassable'].includes(stuck_time_estimate.severity_level);

    // Determine recommendation color
    const getRecommendationStyle = () => {
        if (isStrongRecommendation || hasSevereFlooding) {
            return 'bg-red-100 border-red-300 text-red-800';
        }
        if (flood_zones_avoided > 0) {
            return 'bg-amber-100 border-amber-300 text-amber-800';
        }
        return 'bg-green-100 border-green-300 text-green-800';
    };

    return (
        <div className="space-y-3">
            {/* Recommendation Banner */}
            <div className={`p-3 rounded-lg border ${getRecommendationStyle()}`}>
                <div className="flex items-start gap-2">
                    <AlertTriangle className="h-5 w-5 flex-shrink-0 mt-0.5" />
                    <p className="text-sm font-medium">{recommendation}</p>
                </div>
            </div>

            {/* Route Comparison Cards */}
            <div className="grid grid-cols-2 gap-3">
                {/* Normal Route Card */}
                <button
                    onClick={onSelectNormal}
                    disabled={!normal_route}
                    className={`p-3 rounded-lg border-2 text-left transition-all relative ${
                        selectedRoute === 'normal'
                            ? 'border-foreground bg-muted ring-2 ring-ring'
                            : 'border-border hover:border-muted-foreground'
                    } ${!normal_route ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                    {/* Selection checkmark indicator */}
                    {selectedRoute === 'normal' && (
                        <div className="absolute -top-2 -right-2 bg-foreground rounded-full p-1 shadow-sm">
                            <Check className="h-3 w-3 text-white" />
                        </div>
                    )}
                    <div className="flex items-center gap-2 mb-2">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium text-sm">Normal</span>
                    </div>
                    {normal_route ? (
                        <>
                            <div className="text-lg font-bold text-foreground">
                                {formatDuration(normal_route.duration_seconds)}
                            </div>
                            <div className="text-xs text-muted-foreground">
                                {formatDistance(normal_route.distance_meters)}
                            </div>
                            {normal_route.flood_intersections > 0 && (
                                <div className="mt-2 flex items-center gap-1 text-red-600 text-xs font-medium">
                                    <AlertTriangle className="h-3 w-3" />
                                    {normal_route.flood_intersections} flood zone{normal_route.flood_intersections > 1 ? 's' : ''}
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="text-sm text-muted-foreground/60">Unavailable</div>
                    )}
                </button>

                {/* FloodSafe Route Card */}
                <button
                    onClick={onSelectFloodSafe}
                    disabled={!floodsafe_route}
                    className={`p-3 rounded-lg border-2 text-left transition-all relative ${
                        selectedRoute === 'floodsafe'
                            ? 'border-green-500 bg-green-50 ring-2 ring-green-200'
                            : 'border-border hover:border-green-300'
                    } ${!floodsafe_route ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                    {/* Selection checkmark indicator */}
                    {selectedRoute === 'floodsafe' && (
                        <div className="absolute -top-2 -right-2 bg-green-600 rounded-full p-1 shadow-sm">
                            <Check className="h-3 w-3 text-white" />
                        </div>
                    )}
                    <div className="flex items-center gap-2 mb-2">
                        <Shield className="h-4 w-4 text-green-600" />
                        <span className="font-medium text-sm text-green-700">FloodSafe</span>
                    </div>
                    {floodsafe_route ? (
                        <>
                            <div className="text-lg font-bold text-green-700">
                                {formatDuration(floodsafe_route.duration_seconds)}
                            </div>
                            <div className="text-xs text-muted-foreground">
                                {formatDistance(floodsafe_route.distance_meters)}
                            </div>
                            <div className="mt-2 flex items-center gap-1 text-green-600 text-xs font-medium">
                                <Check className="h-3 w-3" />
                                Safety: {floodsafe_route.safety_score}/100
                            </div>
                        </>
                    ) : (
                        <div className="text-sm text-muted-foreground/60">Unavailable</div>
                    )}
                </button>
            </div>

            {/* Time Penalty Badge */}
            {flood_zones_avoided > 0 && (
                <div className="flex items-center justify-center gap-2 p-2 bg-primary/10 rounded-lg border border-primary/20">
                    <Clock className="h-4 w-4 text-primary" />
                    <span className="text-sm text-primary font-medium">
                        +{penaltyMinutes} min to avoid {flood_zones_avoided} flood zone{flood_zones_avoided > 1 ? 's' : ''}
                    </span>
                </div>
            )}

            {/* Expandable Details */}
            <button
                onClick={() => setShowDetails(!showDetails)}
                className="w-full flex items-center justify-between p-2 text-sm text-muted-foreground hover:bg-muted rounded-lg"
            >
                <span>Time Analysis & Risk Details</span>
                {showDetails ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>

            {showDetails && (
                <div className="space-y-3 p-3 bg-muted rounded-lg">
                    {/* Time Analysis */}
                    {stuck_time_estimate.avg_stuck_minutes > 0 && (
                        <div className="space-y-2">
                            <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                                Time Analysis
                            </h4>
                            <div className="space-y-1 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">FloodSafe penalty:</span>
                                    <span className="font-medium">+{penaltyMinutes} min</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">If stuck (average):</span>
                                    <span className="font-medium text-red-600">
                                        ~{stuck_time_estimate.avg_stuck_minutes} min delay
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">If stuck (worst):</span>
                                    <span className="font-medium text-red-600">
                                        ~{stuck_time_estimate.worst_case_minutes} min delay
                                    </span>
                                </div>
                                <div className="flex justify-between pt-1 border-t border-border">
                                    <span className="text-muted-foreground">Net time saved:</span>
                                    <span className="font-medium text-green-600">
                                        {Math.round(net_time_saved.vs_average_stuck)}-{Math.round(net_time_saved.vs_worst_case)} min
                                    </span>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Risk Breakdown */}
                    <div className="space-y-2">
                        <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                            Risk Breakdown
                        </h4>
                        <div className="grid grid-cols-3 gap-2">
                            <div className="flex flex-col items-center p-2 bg-card rounded border border-border">
                                <Droplets className="h-4 w-4 text-blue-500 mb-1" />
                                <span className="text-lg font-bold">{risk_breakdown.active_reports}</span>
                                <span className="text-xs text-muted-foreground">Reports</span>
                            </div>
                            <div className="flex flex-col items-center p-2 bg-card rounded border border-border">
                                <Radio className="h-4 w-4 text-orange-500 mb-1" />
                                <span className="text-lg font-bold">{risk_breakdown.sensor_warnings}</span>
                                <span className="text-xs text-muted-foreground">Sensors</span>
                            </div>
                            <div className="flex flex-col items-center p-2 bg-card rounded border border-border">
                                <Brain className="h-4 w-4 text-purple-500 mb-1" />
                                <span className="text-lg font-bold">{risk_breakdown.ml_high_risk_zones}</span>
                                <span className="text-xs text-muted-foreground">AI Risk</span>
                            </div>
                        </div>
                    </div>

                    {/* Risk Factors */}
                    {stuck_time_estimate.risk_factors.length > 0 && (
                        <div className="space-y-2">
                            <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                                Risk Factors
                            </h4>
                            <ul className="space-y-1">
                                {stuck_time_estimate.risk_factors.map((factor, idx) => (
                                    <li key={idx} className="flex items-center gap-2 text-sm text-muted-foreground">
                                        <span className="w-1.5 h-1.5 bg-red-500 rounded-full" />
                                        {factor}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}

            {/* Hotspot Analysis Section - Only shown for Delhi routes with hotspots */}
            {hotspot_analysis && hotspot_analysis.nearby_hotspots.length > 0 && (
                <div className="space-y-2 p-3 bg-amber-50 rounded-lg border border-amber-200">
                    <h4 className="text-xs font-semibold text-amber-800 uppercase tracking-wider flex items-center gap-1">
                        <MapPin className="h-3 w-3" />
                        Waterlogging Hotspots on Route
                    </h4>

                    {/* Must Reroute Warning */}
                    {hotspot_analysis.must_reroute && (
                        <div className="flex items-start gap-2 p-2 bg-red-100 rounded border border-red-200 mb-2">
                            <AlertTriangle className="h-4 w-4 text-red-600 flex-shrink-0 mt-0.5" />
                            <p className="text-xs text-red-700 font-medium">
                                {hotspot_analysis.warning_message || 'Route passes through HIGH/EXTREME risk areas - reroute recommended'}
                            </p>
                        </div>
                    )}

                    {/* Hotspot List */}
                    <div className="space-y-1.5">
                        {hotspot_analysis.nearby_hotspots.slice(0, 3).map((hotspot) => (
                            <div
                                key={hotspot.id}
                                className="flex items-center justify-between text-xs"
                            >
                                <div className="flex items-center gap-2">
                                    <div
                                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                                        style={{ backgroundColor: hotspot.fhi_color }}
                                    />
                                    <span className="text-foreground truncate max-w-[160px]">
                                        {hotspot.name}
                                    </span>
                                </div>
                                <span
                                    className="px-1.5 py-0.5 rounded text-[10px] font-bold flex-shrink-0"
                                    style={{
                                        backgroundColor: `${hotspot.fhi_color}20`,
                                        color: hotspot.fhi_color
                                    }}
                                >
                                    {hotspot.fhi_level.toUpperCase()}
                                </span>
                            </div>
                        ))}
                    </div>

                    {/* Hotspots Avoided Summary */}
                    {hotspot_analysis.hotspots_avoided > 0 && (
                        <p className="text-xs text-amber-700 pt-2 border-t border-amber-200 font-medium">
                            FloodSafe route avoids {hotspot_analysis.hotspots_avoided} hotspot(s)
                            {hotspot_analysis.critical_hotspots_avoided > 0 && (
                                <span className="text-red-600">
                                    {' '}({hotspot_analysis.critical_hotspots_avoided} critical)
                                </span>
                            )}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}

export default RouteComparisonCard;
