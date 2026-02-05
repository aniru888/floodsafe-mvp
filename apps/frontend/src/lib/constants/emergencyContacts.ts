/**
 * Emergency Contact Numbers for India
 *
 * Zero-cost implementation using static data.
 * All numbers verified for India as of 2024.
 */

export type EmergencyContactCategory = 'critical' | 'police-fire' | 'medical' | 'flood' | 'city-specific';
export type CityFilter = 'delhi' | 'bangalore' | 'all';

export interface EmergencyContact {
    id: string;
    name: string;
    nameHindi?: string;
    number: string;
    description: string;
    category: EmergencyContactCategory;
    icon: 'AlertTriangle' | 'Shield' | 'Flame' | 'Ambulance' | 'Heart' | 'Waves' | 'Building' | 'Building2';
    city: CityFilter;
    available24x7: boolean;
}

/**
 * All emergency contacts for India.
 * Ordered by priority within each category.
 */
export const EMERGENCY_CONTACTS: EmergencyContact[] = [
    // ===================
    // CRITICAL (Top Priority)
    // ===================
    {
        id: 'national-emergency',
        name: 'National Emergency',
        nameHindi: 'राष्ट्रीय आपातकालीन',
        number: '112',
        description: 'Police, Fire, Ambulance (like 911)',
        category: 'critical',
        icon: 'AlertTriangle',
        city: 'all',
        available24x7: true,
    },
    {
        id: 'ndma',
        name: 'Disaster Management',
        nameHindi: 'आपदा प्रबंधन',
        number: '1070',
        description: 'NDMA Helpline',
        category: 'critical',
        icon: 'Shield',
        city: 'all',
        available24x7: true,
    },

    // ===================
    // POLICE & FIRE
    // ===================
    {
        id: 'police',
        name: 'Police',
        nameHindi: 'पुलिस',
        number: '100',
        description: 'Emergency police assistance',
        category: 'police-fire',
        icon: 'Shield',
        city: 'all',
        available24x7: true,
    },
    {
        id: 'fire',
        name: 'Fire Services',
        nameHindi: 'दमकल सेवा',
        number: '101',
        description: 'Fire emergency',
        category: 'police-fire',
        icon: 'Flame',
        city: 'all',
        available24x7: true,
    },

    // ===================
    // MEDICAL
    // ===================
    {
        id: 'ambulance',
        name: 'Ambulance',
        nameHindi: 'एम्बुलेंस',
        number: '102',
        description: 'Government ambulance service',
        category: 'medical',
        icon: 'Ambulance',
        city: 'all',
        available24x7: true,
    },
    {
        id: 'ems',
        name: 'Emergency Medical',
        nameHindi: 'आपातकालीन चिकित्सा',
        number: '108',
        description: 'Advanced EMS with GPS tracking',
        category: 'medical',
        icon: 'Heart',
        city: 'all',
        available24x7: true,
    },

    // ===================
    // FLOOD-SPECIFIC
    // ===================
    {
        id: 'flood-control',
        name: 'Flood Control Room',
        nameHindi: 'बाढ़ नियंत्रण कक्ष',
        number: '1078',
        description: 'Central flood helpline',
        category: 'flood',
        icon: 'Waves',
        city: 'all',
        available24x7: true,
    },

    // ===================
    // CITY-SPECIFIC: DELHI
    // ===================
    {
        id: 'delhi-ddma',
        name: 'Delhi Disaster Mgmt',
        nameHindi: 'दिल्ली आपदा प्रबंधन',
        number: '1077',
        description: 'Delhi Disaster Management Authority',
        category: 'city-specific',
        icon: 'Building',
        city: 'delhi',
        available24x7: true,
    },
    {
        id: 'delhi-mcd',
        name: 'MCD Control Room',
        nameHindi: 'एमसीडी नियंत्रण कक्ष',
        number: '155304',
        description: 'Municipal waterlogging complaints',
        category: 'city-specific',
        icon: 'Building2',
        city: 'delhi',
        available24x7: true,
    },

    // ===================
    // CITY-SPECIFIC: BANGALORE
    // ===================
    {
        id: 'blr-bbmp',
        name: 'BBMP Control Room',
        nameHindi: 'बीबीएमपी नियंत्रण कक्ष',
        number: '080-22221188',
        description: 'Bangalore flood & waterlogging',
        category: 'city-specific',
        icon: 'Building',
        city: 'bangalore',
        available24x7: true,
    },
];

/**
 * Filter contacts by city.
 * Returns universal contacts (city='all') plus city-specific ones.
 */
export function getContactsForCity(city: 'delhi' | 'bangalore' | null): EmergencyContact[] {
    return EMERGENCY_CONTACTS.filter(
        contact => contact.city === 'all' || contact.city === city
    );
}

/**
 * Get contacts grouped by category for the given city.
 * Returns an object with arrays for each category.
 */
export function getContactsByCategory(city: 'delhi' | 'bangalore' | null): {
    critical: EmergencyContact[];
    policeFire: EmergencyContact[];
    medical: EmergencyContact[];
    flood: EmergencyContact[];
    citySpecific: EmergencyContact[];
} {
    const contacts = getContactsForCity(city);
    return {
        critical: contacts.filter(c => c.category === 'critical'),
        policeFire: contacts.filter(c => c.category === 'police-fire'),
        medical: contacts.filter(c => c.category === 'medical'),
        flood: contacts.filter(c => c.category === 'flood'),
        citySpecific: contacts.filter(c => c.category === 'city-specific'),
    };
}

/**
 * Sanitize phone number for tel: protocol.
 * Removes spaces and preserves digits, plus sign, and hyphens.
 */
export function sanitizePhoneNumber(number: string): string {
    return number.replace(/\s/g, '');
}
