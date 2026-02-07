/**
 * FloodHub Footer - Attribution and external links
 */

import { ExternalLink } from 'lucide-react';

export function FloodHubFooter() {
    return (
        <div className="mt-6 pt-4 border-t border-border">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                    <span>Powered by</span>
                    <a
                        href="https://sites.research.google/floods/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:text-primary/80 font-medium inline-flex items-center gap-0.5"
                    >
                        Google FloodHub
                        <ExternalLink className="w-3 h-3" />
                    </a>
                </div>
                <div className="text-muted-foreground/60">
                    Data licensed under{' '}
                    <a
                        href="https://creativecommons.org/licenses/by/4.0/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-muted-foreground"
                    >
                        CC BY 4.0
                    </a>
                </div>
            </div>
        </div>
    );
}
