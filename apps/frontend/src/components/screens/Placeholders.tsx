import { useState } from 'react';
import { Bell, CheckCheck, MapPin, Clock, Loader2 } from 'lucide-react';
import { FloodAlert } from '../../types';
import { useUserAlerts, useMarkAlertRead, useMarkAllAlertsRead, Alert } from '../../lib/api/hooks';
import { useUser } from '../../contexts/UserContext';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';

export function AlertDetailScreen({ alert, onBack }: { alert: FloodAlert; onBack: () => void }) {
    return <div className="p-4">Alert Detail: {alert.location} <button onClick={onBack}>Back</button></div>;
}

export function AlertsListScreen({ onAlertClick: _onAlertClick }: { onAlertClick: (alert: FloodAlert) => void }) {
    const { user } = useUser();
    const { data: alerts, isLoading, error } = useUserAlerts(user?.id);
    const markRead = useMarkAlertRead();
    const markAllRead = useMarkAllAlertsRead();
    const [filter, setFilter] = useState<'all' | 'unread'>('all');

    const filteredAlerts = filter === 'unread'
        ? alerts?.filter((a: Alert) => !a.is_read)
        : alerts;

    const handleMarkRead = (alertId: string) => {
        if (user?.id) {
            markRead.mutate({ alertId, userId: user.id });
        }
    };

    const handleMarkAllRead = () => {
        if (user?.id) {
            markAllRead.mutate(user.id);
        }
    };

    if (isLoading) {
        return (
            <div className="pb-4 min-h-full bg-muted flex items-center justify-center">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="pb-4 min-h-full bg-muted p-4">
                <div className="text-center py-16 text-red-600">
                    Failed to load alerts. Please try again.
                </div>
            </div>
        );
    }

    const unreadCount = alerts?.filter((a: Alert) => !a.is_read).length || 0;

    return (
        <div className="pb-4 min-h-full bg-muted">
            {/* Header */}
            <div className="bg-card shadow-sm sticky top-14 z-40">
                <div className="flex items-center justify-between px-4 h-14">
                    <div className="flex items-center gap-2">
                        <Bell className="w-5 h-5 text-blue-600" />
                        <h1 className="font-semibold">Alerts</h1>
                        {unreadCount > 0 && (
                            <Badge variant="destructive" className="ml-2">{unreadCount}</Badge>
                        )}
                    </div>
                    {unreadCount > 0 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleMarkAllRead}
                            disabled={markAllRead.isPending}
                        >
                            <CheckCheck className="w-4 h-4 mr-1" />
                            Mark all read
                        </Button>
                    )}
                </div>

                {/* Filter Chips */}
                <div className="flex gap-2 px-4 pb-3">
                    {(['all', 'unread'] as const).map((f) => (
                        <Badge
                            key={f}
                            variant={filter === f ? 'default' : 'outline'}
                            className="cursor-pointer capitalize"
                            onClick={() => setFilter(f)}
                        >
                            {f}
                        </Badge>
                    ))}
                </div>
            </div>

            {/* Alerts List */}
            <div className="p-4 space-y-3">
                {filteredAlerts && filteredAlerts.length > 0 ? (
                    filteredAlerts.map((alert: Alert) => (
                        <Card
                            key={alert.id}
                            className={`p-4 ${!alert.is_read ? 'border-l-4 border-l-blue-500 bg-blue-50/50' : ''}`}
                        >
                            <div className="flex items-start gap-3">
                                <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center">
                                    <Bell className="w-5 h-5 text-orange-600" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-start justify-between gap-2 mb-1">
                                        <h3 className="font-medium text-sm">{alert.message}</h3>
                                        {!alert.is_read && (
                                            <span className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-1.5" />
                                        )}
                                    </div>

                                    {alert.watch_area_name && (
                                        <div className="flex items-center gap-1 text-xs text-muted-foreground mb-2">
                                            <MapPin className="w-3 h-3" />
                                            {alert.watch_area_name}
                                        </div>
                                    )}

                                    <div className="flex items-center gap-1 text-xs text-muted-foreground/60">
                                        <Clock className="w-3 h-3" />
                                        {new Date(alert.created_at).toLocaleString()}
                                    </div>

                                    {!alert.is_read && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="mt-2 text-xs"
                                            onClick={() => handleMarkRead(alert.id)}
                                            disabled={markRead.isPending}
                                        >
                                            Mark as read
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </Card>
                    ))
                ) : (
                    <div className="text-center py-16">
                        <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                            <Bell className="w-8 h-8 text-green-600" />
                        </div>
                        <h2 className="text-xl font-medium mb-2">No Alerts</h2>
                        <p className="text-muted-foreground">
                            {filter === 'unread'
                                ? "You're all caught up!"
                                : "Add watch areas to receive flood alerts"}
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
