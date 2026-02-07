import { Trophy, Zap, Star } from 'lucide-react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { User } from '../../types';
import { cn } from '../../lib/utils';

interface LevelProgressCardProps {
  user: User;
  className?: string;
}

export function LevelProgressCard({ user, className }: LevelProgressCardProps) {
  const currentLevel = user?.level ?? 1;
  const currentPoints = user?.points ?? 0;

  // 100 points per level
  const pointsPerLevel = 100;
  const pointsInCurrentLevel = currentPoints % pointsPerLevel;
  const pointsToNextLevel = pointsPerLevel - pointsInCurrentLevel;
  const progressPercent = (pointsInCurrentLevel / pointsPerLevel) * 100;

  // Level milestones
  const milestones = [
    { level: 5, label: 'Reporter', icon: '🌱', color: 'text-green-600' },
    { level: 10, label: 'Guardian', icon: '🛡️', color: 'text-blue-600' },
    { level: 15, label: 'Sentinel', icon: '⚔️', color: 'text-purple-600' },
    { level: 20, label: 'Hero', icon: '🦸', color: 'text-orange-600' },
    { level: 25, label: 'Legend', icon: '👑', color: 'text-yellow-600' },
  ];

  const currentMilestone = milestones.reverse().find(m => currentLevel >= m.level) || null;
  const nextMilestone = milestones.find(m => currentLevel < m.level);

  // Estimate reports needed (assuming 10 points per verified report)
  const reportsNeeded = Math.ceil(pointsToNextLevel / 10);

  return (
    <Card className={cn('p-4 bg-gradient-to-br from-purple-50 to-blue-50 border-purple-200', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Trophy className="w-4 h-4 text-purple-600" />
          Level Progress
        </h3>
        {currentMilestone && (
          <Badge variant="secondary" className="bg-purple-100 text-purple-800 text-xs">
            {currentMilestone.icon} {currentMilestone.label}
          </Badge>
        )}
      </div>

      {/* Current Level */}
      <div className="mb-4">
        <div className="flex items-center gap-3">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-blue-500 rounded-full flex items-center justify-center shadow-lg">
            <span className="text-2xl font-bold text-white">{currentLevel}</span>
          </div>
          <div className="flex-1">
            <p className="text-xs text-muted-foreground font-medium">Current Level</p>
            <p className="text-2xl font-bold text-foreground">Level {currentLevel}</p>
            <p className="text-xs text-muted-foreground">{currentPoints} total points</p>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-muted-foreground font-medium">
            Progress to Level {currentLevel + 1}
          </span>
          <span className="text-xs text-purple-600 font-semibold">
            {pointsInCurrentLevel}/{pointsPerLevel}
          </span>
        </div>
        <div className="relative">
          <Progress
            value={progressPercent}
            className="h-3 bg-muted"
          />
          <div
            className="absolute top-0 h-3 rounded-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          {pointsToNextLevel} more points to level up
        </p>
      </div>

      {/* Milestones Visualization */}
      <div className="mb-4">
        <p className="text-xs font-semibold text-foreground mb-2">Milestones</p>
        <div className="flex justify-between items-center">
          {[5, 10, 15, 20, 25].map((milestone) => {
            const achieved = currentLevel >= milestone;
            const isCurrent = currentLevel >= milestone && (currentLevel < (milestones.find(m => m.level > milestone)?.level || Infinity));

            return (
              <div key={milestone} className="flex flex-col items-center">
                <div
                  className={cn(
                    'w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all',
                    achieved
                      ? 'bg-purple-500 border-purple-600 shadow-md'
                      : 'bg-muted border-border',
                    isCurrent && 'ring-2 ring-purple-400 ring-offset-2'
                  )}
                >
                  {achieved ? (
                    <Star className="w-5 h-5 text-white fill-current" />
                  ) : (
                    <span className="text-xs font-medium text-muted-foreground">{milestone}</span>
                  )}
                </div>
                <span className={cn(
                  'text-[10px] mt-1 font-medium',
                  achieved ? 'text-purple-600' : 'text-muted-foreground/60'
                )}>
                  {milestone}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Estimate to Next Level */}
      <div className="pt-3 border-t border-purple-200 bg-card/50 rounded-lg p-3">
        <div className="flex items-start gap-2">
          <Zap className="w-4 h-4 text-purple-600 mt-0.5" />
          <div className="flex-1">
            <p className="text-xs font-medium text-foreground">Quick Tip</p>
            <p className="text-xs text-muted-foreground mt-1">
              Submit <span className="font-semibold text-purple-600">~{reportsNeeded} more verified reports</span> to reach Level {currentLevel + 1}
            </p>
          </div>
        </div>
      </div>

      {/* Next Milestone */}
      {nextMilestone && (
        <div className="mt-3 pt-3 border-t border-purple-200">
          <p className="text-xs text-muted-foreground">
            Next milestone: <span className="font-semibold text-purple-600">
              {nextMilestone.icon} {nextMilestone.label} (Level {nextMilestone.level})
            </span>
          </p>
        </div>
      )}
    </Card>
  );
}
