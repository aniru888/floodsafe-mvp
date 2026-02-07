import { AlertTriangle, Clock, Check } from 'lucide-react';
import { useMarkCircleAlertRead } from '../../lib/api/hooks';
import type { CircleAlert } from '../../types';
import { toast } from 'sonner';

interface CircleAlertCardProps {
    alert: CircleAlert;
}

function timeAgo(dateStr: string): string {
    const date = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z');
    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

export function CircleAlertCard({ alert }: CircleAlertCardProps) {
    const markRead = useMarkCircleAlertRead();

    const handleMarkRead = () => {
        if (alert.is_read) return;
        markRead.mutate(alert.id, {
            onError: (err: Error) => {
                toast.error(err.message || 'Failed to mark alert as read');
            },
        });
    };

    return (
        <div
            className={`rounded-xl border p-3 transition-colors cursor-pointer ${
                alert.is_read
                    ? 'bg-card border-border'
                    : 'bg-primary/5 border-primary/20'
            }`}
            onClick={handleMarkRead}
        >
            <div className="flex items-start gap-3">
                <div className={`mt-0.5 p-1.5 rounded-full flex-shrink-0 ${
                    alert.is_read ? 'bg-muted' : 'bg-red-100'
                }`}>
                    <AlertTriangle className={`w-4 h-4 ${
                        alert.is_read ? 'text-muted-foreground' : 'text-red-500'
                    }`} />
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium text-foreground truncate">
                            {alert.reporter_name} reported flooding
                        </p>
                        {alert.is_read && (
                            <Check className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
                        )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                        Circle: {alert.circle_name}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {alert.message}
                    </p>
                    <div className="flex items-center gap-1 mt-1.5 text-xs text-muted-foreground/60">
                        <Clock className="w-3 h-3" />
                        <span>{timeAgo(alert.created_at)}</span>
                        {alert.notification_sent && (
                            <span className="ml-2 text-green-500">
                                via {alert.notification_channel}
                            </span>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
