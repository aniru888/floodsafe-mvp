import React, { useState } from 'react';
import { Users, RefreshCw, CheckCircle, Clock, TrendingUp } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useReports } from '../../lib/api/hooks';
import { ReportCard } from '../ReportCard';

type FilterType = 'recent' | 'verified' | 'trending';

interface CommunityFeedScreenProps {
    onLocateReport?: (lat: number, lng: number) => void;
}

export function CommunityFeedScreen({ onLocateReport }: CommunityFeedScreenProps) {
    const [filter, setFilter] = useState<FilterType>('recent');
    const { data: reports, isLoading, refetch, isRefetching } = useReports();

    // Filter and sort reports based on selected filter
    const filteredReports = React.useMemo(() => {
        if (!reports) return [];

        let sorted = [...reports];

        switch (filter) {
            case 'verified':
                sorted = sorted.filter(r => r.verified);
                break;
            case 'trending':
                // Sort by net votes (upvotes - downvotes)
                sorted.sort((a, b) => {
                    const aScore = (a.upvotes || 0) - (a.downvotes || 0);
                    const bScore = (b.upvotes || 0) - (b.downvotes || 0);
                    return bScore - aScore;
                });
                break;
            case 'recent':
            default:
                // Sort by timestamp (newest first)
                sorted.sort((a, b) => {
                    const aTime = new Date(a.timestamp).getTime();
                    const bTime = new Date(b.timestamp).getTime();
                    return bTime - aTime;
                });
                break;
        }

        return sorted;
    }, [reports, filter]);

    const handleRefresh = () => {
        refetch();
    };

    const filterButtons: { key: FilterType; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
        { key: 'recent', label: 'Recent', icon: Clock },
        { key: 'verified', label: 'Verified', icon: CheckCircle },
        { key: 'trending', label: 'Trending', icon: TrendingUp },
    ];

    return (
        <div className="flex flex-col h-full bg-muted">
            {/* Header */}
            <div className="bg-card border-b border-border px-4 py-3">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        <Users className="w-5 h-5 text-purple-600" />
                        <h1 className="text-lg font-semibold text-foreground">Community Reports</h1>
                    </div>
                    <button
                        onClick={handleRefresh}
                        disabled={isRefetching}
                        className={cn(
                            "p-2 rounded-full hover:bg-muted transition-colors",
                            isRefetching && "animate-spin"
                        )}
                    >
                        <RefreshCw className="w-5 h-5 text-muted-foreground" />
                    </button>
                </div>

                {/* Filter Tabs */}
                <div className="flex gap-2">
                    {filterButtons.map(({ key, label, icon: Icon }) => (
                        <button
                            key={key}
                            onClick={() => setFilter(key)}
                            className={cn(
                                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors",
                                filter === key
                                    ? "bg-purple-100 text-purple-700"
                                    : "bg-muted text-muted-foreground hover:bg-accent"
                            )}
                        >
                            <Icon className="w-4 h-4" />
                            {label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-auto px-4 py-4">
                {isLoading ? (
                    <div className="flex flex-col items-center justify-center py-12">
                        <RefreshCw className="w-8 h-8 text-muted-foreground/40 animate-spin" />
                        <p className="mt-3 text-muted-foreground">Loading reports...</p>
                    </div>
                ) : filteredReports.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12">
                        <Users className="w-12 h-12 text-muted-foreground/40" />
                        <h3 className="mt-4 text-lg font-medium text-foreground">No Reports Found</h3>
                        <p className="mt-1 text-sm text-muted-foreground text-center max-w-xs">
                            {filter === 'verified'
                                ? "No verified reports yet. Community reports get verified over time."
                                : filter === 'trending'
                                ? "No trending reports yet. Vote on reports to help them trend!"
                                : "Be the first to report flooding in your area."}
                        </p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {/* Report Count */}
                        <div className="text-sm text-muted-foreground">
                            {filteredReports.length} {filter === 'verified' ? 'verified ' : ''} report{filteredReports.length !== 1 ? 's' : ''}
                        </div>

                        {/* Report Cards */}
                        {filteredReports.map((report) => (
                            <ReportCard
                                key={report.id}
                                report={report}
                                onLocate={onLocateReport}
                                showFullDetails
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
