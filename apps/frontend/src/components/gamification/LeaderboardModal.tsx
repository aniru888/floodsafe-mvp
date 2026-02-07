import { useState } from 'react';
import { Trophy, Medal, Crown, Users, Award, TrendingUp } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { ScrollArea } from '../ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Badge } from '../ui/badge';
import { useLeaderboard } from '../../lib/api/hooks';
import { cn } from '../../lib/utils';

interface LeaderboardModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userId?: string;
}

export function LeaderboardModal({ open, onOpenChange, userId }: LeaderboardModalProps) {
  const [activeTab, setActiveTab] = useState<'global' | 'weekly' | 'monthly'>('global');

  // Fetch leaderboards for each type (top 100)
  const { data: globalData, isLoading: globalLoading, error: globalError } = useLeaderboard('global', 100, userId);
  const { data: weeklyData, isLoading: weeklyLoading, error: weeklyError } = useLeaderboard('weekly', 100, userId);
  const { data: monthlyData, isLoading: monthlyLoading, error: monthlyError } = useLeaderboard('monthly', 100, userId);

  // Get current data based on active tab
  const getCurrentData = () => {
    switch (activeTab) {
      case 'weekly': return weeklyData;
      case 'monthly': return monthlyData;
      default: return globalData;
    }
  };

  const getCurrentLoading = () => {
    switch (activeTab) {
      case 'weekly': return weeklyLoading;
      case 'monthly': return monthlyLoading;
      default: return globalLoading;
    }
  };

  const getCurrentError = () => {
    switch (activeTab) {
      case 'weekly': return weeklyError;
      case 'monthly': return monthlyError;
      default: return globalError;
    }
  };

  const currentData = getCurrentData();
  const isLoading = getCurrentLoading();
  const error = getCurrentError();

  // Rank icons for top 3
  const getRankIcon = (rank: number) => {
    if (rank === 1) return <Crown className="w-5 h-5 text-yellow-500" />;
    if (rank === 2) return <Medal className="w-5 h-5 text-gray-400" />;
    if (rank === 3) return <Medal className="w-5 h-5 text-orange-400" />;
    return null;
  };

  // Rank styling
  const getRankStyle = (rank: number) => {
    if (rank === 1) return 'bg-gradient-to-r from-yellow-50 to-yellow-100 border-yellow-300';
    if (rank === 2) return 'bg-gradient-to-r from-gray-50 to-gray-100 border-gray-300';
    if (rank === 3) return 'bg-gradient-to-r from-orange-50 to-orange-100 border-orange-300';
    return 'bg-card';
  };

  const getRankTextColor = (rank: number) => {
    if (rank === 1) return 'text-yellow-700';
    if (rank === 2) return 'text-gray-700';
    if (rank === 3) return 'text-orange-700';
    return 'text-foreground';
  };

  // Get total user count (estimate based on current user rank if available)
  const totalUsers = currentData?.current_user_rank || currentData?.entries.length || 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] p-0">
        <DialogHeader className="p-6 pb-4 border-b border-border">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Trophy className="w-6 h-6 text-purple-600" />
            Leaderboard
          </DialogTitle>
          <p className="text-sm text-muted-foreground mt-1">
            Top contributors ranked by points and verified reports
          </p>
        </DialogHeader>

        {/* Tabs */}
        <Tabs defaultValue="global" value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="flex-1">
          <div className="px-6 pt-4">
            <TabsList className="w-full grid grid-cols-3">
              <TabsTrigger value="global" className="text-sm">
                <Trophy className="w-4 h-4 mr-2" />
                All Time
              </TabsTrigger>
              <TabsTrigger value="weekly" className="text-sm">
                <TrendingUp className="w-4 h-4 mr-2" />
                Weekly
              </TabsTrigger>
              <TabsTrigger value="monthly" className="text-sm">
                <Award className="w-4 h-4 mr-2" />
                Monthly
              </TabsTrigger>
            </TabsList>
          </div>

          {/* Content for each tab */}
          {['global', 'weekly', 'monthly'].map((tabValue) => (
            <TabsContent key={tabValue} value={tabValue} className="flex-1 m-0">
              {/* Loading State */}
              {isLoading && (
                <div className="px-6 py-4 space-y-2">
                  {[...Array(10)].map((_, i) => (
                    <div key={i} className="h-16 bg-muted rounded-lg animate-pulse"></div>
                  ))}
                </div>
              )}

              {/* Error State */}
              {error && (
                <div className="px-6 py-4">
                  <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
                    <p className="text-sm text-destructive">Failed to load leaderboard. Please try again.</p>
                  </div>
                </div>
              )}

              {/* Table */}
              {!isLoading && !error && currentData && (
                <>
                  <ScrollArea className="h-[500px]">
                    <div className="px-6 py-4">
                      {/* Table Header */}
                      <div className="grid grid-cols-12 gap-3 px-4 py-2 text-xs font-medium text-muted-foreground border-b border-border mb-2">
                        <div className="col-span-1 text-center">Rank</div>
                        <div className="col-span-4">User</div>
                        <div className="col-span-2 text-center">Level</div>
                        <div className="col-span-2 text-center">Points</div>
                        <div className="col-span-2 text-center">Reputation</div>
                        <div className="col-span-1 text-center">Badges</div>
                      </div>

                      {/* Table Rows */}
                      <div className="space-y-1">
                        {currentData.entries.map((entry) => {
                          const isCurrentUser = userId && entry.rank === currentData.current_user_rank;

                          return (
                            <div
                              key={entry.rank}
                              className={cn(
                                'grid grid-cols-12 gap-3 px-4 py-3 rounded-xl border transition-all',
                                isCurrentUser
                                  ? 'bg-purple-50 border-purple-300 shadow-sm ring-2 ring-purple-200'
                                  : entry.rank <= 3
                                    ? `${getRankStyle(entry.rank)} border`
                                    : 'bg-card border-border hover:bg-muted'
                              )}
                            >
                              {/* Rank */}
                              <div className="col-span-1 flex items-center justify-center">
                                {getRankIcon(entry.rank) || (
                                  <span className={cn(
                                    'text-sm font-semibold',
                                    isCurrentUser ? 'text-purple-700' : getRankTextColor(entry.rank)
                                  )}>
                                    #{entry.rank}
                                  </span>
                                )}
                              </div>

                              {/* User */}
                              <div className="col-span-4 flex items-center gap-2 min-w-0">
                                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-400 to-blue-400 flex items-center justify-center flex-shrink-0">
                                  <Users className="w-4 h-4 text-white" />
                                </div>
                                <div className="min-w-0 flex-1">
                                  <p className={cn(
                                    'text-sm font-medium truncate',
                                    isCurrentUser ? 'text-purple-700' : 'text-foreground'
                                  )}>
                                    {entry.is_anonymous ? 'Anonymous User' : entry.display_name}
                                  </p>
                                  {isCurrentUser && (
                                    <Badge variant="secondary" className="bg-purple-200 text-purple-800 text-[10px] px-1.5 py-0 mt-0.5">
                                      You
                                    </Badge>
                                  )}
                                </div>
                              </div>

                              {/* Level */}
                              <div className="col-span-2 flex items-center justify-center">
                                <Badge variant="secondary" className={cn(
                                  'text-xs',
                                  isCurrentUser ? 'bg-purple-200 text-purple-800' : 'bg-blue-100 text-blue-700'
                                )}>
                                  L{entry.level}
                                </Badge>
                              </div>

                              {/* Points */}
                              <div className="col-span-2 flex items-center justify-center">
                                <div className="text-center">
                                  <p className={cn(
                                    'text-sm font-semibold',
                                    isCurrentUser ? 'text-purple-700' : 'text-foreground'
                                  )}>
                                    {entry.points}
                                  </p>
                                  <p className="text-[10px] text-muted-foreground">pts</p>
                                </div>
                              </div>

                              {/* Reputation */}
                              <div className="col-span-2 flex items-center justify-center">
                                <div className="text-center">
                                  <p className={cn(
                                    'text-sm font-semibold',
                                    entry.reputation_score >= 70
                                      ? 'text-green-600'
                                      : entry.reputation_score >= 40
                                        ? 'text-yellow-600'
                                        : 'text-red-600'
                                  )}>
                                    {Math.round(entry.reputation_score)}
                                  </p>
                                  <p className="text-[10px] text-muted-foreground">score</p>
                                </div>
                              </div>

                              {/* Badges */}
                              <div className="col-span-1 flex items-center justify-center">
                                <Badge variant="secondary" className="bg-yellow-100 text-yellow-700 text-xs">
                                  {entry.badges_count}
                                </Badge>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </ScrollArea>

                  {/* Footer with User Position */}
                  {userId && currentData.current_user_rank && (
                    <div className="px-6 py-4 border-t border-border bg-muted">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-semibold text-foreground">
                            Your Position
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Ranked #{currentData.current_user_rank} of {totalUsers.toLocaleString()} users
                          </p>
                        </div>
                        <div className="text-right">
                          <Badge variant="secondary" className="bg-purple-100 text-purple-700 text-sm px-3 py-1">
                            #{currentData.current_user_rank}
                          </Badge>
                          {currentData.current_user_rank > 10 && (
                            <p className="text-xs text-muted-foreground mt-1">
                              {currentData.current_user_rank <= 50 ? 'So close to top 50!' : 'Keep climbing!'}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Empty State */}
              {!isLoading && !error && currentData && currentData.entries.length === 0 && (
                <div className="px-6 py-16 text-center">
                  <Trophy className="w-16 h-16 mx-auto text-muted-foreground/40 mb-3" />
                  <p className="text-sm text-muted-foreground font-medium">No leaderboard data yet</p>
                  <p className="text-xs text-muted-foreground mt-1">Be the first to start reporting!</p>
                </div>
              )}
            </TabsContent>
          ))}
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
