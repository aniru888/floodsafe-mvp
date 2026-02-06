import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for UI overhaul visual regression testing.
 *
 * Two viewport sizes:
 * - Mobile (375x812): iPhone-size, tests BottomNav + TopNav layout
 * - Desktop (1280x800): Tests Sidebar layout
 *
 * Usage:
 *   npx playwright test                    # Run all tests
 *   npx tsx scripts/ui-overhaul-visual-test.ts  # Baseline screenshots
 */
export default defineConfig({
    testDir: './scripts',
    timeout: 60_000,
    expect: {
        timeout: 10_000,
    },
    fullyParallel: false,
    retries: 0,
    reporter: 'list',
    use: {
        baseURL: 'http://localhost:5175',
        trace: 'on-first-retry',
        screenshot: 'on',
    },
    projects: [
        {
            name: 'mobile',
            use: {
                ...devices['iPhone 13'],
                viewport: { width: 375, height: 812 },
            },
        },
        {
            name: 'desktop',
            use: {
                viewport: { width: 1280, height: 800 },
            },
        },
    ],
});
