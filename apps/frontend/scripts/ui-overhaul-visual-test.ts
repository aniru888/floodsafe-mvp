/**
 * UI Overhaul — Comprehensive Baseline Screenshot Capture (v2)
 *
 * Captures EVERY screen, modal, panel, button state, and scroll position
 * at both mobile (375px) and desktop (1280px) viewports.
 *
 * KEY DESIGN: Each screen capture starts with a fresh page reload to prevent
 * cascading failures. Modal captures are isolated in try/catch blocks.
 *
 * Usage:
 *   npx tsx scripts/ui-overhaul-visual-test.ts [--viewport mobile|desktop|both]
 *
 * Requires:
 *   - App running on localhost:5175 (with VITE_API_URL pointing to prod backend)
 *   - Pre-onboarded test account (created automatically if needed)
 *
 * Output: screenshots/baseline/<viewport>/<NNN>-<category>-<name>.png
 */

import { chromium, Page, Browser, BrowserContext } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

// ESM-compatible __dirname
const __filename_esm = fileURLToPath(import.meta.url);
const __dirname_esm = path.dirname(__filename_esm);

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const APP_URL = 'http://localhost:5175';
const PROD_API = 'https://floodsafe-backend-floodsafe-dda84554.koyeb.app';

// Parse CLI args
const args = process.argv.slice(2);
const vpArg = args.find(a => a.startsWith('--viewport='))?.split('=')[1] || 'both';

const VIEWPORTS = {
    mobile: { width: 375, height: 812 },
    desktop: { width: 1280, height: 800 },
};

// Test account credentials
const TEST_EMAIL = 'ui_test_1770416767@floodsafe.test';
const TEST_PASSWORD = 'TestPassword123!';

// Directories
const BASE_DIR = path.resolve(__dirname_esm, '..', 'screenshots', 'baseline');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let stepCounter = 0;

function ensureDir(dir: string) {
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

async function ss(page: Page, vpName: string, category: string, name: string, opts?: { fullPage?: boolean }) {
    stepCounter++;
    const dir = path.join(BASE_DIR, vpName);
    ensureDir(dir);
    const filename = `${String(stepCounter).padStart(3, '0')}-${category}-${name}.png`;
    const filePath = path.join(dir, filename);
    await page.screenshot({ path: filePath, fullPage: opts?.fullPage ?? false });
    console.log(`  [${vpName}] ${filename}`);
}

async function wait(page: Page, ms = 500) {
    await page.waitForTimeout(ms);
}

async function clickIfVisible(page: Page, selector: string, timeout = 2000): Promise<boolean> {
    try {
        const el = page.locator(selector).first();
        if (await el.isVisible({ timeout }).catch(() => false)) {
            await el.click({ timeout: 3000 });
            return true;
        }
    } catch {
        // Click failed — element might have moved or be covered
    }
    return false;
}

async function scrollTo(page: Page, y: number) {
    await page.evaluate((scrollY) => window.scrollTo({ top: scrollY, behavior: 'instant' }), y);
    await wait(page, 300);
}

async function scrollToBottom(page: Page) {
    await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'instant' }));
    await wait(page, 300);
}

async function scrollToTop(page: Page) {
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await wait(page, 300);
}

/** Close any open dialog/modal by pressing Escape or clicking close button */
async function closeAnyModal(page: Page) {
    try {
        const dialog = page.locator('[role="dialog"]').first();
        if (await dialog.isVisible({ timeout: 500 }).catch(() => false)) {
            // Try close button first
            const closed = await clickIfVisible(page, '[role="dialog"] button[aria-label="Close"]', 500);
            if (!closed) {
                // Try X button (svg icon)
                await clickIfVisible(page, '[role="dialog"] button:has(svg.lucide-x)', 500);
            }
            if (!closed) {
                // Escape key as last resort
                await page.keyboard.press('Escape');
            }
            await wait(page, 300);
        }
    } catch {
        // Ignore — no modal to close
    }
}

// ---------------------------------------------------------------------------
// Auth — Get tokens from production API, inject into localStorage
// ---------------------------------------------------------------------------

let cachedTokens: { access_token: string; refresh_token: string } | null = null;

