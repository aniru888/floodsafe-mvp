import { useState } from 'react';
import { Users, ChevronDown, ChevronUp, Trophy, Medal, Crown } from 'lucide-react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { useLeaderboard } from '../../lib/api/hooks';
import { cn } from '../../lib/utils';

interface LeaderboardSectionProps {
  userId: string;
  onViewFull?: () => void;
  className?: string;
}

export function LeaderboardSection({ userId, onViewFull, className }: LeaderboardSectionProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedType, setSelectedType] = useState<'global' | 'weekly' | 'monthly'>('global');

  const { data: leaderboardData, isLoading, error } = useLeaderboard(selectedType, 10, userId);

  // Get user's rank from response
  const currentUserRank = leaderboardData?.current_user_rank;

  // Rank icons for top 3
  const getRankIcon = (rank: number) => {
    if (rank === 1) return <Crown className="w-4 h-4 text-yellow-500" />;
    if (rank === 2) return <Medal className="w-4 h-4 text-gray-400" />;
    if (rank === 3) return <Medal className="w-4 h-4 text-orange-400" />;
    return null;
  };

  // Rank color
  const getRankColor = (rank: number) => {
    if (rank === 1) return 'text-yellow-600 font-bold';
    if (rank === 2) return 'text-gray-600 font-bold';
    if (rank === 3) return 'text-orange-600 font-bold';
    return 'text-gray-600';
  };

  return (
    <Card className={cn('overflow-hidden', className)}>
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger className="w-full">
          <div className="p-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center">
                <Users className="w-5 h-5 text-purple-600" />
              </div>
              <div className="text-left">
                <h3 className="text-sm font-semibold text-gray-800">Leaderboard</h3>
                {currentUserRank && (
                  <p className="text-xs text-gray-500">
                    Your Rank: <span className="font-semibold text-purple-600">#{currentUserRank}</span>
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {!isOpen && (
                <Badge variant="secondary" className="bg-purple-50 text-purple-700 text-xs">
                  Top 10
                </Badge>
              )}
              {isOpen ? (
                <ChevronUp className="w-5 h-5 text-gray-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
              )}
            </div>
          </div>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="px-4 pb-4 border-t border-gray-100">
            {/* Tab Selector */}
            <div className="flex gap-2 pt-4 pb-3">
              <button
                onClick={() => setSelectedType('global')}
                className={cn(
                  'flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all',
                  selectedType === 'global'
                    ? 'bg-purple-500 text-white shadow-sm'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                All Time
              </button>
              <button
                onClick={() => setSelectedType('weekly')}
                className={cn(
                  'flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all',
                  selectedType === 'weekly'
                    ? 'bg-purple-500 text-white shadow-sm'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                Weekly
              </button>
              <button
                onClick={() => setSelectedType('monthly')}
                className={cn(
                  'flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all',
                  selectedType === 'monthly'
                    ? 'bg-purple-500 text-white shadow-sm'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                Monthly
              </button>
            </div>

            {/* Loading State */}
            {isLoading && (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-12 bg-gray-100 rounded-lg animate-pulse"></div>
                ))}
              </div>
            )}

            {/* Error State */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <p className="text-xs text-red-600">Failed to load leaderboard. Please try again.</p>
              </div>
            )}

            {/* Leaderboard Table */}
            {!isLoading && !error && leaderboardData && !Array.isArray(leaderboardData) && (
              <>
                <div className="space-y-1 mb-3">
                  {(leaderboardData.entries || []).map((entry) => {
                    const isCurrentUser = entry.rank === currentUserRank;

                    return (
                      <div
                        key={entry.rank}
                        className={cn(
                          'flex items-center gap-3 p-2 rounded-lg transition-colors',
                          isCurrentUser
                            ? 'bg-purple-50 border-2 border-purple-200'
                            : 'hover:bg-gray-50'
                        )}
                      >
                        {/* Rank */}
                        <div className="w-8 flex items-center justify-center">
                          {getRankIcon(entry.rank) || (
                            <span className={cn('text-sm font-medium', getRankColor(entry.rank))}>
                              #{entry.rank}
                            </span>
                          )}
                        </div>

                        {/* User Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className={cn(
                              'text-sm font-medium truncate',
                              isCurrentUser ? 'text-purple-700' : 'text-gray-800'
                            )}>
                              {entry.is_anonymous ? 'Anonymous User' : entry.display_name}
                            </p>
                            {isCurrentUser && (
                              <Badge variant="secondary" className="bg-purple-100 text-purple-700 text-[10px] px-1.5 py-0">
                                You
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span>Level {entry.level}</span>
                            <span>•</span>
                            <span>{entry.verified_reports} verified</span>
                          </div>
                        </div>

                        {/* Points */}
                        <div className="text-right">
                          <p className={cn(
                            'text-sm font-semibold',
                            isCurrentUser ? 'text-purple-600' : 'text-gray-700'
                          )}>
                            {entry.points}
                          </p>
                          <p className="text-[10px] text-gray-500">points</p>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* View Full Leaderboard Button */}
                {onViewFull && (
                  <button
                    onClick={onViewFull}
                    className="w-full py-2 px-4 bg-purple-500 text-white rounded-lg text-sm font-medium hover:bg-purple-600 transition-colors shadow-sm"
                  >
                    View Full Leaderboard
                  </button>
                )}

                {/* Current User Not in Top 10 */}
                {currentUserRank && currentUserRank > 10 && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <p className="text-xs text-center text-gray-600">
                      You're ranked <span className="font-semibold text-purple-600">#{currentUserRank}</span> overall
                    </p>
                    <p className="text-xs text-center text-gray-500 mt-1">
                      Keep reporting to climb the ranks!
                    </p>
                  </div>
                )}
              </>
            )}

            {/* Empty State */}
            {!isLoading && !error && leaderboardData && !Array.isArray(leaderboardData) && (leaderboardData.entries || []).length === 0 && (
              <div className="text-center py-8">
                <Trophy className="w-12 h-12 mx-auto text-gray-300 mb-2" />
                <p className="text-sm text-gray-600">No leaderboard data yet</p>
                <p className="text-xs text-gray-500 mt-1">Be the first to start reporting!</p>
              </div>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}
