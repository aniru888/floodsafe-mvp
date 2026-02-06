import { useState, useEffect } from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from './ui/dialog';
import { parseReportDescription } from '../lib/tagParser';
import { ReportTagList } from './ReportTagBadge';
import { useAuth } from '../contexts/AuthContext';
import {
    useUpvoteReport,
    useDownvoteReport,
    useComments,
    useAddComment,
    useDeleteComment,
    Report,
    Comment,
} from '../lib/api/hooks';
import {
    ThumbsUp,
    ThumbsDown,
    MessageCircle,
    MapPin,
    Clock,
    CheckCircle,
    AlertTriangle,
    Send,
    Trash2,
    Droplets,
    Car,
    Shield,
    Loader2,
} from 'lucide-react';
import { cn } from '../lib/utils';

interface ReportDetailModalProps {
    report: Report | null;
    isOpen: boolean;
    onClose: () => void;
    onLocate?: (lat: number, lng: number) => void;
}

/**
 * Format timestamp to readable format.
 */
function formatTimestamp(timestamp: string): string {
    try {
        // Backend stores UTC without 'Z', so add it
        const dateStr = timestamp.endsWith('Z') || timestamp.includes('+')
            ? timestamp
            : timestamp + 'Z';
        const date = new Date(dateStr);
        return date.toLocaleString('en-IN', {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
        });
    } catch {
        return timestamp;
    }
}

/**
 * Format time ago string.
 */
