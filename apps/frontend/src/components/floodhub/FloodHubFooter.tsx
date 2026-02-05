/**
 * FloodHub Footer - Attribution and external links
 */

import { ExternalLink } from 'lucide-react';

export function FloodHubFooter() {
    return (
        <div className="mt-6 pt-4 border-t border-gray-200">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-500">
                <div className="flex items-center gap-1">
                    <span>Powered by</span>
                    <a
                        href="https://sites.research.google/floods/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 font-medium inline-flex items-center gap-0.5"
                    >
                        Google FloodHub
                        <ExternalLink className="w-3 h-3" />
                    </a>
                </div>
                <div className="text-gray-400">
                    Data licensed under{' '}
                    <a
                        href="https://creativecommons.org/licenses/by/4.0/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-gray-600"
                    >
                        CC BY 4.0
                    </a>
                </div>
            </div>
        </div>
    );
}
