import { Award, Lock, TrendingUp } from 'lucide-react';
import { Card } from '../ui/card';
import { Badge as BadgeUI } from '../ui/badge';
import { Progress } from '../ui/progress';
import { useMyBadges } from '../../lib/api/hooks';
import { cn } from '../../lib/utils';

interface BadgeGridProps {
  className?: string;
  limit?: number; // Limit number of badges shown (default: show all)
  onViewAll?: () => void; // Callback when "View All" is clicked
}

export function BadgeGrid({ className, limit, onViewAll }: BadgeGridProps) {
  const { data: badgesData, isLoading, error } = useMyBadges();

  if (isLoading) {
    return (
      <Card className={cn('p-4', className)}>
        <div className="animate-pulse space-y-3">
          <div className="h-6 bg-muted rounded w-32"></div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-24 bg-muted rounded-lg"></div>
            ))}
          </div>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={cn('p-4 bg-destructive/10 border-destructive/20', className)}>
        <p className="text-sm text-destructive">Failed to load badges</p>
      </Card>
    );
  }

  // Guard: API may return [] instead of object — [] is truthy, bypasses !data check
  if (!badgesData || typeof badgesData !== 'object' || Array.isArray(badgesData)) {
    return null;
  }

  const earnedBadges = badgesData.earned || [];
  const inProgressBadges = badgesData.in_progress || [];

  // Combine and optionally limit
  const allBadges = [
    ...earnedBadges.map(b => ({ ...b, earned: true })),
    ...inProgressBadges.map(b => ({ ...b, earned: false }))
  ];

  const displayBadges = limit ? allBadges.slice(0, limit) : allBadges;

  return (
    <Card className={cn('p-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Award className="w-4 h-4 text-yellow-600" />
          Badges
          <BadgeUI variant="secondary" className="text-xs bg-yellow-50 text-yellow-700">
            {earnedBadges.length} / {allBadges.length}
          </BadgeUI>
        </h3>
        {onViewAll && (
          <button
            onClick={onViewAll}
            className="text-xs text-purple-600 hover:text-purple-700 font-medium hover:underline"
          >
            View All
          </button>
        )}
      </div>

      {displayBadges.length === 0 ? (
        <div className="text-center py-8">
          <Award className="w-12 h-12 mx-auto text-muted-foreground/40 mb-2" />
          <p className="text-sm text-muted-foreground">No badges yet</p>
          <p className="text-xs text-muted-foreground/60 mt-1">Keep submitting reports to earn badges!</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {displayBadges.map((item) => {
            const isEarned = 'earned' in item && item.earned;
            const badge = 'badge' in item ? item.badge : item;
            const progressPercent = 'progress_percent' in item ? item.progress_percent : 100;
            const currentValue = 'current_value' in item ? item.current_value : 0;
            const requiredValue = 'required_value' in item ? item.required_value : 0;

            // Parse icon emoji from badge.icon field
            const iconEmoji = badge.icon || '🏅';

            // Category colors
            const categoryColors: Record<string, string> = {
              reporting: 'border-blue-200 bg-blue-50',
              verification: 'border-green-200 bg-green-50',
              community: 'border-purple-200 bg-purple-50',
              streak: 'border-orange-200 bg-orange-50',
              special: 'border-yellow-200 bg-yellow-50',
            };

            const categoryColor = categoryColors[badge.category] || 'border-border bg-muted';

            return (
              <div
                key={badge.key}
                className={cn(
                  'p-3 rounded-lg border-2 transition-all relative',
                  isEarned
                    ? `${categoryColor} shadow-sm`
                    : 'border-border bg-muted opacity-60',
                  'hover:scale-105 cursor-pointer'
                )}
                title={badge.description || badge.name}
              >
                {/* Lock Icon for Locked Badges */}
                {!isEarned && (
                  <div className="absolute top-2 right-2">
                    <Lock className="w-3 h-3 text-muted-foreground/60" />
                  </div>
                )}

                {/* Badge Icon */}
                <div className="text-center mb-2">
                  <div className={cn(
                    'text-3xl mx-auto w-12 h-12 flex items-center justify-center rounded-full',
                    isEarned ? 'bg-card shadow-sm' : 'bg-muted grayscale'
                  )}>
                    {iconEmoji}
                  </div>
                </div>

                {/* Badge Name */}
                <p className={cn(
                  'text-xs font-semibold text-center mb-1 line-clamp-1',
                  isEarned ? 'text-foreground' : 'text-muted-foreground'
                )}>
                  {badge.name}
                </p>

                {/* Progress Bar (for in-progress badges) */}
                {!isEarned && progressPercent < 100 && (
                  <div className="mt-2">
                    <Progress value={progressPercent} className="h-1.5 bg-muted" />
                    <div className="flex items-center justify-center gap-1 mt-1">
                      <TrendingUp className="w-3 h-3 text-muted-foreground/60" />
                      <p className="text-[10px] text-muted-foreground">
                        {currentValue}/{requiredValue}
                      </p>
                    </div>
                  </div>
                )}

                {/* Points Reward */}
                {isEarned && badge.points_reward > 0 && (
                  <div className="mt-1 text-center">
                    <BadgeUI variant="secondary" className="text-[10px] bg-yellow-100 text-yellow-700 px-1.5 py-0.5">
                      +{badge.points_reward} pts
                    </BadgeUI>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Show All Link (if limited) */}
      {limit && allBadges.length > limit && (
        <div className="mt-4 text-center">
          {onViewAll ? (
            <button
              onClick={onViewAll}
              className="text-xs text-purple-600 hover:text-purple-700 font-medium hover:underline"
            >
              View all {allBadges.length} badges →
            </button>
          ) : (
            <p className="text-xs text-muted-foreground">
              Showing {limit} of {allBadges.length} badges
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
