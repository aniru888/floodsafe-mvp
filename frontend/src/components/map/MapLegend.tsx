import { useState } from 'react';
import { ChevronDown, ChevronUp, Eye, EyeOff } from 'lucide-react';

export type MapLegendLayerKey =
    | 'hotspots'
    | 'sensors'
    | 'reports'
    | 'route'
    | 'floodAreas'
    | 'metroLines'
    | 'metroStations';

export type MapLegendLayerVisibility = Record<MapLegendLayerKey, boolean>;

interface MapLegendProps {
    className?: string;
    layerVisibility: MapLegendLayerVisibility;
    onToggleLayer: (layer: MapLegendLayerKey) => void;
}

export default function MapLegend({ className, layerVisibility, onToggleLayer }: MapLegendProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
        <div className={`bg-white rounded-lg shadow-xl border border-gray-200 ${className}`}>
            {/* Header */}
            <div className="flex items-center justify-between p-3 border-b">
                <h3 className="text-sm font-semibold text-gray-900">Map Legend</h3>
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-gray-100"
                >
                    {isExpanded ? (
                        <ChevronDown className="h-4 w-4" />
                    ) : (
                        <ChevronUp className="h-4 w-4" />
                    )}
                </button>
            </div>

            {/* Legend Content - max-height for mobile scroll */}
            {isExpanded && (
                <div className="p-3 space-y-3 max-h-[50vh] overflow-y-auto">
                    {/* Waterlogging Hotspots (FHI) - Main feature, shown first */}
                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <h4 className="text-xs font-semibold text-gray-700 flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                                Waterlogging Hotspots (Live)
                            </h4>
                            <VisibilityToggle
                                isVisible={layerVisibility.hotspots}
                                onClick={() => onToggleLayer('hotspots')}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full ring-2 ring-green-300" style={{ backgroundColor: '#22c55e' }}></div>
                                <span className="text-xs text-gray-600">Low Risk (0-20%)</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full ring-2 ring-yellow-300" style={{ backgroundColor: '#eab308' }}></div>
                                <span className="text-xs text-gray-600">Moderate (20-40%)</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full ring-2 ring-orange-300" style={{ backgroundColor: '#f97316' }}></div>
                                <span className="text-xs text-gray-600">High (40-70%)</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full ring-2 ring-red-300" style={{ backgroundColor: '#ef4444' }}></div>
                                <span className="text-xs text-gray-600">Extreme (70-100%)</span>
                            </div>
                        </div>
                        <p className="text-xs text-gray-400 mt-1.5 italic">
                            Real-time weather conditions
                        </p>
                    </div>

                    {/* User Location */}
                    <div>
                        <h4 className="text-xs font-medium text-gray-700 mb-2">Your Location</h4>
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full bg-blue-500 animate-pulse ring-2 ring-blue-300"></div>
                            <span className="text-xs text-gray-600">Current position</span>
                        </div>
                    </div>

                    {/* Sensor Status */}
                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <h4 className="text-xs font-medium text-gray-700">Sensors</h4>
                            <VisibilityToggle
                                isVisible={layerVisibility.sensors}
                                onClick={() => onToggleLayer('sensors')}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <LegendItem color="#22c55e" label="Active" shape="circle" />
                            <LegendItem color="#f97316" label="Warning" shape="circle" />
                            <LegendItem color="#ef4444" label="Critical" shape="circle" />
                        </div>
                    </div>

                    {/* Community Reports */}
                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <h4 className="text-xs font-medium text-gray-700">Community Reports</h4>
                            <VisibilityToggle
                                isVisible={layerVisibility.reports}
                                onClick={() => onToggleLayer('reports')}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <LegendItem color="#3b82f6" label="Ankle Deep" shape="circle" />
                            <LegendItem color="#f59e0b" label="Knee Deep" shape="circle" />
                            <LegendItem color="#f97316" label="Waist Deep" shape="circle" />
                            <LegendItem color="#ef4444" label="Impassable" shape="circle" />
                        </div>
                        <div className="mt-2 pt-2 border-t border-gray-200">
                            <div className="flex items-center gap-2 text-xs text-gray-600">
                                <div className="w-4 h-4 rounded-full border-2 border-green-500 bg-gray-300"></div>
                                <span>Verified</span>
                            </div>
                        </div>
                    </div>

                    {/* Routes */}
                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <h4 className="text-xs font-medium text-gray-700">Navigation Routes</h4>
                            <VisibilityToggle
                                isVisible={layerVisibility.route}
                                onClick={() => onToggleLayer('route')}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <LegendItem color="#3b82f6" label="Fastest Route" shape="line" />
                            <LegendItem color="#22c55e" label="Safest Route" shape="line" />
                            <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                    <div className="w-4 h-3 rounded bg-red-500 opacity-50"></div>
                                    <span className="text-xs text-gray-600">Flood area (avoid)</span>
                                </div>
                                <VisibilityToggle
                                    isVisible={layerVisibility.floodAreas}
                                    onClick={() => onToggleLayer('floodAreas')}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Metro Lines */}
                    <div>
                        <h4 className="text-xs font-medium text-gray-700 mb-2">Metro</h4>
                        <div className="space-y-1.5">
                            <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                    <div className="w-6 h-1 rounded bg-indigo-500"></div>
                                    <span className="text-xs text-gray-600">Metro routes</span>
                                </div>
                                <VisibilityToggle
                                    isVisible={layerVisibility.metroLines}
                                    onClick={() => onToggleLayer('metroLines')}
                                />
                            </div>
                            <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 rounded-full bg-indigo-600 border-2 border-white shadow-sm"></div>
                                    <span className="text-xs text-gray-600">Metro station</span>
                                </div>
                                <VisibilityToggle
                                    isVisible={layerVisibility.metroStations}
                                    onClick={() => onToggleLayer('metroStations')}
                                />
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

interface LegendItemProps {
    color: string;
    label: string;
    shape?: 'square' | 'circle' | 'line';
    thickness?: 'normal' | 'thick';
}

function LegendItem({ color, label, shape = 'square', thickness = 'normal' }: LegendItemProps) {
    return (
        <div className="flex items-center gap-2">
            {shape === 'square' && (
                <div
                    className="w-4 h-4 rounded border border-gray-300"
                    style={{ backgroundColor: color, opacity: 0.6 }}
                />
            )}
            {shape === 'circle' && (
                <div
                    className="w-4 h-4 rounded-full border-2 border-white shadow-sm"
                    style={{ backgroundColor: color }}
                />
            )}
            {shape === 'line' && (
                <div
                    className={`w-6 rounded ${thickness === 'thick' ? 'h-1 shadow-md' : 'h-0.5'}`}
                    style={{ backgroundColor: color }}
                />
            )}
            <span className="text-xs text-gray-600">{label}</span>
        </div>
    );
}

interface VisibilityToggleProps {
    isVisible: boolean;
    onClick: () => void;
}

function VisibilityToggle({ isVisible, onClick }: VisibilityToggleProps) {
    return (
        <button
            type="button"
            onClick={onClick}
            className="h-7 w-7 flex items-center justify-center rounded-md border border-gray-200 hover:bg-gray-50 text-gray-600"
        >
            {isVisible ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
        </button>
    );
}
