import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { CITIES, type CityKey } from '../lib/map/cityConfigs';
import { MAP_CONSTANTS } from '../lib/map/config';
import { useAuth } from './AuthContext';
import { API_BASE_URL } from '../lib/api/config';
import { TokenStorage } from '../lib/auth/token-storage';

interface CityContextType {
    city: CityKey;
    setCity: (city: CityKey) => void;
    syncCityToUser: (userId: string, newCity: CityKey) => Promise<void>;
}

const CityContext = createContext<CityContextType | undefined>(undefined);

const STORAGE_KEY = 'floodsafe_selected_city';

interface CityProviderProps {
    children: ReactNode;
}

export function CityProvider({ children }: CityProviderProps) {
    const { user, refreshUser } = useAuth();

    // Initialize from user preference > localStorage > default
    const [city, setCityState] = useState<CityKey>(() => {
        // Priority 1: User preference (if logged in)
        const validCities = Object.keys(CITIES);
        if (user?.city_preference && validCities.includes(user.city_preference)) {
            return user.city_preference as CityKey;
        }
        // Priority 2: localStorage
        if (typeof window !== 'undefined') {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved && validCities.includes(saved)) {
                return saved as CityKey;
            }
        }
        // Priority 3: Default
        return MAP_CONSTANTS.DEFAULT_CITY;
    });

    // Sync with user preference on mount or when user changes
    useEffect(() => {
        if (user?.city_preference && user.city_preference !== city) {
            if (Object.keys(CITIES).includes(user.city_preference)) {
                setCityState(user.city_preference as CityKey);
            }
        }
    }, [user?.city_preference]);

    // Persist to localStorage when city changes
    useEffect(() => {
        if (typeof window !== 'undefined') {
            localStorage.setItem(STORAGE_KEY, city);
        }
    }, [city]);

    const setCity = (newCity: CityKey) => {
        setCityState(newCity);
    };

    /**
     * Sync city preference to user profile in backend
     * Should be called when user explicitly changes city during onboarding
     */
    const syncCityToUser = async (userId: string, newCity: CityKey) => {
        try {
            const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${TokenStorage.getAccessToken()}`
                },
                body: JSON.stringify({ city_preference: newCity })
            });

            if (!response.ok) {
                throw new Error('Failed to sync city to user profile');
            }

            // Update local state after successful API call
            setCityState(newCity);
            // Refresh AuthContext user so user.city_preference stays in sync
            await refreshUser();
        } catch (error) {
            console.error('Error syncing city to user:', error);
            throw error;
        }
    };

    return (
        <CityContext.Provider value={{ city, setCity, syncCityToUser }}>
            {children}
        </CityContext.Provider>
    );
}

/**
 * Hook to access the current city and city setter
 * @returns Current city key and setter function
 * @throws Error if used outside CityProvider
 */
export function useCityContext(): CityContextType {
    const context = useContext(CityContext);
    if (context === undefined) {
        throw new Error('useCityContext must be used within a CityProvider');
    }
    return context;
}

/**
 * Hook to get just the current city (convenience hook)
 */
export function useCurrentCity(): CityKey {
    const { city } = useCityContext();
    return city;
}
