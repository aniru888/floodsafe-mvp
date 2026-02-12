/**
 * Emergency Contact Numbers for India and Indonesia
 *
 * Zero-cost implementation using static data.
 * All numbers verified as of 2024.
 *
 * SAFETY-CRITICAL: Country-aware filtering ensures Indian numbers
 * are never shown to Indonesian users and vice versa.
 */

export type EmergencyContactCategory = 'critical' | 'police-fire' | 'medical' | 'flood' | 'city-specific';
export type CityFilter = 'delhi' | 'bangalore' | 'yogyakarta' | 'all';

export interface EmergencyContact {
    id: string;
    name: string;
    nameHindi?: string;
    nameLocal?: string;
    number: string;
    description: string;
    category: EmergencyContactCategory;
    icon: 'AlertTriangle' | 'Shield' | 'Flame' | 'Ambulance' | 'Heart' | 'Waves' | 'Building' | 'Building2';
    city: CityFilter;
    country?: 'india' | 'indonesia';
    available24x7: boolean;
}

const CITY_COUNTRY: Record<string, string> = {
    delhi: 'india',
    bangalore: 'india',
    yogyakarta: 'indonesia',
};

/**
 * All emergency contacts for India and Indonesia.
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
        country: 'india',
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
        country: 'india',
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
        country: 'india',
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
        country: 'india',
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
        country: 'india',
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
        country: 'india',
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

    // ===================
    // INDONESIA — NATIONAL
    // ===================
    {
        id: 'id-police',
        name: 'Polisi',
        nameLocal: 'Polisi',
        number: '110',
        description: 'Kepolisian (Police)',
        category: 'police-fire',
        icon: 'Shield',
        city: 'all',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'id-fire',
        name: 'Pemadam Kebakaran',
        nameLocal: 'Pemadam Kebakaran',
        number: '113',
        description: 'Dinas Pemadam (Fire Service)',
        category: 'police-fire',
        icon: 'Flame',
        city: 'all',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'id-ambulance',
        name: 'Ambulans',
        nameLocal: 'Ambulans',
        number: '118',
        description: 'Ambulans darurat (Emergency Ambulance)',
        category: 'medical',
        icon: 'Ambulance',
        city: 'all',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'id-sar',
        name: 'SAR / Basarnas',
        nameLocal: 'Basarnas',
        number: '117',
        description: 'Search & Rescue (Badan SAR Nasional)',
        category: 'critical',
        icon: 'Shield',
        city: 'all',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'id-bnpb',
        name: 'BNPB',
        nameLocal: 'BNPB',
        number: '021-29827444',
        description: 'Badan Nasional Penanggulangan Bencana (National Disaster Agency)',
        category: 'flood',
        icon: 'Waves',
        city: 'all',
        country: 'indonesia',
        available24x7: true,
    },

    // ===================
    // CITY-SPECIFIC: YOGYAKARTA
    // ===================
    {
        id: 'ygy-bpbd',
        name: 'BPBD DIY',
        nameLocal: 'BPBD DIY',
        number: '0274-555459',
        description: 'Badan Penanggulangan Bencana Daerah (Local Disaster Agency)',
        category: 'city-specific',
        icon: 'Building',
        city: 'yogyakarta',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'ygy-bmkg',
        name: 'BMKG Yogyakarta',
        nameLocal: 'BMKG',
        number: '0274-512624',
        description: 'Badan Meteorologi & Geofisika (Weather & Seismology)',
        category: 'city-specific',
        icon: 'Building2',
        city: 'yogyakarta',
        country: 'indonesia',
        available24x7: true,
    },
];

/**
 * Filter contacts by city with country awareness.
 * Returns truly universal contacts (112) + country-wide contacts + city-specific ones.
 *
 * Country logic: contacts with no `country` field are universal.
 * Contacts with `country` field only appear for cities in that country.
 */
export function getContactsForCity(city: 'delhi' | 'bangalore' | 'yogyakarta' | null): EmergencyContact[] {
    const country = city ? CITY_COUNTRY[city] : 'india';
    return EMERGENCY_CONTACTS.filter(contact => {
        const cityMatch = contact.city === 'all' || contact.city === city;
        const countryMatch = !contact.country || contact.country === country;
        return cityMatch && countryMatch;
    });
}

/**
 * Get contacts grouped by category for the given city.
 * Returns an object with arrays for each category.
 */
export function getContactsByCategory(city: 'delhi' | 'bangalore' | 'yogyakarta' | null): {
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
