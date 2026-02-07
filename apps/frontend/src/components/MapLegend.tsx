import { useState } from 'react';
import { Button } from './ui/button';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface MapLegendProps {
    className?: string;
}

export default function MapLegend({ className }: MapLegendProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
        <div className={`bg-card rounded-lg shadow-xl border border-border ${className}`}>
            {/* Header */}
            <div className="flex items-center justify-between p-3 border-b border-border">
                <h3 className="text-sm font-semibold text-foreground">Map Legend</h3>
                <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="h-11 w-11 p-0"
                >
                    {isExpanded ? (
                        <ChevronDown className="h-4 w-4" />
                    ) : (
                        <ChevronUp className="h-4 w-4" />
                    )}
                </Button>
            </div>

            {/* Legend Content - max-height for mobile scroll */}
            {isExpanded && (
                <div className="p-3 space-y-3 max-h-[50vh] overflow-y-auto">
                    {/* Waterlogging Hotspots (FHI) - Main feature, shown first */}
                    <div>
                        <h4 className="text-xs font-semibold text-foreground/80 mb-2 flex items-center gap-1">
                            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                            Waterlogging Hotspots (Live)
                        </h4>
                        <div className="space-y-1.5">
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full ring-2 ring-green-300" style={{ backgroundColor: '#22c55e' }}></div>
                                <span className="text-xs text-muted-foreground">Low Risk (0-20%)</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full ring-2 ring-yellow-300" style={{ backgroundColor: '#eab308' }}></div>
                                <span className="text-xs text-muted-foreground">Moderate (20-40%)</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full ring-2 ring-orange-300" style={{ backgroundColor: '#f97316' }}></div>
                                <span className="text-xs text-muted-foreground">High (40-70%)</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full ring-2 ring-red-300" style={{ backgroundColor: '#ef4444' }}></div>
                                <span className="text-xs text-muted-foreground">Extreme (70-100%)</span>
                            </div>
                        </div>
                        <p className="text-xs text-muted-foreground/70 mt-1.5 italic">
                            Real-time weather conditions
                        </p>
                    </div>

                    {/* User Location */}
                    <div>
                        <h4 className="text-xs font-medium text-foreground/80 mb-2">Your Location</h4>
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full bg-blue-500 animate-pulse ring-2 ring-blue-300"></div>
                            <span className="text-xs text-muted-foreground">Current position</span>
                        </div>
                    </div>

                    {/* Sensor Status */}
                    <div>
                        <h4 className="text-xs font-medium text-foreground/80 mb-2">Sensors</h4>
                        <div className="space-y-1.5">
                            <LegendItem color="#22c55e" label="Active" shape="circle" />
                            <LegendItem color="#f97316" label="Warning" shape="circle" />
                            <LegendItem color="#ef4444" label="Critical" shape="circle" />
                        </div>
                    </div>

                    {/* Community Reports */}
                    <div>
                        <h4 className="text-xs font-medium text-foreground/80 mb-2">Community Reports</h4>
                        <div className="space-y-1.5">
                            <LegendItem color="#3b82f6" label="Ankle Deep" shape="circle" />
                            <LegendItem color="#f59e0b" label="Knee Deep" shape="circle" />
                            <LegendItem color="#f97316" label="Waist Deep" shape="circle" />
                            <LegendItem color="#ef4444" label="Impassable" shape="circle" />
                        </div>
                        <div className="mt-2 pt-2 border-t border-border">
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <div className="w-4 h-4 rounded-full border-2 border-green-500 bg-muted"></div>
                                <span>Verified</span>
                            </div>
                        </div>
                    </div>

                    {/* Routes */}
                    <div>
                        <h4 className="text-xs font-medium text-foreground/80 mb-2">Navigation Routes</h4>
                        <div className="space-y-1.5">
                            <LegendItem color="#3b82f6" label="Fastest Route" shape="line" />
                            <LegendItem color="#22c55e" label="Safest Route" shape="line" />
                            <div className="flex items-center gap-2">
                                <div className="w-4 h-3 rounded bg-red-500 opacity-50"></div>
                                <span className="text-xs text-muted-foreground">Flood area (avoid)</span>
                            </div>
                        </div>
                    </div>

                    {/* Metro Lines */}
                    <div>
                        <h4 className="text-xs font-medium text-foreground/80 mb-2">Metro</h4>
                        <div className="space-y-1.5">
                            <div className="flex items-center gap-2">
                                <div className="w-6 h-1 rounded bg-indigo-500"></div>
                                <span className="text-xs text-muted-foreground">Metro routes</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full bg-indigo-600 border-2 border-white shadow-sm"></div>
                                <span className="text-xs text-muted-foreground">Metro station</span>
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
                    className="w-4 h-4 rounded border border-border"
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
            <span className="text-xs text-muted-foreground">{label}</span>
        </div>
    );
}
