/**
 * FloodHub Forecast Chart - 7-day water level forecast visualization
 *
 * CRITICAL: Uses ChartContainer wrapper from ui/chart.tsx
 * This is required for proper theming and responsive sizing.
 */

import { LineChart, Line, XAxis, YAxis, CartesianGrid, ReferenceLine, Dot } from 'recharts';
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
    danger: {
        label: 'Danger Level',
        color: '#D32F2F', // Red
    },
    warning: {
        label: 'Warning Level',
        color: '#F57C00', // Orange
    },
} satisfies ChartConfig;

export function ForecastChart({ forecast }: ForecastChartProps) {
    // Guard against missing or empty forecast data
    if (!forecast?.forecasts?.length) {
        return (
            <div className="bg-white rounded-lg border border-gray-200 p-4">
                <p className="text-sm text-gray-500 text-center py-8">No forecast data available</p>
            </div>
        );
    }

    // Transform forecast data for Recharts
    const data = forecast.forecasts.map((point) => {
        const date = new Date(point.timestamp);
        return {
            date: date.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric' }),
            fullDate: date.toLocaleString('en-IN', {
                weekday: 'short',
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit',
            }),
            level: point.water_level,
            isForecast: point.is_forecast,
        };
    });

    // Calculate Y-axis domain with padding
    const levels = data.map(d => d.level);
    const minLevel = Math.min(...levels, forecast.warning_level) * 0.9;
    const maxLevel = Math.max(...levels, forecast.danger_level) * 1.1;

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
        <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="mb-4">
                <h3 className="font-semibold text-gray-900">
                    {forecast.site_name}
                </h3>
                <p className="text-sm text-gray-500">
                    7-Day Water Level Forecast
                </p>
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-4 mb-4 text-xs">
                <div className="flex items-center gap-1.5">
                    <div className="w-3 h-0.5 bg-[#4285F4]" />
                    <span className="text-gray-600">Water Level (m)</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="w-3 h-0.5 bg-[#D32F2F] opacity-70" style={{ borderStyle: 'dashed', borderWidth: '1px 0 0 0', borderColor: '#D32F2F' }} />
                    <span className="text-gray-600">Danger Level</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="w-3 h-0.5 bg-[#F57C00] opacity-70" style={{ borderStyle: 'dashed', borderWidth: '1px 0 0 0', borderColor: '#F57C00' }} />
                    <span className="text-gray-600">Warning Level</span>
                </div>
            </div>

            {/* Chart using ChartContainer wrapper */}
            <ChartContainer config={chartConfig} className="h-[200px] w-full">
                <LineChart
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
                        tickFormatter={(value) => `${value.toFixed(1)}m`}
                    />
                    <ChartTooltip
                        content={
                            <ChartTooltipContent
                                formatter={(value, name) => (
                                    <span>
                                        {name}: <strong>{Number(value).toFixed(2)}m</strong>
                                    </span>
                                )}
                            />
                        }
                    />

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

                    {/* Water level line */}
                    <Line
                        type="monotone"
                        dataKey="level"
                        stroke="var(--color-level)"
                        strokeWidth={2}
                        dot={renderDot}
                        activeDot={{ r: 5, fill: '#1a73e8' }}
                        name="Water Level"
                    />
                </LineChart>
            </ChartContainer>

            {/* Footer note */}
            <p className="text-xs text-gray-400 mt-3">
                Filled dots = observed, hollow dots = forecast. Data from Google FloodHub.
            </p>
        </div>
    );
}
