import { useState } from 'react';
import { ExternalLink, MapPin, Cloud, MessageCircle, Radio, Rss, AlertTriangle, ChevronDown, ChevronUp, Globe, Shield } from 'lucide-react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import type { UnifiedAlert, AlertSource, AlertSeverity } from '../types';

interface AlertCardProps {
    alert: UnifiedAlert;
}

/**
 * Get icon component for alert source
 */
function getSourceIcon(source: AlertSource) {
    switch (source) {
        case 'imd':
            return <Cloud className="w-4 h-4" />;
        case 'cwc':
            return <AlertTriangle className="w-4 h-4" />;
        case 'twitter':
            return <MessageCircle className="w-4 h-4" />;
        case 'telegram':
            return <Radio className="w-4 h-4" />;
        case 'rss':
            return <Rss className="w-4 h-4" />;
        case 'gdelt':
            return <Globe className="w-4 h-4" />;
        case 'gdacs':
            return <Shield className="w-4 h-4" />;
        case 'floodsafe':
            return <MapPin className="w-4 h-4" />;
        default:
            return <AlertTriangle className="w-4 h-4" />;
    }
}

/**
 * Get display name for alert source
 */
function getSourceDisplayName(source: AlertSource, sourceName?: string): string {
    if (sourceName) return sourceName;

    switch (source) {
        case 'imd':
            return 'IMD';
        case 'cwc':
            return 'CWC';
        case 'twitter':
            return 'Twitter';
        case 'telegram':
            return 'Telegram';
        case 'rss':
            return 'News';
        case 'gdelt':
            return 'GDELT';
        case 'gdacs':
            return 'UN GDACS';
        case 'floodsafe':
            return 'FloodSafe';
        default:
            return 'Unknown';
    }
}

/**
 * Get severity styling (border color)
 */
function getSeverityBorder(severity?: AlertSeverity): string {
    switch (severity) {
        case 'severe':
            return 'border-l-red-500';
        case 'high':
            return 'border-l-orange-500';
        case 'moderate':
            return 'border-l-yellow-500';
        case 'low':
            return 'border-l-green-500';
        default:
            return 'border-l-gray-400';
    }
}

/**
 * Get severity badge styling
 */
function getSeverityBadge(severity?: AlertSeverity) {
    switch (severity) {
        case 'severe':
            return <Badge variant="destructive" className="capitalize">Severe</Badge>;
        case 'high':
            return <Badge className="bg-orange-500 text-white capitalize">High</Badge>;
        case 'moderate':
            return <Badge className="bg-yellow-500 text-white capitalize">Moderate</Badge>;
        case 'low':
            return <Badge className="bg-green-500 text-white capitalize">Low</Badge>;
        default:
            return null;
    }
}

/**
 * Format relative time (e.g., "2h ago", "5m ago")
 */
function formatTimeAgo(timestamp: string): string {
    const now = new Date();
    const then = new Date(timestamp.endsWith('Z') ? timestamp : timestamp + 'Z');
    const diffMs = now.getTime() - then.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    if (diffDays <= 7) return `${diffDays}d ago`;

    return then.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function AlertCard({ alert }: AlertCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const hasUrl = !!alert.url;

    // Truncate message for collapsed state (150 chars)
    const message = alert.message || '';
    const shouldTruncate = message.length > 150;
    const displayMessage = isExpanded || !shouldTruncate
        ? message
        : message.substring(0, 150) + '...';

    return (
        <Card className={`bg-card text-card-foreground rounded-xl border shadow-sm p-4 border-l-4 ${getSeverityBorder(alert.severity)}`}>
            <div className="flex flex-col gap-3">
                {/* Header */}
                <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                            {getSourceIcon(alert.source)}
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-medium text-muted-foreground">
                                    {getSourceDisplayName(alert.source, alert.source_name)}
                                </span>
                                <span className="text-xs text-muted-foreground/60">
                                    {formatTimeAgo(alert.created_at)}
                                </span>
                            </div>
                            {alert.title && (
                                <h3 className="text-sm font-semibold mt-1 text-foreground line-clamp-2">
                                    {alert.title}
                                </h3>
                            )}
                        </div>
                    </div>
                    {alert.severity && getSeverityBadge(alert.severity)}
                </div>

                {/* Message */}
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                    {displayMessage}
                </p>

                {/* Expand/Collapse for long messages */}
                {shouldTruncate && (
                    <Button
                        variant="ghost"
                        size="default"
                        className="w-fit text-xs -mt-2"
                        onClick={() => setIsExpanded(!isExpanded)}
                    >
                        {isExpanded ? (
                            <>
                                <ChevronUp className="w-3 h-3 mr-1" />
                                Show less
                            </>
                        ) : (
                            <>
                                <ChevronDown className="w-3 h-3 mr-1" />
                                Show more
                            </>
                        )}
                    </Button>
                )}

                {/* Action Buttons */}
                {hasUrl && (
                    <div className="flex gap-2 flex-wrap">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => window.open(alert.url, '_blank')}
                        >
                            <ExternalLink className="w-3 h-3 mr-1" />
                            View Source
                        </Button>
                    </div>
                )}
            </div>
        </Card>
    );
}
