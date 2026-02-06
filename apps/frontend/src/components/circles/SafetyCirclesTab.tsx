import { useState } from 'react';
import { Shield, Plus, LogIn, Loader2, Users, Bell, CheckCheck } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { useMyCircles, useCircleAlerts, useMarkAllCircleAlertsRead, useUnreadCircleAlertCount } from '../../lib/api/hooks';
import { useAuth } from '../../contexts/AuthContext';
import { CreateCircleModal } from './CreateCircleModal';
import { JoinCircleModal } from './JoinCircleModal';
import { CircleDetailModal } from './CircleDetailModal';
import { CircleAlertCard } from './CircleAlertCard';
import type { SafetyCircle, CircleType } from '../../types';
import { toast } from 'sonner';

const TYPE_EMOJI: Record<CircleType, string> = {
    family: '\uD83C\uDFE0',
    school: '\uD83C\uDFEB',
    apartment: '\uD83C\uDFE2',
    neighborhood: '\uD83C\uDFD8\uFE0F',
    custom: '\uD83D\uDC65',
};

function CircleCard({ circle, onClick }: { circle: SafetyCircle; onClick: () => void }) {
    return (
        <button
            onClick={onClick}
            className="w-full text-left p-3 rounded-xl border border-gray-200 bg-white hover:border-blue-300 hover:shadow-sm transition-all"
        >
            <div className="flex items-start gap-2.5">
                <span className="text-xl leading-none mt-0.5">
                    {TYPE_EMOJI[circle.circle_type] || '\uD83D\uDC65'}
                </span>
                <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm text-gray-900 truncate">{circle.name}</p>
                    <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-gray-500">
                            <Users className="w-3 h-3 inline mr-0.5" />
                            {circle.member_count}
                        </span>
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                            {circle.circle_type}
                        </Badge>
                    </div>
                </div>
            </div>
        </button>
    );
}

export function SafetyCirclesTab() {
    const { isAuthenticated } = useAuth();
    const { data: circles, isLoading: circlesLoading, error: circlesError } = useMyCircles();
    const { data: alertsData, isLoading: alertsLoading } = useCircleAlerts();
    const { data: unreadData } = useUnreadCircleAlertCount();
    const markAllRead = useMarkAllCircleAlertsRead();

    const [createOpen, setCreateOpen] = useState(false);
    const [joinOpen, setJoinOpen] = useState(false);
    const [selectedCircleId, setSelectedCircleId] = useState<string | null>(null);

    // Not authenticated guard
    if (!isAuthenticated) {
        return (
            <div className="p-4 text-center py-16">
                <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center mx-auto mb-4">
                    <Shield className="w-8 h-8 text-blue-600" />
                </div>
                <h2 className="text-xl font-medium mb-2">Safety Circles</h2>
                <p className="text-gray-600 mb-4">
                    Create family and community circles to get notified when members report flooding.
                </p>
                <p className="text-sm text-gray-500">Sign in to create or join a circle.</p>
            </div>
        );
    }

    // Loading guard
    if (circlesLoading) {
        return (
            <div className="flex items-center justify-center py-16">
                <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
            </div>
        );
    }

    // Error guard
    if (circlesError) {
        return (
            <div className="p-4 text-center py-16">
                <p className="text-red-500 font-medium">Failed to load circles</p>
                <p className="text-sm text-gray-500 mt-1">{(circlesError as Error).message}</p>
            </div>
        );
    }

    const unreadCount = unreadData?.count || 0;
    const alerts = alertsData?.alerts || [];
    const hasCircles = circles && circles.length > 0;

    const handleMarkAllRead = () => {
        markAllRead.mutate(undefined, {
            onSuccess: () => {
                toast.success('All alerts marked as read');
            },
            onError: (err: Error) => {
                toast.error(err.message || 'Failed to mark alerts as read');
            },
        });
    };

    return (
        <div className="p-4 space-y-5">
            {/* Header with actions */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Shield className="w-5 h-5 text-blue-600" />
                    <h2 className="font-semibold text-gray-900">My Safety Circles</h2>
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setJoinOpen(true)}
                        className="h-8 text-xs"
                    >
                        <LogIn className="w-3 h-3 mr-1" />
                        Join
                    </Button>
                    <Button
                        size="sm"
                        onClick={() => setCreateOpen(true)}
                        className="h-8 text-xs"
                    >
                        <Plus className="w-3 h-3 mr-1" />
                        Create
                    </Button>
                </div>
            </div>

            {/* Circles Grid */}
            {hasCircles ? (
                <div className="grid grid-cols-2 gap-2.5">
                    {circles.map((circle) => (
                        <CircleCard
                            key={circle.id}
                            circle={circle}
                            onClick={() => setSelectedCircleId(circle.id)}
                        />
                    ))}
                </div>
            ) : (
                <div className="text-center py-8 bg-white rounded-xl border border-dashed border-gray-300">
                    <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center mx-auto mb-3">
                        <Shield className="w-6 h-6 text-blue-600" />
                    </div>
                    <p className="text-gray-900 font-medium mb-1">No circles yet</p>
                    <p className="text-sm text-gray-500 mb-3">
                        Create a circle for your family or community
                    </p>
                    <div className="flex items-center justify-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setJoinOpen(true)}
                        >
                            Join with Code
                        </Button>
                        <Button size="sm" onClick={() => setCreateOpen(true)}>
                            Create Circle
                        </Button>
                    </div>
                </div>
            )}

            {/* Recent Circle Alerts */}
            {hasCircles && (
                <div>
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                            <Bell className="w-4 h-4 text-gray-600" />
                            <p className="text-sm font-medium text-gray-700">Recent Alerts</p>
                            {unreadCount > 0 && (
                                <Badge variant="default" className="bg-red-500 text-xs px-1.5 py-0">
                                    {unreadCount}
                                </Badge>
                            )}
                        </div>
                        {unreadCount > 0 && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs text-gray-500"
                                onClick={handleMarkAllRead}
                                disabled={markAllRead.isPending}
                            >
                                <CheckCheck className="w-3 h-3 mr-1" />
                                Mark all read
                            </Button>
                        )}
                    </div>

                    {alertsLoading ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                        </div>
                    ) : alerts.length > 0 ? (
                        <div className="space-y-2">
                            {alerts.map((alert) => (
                                <CircleAlertCard key={alert.id} alert={alert} />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-6 bg-white rounded-lg border">
                            <p className="text-sm text-gray-500">
                                No alerts yet. When circle members report flooding, you'll see alerts here.
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* Modals */}
            <CreateCircleModal isOpen={createOpen} onClose={() => setCreateOpen(false)} />
            <JoinCircleModal isOpen={joinOpen} onClose={() => setJoinOpen(false)} />
            <CircleDetailModal
                isOpen={selectedCircleId !== null}
                onClose={() => setSelectedCircleId(null)}
                circleId={selectedCircleId}
            />
        </div>
    );
}
