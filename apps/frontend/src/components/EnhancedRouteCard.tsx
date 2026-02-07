import React from 'react';
import { Car, Train, Shield, AlertTriangle, Check } from 'lucide-react';
import type { EnhancedRoutes, RouteRecommendation, TrafficLevel } from '../types';
import { formatDuration, formatDistance } from '../lib/geo/distance';

interface EnhancedRouteCardProps {
    routes: EnhancedRoutes;
    recommendation: RouteRecommendation;
    selectedType: 'fastest' | 'metro' | 'safest' | null;
    onSelectRoute: (type: 'fastest' | 'metro' | 'safest') => void;
}

export function EnhancedRouteCard({
    routes,
    recommendation: _recommendation,
    selectedType,
    onSelectRoute,
}: EnhancedRouteCardProps) {
    const getTrafficColor = (level: TrafficLevel): string => {
        switch (level) {
            case 'low': return 'text-green-600 bg-green-100';
            case 'moderate': return 'text-yellow-600 bg-yellow-100';
            case 'heavy': return 'text-orange-600 bg-orange-100';
            case 'severe': return 'text-red-600 bg-red-100';
            default: return 'text-muted-foreground bg-muted';
        }
    };

    return (
        <div className="grid grid-cols-3 gap-3">
            {/* Fastest Route Card */}
            <button
                onClick={() => routes.fastest && onSelectRoute('fastest')}
                disabled={!routes.fastest}
                className={`p-3 rounded-lg border-2 text-left transition-all relative ${
                    selectedType === 'fastest'
                        ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                        : 'border-border hover:border-primary/50'
                } ${!routes.fastest ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
                {/* Recommended Badge */}
                {routes.fastest?.is_recommended && (
                    <div className="absolute -top-2 -left-2 bg-purple-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full shadow-sm">
                        Recommended
                    </div>
                )}

                {/* Selection Checkmark */}
                {selectedType === 'fastest' && (
                    <div className="absolute -top-2 -right-2 bg-blue-600 rounded-full p-1 shadow-sm">
                        <Check className="h-3 w-3 text-white" />
                    </div>
                )}

                <div className="flex items-center gap-2 mb-2">
                    <Car className="h-4 w-4 text-blue-600" />
                    <span className="font-medium text-sm text-blue-700">Fastest</span>
                </div>

                {routes.fastest ? (
                    <>
                        {/* Duration */}
                        <div className="text-lg font-bold text-blue-700">
                            {formatDuration(routes.fastest.duration_seconds)}
                        </div>

                        {/* Distance */}
                        <div className="text-xs text-muted-foreground">
                            {formatDistance(routes.fastest.distance_meters)}
                        </div>

                        {/* Traffic Level */}
                        <div className={`mt-2 px-2 py-0.5 rounded text-xs font-medium inline-flex items-center gap-1 ${getTrafficColor(routes.fastest.traffic_level)}`}>
                            <span className="w-1.5 h-1.5 rounded-full bg-current" />
                            {routes.fastest.traffic_level.charAt(0).toUpperCase() + routes.fastest.traffic_level.slice(1)} traffic
                        </div>

                        {/* Hotspot Count Badge */}
                        {routes.fastest.hotspot_count > 0 && (
                            <div className="mt-1 flex items-center gap-1 text-amber-600 text-xs font-medium">
                                <AlertTriangle className="h-3 w-3" />
                                {routes.fastest.hotspot_count} hotspot{routes.fastest.hotspot_count > 1 ? 's' : ''}
                            </div>
                        )}

                        {/* Safety Score */}
                        <div className="mt-1 text-xs text-muted-foreground">
                            Safety: {routes.fastest.safety_score}/100
                        </div>
                    </>
                ) : (
                    <div className="text-sm text-muted-foreground/60">Unavailable</div>
                )}
            </button>

            {/* Metro Route Card */}
            <button
                onClick={() => routes.metro && onSelectRoute('metro')}
                disabled={!routes.metro}
                className={`p-3 rounded-lg border-2 text-left transition-all relative ${
                    selectedType === 'metro'
                        ? 'border-purple-500 bg-purple-50 ring-2 ring-purple-200'
                        : 'border-border hover:border-purple-300'
                } ${!routes.metro ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
                {/* Recommended Badge */}
                {routes.metro?.is_recommended && (
                    <div className="absolute -top-2 -left-2 bg-purple-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full shadow-sm">
                        Recommended
                    </div>
                )}

                {/* Selection Checkmark */}
                {selectedType === 'metro' && (
                    <div className="absolute -top-2 -right-2 bg-purple-600 rounded-full p-1 shadow-sm">
                        <Check className="h-3 w-3 text-white" />
                    </div>
                )}

                <div className="flex items-center gap-2 mb-2">
                    <Train className="h-4 w-4 text-purple-600" />
                    <span className="font-medium text-sm text-purple-700">Metro</span>
                </div>

                {routes.metro ? (
                    <>
                        {/* Duration */}
                        <div className="text-lg font-bold text-purple-700">
                            {formatDuration(routes.metro.total_duration_seconds)}
                        </div>

                        {/* Metro Line Badge */}
                        <div
                            className="mt-2 px-2 py-0.5 rounded text-xs font-medium inline-block text-white"
                            style={{ backgroundColor: routes.metro.metro_color }}
                        >
                            {routes.metro.metro_line}
                        </div>

                        {/* Walking Distance */}
                        {routes.metro.total_distance_meters > 0 && (
                            <div className="mt-1 text-xs text-muted-foreground">
                                {formatDistance(routes.metro.total_distance_meters)} walking
                            </div>
                        )}

                        {/* Affected Stations Warning */}
                        {routes.metro.affected_stations.length > 0 && (
                            <div className="mt-1 flex items-center gap-1 text-amber-600 text-xs font-medium">
                                <AlertTriangle className="h-3 w-3" />
                                {routes.metro.affected_stations.length} station{routes.metro.affected_stations.length > 1 ? 's' : ''} affected
                            </div>
                        )}
                    </>
                ) : (
                    <div className="text-sm text-muted-foreground/60">Unavailable</div>
                )}
            </button>

            {/* Safest Route Card */}
            <button
                onClick={() => routes.safest && onSelectRoute('safest')}
                disabled={!routes.safest}
                className={`p-3 rounded-lg border-2 text-left transition-all relative ${
                    selectedType === 'safest'
                        ? 'border-green-500 bg-green-50 ring-2 ring-green-200'
                        : 'border-border hover:border-green-300'
                } ${!routes.safest ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
                {/* Recommended Badge */}
                {routes.safest?.is_recommended && (
                    <div className="absolute -top-2 -left-2 bg-purple-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full shadow-sm">
                        Recommended
                    </div>
                )}

                {/* Selection Checkmark */}
                {selectedType === 'safest' && (
                    <div className="absolute -top-2 -right-2 bg-green-600 rounded-full p-1 shadow-sm">
                        <Check className="h-3 w-3 text-white" />
                    </div>
                )}

                <div className="flex items-center gap-2 mb-2">
                    <Shield className="h-4 w-4 text-green-600" />
                    <span className="font-medium text-sm text-green-700">Safest</span>
                </div>

                {routes.safest ? (
                    <>
                        {/* Duration */}
                        <div className="text-lg font-bold text-green-700">
                            {formatDuration(routes.safest.duration_seconds)}
                        </div>

                        {/* Distance */}
                        <div className="text-xs text-muted-foreground">
                            {formatDistance(routes.safest.distance_meters)}
                        </div>

                        {/* Detour Info */}
                        {routes.safest.detour_minutes > 0 && (
                            <div className="mt-2 text-xs text-amber-600 font-medium">
                                +{routes.safest.detour_minutes} min, +{routes.safest.detour_km.toFixed(1)} km
                            </div>
                        )}

                        {/* Hotspot Count */}
                        {routes.safest.hotspot_count > 0 ? (
                            <div className="mt-1 flex items-center gap-1 text-amber-600 text-xs font-medium">
                                <AlertTriangle className="h-3 w-3" />
                                {routes.safest.hotspot_count} hotspot{routes.safest.hotspot_count > 1 ? 's' : ''}
                            </div>
                        ) : (
                            <div className="mt-1 flex items-center gap-1 text-green-600 text-xs font-medium">
                                <Check className="h-3 w-3" />
                                No hotspots
                            </div>
                        )}

                        {/* Safety Score */}
                        <div className="mt-1 flex items-center gap-1 text-green-600 text-xs font-medium">
                            <Check className="h-3 w-3" />
                            Safety: {routes.safest.safety_score}/100
                        </div>
                    </>
                ) : (
                    <div className="text-sm text-muted-foreground/60">Unavailable</div>
                )}
            </button>
        </div>
    );
}

export default EnhancedRouteCard;
