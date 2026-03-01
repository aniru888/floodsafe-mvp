import React, { createContext, useContext, useState, useCallback } from 'react';

export type AppLanguage = 'en' | 'hi' | 'id';

interface LanguageContextValue {
    language: AppLanguage;
    setLanguage: (lang: AppLanguage) => void;
}

const LS_KEY = 'floodsafe_language';
const VALID_LANGUAGES: AppLanguage[] = ['en', 'hi', 'id'];

/** Convert DB long names to short codes. Accepts both formats. */
export function toShortCode(dbVal: string | undefined | null): AppLanguage {
    if (!dbVal) return 'en';
    const map: Record<string, AppLanguage> = {
        english: 'en', hindi: 'hi', indonesian: 'id',
        en: 'en', hi: 'hi', id: 'id',
    };
    return map[dbVal.toLowerCase()] || 'en';
}

/** Convert short codes to DB long names for PATCH /users/me/profile. */
export function toDbValue(code: AppLanguage): string {
    const map: Record<AppLanguage, string> = { en: 'english', hi: 'hindi', id: 'indonesian' };
    return map[code];
}

function readStoredLanguage(): AppLanguage {
    try {
        const stored = localStorage.getItem(LS_KEY);
        if (stored && VALID_LANGUAGES.includes(stored as AppLanguage)) {
            return stored as AppLanguage;
        }
    } catch {
        // localStorage unavailable (SSR, privacy mode)
    }
    return 'en';
}

const LanguageContext = createContext<LanguageContextValue>({
    language: 'en',
    setLanguage: () => {},
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
    const [language, setLanguageState] = useState<AppLanguage>(readStoredLanguage);

    const setLanguage = useCallback((lang: AppLanguage) => {
        if (!VALID_LANGUAGES.includes(lang)) return;
        setLanguageState(lang);
        try {
            localStorage.setItem(LS_KEY, lang);
        } catch {
            // localStorage unavailable
        }
    }, []);

    return (
        <LanguageContext.Provider value={{ language, setLanguage }}>
            {children}
        </LanguageContext.Provider>
    );
}

/** Primary hook for reading/setting app language. */
export function useLanguage(): LanguageContextValue {
    return useContext(LanguageContext);
}
