import React from 'react';
import { Navigation, ArrowRight, Clock, AlertTriangle, X, Loader2, MapPin } from 'lucide-react';
import { useNavigation } from '../contexts/NavigationContext';
import { formatDuration, formatDistance } from '../lib/geo/distance';

export function LiveNavigationPanel() {
    const { state, stopNavigation } = useNavigation();

    if (!state.isNavigating || !state.activeRoute) {
        return null;
    }

    const hasHotspotWarning = state.nearbyHotspots.length > 0;

    return (
        <div
            className="fixed left-0 md:left-64 right-0 z-[45] bg-card border-t border-border"
            style={{
                bottom: 'calc(64px + env(safe-area-inset-bottom, 0px))',
                boxShadow: '0 -4px 6px -1px rgba(0, 0, 0, 0.1), 0 -2px 4px -2px rgba(0, 0, 0, 0.1)'
            }}
        >
            <div className="max-w-screen-xl mx-auto px-4 py-3">
                {/* Hotspot Warning Banner */}
                {hasHotspotWarning && (
                    <div className="mb-3 p-2 bg-amber-100 border border-amber-300 rounded-lg flex items-start gap-2">
                        <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-amber-800">
                                Flood risk ahead
                            </p>
                            <div className="mt-1 space-y-0.5">
                                {state.nearbyHotspots.slice(0, 2).map((hotspot) => (
                                    <div key={hotspot.id} className="flex items-center gap-2 text-xs text-amber-700">
                                        <div
                                            className="w-2 h-2 rounded-full flex-shrink-0"
                                            style={{ backgroundColor: hotspot.fhi_color }}
                                        />
                                        <span className="truncate">
                                            {hotspot.name} - {Math.round(hotspot.distanceMeters)}m ahead
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {/* Recalculating Indicator */}
                {state.isRecalculating && (
                    <div className="mb-3 p-2 bg-blue-100 border border-blue-300 rounded-lg flex items-center gap-2">
                        <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
                        <span className="text-xs font-medium text-blue-800">
                            Recalculating route...
                        </span>
                    </div>
                )}

                <div className="flex items-start gap-3">
                    {/* Navigation Icon */}
                    <div className="flex-shrink-0 mt-1">
                        <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center">
                            <Navigation className="h-5 w-5 text-white" />
                        </div>
                    </div>

                    {/* Current Instruction */}
                    <div className="flex-1 min-w-0">
                        {state.currentInstruction ? (
                            <>
                                <p className="text-lg font-bold text-foreground truncate">
                                    {state.currentInstruction.instruction}
                                </p>
                                {state.distanceToNextTurn > 0 && (
                                    <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
                                        <ArrowRight className="h-4 w-4" />
                                        <span>
                                            In {formatDistance(state.distanceToNextTurn)}
                                        </span>
                                    </div>
                                )}
                                {state.currentInstruction.street_name && (
                                    <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
                                        <MapPin className="h-3 w-3" />
                                        <span className="truncate">
                                            {state.currentInstruction.street_name}
                                        </span>
                                    </div>
                                )}
                            </>
                        ) : (
                            <p className="text-lg font-bold text-foreground">
                                Continue on route
                            </p>
                        )}

                        {/* ETA and Distance Remaining */}
                        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                            <div className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                <span>ETA: {formatDuration(state.etaSeconds)}</span>
                            </div>
                            <div className="flex items-center gap-1">
                                <MapPin className="h-3 w-3" />
                                <span>{formatDistance(state.distanceRemaining)} remaining</span>
                            </div>
                        </div>

                        {/* Off Route Warning */}
                        {state.isOffRoute && (
                            <div className="mt-2 p-2 bg-red-100 border border-red-300 rounded flex items-center gap-2">
                                <AlertTriangle className="h-4 w-4 text-red-600 flex-shrink-0" />
                                <span className="text-xs font-medium text-red-800">
                                    You're off route - recalculating
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Stop Navigation Button */}
                    <button
                        onClick={stopNavigation}
                        className="flex-shrink-0 w-10 h-10 bg-red-500 hover:bg-red-600 rounded-full flex items-center justify-center transition-colors"
                        aria-label="Stop navigation"
                    >
                        <X className="h-5 w-5 text-white" />
                    </button>
                </div>
            </div>
        </div>
    );
}

export default LiveNavigationPanel;
