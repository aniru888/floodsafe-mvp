import { useState } from 'react';
import { Bell, RefreshCw, Loader2, AlertCircle, Cloud, Newspaper, MessageCircle, Users, Waves, Phone, Shield, ExternalLink } from 'lucide-react';
import { AlertCard } from '../AlertCard';
import { ReportCard } from '../ReportCard';
import { ReportDetailModal } from '../ReportDetailModal';
import { EmergencyContactsModal } from '../EmergencyContactsModal';
import { FloodHubTab } from '../floodhub';
import { SafetyCirclesTab } from '../circles';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { useUnifiedAlerts, useRefreshExternalAlerts, useReports, Report, useUnreadCircleAlertCount } from '../../lib/api/hooks';
import { useCurrentCity } from '../../contexts/CityContext';
import { CITIES } from '../../lib/map/cityConfigs';
import type { AlertSourceFilter } from '../../types';
import { toast } from 'sonner';

/**
 * Get filter display name
 */
function getFilterLabel(filter: AlertSourceFilter): string {
    switch (filter) {
        case 'all':
            return 'All';
        case 'official':
            return 'Official';
        case 'news':
            return 'News';
        case 'social':
            return 'Social';
        case 'community':
            return 'Community';
        case 'floodhub':
            return 'FloodHub';
        case 'circles':
            return 'Circles';
        default:
            return filter;
    }
}

/**
 * Get filter icon
 */
function getFilterIcon(filter: AlertSourceFilter) {
    switch (filter) {
        case 'official':
            return <Cloud className="w-3 h-3" />;
        case 'news':
            return <Newspaper className="w-3 h-3" />;
        case 'social':
            return <MessageCircle className="w-3 h-3" />;
        case 'community':
            return <Users className="w-3 h-3" />;
        case 'floodhub':
            return <Waves className="w-3 h-3" />;
        case 'circles':
            return <Shield className="w-3 h-3" />;
        default:
            return null;
    }
}