function formatTimeAgo(timestamp: string): string {
    try {
        const dateStr = timestamp.endsWith('Z') || timestamp.includes('+')
            ? timestamp
            : timestamp + 'Z';
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${diffDays}d ago`;
    } catch {
        return '';
    }
}

/**
 * Get water depth display info.
 */
function getWaterDepthInfo(depth: string | undefined): { label: string; color: string } | null {
    if (!depth) return null;
    const mapping: Record<string, { label: string; color: string }> = {
        ankle: { label: 'Ankle Deep', color: 'text-yellow-600' },
        knee: { label: 'Knee Deep', color: 'text-orange-600' },
        waist: { label: 'Waist Deep', color: 'text-red-600' },
        impassable: { label: 'Impassable', color: 'text-red-800' },
    };
    return mapping[depth] || null;
}

/**
 * Get vehicle passability display info.
 */
function getPassabilityInfo(passability: string | undefined): { label: string; icon: string } | null {
    if (!passability) return null;
    const mapping: Record<string, { label: string; icon: string }> = {
        all: { label: 'All Vehicles', icon: 'check' },
        'high-clearance': { label: 'High Clearance Only', icon: 'warning' },
        none: { label: 'No Vehicles', icon: 'alert' },
    };
    return mapping[passability] || null;
}

export function ReportDetailModal({ report, isOpen, onClose, onLocate }: ReportDetailModalProps) {
    const { user } = useAuth();
    const [newComment, setNewComment] = useState('');
    const [imageError, setImageError] = useState(false);
    const [isSubmittingComment, setIsSubmittingComment] = useState(false);

    // React Query hooks
    const upvoteMutation = useUpvoteReport();
    const downvoteMutation = useDownvoteReport();
    const { data: comments = [], isLoading: commentsLoading } = useComments(isOpen && report ? report.id : undefined);
    const addCommentMutation = useAddComment();
    const deleteCommentMutation = useDeleteComment();

    // Reset state when modal closes or report changes
    useEffect(() => {
        if (!isOpen) {
            setNewComment('');
            setImageError(false);
            setIsSubmittingComment(false);
        }
    }, [isOpen, report?.id]);

    if (!report) return null;

    // Parse tags from description
    const { tags, description: parsedDescription } = parseReportDescription(report.description);

    // Net score calculation
    const netScore = report.upvotes - report.downvotes;
    const netScoreColor = netScore > 0 ? 'text-green-600' : netScore < 0 ? 'text-red-600' : 'text-gray-500';

    // Handle vote
    const handleVote = async (type: 'upvote' | 'downvote') => {
        if (!user) return;
        try {
            if (type === 'upvote') {
                await upvoteMutation.mutateAsync(report.id);
            } else {
                await downvoteMutation.mutateAsync(report.id);
            }
        } catch (error) {
            console.error('Vote failed:', error);
        }
    };

    // Handle comment submission
    const handleSubmitComment = async () => {
        if (!user || !newComment.trim() || isSubmittingComment) return;

        setIsSubmittingComment(true);
        try {
            await addCommentMutation.mutateAsync({
                reportId: report.id,
                content: newComment.trim(),
            });
            setNewComment('');
        } catch (error) {
            // Rate limit or other error
            console.error('Comment failed:', error);
        } finally {
            setIsSubmittingComment(false);
        }
    };

    // Handle comment delete
    const handleDeleteComment = async (comment: Comment) => {
        if (!user || user.id !== comment.user_id) return;
        try {
            await deleteCommentMutation.mutateAsync({
                commentId: comment.id,
                reportId: report.id,
            });
        } catch (error) {
            console.error('Delete comment failed:', error);
        }
    };

    // Handle locate button
    const handleLocate = () => {
        if (onLocate && report.latitude && report.longitude) {
            onLocate(report.latitude, report.longitude);
            onClose();
        }
    };

    // Water depth and passability info
    const waterDepthInfo = getWaterDepthInfo(report.water_depth);
    const passabilityInfo = getPassabilityInfo(report.vehicle_passability);

    return (
        <Dialog open={isOpen} onOpenChange={(open) => {
            if (!open) onClose();
        }}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto p-4 sm:p-6">
                {/* Header */}
                <DialogHeader className="flex-shrink-0">
                    <div className="flex items-center gap-2">
                        {report.verified ? (
                            <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" />
                        ) : (
                            <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0" />
                        )}
                        <DialogTitle className="text-lg font-semibold">
                            {report.verified ? 'Verified Report' : 'Unverified Report'}
                        </DialogTitle>
                    </div>
                    <DialogDescription className="flex items-center gap-2 text-sm text-gray-500">
                        <Clock className="h-4 w-4" />
                        <span>{formatTimestamp(report.timestamp)}</span>
                        <span className="text-gray-400">({formatTimeAgo(report.timestamp)})</span>
                    </DialogDescription>
                </DialogHeader>

                {/* Photo Section */}
                {report.media_url && !imageError && (
                    <div className="mt-4 rounded-lg overflow-hidden bg-gray-100">
                        <img
                            src={report.media_url}
                            alt="Flood report"
                            className="w-full max-h-[40vh] object-contain"
                            onError={() => setImageError(true)}
                        />
                    </div>
                )}

                {/* Tags Section */}
                {tags.length > 0 && (
                    <div className="mt-4">
                        <ReportTagList tags={tags} />
                    </div>
                )}

                {/* Description */}
                <div className="mt-4">
                    <p className="text-gray-800 whitespace-pre-wrap">{parsedDescription}</p>
                </div>

                {/* Metadata Grid */}
                <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                    {/* Water Depth */}
                    {waterDepthInfo && (
                        <div className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg">
                            <Droplets className={cn("h-4 w-4", waterDepthInfo.color)} />
                            <span className={waterDepthInfo.color}>{waterDepthInfo.label}</span>
                        </div>
                    )}

                    {/* Vehicle Passability */}
                    {passabilityInfo && (
                        <div className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg">
                            <Car className="h-4 w-4 text-gray-600" />
                            <span className="text-gray-700">{passabilityInfo.label}</span>
                        </div>
                    )}

                    {/* IoT Score */}
                    {report.iot_validation_score !== undefined && report.iot_validation_score > 0 && (
                        <div className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg">
                            <Shield className="h-4 w-4 text-blue-600" />
                            <span className="text-gray-700">IoT Score: {report.iot_validation_score}%</span>
                        </div>
                    )}

                    {/* ML Classification */}
                    {report.ml_is_flood !== undefined && (
                        <div className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg">
                            {report.ml_is_flood ? (
                                <>
                                    <Droplets className="h-4 w-4 text-blue-600" />
                                    <span className="text-gray-700">
                                        AI Analysis: Flood Detected ({Math.round((report.ml_confidence || 0) * 100)}%)
                                    </span>
                                </>
                            ) : report.ml_needs_review ? (
                                <>
                                    <AlertTriangle className="h-4 w-4 text-yellow-600" />
                                    <span className="text-gray-700">AI Analysis: Needs Review</span>
                                </>
                            ) : (
                                <>
                                    <AlertTriangle className="h-4 w-4 text-orange-600" />
                                    <span className="text-gray-700">AI Analysis: May Not Be Flood</span>
                                </>
                            )}
                        </div>
                    )}

                    {/* Location */}
                    {report.latitude && report.longitude && onLocate && (
                        <button
                            onClick={handleLocate}
                            className="flex items-center gap-2 p-2 bg-blue-50 rounded-lg text-blue-700 hover:bg-blue-100 transition-colors"
                        >
                            <MapPin className="h-4 w-4" />
                            <span>View on Map</span>
                        </button>
                    )}
                </div>

                {/* Voting Section */}
                <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            {/* Upvote */}
                            <button
                                onClick={() => handleVote('upvote')}
                                disabled={!user || upvoteMutation.isPending}
                                className={cn(
                                    "flex items-center gap-1 px-3 py-1.5 rounded-lg transition-colors",
                                    report.user_vote === 'upvote'
                                        ? "bg-green-100 text-green-700"
                                        : "hover:bg-gray-200 text-gray-600",
                                    !user && "opacity-50 cursor-not-allowed"
                                )}
                            >
                                <ThumbsUp className="h-4 w-4" />
                                <span>{report.upvotes}</span>
                            </button>

                            {/* Downvote */}
                            <button
                                onClick={() => handleVote('downvote')}
                                disabled={!user || downvoteMutation.isPending}
                                className={cn(
                                    "flex items-center gap-1 px-3 py-1.5 rounded-lg transition-colors",
                                    report.user_vote === 'downvote'
                                        ? "bg-red-100 text-red-700"
                                        : "hover:bg-gray-200 text-gray-600",
                                    !user && "opacity-50 cursor-not-allowed"
                                )}
                            >
                                <ThumbsDown className="h-4 w-4" />
                                <span>{report.downvotes}</span>
                            </button>

                            {/* Net Score */}
                            <span className={cn("font-medium", netScoreColor)}>
                                {netScore > 0 ? '+' : ''}{netScore} net
                            </span>
                        </div>

                        {/* Comment Count */}
                        <div className="flex items-center gap-1 text-gray-500">
                            <MessageCircle className="h-4 w-4" />
                            <span>{report.comment_count || comments.length}</span>
                        </div>
                    </div>

                    {!user && (
                        <p className="mt-2 text-xs text-gray-500">
                            Log in to vote on this report
                        </p>
                    )}
                </div>

                {/* Comments Section */}
                <div className="mt-4">
                    <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                        <MessageCircle className="h-4 w-4" />
                        Comments
                    </h3>

                    {/* Add Comment Input */}
                    {user ? (
                        <div className="flex gap-2 mb-4">
                            <input
                                type="text"
                                value={newComment}
                                onChange={(e) => setNewComment(e.target.value.slice(0, 500))}
                                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSubmitComment()}
                                placeholder="Add a comment..."
                                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                disabled={isSubmittingComment}
                            />
                            <button
                                onClick={handleSubmitComment}
                                disabled={!newComment.trim() || isSubmittingComment}
                                className={cn(
                                    "px-3 py-2 rounded-lg transition-colors",
                                    newComment.trim()
                                        ? "bg-blue-600 text-white hover:bg-blue-700"
                                        : "bg-gray-100 text-gray-400 cursor-not-allowed"
                                )}
                            >
                                {isSubmittingComment ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Send className="h-4 w-4" />
                                )}
                            </button>
                        </div>
                    ) : (
                        <p className="text-sm text-gray-500 mb-4">
                            Log in to add a comment
                        </p>
                    )}

                    {/* Character count */}
                    {user && newComment.length > 0 && (
                        <p className="text-xs text-gray-400 -mt-3 mb-3">
                            {newComment.length}/500 characters
                        </p>
                    )}

                    {/* Comments List */}
                    <div className="max-h-[20rem] sm:max-h-[15rem] overflow-y-auto space-y-3 scrollbar-thin scrollbar-thumb-purple-300 scrollbar-track-gray-100">
                        {commentsLoading ? (
                            <div className="flex items-center justify-center py-4">
                                <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                            </div>
                        ) : comments.length === 0 ? (
                            <p className="text-sm text-gray-500 text-center py-4">
                                No comments yet. Be the first to comment!
                            </p>
                        ) : (
                            comments.map((comment) => (
                                <div
                                    key={comment.id}
                                    className="p-3 bg-white border border-gray-100 rounded-lg"
                                >
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="font-medium text-sm text-gray-800 truncate">
                                                    {comment.username}
                                                </span>
                                                <span className="text-xs text-gray-400">
                                                    {formatTimeAgo(comment.created_at)}
                                                </span>
                                            </div>
                                            <p className="text-sm text-gray-700 break-words">
                                                {comment.content}
                                            </p>
                                        </div>
                                        {user && user.id === comment.user_id && (
                                            <button
                                                onClick={() => handleDeleteComment(comment)}
                                                disabled={deleteCommentMutation.isPending}
                                                className="text-gray-400 hover:text-red-500 transition-colors flex-shrink-0"
                                                title="Delete comment"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </button>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
