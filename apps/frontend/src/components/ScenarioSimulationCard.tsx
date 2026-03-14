/**
 * ScenarioSimulationCard — "What If?" rainfall impact simulation
 *
 * Uses the AI chat endpoint to simulate the impact of a given rainfall amount
 * on the current city's flood risk (FHI).
 */

import { useState } from 'react';
import { CloudRain, Play, Loader2 } from 'lucide-react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { useAiChat } from '../lib/api/hooks';

interface ScenarioSimulationCardProps {
    city: string;
    latitude?: number;
    longitude?: number;
}

export function ScenarioSimulationCard({ city, latitude, longitude }: ScenarioSimulationCardProps) {
    const [rainfallMm, setRainfallMm] = useState(50);
    const [result, setResult] = useState<string | null>(null);
    const { mutate: sendChat, isPending } = useAiChat();

    function handleSimulate() {
        const message = `Simulate: What would happen if ${rainfallMm}mm of rain fell in ${city} right now? Give a brief flood risk assessment.`;
        sendChat(
            { message, city, latitude, longitude },
            {
                onSuccess: (data) => {
                    setResult(data.reply);
                },
                onError: () => {
                    setResult('Unable to run simulation. Please try again.');
                },
            }
        );
    }

    // Clear previous result when slider changes
    function handleSliderChange(e: React.ChangeEvent<HTMLInputElement>) {
        setRainfallMm(Number(e.target.value));
        setResult(null);
    }

    // Label color based on rainfall amount
    function getRainfallLabel(): { text: string; className: string } {
        if (rainfallMm < 30) return { text: 'Light rain', className: 'text-green-600' };
        if (rainfallMm < 70) return { text: 'Moderate rain', className: 'text-yellow-600' };
        if (rainfallMm < 120) return { text: 'Heavy rain', className: 'text-orange-600' };
        return { text: 'Extreme rainfall', className: 'text-red-600' };
    }

    const rainfallLabel = getRainfallLabel();

    return (
        <Card className="bg-card text-card-foreground rounded-xl border shadow-sm p-4">
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                    <CloudRain className="w-4 h-4 text-blue-600" />
                </div>
                <div>
                    <h3 className="text-sm font-semibold text-foreground">What If It Rained?</h3>
                    <p className="text-xs text-muted-foreground">Simulate rainfall impact on {city}</p>
                </div>
            </div>

            {/* Slider */}
            <div className="mb-3">
                <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-muted-foreground">Rainfall amount</span>
                    <div className="flex items-center gap-1">
                        <span className="text-sm font-bold text-foreground">{rainfallMm}mm</span>
                        <span className={`text-xs font-medium ${rainfallLabel.className}`}>
                            — {rainfallLabel.text}
                        </span>
                    </div>
                </div>
                <input
                    type="range"
                    min={10}
                    max={200}
                    step={5}
                    value={rainfallMm}
                    onChange={handleSliderChange}
                    className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-gradient-to-r from-green-300 via-yellow-300 via-orange-300 to-red-400 accent-blue-600"
                    aria-label="Rainfall amount in millimetres"
                />
                <div className="flex justify-between text-xs text-muted-foreground/60 mt-1">
                    <span>10mm</span>
                    <span>200mm</span>
                </div>
            </div>

            {/* Simulate button */}
            <Button
                size="sm"
                className="w-full"
                onClick={handleSimulate}
                disabled={isPending}
            >
                {isPending ? (
                    <>
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Simulating...
                    </>
                ) : (
                    <>
                        <Play className="w-3 h-3" />
                        Simulate {rainfallMm}mm
                    </>
                )}
            </Button>

            {/* Result */}
            {result && (
                <div className="mt-3 p-3 rounded-lg bg-muted/50 border border-border">
                    <p className="text-xs text-muted-foreground leading-relaxed">{result}</p>
                </div>
            )}
        </Card>
    );
}
