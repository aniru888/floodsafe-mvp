/**
 * FloodHub Tab - Main container for Google FloodHub integration
 *
 * Shows flood forecasting data for Delhi's Yamuna River.
 * Handles all states: loading, error, not configured, wrong city.
 *
 * NO SILENT FALLBACKS - all errors are explicitly displayed.
 */

import { useState } from 'react';
import { Loader2, AlertCircle, Info, MapPinOff } from 'lucide-react';
import { Button } from '../ui/button';
import { useCurrentCity } from '../../contexts/CityContext';
import { useFloodHubStatus, useFloodHubGauges, useFloodHubForecast } from '../../lib/api/hooks';

import { FloodHubHeader } from './FloodHubHeader';
import { FloodHubAlertsList } from './FloodHubAlertsList';
import { ForecastChart } from './ForecastChart';
import { FloodHubFooter } from './FloodHubFooter';

// Not available for non-Delhi cities
function NotAvailableState() {
    return (
        <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="p-3 rounded-full bg-gray-100 mb-4">
                <MapPinOff className="w-8 h-8 text-gray-400" />
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
                FloodHub Coming Soon
            </h2>
            <p className="text-gray-600 max-w-sm">
                Google FloodHub coverage is currently available for Delhi only.
                Bangalore support coming soon.
            </p>
        </div>
    );
}

// Service not configured (no API key)
function NotConfiguredState({ message }: { message?: string }) {
    return (
        <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="p-3 rounded-full bg-blue-50 mb-4">
                <Info className="w-8 h-8 text-blue-500" />
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
                FloodHub Not Configured
            </h2>
            <p className="text-gray-600 max-w-sm mb-4">
                {message || 'Google FloodHub API key is not configured.'}
            </p>
            <a
                href="https://developers.google.com/flood-forecasting"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 text-sm font-medium"
            >
                Learn about FloodHub API access →
            </a>
        </div>
    );
}

// Error state with retry button
function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
    return (
        <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="p-3 rounded-full bg-red-50 mb-4">
                <AlertCircle className="w-8 h-8 text-red-500" />
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Unable to Load FloodHub
            </h2>
            <p className="text-gray-600 max-w-sm mb-4">
                {message}
            </p>
            <Button onClick={onRetry} variant="outline">
                Try Again
            </Button>
        </div>
    );
}

// Loading state
function LoadingState() {
    return (
        <div className="flex flex-col items-center justify-center py-16">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-4" />
            <p className="text-gray-600">Loading FloodHub data...</p>
        </div>
    );
}

export function FloodHubTab() {
    const city = useCurrentCity();
    const [selectedGaugeId, setSelectedGaugeId] = useState<string | null>(null);

    // Fetch FloodHub data
    const {
        data: status,
        isLoading: statusLoading,
        error: statusError,
        refetch: refetchStatus,
    } = useFloodHubStatus(city);

    const {
        data: gauges,
        isLoading: gaugesLoading,
        error: gaugesError,
        refetch: refetchGauges,
    } = useFloodHubGauges();

    const {
        data: forecast,
        isLoading: forecastLoading,
    } = useFloodHubForecast(selectedGaugeId);

    // City guard - FloodHub only available for Delhi
    if (city !== 'delhi') {
        return <NotAvailableState />;
    }

    // Loading state
    if (statusLoading) {
        return <LoadingState />;
    }

    // Error state - NO SILENT FALLBACK
    if (statusError) {
        return (
            <ErrorState
                message={statusError instanceof Error ? statusError.message : 'Failed to load FloodHub status'}
                onRetry={() => refetchStatus()}
            />
        );
    }

    // Not configured (no API key)
    if (status && !status.enabled) {
        return <NotConfiguredState message={status.message} />;
    }

    // Gauge loading/error (show partial UI with status header)
    const showGaugeError = gaugesError && !gaugesLoading;

    return (
        <div className="space-y-4 p-4">
            {/* Status Header */}
            {status && <FloodHubHeader status={status} />}

            {/* Gauge List */}
            {gaugesLoading ? (
                <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-5 h-5 text-gray-400 animate-spin mr-2" />
                    <span className="text-gray-500">Loading monitoring stations...</span>
                </div>
            ) : showGaugeError ? (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
                    <p className="text-red-700 mb-2">Failed to load gauge data</p>
                    <Button size="sm" variant="outline" onClick={() => refetchGauges()}>
                        Retry
                    </Button>
                </div>
            ) : gauges && gauges.length > 0 ? (
                <FloodHubAlertsList
                    gauges={gauges}
                    selectedGaugeId={selectedGaugeId}
                    onSelectGauge={setSelectedGaugeId}
                />
            ) : (
                <div className="text-center py-8 text-gray-500">
                    <p>No monitoring stations available</p>
                </div>
            )}

            {/* Forecast Chart (when gauge selected) */}
            {selectedGaugeId && (
                <div className="mt-4">
                    {forecastLoading ? (
                        <div className="flex items-center justify-center py-8 bg-gray-50 rounded-lg border">
                            <Loader2 className="w-5 h-5 text-gray-400 animate-spin mr-2" />
                            <span className="text-gray-500">Loading forecast...</span>
                        </div>
                    ) : forecast ? (
                        <ForecastChart forecast={forecast} />
                    ) : (
                        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
                            <p className="text-yellow-700">
                                No forecast available for this station
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* Footer */}
            <FloodHubFooter />
        </div>
    );
}
