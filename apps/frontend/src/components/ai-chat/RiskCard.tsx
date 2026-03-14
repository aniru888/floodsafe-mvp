/**
 * RiskCard — Inline FHI risk summary shown inside the chat window.
 *
 * Displays a colored risk badge, a visual gauge bar for the FHI score,
 * and the historical episode count when available.
 */

import { cn } from '../../lib/utils';

interface RiskCardProps {
  fhiScore: number;
  fhiLevel: string;
  episodeCount?: number;
}

interface LevelStyle {
  badge: string;
  bar: string;
  label: string;
}

const LEVEL_STYLES: Record<string, LevelStyle> = {
  low:      { badge: 'bg-green-100 text-green-700',   bar: 'bg-green-500',  label: 'Low' },
  moderate: { badge: 'bg-yellow-100 text-yellow-700', bar: 'bg-yellow-500', label: 'Moderate' },
  high:     { badge: 'bg-orange-100 text-orange-700', bar: 'bg-orange-500', label: 'High' },
  extreme:  { badge: 'bg-red-100 text-red-700',       bar: 'bg-red-500',    label: 'Extreme' },
};

const DEFAULT_STYLE: LevelStyle = LEVEL_STYLES['low'];

function getLevelStyle(level: string): LevelStyle {
  return LEVEL_STYLES[level.toLowerCase()] ?? DEFAULT_STYLE;
}

export function RiskCard({ fhiScore, fhiLevel, episodeCount }: RiskCardProps) {
  const style = getLevelStyle(fhiLevel);
  // FHI score is 0-1; convert to percentage for the bar
  const pct = Math.min(100, Math.max(0, Math.round(fhiScore * 100)));

  return (
    <div className="mt-2 rounded-xl border bg-card p-3 space-y-2">
      {/* Header row: label + badge */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Flood Hazard Index
        </span>
        <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium', style.badge)}>
          {style.label}
        </span>
      </div>

      {/* Score + gauge bar */}
      <div className="space-y-1">
        <div className="flex items-baseline justify-between">
          <span className="text-2xl font-bold text-foreground">{fhiScore.toFixed(2)}</span>
          <span className="text-xs text-muted-foreground">/1.00</span>
        </div>
        <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all duration-500', style.bar)}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Historical episodes */}
      {episodeCount !== undefined && (
        <p className="text-xs text-muted-foreground">
          {episodeCount} historical flood{episodeCount !== 1 ? 's' : ''} recorded in this area
        </p>
      )}
    </div>
  );
}
