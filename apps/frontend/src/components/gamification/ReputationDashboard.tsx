import { useState } from 'react';
import { TrendingUp, ChevronDown, ChevronUp, Info, Award, Target } from 'lucide-react';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { useMyReputation, useMyReputationHistory } from '../../lib/api/hooks';
import { cn } from '../../lib/utils';

interface ReputationDashboardProps {
  className?: string;
}

export function ReputationDashboard({ className }: ReputationDashboardProps) {
  const [showExplainer, setShowExplainer] = useState(false);
  const { data: reputation, isLoading, error } = useMyReputation();
  const { data: history, isLoading: historyLoading } = useMyReputationHistory(5);

  if (isLoading) {
    return (
      <Card className={cn('p-4', className)}>
        <div className="animate-pulse space-y-3">
          <div className="h-6 bg-gray-200 rounded w-40"></div>
          <div className="h-24 bg-gray-200 rounded"></div>
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={cn('p-4 bg-red-50 border-red-200', className)}>
        <p className="text-sm text-red-600">Failed to load reputation data</p>
      </Card>
    );
  }

  // Guard: API may return [] instead of object — [] is truthy, bypasses !data check
  if (!reputation || typeof reputation !== 'object' || Array.isArray(reputation)) {
    return null;
  }

  const reputationScore = reputation.reputation_score || 0;
  const accuracyRate = reputation.accuracy_rate || 0;
  const streakDays = reputation.streak_days || 0;

  // Color coding for reputation score
  const getScoreColor = (score: number): string => {
    if (score >= 70) return 'text-green-600';
    if (score >= 40) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getScoreBgColor = (score: number): string => {
    if (score >= 70) return 'bg-green-50 border-green-200';
    if (score >= 40) return 'bg-yellow-50 border-yellow-200';
    return 'bg-red-50 border-red-200';
  };

  return (
    <Card className={cn('p-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <Award className="w-4 h-4 text-purple-600" />
          Reputation Dashboard
        </h3>
        <button
          onClick={() => setShowExplainer(!showExplainer)}
          className="text-gray-400 hover:text-gray-600 transition-colors"
          aria-label="Show explanation"
        >
          <Info className="w-4 h-4" />
        </button>
      </div>

      {/* Reputation Score */}
      <div className={cn(
        'p-4 rounded-lg border-2 mb-4',
        getScoreBgColor(reputationScore)
      )}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-600 font-medium mb-1">Reputation Score</p>
            <div className="flex items-baseline gap-2">
              <span className={cn('text-4xl font-bold', getScoreColor(reputationScore))}>
                {Math.round(reputationScore)}
              </span>
              <span className="text-lg text-gray-500">/100</span>
            </div>
          </div>
          <TrendingUp className={cn('w-10 h-10', getScoreColor(reputationScore))} />
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
          <div className="flex items-center gap-2 mb-1">
            <Target className="w-4 h-4 text-blue-600" />
            <p className="text-xs text-gray-600 font-medium">Accuracy</p>
          </div>
          <p className="text-2xl font-bold text-blue-600">
            {Math.round(accuracyRate * 100)}%
          </p>
        </div>

        <div className="p-3 bg-orange-50 rounded-lg border border-orange-100">
          <div className="flex items-center gap-2 mb-1">
            <Award className="w-4 h-4 text-orange-600" />
            <p className="text-xs text-gray-600 font-medium">Streak</p>
          </div>
          <p className="text-2xl font-bold text-orange-600">
            {streakDays} {streakDays === 1 ? 'day' : 'days'}
          </p>
        </div>
      </div>

      {/* Recent Activity */}
      <div>
        <p className="text-xs font-semibold text-gray-700 mb-2">Recent Activity</p>
        {historyLoading ? (
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-100 rounded animate-pulse"></div>
            ))}
          </div>
        ) : history && history.length > 0 ? (
          <div className="space-y-2">
            {history.map((entry, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-2 bg-gray-50 rounded-lg"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">
                    {entry.action}
                  </p>
                  {entry.reason && (
                    <p className="text-xs text-gray-500 truncate">{entry.reason}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant="secondary"
                    className={cn(
                      'text-xs',
                      entry.points_change > 0
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    )}
                  >
                    {entry.points_change > 0 ? '+' : ''}{entry.points_change}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-4 text-gray-500">
            <p className="text-xs">No recent activity</p>
          </div>
        )}
      </div>

      {/* Explainer */}
      {showExplainer && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <button
            onClick={() => setShowExplainer(false)}
            className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2 hover:text-gray-900"
          >
            <ChevronUp className="w-4 h-4" />
            How is reputation calculated?
          </button>
          <div className="text-xs text-gray-600 space-y-2 bg-blue-50 p-3 rounded-lg border border-blue-100">
            <p>
              <strong>Reputation Score (0-100):</strong> Based on verified reports, accuracy, and community trust.
            </p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>Submit verified reports: +10 points</li>
              <li>Report upvoted by community: +5 points</li>
              <li>Report downvoted: -3 points</li>
              <li>Maintain daily streak: Bonus multiplier</li>
            </ul>
            <p className="pt-2">
              <strong>Accuracy Rate:</strong> Percentage of your reports that were verified.
            </p>
            <p>
              <strong>Streak:</strong> Consecutive days with at least one verified report.
            </p>
          </div>
        </div>
      )}

      {!showExplainer && (
        <button
          onClick={() => setShowExplainer(true)}
          className="mt-3 flex items-center gap-2 text-xs text-gray-500 hover:text-gray-700 transition-colors mx-auto"
        >
          <ChevronDown className="w-3 h-3" />
          How is this calculated?
        </button>
      )}
    </Card>
  );
}
