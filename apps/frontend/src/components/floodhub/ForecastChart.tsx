/**
 * FloodHub Forecast Chart - 7-day water level forecast visualization
 *
 * CRITICAL: Uses ChartContainer wrapper from ui/chart.tsx
 * This is required for proper theming and responsive sizing.
 */

import { LineChart, Line, XAxis, YAxis, CartesianGrid, ReferenceLine, ReferenceArea, Dot, Area, ComposedChart } from 'recharts';
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '../ui/chart';
import type { FloodHubForecast } from '../../types';

interface ForecastChartProps {
    forecast: FloodHubForecast;
}

// Chart color configuration
const chartConfig = {
    level: {
        label: 'Water Level',
        color: '#4285F4', // Google Blue
    },
    band: {
        label: 'Uncertainty',
        color: '#4285F4', // Blue (semi-transparent fill)
    },
    danger: {
        label: 'Danger Level',
        color: '#D32F2F', // Red
    },
    warning: {
        label: 'Warning Level',
        color: '#F57C00', // Orange
    },
    extreme: {
        label: 'Extreme Danger',
        color: '#7B1FA2', // Purple
    },
} satisfies ChartConfig;

export function ForecastChart({ forecast }: ForecastChartProps) {
    // Guard against missing or empty forecast data
    if (!forecast?.forecasts?.length) {
        return (
            <div className="bg-card rounded-lg border border-border p-4">
                <p className="text-sm text-muted-foreground text-center py-8">No forecast data available</p>
            </div>
        );
    }

    // Unit label from gauge model (meters vs discharge)
    const isDischarge = forecast.gauge_value_unit === 'CUBIC_METERS_PER_SECOND';
    const unitLabel = isDischarge ? 'm³/s' : 'm';
    const unitName = isDischarge ? 'Discharge' : 'Water Level';

    // Transform forecast data for Recharts — add confidence band for forecast points
    const data = forecast.forecasts.map((point) => {
        const date = new Date(point.timestamp);
        const level = point.water_level;
        // Confidence band: ±8% for forecast points. Null levels (dry season) get no band.
        const bandWidth = (point.is_forecast && level !== null) ? level * 0.08 : 0;
        return {
            date: date.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric' }),
            fullDate: date.toLocaleString('en-IN', {
                weekday: 'short',
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit',
            }),
            level,
            bandLow: (point.is_forecast && level !== null) ? level - bandWidth : null,
            bandHigh: (point.is_forecast && level !== null) ? level + bandWidth : null,
            isForecast: point.is_forecast,
        };
    });

    // Find the label for the "Now" reference line (closest observed-to-forecast boundary)
    const nowEntry = data.find((d) => d.isForecast) ?? data[data.length - 1];
    const nowLabel = nowEntry?.date ?? '';

    // Calculate Y-axis domain with padding — include extreme level if present
    // Filter out null levels (dry season NaN from Google API)
    const levels = data.map(d => d.level).filter((v): v is number => v !== null);

    // Guard: all null water levels (dry season) — show message instead of broken chart
    if (levels.length === 0) {
        return (
            <div className="bg-card rounded-xl border border-border p-4">
                <h3 className="font-semibold text-foreground">{forecast.site_name}</h3>
                <p className="text-sm text-muted-foreground text-center py-8">
                    No water level readings available (dry season)
                </p>
            </div>
        );
    }

    // Filter out zero-value thresholds (unconfigured gauges)
    const thresholds = [forecast.warning_level, forecast.danger_level, forecast.extreme_danger_level]
        .filter((v): v is number => v != null && v > 0);
    const minLevel = Math.min(...levels, ...thresholds) * 0.9;
    const maxLevel = Math.max(...levels, ...thresholds) * 1.1;

    // Custom dot renderer to distinguish observed vs forecast
    const renderDot = (props: any) => {
        const { cx, cy, payload } = props;
        if (!cx || !cy) return null;

        return (
            <Dot
                cx={cx}
                cy={cy}
                r={payload.isForecast ? 3 : 4}
                fill={payload.isForecast ? '#4285F4' : '#1a73e8'}
                stroke={payload.isForecast ? 'none' : '#fff'}
                strokeWidth={payload.isForecast ? 0 : 2}
            />
        );
    };

    return (
        <div className="bg-card rounded-xl border border-border p-4 shadow-sm">
            <div className="mb-4">
                <h3 className="font-semibold text-foreground">
                    {forecast.site_name}
                </h3>
                <p className="text-sm text-muted-foreground">
                    7-Day {unitName} Forecast{isDischarge ? '' : ''}
                </p>
            </div>

            {/* Legend — chart hex colors kept as-is (data visualization) */}
            <div className="flex flex-wrap gap-4 mb-4 text-xs">
                <div className="flex items-center gap-1.5">
                    <div className="w-3 h-0.5 bg-[#4285F4]" />
                    <span className="text-muted-foreground">{unitName} ({unitLabel})</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded-sm" style={{ background: 'rgba(66,133,244,0.15)' }} />
                    <span className="text-muted-foreground">Uncertainty</span>
                </div>
                {forecast.extreme_danger_level != null && forecast.extreme_danger_level > 0 && (
                    <div className="flex items-center gap-1.5">
                        <div className="w-3 h-0.5" style={{ borderStyle: 'dashed', borderWidth: '1px 0 0 0', borderColor: '#7B1FA2' }} />
                        <span className="text-muted-foreground">Extreme</span>
                    </div>
                )}
                <div className="flex items-center gap-1.5">
                    <div className="w-3 h-0.5" style={{ borderStyle: 'dashed', borderWidth: '1px 0 0 0', borderColor: '#D32F2F' }} />
                    <span className="text-muted-foreground">Danger</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="w-3 h-0.5" style={{ borderStyle: 'dashed', borderWidth: '1px 0 0 0', borderColor: '#F57C00' }} />
                    <span className="text-muted-foreground">Warning</span>
                </div>
            </div>

            {/* Chart using ChartContainer wrapper */}
            <ChartContainer config={chartConfig} className="h-[220px] w-full">
                <ComposedChart
                    data={data}
                    margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                        dataKey="date"
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        tick={{ fill: '#6b7280' }}
                    />
                    <YAxis
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        tick={{ fill: '#6b7280' }}
                        domain={[minLevel, maxLevel]}
                        tickFormatter={(value) => `${value.toFixed(1)}${unitLabel}`}
                    />
                    <ChartTooltip
                        content={
                            <ChartTooltipContent
                                formatter={(value, name) => (
                                    <span>
                                        {name}: <strong>{Number(value).toFixed(2)} {unitLabel}</strong>
                                    </span>
                                )}
                            />
                        }
                    />

                    {/* Threshold background zones (colored bands between thresholds) */}
                    {/* Normal zone: minLevel → warning_level (green) */}
                    {forecast.warning_level > 0 && (
                        <ReferenceArea
                            y1={minLevel}
                            y2={forecast.warning_level}
                            fill="#22c55e"
                            fillOpacity={0.06}
                            ifOverflow="visible"
                        />
                    )}
                    {/* Minor zone: warning_level → danger_level (yellow) */}
                    {forecast.warning_level > 0 && forecast.danger_level > forecast.warning_level && (
                        <ReferenceArea
                            y1={forecast.warning_level}
                            y2={forecast.danger_level}
                            fill="#eab308"
                            fillOpacity={0.08}
                            ifOverflow="visible"
                        />
                    )}
                    {/* Moderate zone: danger_level → extreme (orange), or danger_level → maxLevel if no extreme */}
                    {forecast.danger_level > 0 && (
                        <ReferenceArea
                            y1={forecast.danger_level}
                            y2={forecast.extreme_danger_level != null && forecast.extreme_danger_level > forecast.danger_level
                                ? forecast.extreme_danger_level
                                : maxLevel}
                            fill="#f97316"
                            fillOpacity={0.08}
                            ifOverflow="visible"
                        />
                    )}
                    {/* Major zone: extreme_danger_level → maxLevel (red) */}
                    {forecast.extreme_danger_level != null && forecast.extreme_danger_level > 0 && (
                        <ReferenceArea
                            y1={forecast.extreme_danger_level}
                            y2={maxLevel}
                            fill="#ef4444"
                            fillOpacity={0.1}
                            ifOverflow="visible"
                        />
                    )}

                    {/* Confidence band (shaded area for forecast uncertainty) */}
                    <Area
                        type="monotone"
                        dataKey="bandHigh"
                        stroke="none"
                        fill="#4285F4"
                        fillOpacity={0.1}
                        legendType="none"
                        name="Upper bound"
                        connectNulls={false}
                        dot={false}
                        activeDot={false}
                        isAnimationActive={false}
                    />
                    <Area
                        type="monotone"
                        dataKey="bandLow"
                        stroke="none"
                        fill="#ffffff"
                        fillOpacity={1}
                        legendType="none"
                        name="Lower bound"
                        connectNulls={false}
                        dot={false}
                        activeDot={false}
                        isAnimationActive={false}
                    />

                    {/* Extreme danger level reference line */}
                    {forecast.extreme_danger_level != null && forecast.extreme_danger_level > 0 && (
                        <ReferenceLine
                            y={forecast.extreme_danger_level}
                            stroke="#7B1FA2"
                            strokeDasharray="5 5"
                            strokeOpacity={0.7}
                            label={{
                                value: 'Extreme',
                                position: 'right',
                                fill: '#7B1FA2',
                                fontSize: 10,
                            }}
                        />
                    )}

                    {/* Danger level reference line */}
                    {forecast.danger_level > 0 && (
                        <ReferenceLine
                            y={forecast.danger_level}
                            stroke="#D32F2F"
                            strokeDasharray="5 5"
                            strokeOpacity={0.7}
                            label={{
                                value: 'Danger',
                                position: 'right',
                                fill: '#D32F2F',
                                fontSize: 10,
                            }}
                        />
                    )}

                    {/* Warning level reference line */}
                    {forecast.warning_level > 0 && (
                        <ReferenceLine
                            y={forecast.warning_level}
                            stroke="#F57C00"
                            strokeDasharray="5 5"
                            strokeOpacity={0.7}
                            label={{
                                value: 'Warning',
                                position: 'right',
                                fill: '#F57C00',
                                fontSize: 10,
                            }}
                        />
                    )}

                    {/* "Now" vertical indicator at the observed→forecast boundary */}
                    {nowLabel && (
                        <ReferenceLine
                            x={nowLabel}
                            stroke="#6b7280"
                            strokeDasharray="3 3"
                            strokeOpacity={0.6}
                            label={{
                                value: 'Now',
                                position: 'top',
                                fill: '#6b7280',
                                fontSize: 10,
                            }}
                        />
                    )}

                    {/* Water level line — rendered on top */}
                    <Line
                        type="monotone"
                        dataKey="level"
                        stroke="var(--color-level)"
                        strokeWidth={2}
                        dot={renderDot}
                        activeDot={{ r: 5, fill: '#1a73e8' }}
                        name="Water Level"
                    />
                </ComposedChart>
            </ChartContainer>

            {/* Footer note */}
            <p className="text-xs text-muted-foreground/60 mt-3">
                Filled dots = observed, hollow dots = forecast. Shaded band = uncertainty range. Data from Google FloodHub.
            </p>
        </div>
    );
}