async function getTokens(): Promise<{ access_token: string; refresh_token: string } | null> {
    if (cachedTokens) return cachedTokens;

    console.log(`  Logging in via API: ${TEST_EMAIL}...`);
    try {
        const resp = await fetch(`${PROD_API}/api/auth/login/email`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD }),
            signal: AbortSignal.timeout(10000),
        });
        if (resp.ok) {
            cachedTokens = await resp.json() as typeof cachedTokens;
            console.log('  Got tokens from production API!');
            return cachedTokens;
        }
        console.log(`  API login returned ${resp.status}: ${await resp.text().catch(() => '')}`);
    } catch (e) {
        console.log(`  API login failed: ${(e as Error).message?.slice(0, 80)}`);
    }

    // Try creating account if login failed
    try {
        console.log('  Creating test account...');
        const regResp = await fetch(`${PROD_API}/api/auth/register/email`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: TEST_EMAIL,
                password: TEST_PASSWORD,
                username: 'UITest1770416767',
                city: 'delhi',
                profile_complete: true,
            }),
            signal: AbortSignal.timeout(10000),
        });
        if (regResp.ok) {
            cachedTokens = await regResp.json() as typeof cachedTokens;
            console.log('  Account created and tokens received!');
            return cachedTokens;
        }
    } catch {
        // Account might already exist
    }

    return null;
}

