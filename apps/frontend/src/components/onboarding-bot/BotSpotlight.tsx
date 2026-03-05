/**
 * BotSpotlight — DISABLED.
 *
 * The driver.js overlay was removed because it creates a viewport-covering
 * overlay that traps clicks outside the spotlit element, even with
 * disableActiveInteraction: false. This repeatedly broke the onboarding
 * experience by preventing users from interacting with the app.
 *
 * The onboarding bot now uses BotTooltip positioning only (no overlay).
 * All tour steps have useSpotlight: false.
 */
export function BotSpotlight() {
    return null;
}
