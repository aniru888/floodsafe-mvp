/**
 * Emergency Contact Numbers for India, Indonesia, and Singapore
 *
 * Zero-cost implementation using static data.
 * All numbers verified as of 2024.
 *
 * SAFETY-CRITICAL: Country-aware filtering ensures Indian numbers
 * are never shown to Indonesian users and vice versa.
 */

export type EmergencyContactCategory = 'critical' | 'police-fire' | 'medical' | 'flood' | 'city-specific';
export type CityFilter = 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore' | 'indore' | 'all';

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
    country?: 'india' | 'indonesia' | 'singapore';
    available24x7: boolean;
}

const CITY_COUNTRY: Record<string, string> = {
    delhi: 'india',
    bangalore: 'india',
    yogyakarta: 'indonesia',
    singapore: 'singapore',
    indore: 'india',
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
        id: 'id-psc119',
        name: 'Medical Emergency',
        nameLocal: 'PSC 119',
        number: '119',
        description: 'Pusat Komando Kesehatan (Health Command Center)',
        category: 'medical',
        icon: 'Heart',
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
        number: '08112828911',
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
    {
        id: 'ygy-polda',
        name: 'Police (Polda DIY)',
        nameLocal: 'Polda DIY',
        number: '0274-563494',
        description: 'Kepolisian Daerah Yogyakarta (Regional Police)',
        category: 'city-specific',
        icon: 'Shield',
        city: 'yogyakarta',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'ygy-fire-city',
        name: 'Fire - Yogyakarta City',
        nameLocal: 'Damkar Kota Yogyakarta',
        number: '0274-587101',
        description: 'Damkar Kota Yogyakarta (City Fire Department)',
        category: 'city-specific',
        icon: 'Flame',
        city: 'yogyakarta',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'ygy-fire-sleman',
        name: 'Fire - Sleman',
        nameLocal: 'Damkar Sleman',
        number: '0274-868351',
        description: 'Damkar Kabupaten Sleman (Sleman Fire Department)',
        category: 'city-specific',
        icon: 'Flame',
        city: 'yogyakarta',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'ygy-fire-bantul',
        name: 'Fire - Bantul',
        nameLocal: 'Damkar Bantul',
        number: '0274-6462100',
        description: 'Damkar Kabupaten Bantul (Bantul Fire Department)',
        category: 'city-specific',
        icon: 'Flame',
        city: 'yogyakarta',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'ygy-fire-kulonprogo',
        name: 'Fire - Kulon Progo',
        nameLocal: 'Damkar Kulon Progo',
        number: '0274-774710',
        description: 'Damkar Kabupaten Kulon Progo (Kulon Progo Fire Department)',
        category: 'city-specific',
        icon: 'Flame',
        city: 'yogyakarta',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'ygy-sar',
        name: 'SAR Yogyakarta',
        nameLocal: 'SAR Yogyakarta',
        number: '0274-587559',
        description: 'Kantor SAR Yogyakarta (Local Search & Rescue)',
        category: 'city-specific',
        icon: 'Shield',
        city: 'yogyakarta',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'ygy-pmi',
        name: 'Red Cross (PMI) DIY',
        nameLocal: 'PMI DIY',
        number: '0274-372176',
        description: 'Palang Merah Indonesia DIY (Indonesian Red Cross)',
        category: 'city-specific',
        icon: 'Heart',
        city: 'yogyakarta',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'ygy-pln',
        name: 'PLN (Power Outage)',
        nameLocal: 'PLN',
        number: '123',
        description: 'Perusahaan Listrik Negara (Power Outage Reporting)',
        category: 'city-specific',
        icon: 'Building2',
        city: 'yogyakarta',
        country: 'indonesia',
        available24x7: true,
    },
    {
        id: 'ygy-pdam',
        name: 'PDAM (Water Utility)',
        nameLocal: 'PDAM',
        number: '0274-515870',
        description: 'Perusahaan Daerah Air Minum (Water Utility Disturbance)',
        category: 'city-specific',
        icon: 'Building',
        city: 'yogyakarta',
        country: 'indonesia',
        available24x7: true,
    },

    // ===================
    // SINGAPORE — NATIONAL & CITY-SPECIFIC
    // ===================
    {
        id: 'sg-police',
        name: 'Police (SPF)',
        number: '999',
        description: 'Singapore Police Force',
        category: 'police-fire',
        icon: 'Shield',
        city: 'all',
        country: 'singapore',
        available24x7: true,
    },
    {
        id: 'sg-fire-ambulance',
        name: 'Fire & Ambulance (SCDF)',
        number: '995',
        description: 'Singapore Civil Defence Force',
        category: 'critical',
        icon: 'Flame',
        city: 'all',
        country: 'singapore',
        available24x7: true,
    },
    {
        id: 'sg-non-emergency',
        name: 'Non-Emergency Police',
        number: '1800-255-0000',
        description: 'SPF non-emergency hotline',
        category: 'police-fire',
        icon: 'Shield',
        city: 'singapore',
        country: 'singapore',
        available24x7: true,
    },
    {
        id: 'sg-pub',
        name: 'PUB 24h Hotline',
        number: '1800-284-6600',
        description: 'Public Utilities Board — flooding & water emergencies',
        category: 'flood',
        icon: 'Waves',
        city: 'singapore',
        country: 'singapore',
        available24x7: true,
    },
    {
        id: 'sg-nea',
        name: 'NEA Hotline',
        number: '1800-225-5632',
        description: 'National Environment Agency — weather & environment',
        category: 'city-specific',
        icon: 'Building',
        city: 'singapore',
        country: 'singapore',
        available24x7: true,
    },
    {
        id: 'sg-lta',
        name: 'LTA Hotline',
        number: '1800-225-5582',
        description: 'Land Transport Authority — road flooding & traffic',
        category: 'city-specific',
        icon: 'Building2',
        city: 'singapore',
        country: 'singapore',
        available24x7: true,
    },
    {
        id: 'sg-town-council',
        name: 'Town Council Hotline',
        number: '1800-286-1188',
        description: 'HDB estate flooding & drainage issues',
        category: 'city-specific',
        icon: 'Building',
        city: 'singapore',
        country: 'singapore',
        available24x7: true,
    },

    // ─── Indore, Madhya Pradesh ───────────────────────────────────────
    {
        id: 'indore-emergency',
        name: 'Emergency (Police/Fire/Ambulance)',
        number: '112',
        description: 'National emergency number',
        category: 'critical',
        icon: 'AlertTriangle',
        city: 'indore',
        country: 'india',
        available24x7: true,
    },
    {
        id: 'indore-police',
        name: 'Indore Police Control Room',
        number: '0731-2435023',
        description: 'Indore city police control room',
        category: 'city-specific',
        icon: 'Shield',
        city: 'indore',
        country: 'india',
        available24x7: true,
    },
    {
        id: 'indore-fire',
        name: 'Fire Brigade',
        number: '101',
        description: 'Fire brigade emergency',
        category: 'police-fire',
        icon: 'Flame',
        city: 'indore',
        country: 'india',
        available24x7: true,
    },
    {
        id: 'indore-disaster',
        name: 'Disaster Helpline',
        number: '1070',
        description: 'National disaster helpline',
        category: 'flood',
        icon: 'Waves',
        city: 'indore',
        country: 'india',
        available24x7: true,
    },
    {
        id: 'indore-sdma',
        name: 'MP SDMA',
        number: '0755-2441825',
        description: 'Madhya Pradesh State Disaster Management Authority',
        category: 'city-specific',
        icon: 'Building',
        city: 'indore',
        country: 'india',
        available24x7: true,
    },
    {
        id: 'indore-imc',
        name: 'Indore Municipal Corporation',
        number: '0731-2432222',
        description: 'IMC helpline for flood/drainage complaints',
        category: 'city-specific',
        icon: 'Building2',
        city: 'indore',
        country: 'india',
        available24x7: true,
    },
    {
        id: 'indore-ambulance',
        name: 'Ambulance (108)',
        number: '108',
        description: 'Emergency ambulance service',
        category: 'medical',
        icon: 'Ambulance',
        city: 'indore',
        country: 'india',
        available24x7: true,
    },
    {
        id: 'indore-sewag',
        name: 'SEWAG Flood/Drain Complaint',
        number: '0731-2534666',
        description: 'Indore drainage and sewage authority',
        category: 'city-specific',
        icon: 'Building',
        city: 'indore',
        country: 'india',
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
export function getContactsForCity(city: 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore' | 'indore' | null): EmergencyContact[] {
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
export function getContactsByCategory(city: 'delhi' | 'bangalore' | 'yogyakarta' | 'singapore' | 'indore' | null): {
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