export function AlertsScreen() {
    const city = useCurrentCity();
    const [sourceFilter, setSourceFilter] = useState<AlertSourceFilter>('all');
    const [selectedReport, setSelectedReport] = useState<Report | null>(null);
    const [emergencyModalOpen, setEmergencyModalOpen] = useState(false);

    // Fetch alerts
    const { data, isLoading, error, refetch } = useUnifiedAlerts(city, sourceFilter);
    const refreshMutation = useRefreshExternalAlerts(city);

    // Fetch community reports when community filter is active
    const { data: communityReports, isLoading: reportsLoading } = useReports();

    // Fetch circle alert unread count for badge
    const { data: circleUnreadCount } = useUnreadCircleAlertCount();

    // Handle manual refresh
    const handleRefresh = async () => {
        try {
            await refreshMutation.mutateAsync();
            await refetch();
            toast.success('Alerts refreshed successfully');
        } catch (err) {
            toast.error('Failed to refresh alerts. Please try again.');
        }
    };

    // Filter tabs with counts
    const filters: AlertSourceFilter[] = ['all', 'official', 'news', 'social', 'community', 'floodhub', 'circles'];

    // Get count for each filter
    const getFilterCount = (filter: AlertSourceFilter): number => {
        if (filter === 'community') {
            return communityReports?.length || 0;
        }
        // FloodHub has its own status display - don't show count badge
        if (filter === 'floodhub') {
            return -1; // -1 signals "no count badge"
        }
        // Circles uses its own unread count from circle alerts
        if (filter === 'circles') {
            return circleUnreadCount?.count || 0;
        }
        if (!data?.alerts) return 0;
        if (filter === 'all') return (data.total ?? 0) + (communityReports?.length || 0);

        // Map filters to source types
        const sourceMapping: Record<AlertSourceFilter, string[]> = {
            all: [],
            official: ['imd', 'cwc', 'gdacs', 'pub', 'telegram'],  // Government agencies
            news: ['rss', 'gdelt'],              // GDELT is news intelligence
            social: ['twitter', 'telegram'],
            community: ['floodsafe'],
            floodhub: [], // FloodHub handled separately
            circles: [], // Circles have their own data flow
        };

        const sources = sourceMapping[filter] || [];
        return data.alerts.filter(alert => sources.includes(alert.source)).length;
    };

    // Loading state
    if (isLoading) {
        return (
            <div className="pb-4 min-h-full bg-muted flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <Loader2 className="w-8 h-8 animate-spin text-primary" />
                    <p className="text-muted-foreground">Loading alerts...</p>
                </div>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className="pb-4 min-h-full bg-muted p-4">
                <div className="flex flex-col items-center justify-center py-16">
                    <AlertCircle className="w-12 h-12 text-destructive mb-4" />
                    <h2 className="text-xl font-semibold text-foreground mb-2">Failed to Load Alerts</h2>
                    <p className="text-muted-foreground mb-4">Please check your connection and try again.</p>
                    <Button onClick={() => refetch()} variant="outline">
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Retry
                    </Button>
                </div>
            </div>
        );
    }

    const alerts = data?.alerts || [];
    const sources = data?.sources || {};

    // Build source summary text
    const sourceSummary = Object.entries(sources)
        .filter(([_, meta]) => meta.enabled && meta.count > 0)
        .map(([_, meta]) => `${meta.name} (${meta.count})`)
        .join(' • ');

    return (
        <div className="pb-4 min-h-full bg-muted">
            {/* Header */}
            <div className="bg-card shadow-sm sticky top-14 md:top-0 z-40 border-b border-border">
                <div className="flex items-center justify-between px-4 h-14 max-w-4xl mx-auto">
                    <div className="flex items-center gap-2">
                        <Bell className="w-5 h-5 text-primary" />
                        <h1 className="font-semibold text-foreground">Alerts</h1>
                        <Badge variant="outline" className="ml-1">
                            {CITIES[city]?.displayName || city}
                        </Badge>
                    </div>
                    <div className="flex items-center gap-1">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setEmergencyModalOpen(true)}
                            className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            title="Emergency Contacts"
                        >
                            <Phone className="w-4 h-4" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleRefresh}
                            disabled={refreshMutation.isPending}
                        >
                            <RefreshCw className={`w-4 h-4 ${refreshMutation.isPending ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>
                </div>

                {/* Filter Tabs */}
                <div className="flex gap-2 px-4 pb-3 overflow-x-auto scrollbar-hide max-w-4xl mx-auto">
                    {filters.map((filter) => {
                        const count = getFilterCount(filter);
                        const isActive = sourceFilter === filter;

                        return (
                            <Badge
                                key={filter}
                                variant={isActive ? 'default' : 'outline'}
                                className="cursor-pointer capitalize flex-shrink-0 px-3 py-1.5 transition-colors"
                                onClick={() => setSourceFilter(filter)}
                            >
                                {getFilterIcon(filter)}
                                <span className="ml-1">{getFilterLabel(filter)}</span>
                                {count > 0 && (
                                    <span className={`ml-1.5 ${isActive ? 'opacity-90' : 'opacity-60'}`}>
                                        {count}
                                    </span>
                                )}
                            </Badge>
                        );
                    })}
                </div>

                {/* Source Summary */}
                {sourceSummary && (
                    <div className="px-4 pb-3 text-xs text-muted-foreground border-t border-border pt-2 max-w-4xl mx-auto">
                        <span className="font-medium">Sources: </span>
                        {sourceSummary}
                    </div>
                )}
            </div>

            {/* Content based on filter */}
            <div className={sourceFilter === 'floodhub' || sourceFilter === 'circles' ? '' : 'p-4 space-y-3 max-w-4xl mx-auto'} data-tour-id="unified-alerts">
                {sourceFilter === 'circles' ? (
                    // Safety Circles Tab - Family & Community Notifications
                    <SafetyCirclesTab />
                ) : sourceFilter === 'floodhub' ? (
                    // FloodHub Tab - Google Flood Forecasting
                    <FloodHubTab />
                ) : sourceFilter === 'community' ? (
                    // Community Reports Section
                    reportsLoading ? (
                        <div className="flex items-center justify-center py-16">
                            <Loader2 className="w-8 h-8 animate-spin text-primary" />
                        </div>
                    ) : communityReports && communityReports.length > 0 ? (
                        <>
                            <p className="text-sm text-muted-foreground mb-2">
                                {communityReports.length} community report{communityReports.length !== 1 ? 's' : ''}
                            </p>
                            {communityReports.map((report) => (
                                <ReportCard
                                    key={report.id}
                                    report={report}
                                    onViewDetails={setSelectedReport}
                                />
                            ))}
                        </>
                    ) : (
                        <div className="text-center py-16">
                            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                                <Users className="w-8 h-8 text-primary" />
                            </div>
                            <h2 className="text-xl font-medium text-foreground mb-2">No Community Reports</h2>
                            <p className="text-muted-foreground">
                                Be the first to report flooding in your area
                            </p>
                        </div>
                    )
                ) : sourceFilter === 'social' ? (
                    // Social Tab - Telegram branded frame (Singapore) + alert cards
                    <>
                        {/* Telegram Channel Frame — Singapore only */}
                        {city.toLowerCase() === 'singapore' && (() => {
                            const telegramAlerts = alerts.filter(a => a.source === 'telegram');
                            return (
                                <div className="mb-4 rounded-xl border border-[#0088cc]/20 bg-card shadow-sm overflow-hidden">
                                    {/* Header */}
                                    <div className="flex items-center justify-between px-4 py-3 border-b border-[#0088cc]/10 bg-[#0088cc]/5">
                                        <div className="flex items-center gap-2.5">
                                            <svg viewBox="0 0 24 24" className="w-5 h-5 text-[#0088cc] flex-shrink-0" fill="currentColor">
                                                <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                                            </svg>
                                            <div>
                                                <span className="font-semibold text-sm text-foreground">PUB Flood Alerts</span>
                                                <p className="text-xs text-muted-foreground">Official PUB updates via Telegram</p>
                                            </div>
                                        </div>
                                        <a
                                            href="https://t.me/pubfloodalerts"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-[#0088cc] hover:bg-[#006699] transition-colors flex-shrink-0"
                                        >
                                            Open in Telegram
                                            <ExternalLink className="w-3 h-3" />
                                        </a>
                                    </div>

                                    {/* Alert cards inside branded frame */}
                                    {(() => {
                                        const now = Date.now();
                                        const ACTIVE_WINDOW_MS = 48 * 60 * 60 * 1000; // 48 hours
                                        const activeAlerts = telegramAlerts.filter(a => {
                                            const ts = a.created_at.endsWith('Z') ? a.created_at : a.created_at + 'Z';
                                            return now - new Date(ts).getTime() < ACTIVE_WINDOW_MS;
                                        });
                                        const historyAlerts = telegramAlerts.filter(a => {
                                            const ts = a.created_at.endsWith('Z') ? a.created_at : a.created_at + 'Z';
                                            return now - new Date(ts).getTime() >= ACTIVE_WINDOW_MS;
                                        }).slice(0, 3);

                                        return (
                                            <div className="p-3 space-y-3">
                                                {activeAlerts.length > 0 ? (
                                                    activeAlerts.map((alert) => (
                                                        <AlertCard key={alert.id} alert={alert} />
                                                    ))
                                                ) : (
                                                    <div className="text-center py-4">
                                                        <p className="text-sm text-muted-foreground">No active flood warnings</p>
                                                    </div>
                                                )}

                                                {historyAlerts.length > 0 && (
                                                    <>
                                                        <div className="flex items-center gap-2 pt-1">
                                                            <div className="flex-1 h-px bg-border" />
                                                            <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Recent History</span>
                                                            <div className="flex-1 h-px bg-border" />
                                                        </div>
                                                        <div className="space-y-2 opacity-60">
                                                            {historyAlerts.map((alert) => (
                                                                <AlertCard key={alert.id} alert={alert} />
                                                            ))}
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                        );
                                    })()}
                                </div>
                            );
                        })()}

                        {/* Other social alerts (Twitter, etc.) outside the frame */}
                        {alerts.filter(a => a.source !== 'telegram').map((alert) => (
                            <AlertCard key={alert.id} alert={alert} />
                        ))}

                        {/* Empty state when no social alerts at all */}
                        {alerts.length === 0 && city.toLowerCase() !== 'singapore' && (
                            <div className="text-center py-10">
                                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-3">
                                    <MessageCircle className="w-6 h-6 text-primary" />
                                </div>
                                <p className="text-muted-foreground text-sm">
                                    No social media alerts available
                                </p>
                            </div>
                        )}
                    </>
                ) : (
                    // Alerts Section (for all/official/news filters)
                    alerts.length > 0 ? (
                        alerts.map((alert) => (
                            <AlertCard
                                key={alert.id}
                                alert={alert}
                            />
                        ))
                    ) : (
                        <div className="text-center py-16">
                            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                                <Bell className="w-8 h-8 text-primary" />
                            </div>
                            <h2 className="text-xl font-medium text-foreground mb-2">No Alerts</h2>
                            <p className="text-muted-foreground">
                                {sourceFilter === 'all'
                                    ? 'No active alerts in your area'
                                    : `No ${getFilterLabel(sourceFilter).toLowerCase()} alerts available`}
                            </p>
                            <Button
                                variant="outline"
                                className="mt-4"
                                onClick={handleRefresh}
                                disabled={refreshMutation.isPending}
                            >
                                <RefreshCw className={`w-4 h-4 mr-2 ${refreshMutation.isPending ? 'animate-spin' : ''}`} />
                                Check for Updates
                            </Button>
                        </div>
                    )
                )}
            </div>

            {/* Report Detail Modal */}
            <ReportDetailModal
                report={selectedReport}
                isOpen={selectedReport !== null}
                onClose={() => setSelectedReport(null)}
            />

            {/* Emergency Contacts Modal */}
            <EmergencyContactsModal
                isOpen={emergencyModalOpen}
                onClose={() => setEmergencyModalOpen(false)}
            />
        </div>
    );
}
