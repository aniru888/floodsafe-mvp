import { useState, useCallback } from 'react';
import { useOnboardingBot } from '../../contexts/OnboardingBotContext';
import { BotCompanion } from './BotCompanion';
import { BotTooltip } from './BotTooltip';
import { BotSpotlight } from './BotSpotlight';

/**
 * OnboardingBot — Main orchestrator component.
 *
 * Renders different UI based on phase:
 * - 'onboarding' → returns null here (BotInlineCard is embedded in OnboardingScreen)
 * - 'app-tour' → renders BotCompanion + BotTooltip + BotSpotlight via Portal
 * - 'idle' → returns null
 */
export function OnboardingBot() {
    const { state } = useOnboardingBot();
    const [tooltipVisible, setTooltipVisible] = useState(true);

    const handleCompanionClick = useCallback(() => {
        setTooltipVisible(prev => !prev);
    }, []);

    // Onboarding phase: BotInlineCard is rendered inline in OnboardingScreen
    // Idle phase: nothing to render
    if (state.phase !== 'app-tour') return null;

    return (
        <>
            <BotCompanion onClick={handleCompanionClick} />
            <BotTooltip visible={tooltipVisible} />
            <BotSpotlight />
        </>
    );
}
