import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';

interface SpeakOptions {
    language?: string;
    priority?: 'normal' | 'high';
}

interface VoiceGuidanceContextValue {
    isEnabled: boolean;
    setEnabled: (enabled: boolean) => void;
    speak: (text: string, optionsOrPriority?: SpeakOptions | 'normal' | 'high') => void;
    stop: () => void;
    voicesReady: boolean;
}

const VoiceGuidanceContext = createContext<VoiceGuidanceContextValue | null>(null);

/**
 * Find the best matching voice for a given language code.
 * Tries exact match (e.g. 'hi-IN'), then prefix (e.g. 'hi'), then English fallback.
 */
function findVoiceForLanguage(voices: SpeechSynthesisVoice[], langCode: string): SpeechSynthesisVoice | null {
    if (!langCode || voices.length === 0) return null;

    // Try exact match
    const exact = voices.find(v => v.lang.toLowerCase() === langCode.toLowerCase());
    if (exact) return exact;

    // Try prefix match (e.g. 'hi' matches 'hi-IN')
    const prefix = langCode.split('-')[0].toLowerCase();
    const prefixMatch = voices.find(v => v.lang.toLowerCase().startsWith(prefix));
    if (prefixMatch) return prefixMatch;

    return null;
}

export function VoiceGuidanceProvider({ children }: { children: React.ReactNode }) {
    const [isEnabled, setIsEnabledState] = useState(true);
    const [voicesReady, setVoicesReady] = useState(false);
    const synthRef = useRef<SpeechSynthesis | null>(null);
    const queueRef = useRef<{ text: string; language?: string }[]>([]);
    const isSpeakingRef = useRef(false);

    // Initialize speech synthesis and listen for voices
    useEffect(() => {
        if (typeof window === 'undefined' || !window.speechSynthesis) return;

        synthRef.current = window.speechSynthesis;

        const checkVoices = () => {
            const voices = synthRef.current?.getVoices() || [];
            if (voices.length > 0) {
                setVoicesReady(true);
            }
        };

        // Chrome loads voices asynchronously
        checkVoices();
        window.speechSynthesis.addEventListener('voiceschanged', checkVoices);

        return () => {
            window.speechSynthesis.removeEventListener('voiceschanged', checkVoices);
        };
    }, []);

    const processQueue = useCallback(() => {
        if (!synthRef.current || !isEnabled || isSpeakingRef.current) return;
        if (queueRef.current.length === 0) return;

        const item = queueRef.current.shift()!;
        const utterance = new SpeechSynthesisUtterance(item.text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        // Select voice based on language
        const voices = synthRef.current.getVoices();
        const langCode = item.language || 'en';

        const targetVoice = findVoiceForLanguage(voices, langCode);
        if (targetVoice) {
            utterance.voice = targetVoice;
            utterance.lang = targetVoice.lang;
        } else {
            // Fallback to any English voice
            const englishVoice = voices.find(v => v.lang.startsWith('en'));
            if (englishVoice) {
                utterance.voice = englishVoice;
                utterance.lang = englishVoice.lang;
            }
        }

        utterance.onstart = () => { isSpeakingRef.current = true; };
        utterance.onend = () => {
            isSpeakingRef.current = false;
            processQueue();
        };
        utterance.onerror = () => {
            isSpeakingRef.current = false;
            processQueue();
        };

        synthRef.current.speak(utterance);
    }, [isEnabled]);

    const speak = useCallback((text: string, optionsOrPriority?: SpeakOptions | 'normal' | 'high') => {
        if (!isEnabled || !synthRef.current) return;

        // Backward-compatible: accept string priority or options object
        let priority: 'normal' | 'high' = 'normal';
        let language: string | undefined;

        if (typeof optionsOrPriority === 'string') {
            priority = optionsOrPriority;
        } else if (optionsOrPriority) {
            priority = optionsOrPriority.priority || 'normal';
            language = optionsOrPriority.language;
        }

        if (priority === 'high') {
            queueRef.current = [];
            synthRef.current.cancel();
            isSpeakingRef.current = false;
        }

        queueRef.current.push({ text, language });
        processQueue();
    }, [isEnabled, processQueue]);

    const stop = useCallback(() => {
        queueRef.current = [];
        synthRef.current?.cancel();
        isSpeakingRef.current = false;
    }, []);

    const setEnabled = useCallback((enabled: boolean) => {
        setIsEnabledState(enabled);
        localStorage.setItem('floodsafe_voice_enabled', String(enabled));
        if (!enabled) {
            stop();
        }
    }, [stop]);

    // Load preference from localStorage on mount
    useEffect(() => {
        const saved = localStorage.getItem('floodsafe_voice_enabled');
        if (saved !== null) {
            setIsEnabledState(saved === 'true');
        }
    }, []);

    return (
        <VoiceGuidanceContext.Provider value={{ isEnabled, setEnabled, speak, stop, voicesReady }}>
            {children}
        </VoiceGuidanceContext.Provider>
    );
}

export function useVoiceGuidance() {
    const context = useContext(VoiceGuidanceContext);
    if (!context) {
        throw new Error('useVoiceGuidance must be used within VoiceGuidanceProvider');
    }
    return context;
}
