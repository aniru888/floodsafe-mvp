import React, { useState } from 'react';
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
    ChevronDown,
    ChevronUp,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { Report, useUpvoteReport, useDownvoteReport, useComments, useAddComment, useDeleteComment, Comment } from '../lib/api/hooks';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { parseReportDescription } from '../lib/tagParser';
import { ReportTagList } from './ReportTagBadge';

interface ReportCardProps {
    report: Report;
    onLocate?: (lat: number, lng: number) => void;
    onViewDetails?: (report: Report) => void;
    showFullDetails?: boolean;
}

function formatTimeAgo(timestamp: string): string {
    const date = new Date(timestamp.endsWith('Z') ? timestamp : timestamp + 'Z');
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
}

function formatExactTime(timestamp: string): string {
    const date = new Date(timestamp.endsWith('Z') ? timestamp : timestamp + 'Z');
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function getWaterDepthLabel(depth: string | undefined): string | null {
    if (!depth) return null;
    const labels: Record<string, string> = {
        ankle: 'Ankle deep',
        knee: 'Knee deep',
        waist: 'Waist deep',
        impassable: 'Impassable',
    };
    return labels[depth] || depth;
}

export function ReportCard({ report, onLocate, onViewDetails, showFullDetails = false }: ReportCardProps) {
    const { user } = useAuth();
    const [showComments, setShowComments] = useState(false);
    const [newComment, setNewComment] = useState('');

    const upvoteMutation = useUpvoteReport();
    const downvoteMutation = useDownvoteReport();
    const { data: comments, isLoading: commentsLoading } = useComments(showComments ? report.id : undefined);
    const addCommentMutation = useAddComment();
    const deleteCommentMutation = useDeleteComment();

    const isVoting = upvoteMutation.isPending || downvoteMutation.isPending;
    const _isOwnReport = user?.id === report.id; // Note: reports don't have user_id exposed

    const handleUpvote = async () => {
        if (!user) {
            toast.error('Please log in to vote');
            return;
        }
        try {
            await upvoteMutation.mutateAsync(report.id);
        } catch (error) {
            toast.error('Failed to vote. Please try again.');
        }
    };

    const handleDownvote = async () => {
        if (!user) {
            toast.error('Please log in to vote');
            return;
        }
        try {
            await downvoteMutation.mutateAsync(report.id);
        } catch (error) {
            toast.error('Failed to vote. Please try again.');
        }
    };

    const handleAddComment = async () => {
        if (!user) {
            toast.error('Please log in to comment');
            return;
        }
        if (!newComment.trim()) return;
        if (newComment.length > 500) {
            toast.error('Comment must be 500 characters or less');
            return;
        }

        try {
            await addCommentMutation.mutateAsync({ reportId: report.id, content: newComment.trim() });
            setNewComment('');
            toast.success('Comment added');
        } catch (error: unknown) {
            if (error instanceof Error && error.message.includes('429')) {
                toast.error('Too many comments. Please wait a moment.');
            } else {
                toast.error('Failed to add comment');
            }
        }
    };

    const handleDeleteComment = async (comment: Comment) => {
        try {
            await deleteCommentMutation.mutateAsync({ commentId: comment.id, reportId: report.id });
            toast.success('Comment deleted');
        } catch {
            toast.error('Failed to delete comment');
        }
    };

    const waterDepthLabel = getWaterDepthLabel(report.water_depth);
    const netVotes = (report.upvotes || 0) - (report.downvotes || 0);

    return (
        <div className="bg-card rounded-lg shadow-sm border border-border overflow-hidden">
            {/* Header */}
            <div className="p-4">
                <div className="flex items-start gap-3">
                    {/* Status Icon */}
                    <div className={cn(
                        'p-2 rounded-full flex-shrink-0',
                        report.verified
                            ? 'bg-green-100 text-green-600'
                            : 'bg-yellow-100 text-yellow-600'
                    )}>
                        {report.verified ? (
                            <CheckCircle className="w-5 h-5" />
                        ) : (
                            <AlertTriangle className="w-5 h-5" />
                        )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Clock className="w-3 h-3" />
                            <span>{formatExactTime(report.timestamp)} ({formatTimeAgo(report.timestamp)})</span>
                            {report.verified && (
                                <span className="bg-green-100 text-green-700 px-1.5 py-0.5 rounded text-xs font-medium">
                                    Verified
                                </span>
                            )}
                        </div>

                        {/* Tags and Description */}
                        {(() => {
                            const { tags, description } = parseReportDescription(report.description);
                            return (
                                <>
                                    <ReportTagList tags={tags} />
                                    <p className={cn(
                                        "text-foreground mt-1",
                                        showFullDetails ? "" : "line-clamp-2"
                                    )}>
                                        {description}
                                    </p>
                                </>
                            );
                        })()}

                        {/* Water depth badge */}
                        {waterDepthLabel && (
                            <div className="mt-2">
                                <span className={cn(
                                    "inline-flex items-center px-2 py-1 rounded-full text-xs font-medium",
                                    report.water_depth === 'impassable' ? 'bg-red-100 text-red-700' :
                                    report.water_depth === 'waist' ? 'bg-orange-100 text-orange-700' :
                                    report.water_depth === 'knee' ? 'bg-yellow-100 text-yellow-700' :
                                    'bg-blue-100 text-blue-700'
                                )}>
                                    {waterDepthLabel}
                                </span>
                            </div>
                        )}

                        {/* Location */}
                        <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
                            <MapPin className="w-3 h-3" />
                            <span>{report.latitude.toFixed(4)}, {report.longitude.toFixed(4)}</span>
                            {onLocate && (
                                <button
                                    onClick={() => onLocate(report.latitude, report.longitude)}
                                    className="ml-2 text-purple-600 hover:text-purple-700 font-medium"
                                >
                                    Locate
                                </button>
                            )}
                        </div>
                    </div>
                </div>

                {/* Media */}
                {report.media_url && showFullDetails && (
                    <div className="mt-3">
                        <img
                            src={report.media_url}
                            alt="Report photo"
                            className="w-full h-48 object-cover rounded-lg"
                        />
                    </div>
                )}
            </div>

            {/* Action Bar */}
            <div className="px-4 py-3 bg-muted border-t border-border flex items-center gap-4">
                {/* Upvote */}
                <button
                    onClick={handleUpvote}
                    disabled={isVoting}
                    className={cn(
                        "flex items-center gap-1 px-3 py-1.5 rounded-full text-sm transition-colors",
                        report.user_vote === 'upvote'
                            ? "bg-green-100 text-green-700"
                            : "hover:bg-muted text-muted-foreground"
                    )}
                >
                    <ThumbsUp className={cn("w-4 h-4", report.user_vote === 'upvote' && "fill-current")} />
                    <span>{report.upvotes || 0}</span>
                </button>

                {/* Downvote */}
                <button
                    onClick={handleDownvote}
                    disabled={isVoting}
                    className={cn(
                        "flex items-center gap-1 px-3 py-1.5 rounded-full text-sm transition-colors",
                        report.user_vote === 'downvote'
                            ? "bg-red-100 text-red-700"
                            : "hover:bg-muted text-muted-foreground"
                    )}
                >
                    <ThumbsDown className={cn("w-4 h-4", report.user_vote === 'downvote' && "fill-current")} />
                    <span>{report.downvotes || 0}</span>
                </button>

                {/* Net Score */}
                <div className={cn(
                    "text-sm font-medium",
                    netVotes > 0 ? "text-green-600" : netVotes < 0 ? "text-red-600" : "text-muted-foreground"
                )}>
                    {netVotes > 0 ? '+' : ''}{netVotes}
                </div>

                {/* View Details button */}
                {onViewDetails && (
                    <button
                        onClick={() => onViewDetails(report)}
                        className="px-3 py-1.5 rounded-full text-sm bg-primary/10 text-primary hover:bg-primary/20 transition-colors ml-auto"
                    >
                        View
                    </button>
                )}

                {/* Comments toggle */}
                <button
                    onClick={() => setShowComments(!showComments)}
                    className={cn(
                        "flex items-center gap-1 px-3 py-1.5 rounded-full text-sm hover:bg-muted text-muted-foreground",
                        !onViewDetails && "ml-auto"
                    )}
                >
                    <MessageCircle className="w-4 h-4" />
                    <span>{report.comment_count || 0}</span>
                    {showComments ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>
            </div>

            {/* Comments Section */}
            {showComments && (
                <div className="px-4 py-3 border-t border-border bg-card">
                    {/* Add Comment */}
                    {user && (
                        <div className="flex gap-2 mb-3">
                            <input
                                type="text"
                                value={newComment}
                                onChange={(e) => setNewComment(e.target.value)}
                                placeholder="Add a comment..."
                                maxLength={500}
                                className="flex-1 px-3 py-2 text-sm border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        handleAddComment();
                                    }
                                }}
                            />
                            <button
                                onClick={handleAddComment}
                                disabled={!newComment.trim() || addCommentMutation.isPending}
                                className="px-3 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <Send className="w-4 h-4" />
                            </button>
                        </div>
                    )}

                    {/* Comments List */}
                    {commentsLoading ? (
                        <div className="text-sm text-muted-foreground text-center py-4">Loading comments...</div>
                    ) : comments && comments.length > 0 ? (
                        <div className="space-y-3">
                            {comments.map((comment) => (
                                <div key={comment.id} className="flex items-start gap-2">
                                    <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs font-medium text-muted-foreground">
                                        {comment.username.charAt(0).toUpperCase()}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-medium text-foreground">{comment.username}</span>
                                            <span className="text-xs text-muted-foreground/60">{formatTimeAgo(comment.created_at)}</span>
                                            {user?.id === comment.user_id && (
                                                <button
                                                    onClick={() => handleDeleteComment(comment)}
                                                    className="text-muted-foreground/60 hover:text-red-500 ml-auto"
                                                >
                                                    <Trash2 className="w-3 h-3" />
                                                </button>
                                            )}
                                        </div>
                                        <p className="text-sm text-muted-foreground">{comment.content}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-sm text-muted-foreground text-center py-4">
                            No comments yet. Be the first to comment!
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
