import { useState } from 'react';
import { Award, Lock, Search } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Badge as BadgeUI } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { useBadgesCatalog, useMyBadges } from '../../lib/api/hooks';
import { cn } from '../../lib/utils';

interface BadgeCatalogModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function BadgeCatalogModal({ open, onOpenChange }: BadgeCatalogModalProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: catalogBadges, isLoading: catalogLoading, error: catalogError } = useBadgesCatalog();
  const { data: myBadgesData, isLoading: myBadgesLoading } = useMyBadges();

  // Get earned badge keys for comparison
  const earnedBadgeKeys = new Set(
    myBadgesData?.earned?.map(eb => eb.badge.key) || []
  );

  // Get progress map for in-progress badges
  const progressMap = new Map(
    myBadgesData?.in_progress?.map(bp => [bp.badge.key, bp]) || []
  );

  // Filter and group badges
  const categories = ['all', 'reporting', 'verification', 'community', 'streak', 'special'];

  const filteredBadges = (catalogBadges || []).filter(badge => {
    const matchesCategory = selectedCategory === 'all' || badge.category === selectedCategory;
    const matchesSearch = !searchQuery ||
      badge.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      badge.description?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  // Group badges by category
  const groupedBadges = categories.reduce((acc, cat) => {
    if (cat === 'all') return acc;
    acc[cat] = filteredBadges.filter(b => b.category === cat);
    return acc;
  }, {} as Record<string, typeof filteredBadges>);

  // Category colors
  const categoryColors: Record<string, { bg: string; text: string; border: string }> = {
    reporting: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
    verification: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
    community: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
    streak: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
    special: { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200' },
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] p-0">
        <DialogHeader className="p-6 pb-4">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Award className="w-6 h-6 text-purple-600" />
            Badge Catalog
          </DialogTitle>
        </DialogHeader>

        {/* Search and Filter */}
        <div className="px-6 pb-4 space-y-3">
          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
            <input
              type="text"
              placeholder="Search badges..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm"
            />
          </div>

          {/* Category Filter Pills */}
          <div className="flex gap-2 flex-wrap">
            {categories.map(cat => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                  selectedCategory === cat
                    ? 'bg-purple-500 text-white shadow-sm'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                )}
              >
                {cat.charAt(0).toUpperCase() + cat.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Loading State */}
        {(catalogLoading || myBadgesLoading) && (
          <div className="px-6 pb-6">
            <div className="animate-pulse space-y-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-20 bg-muted rounded-lg"></div>
              ))}
            </div>
          </div>
        )}

        {/* Error State */}
        {catalogError && (
          <div className="px-6 pb-6">
            <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
              <p className="text-sm text-destructive">Failed to load badges. Please try again.</p>
            </div>
          </div>
        )}

        {/* Badge List */}
        {!catalogLoading && !myBadgesLoading && !catalogError && (
          <ScrollArea className="h-[500px] px-6 pb-6">
            <div className="space-y-6">
              {selectedCategory === 'all' ? (
                // Show grouped by category
                Object.entries(groupedBadges).map(([category, badges]) => (
                  badges.length > 0 && (
                    <div key={category}>
                      <h3 className="text-sm font-semibold text-foreground mb-3 capitalize flex items-center gap-2">
                        {category}
                        <BadgeUI variant="secondary" className="text-xs bg-muted text-muted-foreground">
                          {badges.filter(b => earnedBadgeKeys.has(b.key)).length}/{badges.length}
                        </BadgeUI>
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {badges.map(badge => {
                          const isEarned = earnedBadgeKeys.has(badge.key);
                          const progress = progressMap.get(badge.key);
                          const colors = categoryColors[badge.category];

                          return (
                            <div
                              key={badge.key}
                              className={cn(
                                'p-4 rounded-xl border-2 transition-all',
                                isEarned
                                  ? `${colors.bg} ${colors.border} shadow-sm`
                                  : 'bg-muted border-border opacity-75'
                              )}
                            >
                              <div className="flex gap-3">
                                {/* Badge Icon */}
                                <div className={cn(
                                  'w-12 h-12 rounded-full flex items-center justify-center text-2xl flex-shrink-0',
                                  isEarned ? 'bg-card shadow-sm' : 'bg-muted grayscale'
                                )}>
                                  {badge.icon || '🏅'}
                                  {!isEarned && (
                                    <div className="absolute">
                                      <Lock className="w-4 h-4 text-muted-foreground" />
                                    </div>
                                  )}
                                </div>

                                {/* Badge Info */}
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-start justify-between gap-2 mb-1">
                                    <h4 className={cn(
                                      'font-semibold text-sm',
                                      isEarned ? 'text-foreground' : 'text-muted-foreground'
                                    )}>
                                      {badge.name}
                                    </h4>
                                    {badge.points_reward > 0 && (
                                      <BadgeUI
                                        variant="secondary"
                                        className="text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 flex-shrink-0"
                                      >
                                        +{badge.points_reward}
                                      </BadgeUI>
                                    )}
                                  </div>

                                  <p className={cn(
                                    'text-xs mb-2',
                                    isEarned ? 'text-muted-foreground' : 'text-muted-foreground'
                                  )}>
                                    {badge.description || 'No description available'}
                                  </p>

                                  {/* Progress Bar for In-Progress Badges */}
                                  {!isEarned && progress && (
                                    <div className="space-y-1">
                                      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                                        <div
                                          className="h-full bg-purple-500 transition-all duration-300"
                                          style={{ width: `${progress.progress_percent}%` }}
                                        />
                                      </div>
                                      <p className="text-[10px] text-muted-foreground">
                                        {progress.current_value}/{progress.required_value} - {Math.round(progress.progress_percent)}%
                                      </p>
                                    </div>
                                  )}

                                  {/* Status */}
                                  {isEarned && (
                                    <BadgeUI variant="secondary" className={cn(
                                      'text-xs px-2 py-0.5 w-fit',
                                      `${colors.bg} ${colors.text}`
                                    )}>
                                      Earned
                                    </BadgeUI>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )
                ))
              ) : (
                // Show single category
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {filteredBadges.map(badge => {
                    const isEarned = earnedBadgeKeys.has(badge.key);
                    const progress = progressMap.get(badge.key);
                    const colors = categoryColors[badge.category];

                    return (
                      <div
                        key={badge.key}
                        className={cn(
                          'p-4 rounded-xl border-2 transition-all',
                          isEarned
                            ? `${colors.bg} ${colors.border} shadow-sm`
                            : 'bg-muted border-border opacity-75'
                        )}
                      >
                        <div className="flex gap-3">
                          <div className={cn(
                            'w-12 h-12 rounded-full flex items-center justify-center text-2xl flex-shrink-0',
                            isEarned ? 'bg-card shadow-sm' : 'bg-muted grayscale'
                          )}>
                            {badge.icon || '🏅'}
                            {!isEarned && (
                              <div className="absolute">
                                <Lock className="w-4 h-4 text-muted-foreground" />
                              </div>
                            )}
                          </div>

                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-2 mb-1">
                              <h4 className={cn(
                                'font-semibold text-sm',
                                isEarned ? 'text-foreground' : 'text-muted-foreground'
                              )}>
                                {badge.name}
                              </h4>
                              {badge.points_reward > 0 && (
                                <BadgeUI
                                  variant="secondary"
                                  className="text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 flex-shrink-0"
                                >
                                  +{badge.points_reward}
                                </BadgeUI>
                              )}
                            </div>

                            <p className={cn(
                              'text-xs mb-2',
                              isEarned ? 'text-muted-foreground' : 'text-muted-foreground'
                            )}>
                              {badge.description || 'No description available'}
                            </p>

                            {!isEarned && progress && (
                              <div className="space-y-1">
                                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-purple-500 transition-all duration-300"
                                    style={{ width: `${progress.progress_percent}%` }}
                                  />
                                </div>
                                <p className="text-[10px] text-muted-foreground">
                                  {progress.current_value}/{progress.required_value} - {Math.round(progress.progress_percent)}%
                                </p>
                              </div>
                            )}

                            {isEarned && (
                              <BadgeUI variant="secondary" className={cn(
                                'text-xs px-2 py-0.5 w-fit',
                                `${colors.bg} ${colors.text}`
                              )}>
                                Earned
                              </BadgeUI>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* No Results */}
              {filteredBadges.length === 0 && (
                <div className="text-center py-12">
                  <Award className="w-16 h-16 mx-auto text-muted-foreground/40 mb-3" />
                  <p className="text-sm text-muted-foreground font-medium">No badges found</p>
                  <p className="text-xs text-muted-foreground mt-1">Try adjusting your search or filters</p>
                </div>
              )}
            </div>
          </ScrollArea>
        )}

        {/* Summary Footer */}
        {!catalogLoading && !myBadgesLoading && !catalogError && (
          <div className="px-6 py-4 border-t border-border bg-muted">
            <div className="flex items-center justify-between text-sm">
              <p className="text-muted-foreground">
                You've earned <span className="font-semibold text-purple-600">{earnedBadgeKeys.size}</span> of <span className="font-semibold">{catalogBadges?.length || 0}</span> badges
              </p>
              <BadgeUI variant="secondary" className="bg-purple-100 text-purple-700">
                {Math.round((earnedBadgeKeys.size / (catalogBadges?.length || 1)) * 100)}% Complete
              </BadgeUI>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
