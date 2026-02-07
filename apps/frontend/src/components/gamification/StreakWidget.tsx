import { Flame, Calendar } from 'lucide-react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { useMyReputation } from '../../lib/api/hooks';
import { cn } from '../../lib/utils';

interface StreakWidgetProps {
  className?: string;
}

export function StreakWidget({ className }: StreakWidgetProps) {
  const { data: reputation, isLoading, error } = useMyReputation();

  if (isLoading) {
    return (
      <Card className={cn('p-4', className)}>
        <div className="animate-pulse space-y-3">
          <div className="h-6 bg-muted rounded w-32"></div>
          <div className="h-16 bg-muted rounded"></div>
          <div className="flex gap-2">
            {[...Array(7)].map((_, i) => (
              <div key={i} className="h-8 w-8 bg-muted rounded-full"></div>
            ))}
          </div>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={cn('p-4 bg-destructive/10 border-destructive/20', className)}>
        <p className="text-sm text-destructive">Failed to load streak data</p>
      </Card>
    );
  }

  // Guard: API may return [] instead of object — [] is truthy, bypasses !data check
  if (!reputation || typeof reputation !== 'object' || Array.isArray(reputation)) {
    return null;
  }

  const streakDays = reputation.streak_days || 0;
  const isActiveStreak = streakDays > 0;

  // Milestone badges
  const milestones = [
    { days: 7, label: '7 Day', icon: '🔥' },
    { days: 14, label: '14 Day', icon: '🔥🔥' },
    { days: 30, label: '30 Day', icon: '⭐' },
    { days: 60, label: '60 Day', icon: '💫' },
    { days: 90, label: '90 Day', icon: '🏆' },
  ];

  const earnedMilestones = milestones.filter(m => streakDays >= m.days);
  const nextMilestone = milestones.find(m => streakDays < m.days);

  // Generate last 7 days activity (simplified - we don't have actual daily data)
  // Show filled circles for streak days, empty for rest
  const last7Days = [...Array(7)].map((_, i) => {
    const dayOffset = 6 - i; // 0 = today, 6 = 6 days ago
    return dayOffset < streakDays;
  });

  return (
    <Card className={cn(
      'p-4 relative overflow-hidden',
      isActiveStreak && 'bg-gradient-to-br from-orange-50 to-yellow-50 border-orange-200',
      className
    )}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Calendar className="w-4 h-4" />
          Report Streak
        </h3>
        {isActiveStreak && (
          <Flame className={cn(
            'w-6 h-6 text-orange-500',
            'animate-pulse'
          )} />
        )}
      </div>

      {/* Streak Counter */}
      <div className="mb-4">
        <div className="flex items-baseline gap-2">
          <span className="text-4xl font-bold text-orange-600">{streakDays}</span>
          <span className="text-lg text-muted-foreground">{streakDays === 1 ? 'day' : 'days'}</span>
        </div>
        {isActiveStreak ? (
          <p className="text-xs text-muted-foreground mt-1">
            Keep it going! Report today to maintain your streak.
          </p>
        ) : (
          <p className="text-xs text-muted-foreground mt-1">
            Submit a verified report to start a streak!
          </p>
        )}
      </div>

      {/* 7 Day Indicator */}
      <div className="mb-4">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-muted-foreground">Last 7 days</span>
        </div>
        <div className="flex gap-2">
          {last7Days.map((active, idx) => (
            <div
              key={idx}
              className={cn(
                'w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all',
                active
                  ? 'bg-orange-500 border-orange-600'
                  : 'bg-muted border-border'
              )}
              title={`${6 - idx} days ago`}
            >
              {active && <Flame className="w-4 h-4 text-white" />}
            </div>
          ))}
        </div>
      </div>

      {/* Milestones */}
      {earnedMilestones.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-muted-foreground mb-2">Milestones Unlocked</p>
          <div className="flex flex-wrap gap-1">
            {earnedMilestones.map((milestone) => (
              <Badge
                key={milestone.days}
                variant="secondary"
                className="bg-orange-100 text-orange-800 text-xs"
              >
                {milestone.icon} {milestone.label}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Next Milestone */}
      {nextMilestone && (
        <div className="pt-3 border-t border-orange-100">
          <p className="text-xs text-muted-foreground">
            Next milestone: <span className="font-medium text-orange-600">{nextMilestone.label} {nextMilestone.icon}</span>
            <span className="text-muted-foreground"> ({nextMilestone.days - streakDays} more days)</span>
          </p>
        </div>
      )}
    </Card>
  );
}