/** Navigate to app and inject auth tokens. Returns true if authenticated. */
async function loadAppAuthenticated(page: Page): Promise<boolean> {
    const tokens = await getTokens();

    await page.goto(APP_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await wait(page, 1000);

    if (tokens) {
        await page.evaluate((t) => {
            localStorage.setItem('floodsafe_access_token', t.access_token);
            localStorage.setItem('floodsafe_refresh_token', t.refresh_token);
            // Set city to Delhi — where hotspots, metro, and real flood data live
            localStorage.setItem('floodsafe_selected_city', 'delhi');
        }, tokens);
        await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
        await wait(page, 3000);
    }

    // Verify: check if bottom nav OR sidebar is visible (means we're past login + onboarding)
    // On mobile: BottomNav visible, Sidebar hidden
    // On desktop: Sidebar visible, BottomNav hidden
    const bottomNav = page.locator('[data-bottom-nav]');
    const sidebar = page.locator('[data-sidebar]');
    const bottomNavVisible = await bottomNav.isVisible({ timeout: 5000 }).catch(() => false);
    const sidebarVisible = await sidebar.isVisible({ timeout: 2000 }).catch(() => false);

    if (bottomNavVisible || sidebarVisible) {
        console.log('  Authenticated and on main app!');
        return true;
    }

    // Check if we're on login screen
    const onLogin = await page.locator('#email').isVisible({ timeout: 2000 }).catch(() => false);
    if (onLogin) {
        console.log('  Still on login screen — tokens may be invalid');
        return false;
    }

    // Might be on onboarding
    const onOnboarding = await page.locator('text="Select Your City"').isVisible({ timeout: 2000 }).catch(() => false);
    if (onOnboarding) {
        console.log('  On onboarding screen — account not fully set up');
        return false;
    }

    // Wait a bit more and check again
    await wait(page, 3000);
    return await bottomNav.isVisible({ timeout: 3000 }).catch(() => false);
}

// ---------------------------------------------------------------------------
// Core Navigation — ROBUST tab switching with verification
// ---------------------------------------------------------------------------

/**
 * Navigate to a tab and verify it loaded. If tab navigation fails,
 * reloads the page and tries once more.
 */
async function goToTab(page: Page, tabLabel: string, verifySelector?: string): Promise<boolean> {
    // First, close any open modals that might block the bottom nav
    await closeAnyModal(page);
    await scrollToTop(page);
    await wait(page, 200);

    // Click the bottom nav button (mobile) or sidebar button (desktop)
    const bottomNavBtn = page.locator(`[data-bottom-nav] button:has-text("${tabLabel}")`).first();
    const sidebarBtn = page.locator(`[data-sidebar] button:has-text("${tabLabel}")`).first();
    const bottomBtnVisible = await bottomNavBtn.isVisible({ timeout: 3000 }).catch(() => false);
    const sidebarBtnVisible = await sidebarBtn.isVisible({ timeout: 1000 }).catch(() => false);

    if (bottomBtnVisible) {
        await bottomNavBtn.click();
    } else if (sidebarBtnVisible) {
        await sidebarBtn.click();
    } else {
        console.log(`  [WARN] Nav "${tabLabel}" button not visible — reloading page...`);
        await loadAppAuthenticated(page);
        await wait(page, 1000);
        // Try both again after reload
        const retryBottom = page.locator(`[data-bottom-nav] button:has-text("${tabLabel}")`).first();
        const retrySidebar = page.locator(`[data-sidebar] button:has-text("${tabLabel}")`).first();
        if (await retryBottom.isVisible({ timeout: 3000 }).catch(() => false)) {
            await retryBottom.click();
        } else if (await retrySidebar.isVisible({ timeout: 3000 }).catch(() => false)) {
            await retrySidebar.click();
        } else {
            console.log(`  [ERROR] Nav "${tabLabel}" still not visible after reload!`);
            return false;
        }
    }

    await wait(page, 2000);

    // Verify screen loaded using the provided selector
    if (verifySelector) {
        const verified = await page.locator(verifySelector).first().isVisible({ timeout: 5000 }).catch(() => false);
        if (!verified) {
            console.log(`  [WARN] Screen verification failed for "${tabLabel}" (selector: ${verifySelector})`);
            // Try one more time with reload
            await loadAppAuthenticated(page);
            const retryBottom2 = page.locator(`[data-bottom-nav] button:has-text("${tabLabel}")`).first();
            const retrySidebar2 = page.locator(`[data-sidebar] button:has-text("${tabLabel}")`).first();
            if (await retryBottom2.isVisible({ timeout: 3000 }).catch(() => false)) {
                await retryBottom2.click();
                await wait(page, 3000);
            } else if (await retrySidebar2.isVisible({ timeout: 3000 }).catch(() => false)) {
                await retrySidebar2.click();
                await wait(page, 3000);
            }
            return await page.locator(verifySelector).first().isVisible({ timeout: 5000 }).catch(() => false);
        }
    }

    return true;
}

// ---------------------------------------------------------------------------
// Screen Capture Functions — Each starts fresh!
// ---------------------------------------------------------------------------

async function captureLoginScreen(page: Page, vp: string) {
    console.log('\n--- LoginScreen ---');

    // Clear auth to see login screen
    await page.evaluate(() => {
        localStorage.removeItem('floodsafe_access_token');
        localStorage.removeItem('floodsafe_refresh_token');
    });
    await page.goto(APP_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await wait(page, 2000);

    const loginVisible = await page.locator('#email').isVisible({ timeout: 5000 }).catch(() => false);
    if (!loginVisible) {
        console.log('  Login screen not showing — skip');
        return;
    }

    // Default: Email Sign In
    await ss(page, vp, 'login', 'email-signin');
    await ss(page, vp, 'login', 'full-page', { fullPage: true });

    // Toggle to Sign Up
    if (await clickIfVisible(page, '.inline-flex button:has-text("Sign Up")')) {
        await wait(page, 500);
        await ss(page, vp, 'login', 'email-signup');
    }

    // Google auth tab
    if (await clickIfVisible(page, 'button:has-text("Google")')) {
        await wait(page, 500);
        await ss(page, vp, 'login', 'google-tab');
    }

    // Phone auth tab
    if (await clickIfVisible(page, 'button:has-text("Phone")')) {
        await wait(page, 500);
        await ss(page, vp, 'login', 'phone-tab');
    }

    // Restore auth for subsequent captures
    await loadAppAuthenticated(page);
}

async function captureHomeScreen(page: Page, vp: string) {
    console.log('\n--- HomeScreen ---');

    // Fresh page load — Home is the default tab
    await loadAppAuthenticated(page);
    await wait(page, 1000);

    // Verify we're on Home
    const onHome = await page.locator('text="YOUR AREA"').isVisible({ timeout: 5000 }).catch(() => false);
    if (!onHome) {
        console.log('  [WARN] Home screen content not detected!');
        await goToTab(page, 'Home');
        await wait(page, 2000);
    }

    // --- Basic captures (safe — no interactions that could break state) ---

    await scrollToTop(page);
    await ss(page, vp, 'home', 'top');

    await ss(page, vp, 'home', 'full-page', { fullPage: true });

    // Scroll through sections
    await scrollTo(page, 400);
    await ss(page, vp, 'home', 'stats-quickactions');

    await scrollTo(page, 700);
    await ss(page, vp, 'home', 'map-preview');

    await scrollTo(page, 1100);
    await ss(page, vp, 'home', 'recent-updates');

    await scrollToBottom(page);
    await ss(page, vp, 'home', 'bottom-ambassadors');
}

async function captureHomeModals(page: Page, vp: string) {
    console.log('\n--- HomeScreen Modals ---');

    // Fresh start for modal captures
    await loadAppAuthenticated(page);
    await wait(page, 2000);

    // SOS → Emergency Contacts Modal
    try {
        await scrollToTop(page);
        await wait(page, 500);

        // Scroll to quick actions to make SOS visible
        await scrollTo(page, 500);
        await wait(page, 300);

        const sosBtn = page.locator('button:has-text("SOS")').first();
        if (await sosBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
            await sosBtn.click();
            await wait(page, 1000);

            // Check if modal opened
            const modalOpen = await page.locator('[role="dialog"]').first().isVisible({ timeout: 3000 }).catch(() => false);
            if (modalOpen) {
                await ss(page, vp, 'home', 'emergency-modal-top');

                // Scroll within modal
                const modalScroll = page.locator('[role="dialog"] [class*="overflow"], [role="dialog"] .overflow-y-auto').first();
                if (await modalScroll.isVisible({ timeout: 1000 }).catch(() => false)) {
                    await modalScroll.evaluate(el => el.scrollTop = 300);
                    await wait(page, 300);
                    await ss(page, vp, 'home', 'emergency-modal-middle');

                    await modalScroll.evaluate(el => el.scrollTop = 9999);
                    await wait(page, 300);
                    await ss(page, vp, 'home', 'emergency-modal-bottom');
                }

                await closeAnyModal(page);
            } else {
                console.log('  [WARN] Emergency modal did not open after SOS click');
                await ss(page, vp, 'home', 'sos-click-result');
            }
        }
    } catch (err) {
        console.log(`  [ERROR] SOS modal capture failed: ${(err as Error).message?.slice(0, 80)}`);
        // Recovery: reload to get clean state
        await loadAppAuthenticated(page);
    }
}

async function captureFloodAtlas(page: Page, vp: string) {
    console.log('\n--- FloodAtlasScreen ---');

    // Fresh start
    await loadAppAuthenticated(page);

    // Navigate to Flood Atlas
    const ok = await goToTab(page, 'Flood Atlas');
    if (!ok) {
        console.log('  [ERROR] Could not navigate to Flood Atlas — skipping');
        return;
    }

    // Wait extra for map tiles
    await wait(page, 4000);

    // Default map view
    await ss(page, vp, 'atlas', 'default');
    await ss(page, vp, 'atlas', 'full-page', { fullPage: true });

    // --- Search bar ---
    try {
        const searchInput = page.locator('input[placeholder*="Search"]').first();
        if (await searchInput.isVisible({ timeout: 2000 }).catch(() => false)) {
            await searchInput.click();
            await wait(page, 500);
            await ss(page, vp, 'atlas', 'search-focused');

            await searchInput.fill('Connaught Place');
            await wait(page, 2000);
            await ss(page, vp, 'atlas', 'search-results');

            // Clear search
            await searchInput.clear();
            await page.keyboard.press('Escape');
            await wait(page, 500);
        }
    } catch (err) {
        console.log(`  [WARN] Search capture failed: ${(err as Error).message?.slice(0, 60)}`);
    }

    // --- Map Legend ---
    try {
        if (await clickIfVisible(page, 'button:has-text("Map Legend"), button:has-text("Legend")')) {
            await wait(page, 500);
            await ss(page, vp, 'atlas', 'legend-expanded');
            // Close legend
            await clickIfVisible(page, 'button:has-text("Map Legend"), button:has-text("Legend")');
            await wait(page, 300);
        }
    } catch {
        console.log('  [WARN] Legend capture failed');
    }

    // --- Plan Safe Route → Navigation Panel ---
    try {
        if (await clickIfVisible(page, 'button:has-text("Plan Safe Route"), button:has-text("Plan Route")')) {
            await wait(page, 1000);
            await ss(page, vp, 'atlas', 'nav-panel-open');
            await ss(page, vp, 'atlas', 'nav-panel-full', { fullPage: true });

            // Close panel
            await clickIfVisible(page, 'button[aria-label="Close"], button:has-text("Close"), button:has-text("Back")');
            await wait(page, 500);
        }
    } catch {
        console.log('  [WARN] Navigation panel capture failed');
    }
}

async function captureReportScreen(page: Page, vp: string) {
    console.log('\n--- ReportScreen ---');

    // Fresh start
    await loadAppAuthenticated(page);

    // Navigate to Report
    const ok = await goToTab(page, 'Report');
    if (!ok) {
        console.log('  [ERROR] Could not navigate to Report — skipping');
        return;
    }

    // Wait for report screen to render
    await wait(page, 2000);

    // Step 1: Location & Description
    await scrollToTop(page);
    await ss(page, vp, 'report', 'step1-top');
    await ss(page, vp, 'report', 'step1-full', { fullPage: true });

    // Scroll to description area
    await scrollTo(page, 400);
    await ss(page, vp, 'report', 'step1-description');

    // Scroll to tags
    await scrollTo(page, 700);
    await ss(page, vp, 'report', 'step1-tags');

    // Try to advance through wizard steps
    try {
        // Fill minimum fields for Step 1
        const descInput = page.locator('textarea').first();
        if (await descInput.isVisible({ timeout: 2000 }).catch(() => false)) {
            await descInput.fill('Testing visual baseline capture');
        }

        // Click "Current Location" button to set location
        await clickIfVisible(page, 'button:has-text("Current Location"), button:has-text("Use Current")');
        await wait(page, 1000);

        // Click Continue → Step 2
        if (await clickIfVisible(page, 'button:has-text("Continue")')) {
            await wait(page, 1500);
            await scrollToTop(page);
            await ss(page, vp, 'report', 'step2-details');
            await ss(page, vp, 'report', 'step2-full', { fullPage: true });

            // Click Continue → Step 3
            if (await clickIfVisible(page, 'button:has-text("Continue")')) {
                await wait(page, 1500);
                await scrollToTop(page);
                await ss(page, vp, 'report', 'step3-photo');

                // Click Continue/Skip → Step 4
                const advancedTo4 = await clickIfVisible(page, 'button:has-text("Continue"), button:has-text("Skip"), button:has-text("Review")');
                if (advancedTo4) {
                    await wait(page, 1500);
                    await scrollToTop(page);
                    await ss(page, vp, 'report', 'step4-confirm');
                    await ss(page, vp, 'report', 'step4-full', { fullPage: true });
                }
            }
        }
    } catch (err) {
        console.log(`  [WARN] Report wizard steps failed: ${(err as Error).message?.slice(0, 80)}`);
    }
}

async function captureAlertsScreen(page: Page, vp: string) {
    console.log('\n--- AlertsScreen ---');

    // Fresh start
    await loadAppAuthenticated(page);

    // Navigate to Alerts
    const ok = await goToTab(page, 'Alerts');
    if (!ok) {
        console.log('  [ERROR] Could not navigate to Alerts — skipping');
        return;
    }

    await wait(page, 2000);

    // Default view — All tab
    await scrollToTop(page);
    await ss(page, vp, 'alerts', 'all-tab-top');
    await ss(page, vp, 'alerts', 'all-tab-full', { fullPage: true });

    // Scroll through alerts
    await scrollTo(page, 400);
    await ss(page, vp, 'alerts', 'all-tab-scrolled');

    // --- Filter tabs ---
    // MUST scroll to top first — tabs are in the header area
    await scrollToTop(page);
    await wait(page, 500);

    const filterTabs = ['Official', 'News', 'Social', 'Community', 'FloodHub', 'Circles'];

    for (const tab of filterTabs) {
        try {
            await scrollToTop(page);
            // Filter tabs are Badge components (div, not button) with cursor-pointer class
            const tabBtn = page.locator(`.cursor-pointer:has-text("${tab}"), button:has-text("${tab}"), [role="tab"]:has-text("${tab}")`).first();
            const found = await tabBtn.isVisible({ timeout: 2000 }).catch(() => false);
            if (found) {
                await tabBtn.click();
                await wait(page, 2000);
                await scrollToTop(page);
                await ss(page, vp, 'alerts', `${tab.toLowerCase()}-tab`);

                // Full page for tabs with more content
                if (['News', 'Community', 'FloodHub', 'Circles'].includes(tab)) {
                    await ss(page, vp, 'alerts', `${tab.toLowerCase()}-tab-full`, { fullPage: true });
                }
            } else {
                console.log(`  [WARN] Filter tab "${tab}" not found/visible`);
            }
        } catch (err) {
            console.log(`  [WARN] ${tab} tab capture failed: ${(err as Error).message?.slice(0, 60)}`);
        }
    }

    // --- FloodHub deep captures ---
    try {
        if (await clickIfVisible(page, '.cursor-pointer:has-text("FloodHub"), button:has-text("FloodHub")')) {
            await wait(page, 2000);
            await scrollToTop(page);
            await ss(page, vp, 'alerts', 'floodhub-header');

            await scrollTo(page, 400);
            await ss(page, vp, 'alerts', 'floodhub-chart');

            await scrollToBottom(page);
            await ss(page, vp, 'alerts', 'floodhub-footer');
        }
    } catch {
        console.log('  [WARN] FloodHub deep capture failed');
    }

    // --- Circles tab modals ---
    try {
        if (await clickIfVisible(page, '.cursor-pointer:has-text("Circles"), button:has-text("Circles")')) {
            await wait(page, 1500);
            await scrollToTop(page);
            await ss(page, vp, 'alerts', 'circles-grid');

            // Create Circle modal
            if (await clickIfVisible(page, 'button:has-text("Create")')) {
                await wait(page, 500);
                const modalOpen = await page.locator('[role="dialog"]').first().isVisible({ timeout: 2000 }).catch(() => false);
                if (modalOpen) {
                    await ss(page, vp, 'alerts', 'create-circle-modal');
                    await closeAnyModal(page);
                }
            }

            // Join Circle modal
            if (await clickIfVisible(page, 'button:has-text("Join")')) {
                await wait(page, 500);
                const modalOpen = await page.locator('[role="dialog"]').first().isVisible({ timeout: 2000 }).catch(() => false);
                if (modalOpen) {
                    await ss(page, vp, 'alerts', 'join-circle-modal');
                    await closeAnyModal(page);
                }
            }

            // Scroll to circle alerts
            await scrollTo(page, 500);
            await ss(page, vp, 'alerts', 'circles-alerts-section');
        }
    } catch {
        console.log('  [WARN] Circles modal capture failed');
    }

    // --- Emergency Contacts button (in alerts header) ---
    try {
        // Scroll to top to see the alerts header
        await scrollToTop(page);
        // Click back to All tab first
        await clickIfVisible(page, '.cursor-pointer:has-text("All"), button:has-text("All")');
        await wait(page, 500);

        const emergencyBtn = page.locator('button:has(.lucide-phone), button[aria-label*="Emergency"]').first();
        if (await emergencyBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
            await emergencyBtn.click();
            await wait(page, 500);
            const modalOpen = await page.locator('[role="dialog"]').first().isVisible({ timeout: 2000 }).catch(() => false);
            if (modalOpen) {
                await ss(page, vp, 'alerts', 'emergency-contacts-modal');
                await closeAnyModal(page);
            }
        }
    } catch {
        console.log('  [WARN] Alerts emergency contacts capture failed');
    }

    // --- Expand an alert card ---
    try {
        await scrollToTop(page);
        await clickIfVisible(page, '.cursor-pointer:has-text("All"), button:has-text("All")');
        await wait(page, 1000);

        if (await clickIfVisible(page, 'button:has-text("Show more"), button:has-text("Read more")')) {
            await wait(page, 500);
            await ss(page, vp, 'alerts', 'alert-card-expanded');
        }
    } catch {
        console.log('  [WARN] Alert expand capture failed');
    }
}

async function captureProfileScreen(page: Page, vp: string) {
    console.log('\n--- ProfileScreen ---');

    // Fresh start
    await loadAppAuthenticated(page);

    // Navigate to Profile
    const ok = await goToTab(page, 'Profile');
    if (!ok) {
        console.log('  [ERROR] Could not navigate to Profile — skipping');
        return;
    }

    await wait(page, 2000);

    // --- Basic scroll captures ---
    await scrollToTop(page);
    await ss(page, vp, 'profile', 'header-banner');

    await ss(page, vp, 'profile', 'full-page', { fullPage: true });

    // Gamification
    await scrollTo(page, 400);
    await ss(page, vp, 'profile', 'gamification-streak');

    await scrollTo(page, 800);
    await ss(page, vp, 'profile', 'reputation-level');

    await scrollTo(page, 1200);
    await ss(page, vp, 'profile', 'badges-leaderboard');

    // Watch Areas + City
    await scrollTo(page, 1600);
    await ss(page, vp, 'profile', 'watch-areas-city');

    // Daily Routes + Reports
    await scrollTo(page, 2000);
    await ss(page, vp, 'profile', 'routes-reports');

    // Notifications
    await scrollTo(page, 2400);
    await ss(page, vp, 'profile', 'notification-prefs');

    // Language + Privacy
    await scrollTo(page, 2800);
    await ss(page, vp, 'profile', 'language-privacy');

    // About + Logout
    await scrollToBottom(page);
    await ss(page, vp, 'profile', 'about-logout');
}

async function captureProfileModals(page: Page, vp: string) {
    console.log('\n--- ProfileScreen Modals ---');

    // Fresh start
    await loadAppAuthenticated(page);
    await goToTab(page, 'Profile');
    await wait(page, 2000);

    // Edit Profile modal
    try {
        await scrollToTop(page);
        if (await clickIfVisible(page, 'button:has-text("Edit")')) {
            await wait(page, 500);
            const modalOpen = await page.locator('[role="dialog"]').first().isVisible({ timeout: 2000 }).catch(() => false);
            if (modalOpen) {
                await ss(page, vp, 'profile', 'edit-profile-modal');
                await closeAnyModal(page);
            }
        }
    } catch {
        console.log('  [WARN] Edit profile modal failed');
    }

    // Badge Catalog modal
    try {
        // Scroll to badges section
        await scrollTo(page, 1200);
        await wait(page, 300);
        if (await clickIfVisible(page, 'button:has-text("View All")')) {
            await wait(page, 500);
            const modalOpen = await page.locator('[role="dialog"]').first().isVisible({ timeout: 2000 }).catch(() => false);
            if (modalOpen) {
                await ss(page, vp, 'profile', 'badge-catalog-modal');
                await closeAnyModal(page);
            }
        }
    } catch {
        console.log('  [WARN] Badge catalog modal failed');
    }

    // Leaderboard modal
    try {
        await scrollTo(page, 1200);
        await wait(page, 300);
        if (await clickIfVisible(page, 'button:has-text("View Full"), button:has-text("Top 10")')) {
            await wait(page, 500);
            const modalOpen = await page.locator('[role="dialog"]').first().isVisible({ timeout: 2000 }).catch(() => false);
            if (modalOpen) {
                await ss(page, vp, 'profile', 'leaderboard-modal');
                await closeAnyModal(page);
            }
        }
    } catch {
        console.log('  [WARN] Leaderboard modal failed');
    }

    // Add Watch Area modal
    try {
        await scrollTo(page, 1600);
        await wait(page, 300);
        // Find "+ Add" button near "Watch Areas" text
        const addBtns = page.locator('button:has-text("+ Add"), button:has-text("Add")');
        const count = await addBtns.count();
        for (let i = 0; i < count; i++) {
            const btn = addBtns.nth(i);
            const text = await btn.textContent() || '';
            if (text.includes('Add') && await btn.isVisible().catch(() => false)) {
                await btn.click();
                await wait(page, 500);
                const modalOpen = await page.locator('[role="dialog"]').first().isVisible({ timeout: 2000 }).catch(() => false);
                if (modalOpen) {
                    await ss(page, vp, 'profile', `add-modal-${i}`);
                    await closeAnyModal(page);
                }
                break;
            }
        }
    } catch {
        console.log('  [WARN] Add watch area modal failed');
    }

    // "How is this calculated?" expandable
    try {
        await scrollTo(page, 800);
        await wait(page, 300);
        if (await clickIfVisible(page, 'button:has-text("How is this calculated")')) {
            await wait(page, 500);
            await ss(page, vp, 'profile', 'reputation-expanded');
        }
    } catch {
        console.log('  [WARN] Reputation expandable failed');
    }

    // Emergency Contacts from profile (at bottom)
    try {
        await scrollToBottom(page);
        await wait(page, 300);
        if (await clickIfVisible(page, 'button:has-text("Emergency Contacts")')) {
            await wait(page, 500);
            const modalOpen = await page.locator('[role="dialog"]').first().isVisible({ timeout: 2000 }).catch(() => false);
            if (modalOpen) {
                await ss(page, vp, 'profile', 'emergency-from-profile');
                await closeAnyModal(page);
            }
        }
    } catch {
        console.log('  [WARN] Emergency contacts from profile failed');
    }
}

// ---------------------------------------------------------------------------
// Main Runner
// ---------------------------------------------------------------------------

async function runForViewport(browser: Browser, vpName: string, viewport: { width: number; height: number }) {
    console.log(`\n${'='.repeat(50)}`);
    console.log(`  Viewport: ${vpName} (${viewport.width}x${viewport.height})`);
    console.log(`${'='.repeat(50)}`);

    stepCounter = 0;

    const context = await browser.newContext({
        viewport,
        geolocation: { latitude: 28.6139, longitude: 77.2090 }, // Delhi
        permissions: ['geolocation'],
    });

    const page = await context.newPage();

    // Collect console errors
    const consoleErrors: string[] = [];
    page.on('console', msg => {
        if (msg.type() === 'error') {
            consoleErrors.push(msg.text());
        }
    });

    try {
        // Initial auth check
        const authed = await loadAppAuthenticated(page);
        if (!authed) {
            console.log('\n  FATAL: Could not authenticate. Capturing login screen only.');
            await captureLoginScreen(page, vpName);
            return;
        }

        // ===== SCREEN CAPTURES =====
        // Each function starts with a fresh page load for isolation

        // 1. Login screen (captures unauthenticated state)
        await captureLoginScreen(page, vpName);

        // 2. Home screen — basic scrolls
        await captureHomeScreen(page, vpName);

        // 3. Flood Atlas
        await captureFloodAtlas(page, vpName);

        // 4. Report wizard
        await captureReportScreen(page, vpName);

        // 5. Alerts + filter tabs + FloodHub + Circles
        await captureAlertsScreen(page, vpName);

        // 6. Profile — basic scrolls
        await captureProfileScreen(page, vpName);

        // ===== MODAL CAPTURES (isolated, after all basic screens) =====

        // 7. Home modals (SOS, Emergency Contacts)
        await captureHomeModals(page, vpName);

        // 8. Profile modals (Edit, Badges, Leaderboard, Add Watch Area, Emergency)
        await captureProfileModals(page, vpName);

        // Summary
        console.log(`\n--- Console errors for ${vpName}: ${consoleErrors.length} ---`);
        if (consoleErrors.length > 0) {
            consoleErrors.slice(0, 15).forEach(e => console.log(`  ERR: ${e.slice(0, 150)}`));
        }

    } catch (error) {
        console.error(`\nFATAL ERROR in ${vpName}:`, error);
        try { await ss(page, vpName, 'error', 'fatal'); } catch {}
    } finally {
        await context.close();
    }
}

async function main() {
    console.log('╔═══════════════════════════════════════════════╗');
    console.log('║  FloodSafe UI Overhaul — Baseline Shots v2   ║');
    console.log('╠═══════════════════════════════════════════════╣');
    console.log(`║  URL:      ${APP_URL.padEnd(34)} ║`);
    console.log(`║  API:      ${PROD_API.slice(0, 34).padEnd(34)} ║`);
    console.log(`║  Viewport: ${vpArg.padEnd(34)} ║`);
    console.log(`║  Output:   screenshots/baseline/              ║`);
    console.log('╚═══════════════════════════════════════════════╝');

    // Clean only the viewport directories we're about to capture
    // (don't delete other viewport's screenshots when running --viewport=mobile only)
    const vpsToClear = vpArg === 'both' ? ['mobile', 'desktop'] : [vpArg];
    for (const vp of vpsToClear) {
        const vpDir = path.join(BASE_DIR, vp);
        if (fs.existsSync(vpDir)) {
            fs.rmSync(vpDir, { recursive: true });
            console.log(`Cleaned previous ${vp} screenshots.`);
        }
    }
    ensureDir(BASE_DIR);

    const browser = await chromium.launch({
        headless: false,
        slowMo: 50,
        args: ['--disable-web-security', '--disable-features=CrossOriginOpenerPolicy'],
    });

    try {
        if (vpArg === 'mobile' || vpArg === 'both') {
            await runForViewport(browser, 'mobile', VIEWPORTS.mobile);
        }
        if (vpArg === 'desktop' || vpArg === 'both') {
            await runForViewport(browser, 'desktop', VIEWPORTS.desktop);
        }

        // Count screenshots
        let total = 0;
        for (const vp of ['mobile', 'desktop']) {
            const dir = path.join(BASE_DIR, vp);
            if (fs.existsSync(dir)) {
                const files = fs.readdirSync(dir).filter(f => f.endsWith('.png'));
                console.log(`\n  ${vp}: ${files.length} screenshots`);
                files.forEach(f => console.log(`    ${f}`));
                total += files.length;
            }
        }
        console.log(`\n  TOTAL: ${total} baseline screenshots captured`);
        console.log(`  Location: ${BASE_DIR}`);

    } finally {
        await browser.close();
    }
}

main().catch(console.error);
