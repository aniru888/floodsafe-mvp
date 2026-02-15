/**
 * Centralized city code mappings and metadata.
 *
 * Eliminates duplicated city-code ternary chains across the codebase.
 * Single source of truth for city codes, regions, and phone defaults.
 */

export const CITY_CODES: Record<string, string> = {
  delhi: 'DEL',
  bangalore: 'BLR',
  yogyakarta: 'YGY',
  singapore: 'SIN',
};

/** Convert lowercase city key to uppercase API city code. */
export const getCityCode = (city: string): string =>
  CITY_CODES[city] || city.substring(0, 3).toUpperCase();

export const CITY_REGIONS: Record<string, string> = {
  delhi: 'National Capital Territory, India',
  bangalore: 'Karnataka, India',
  yogyakarta: 'Special Region of Yogyakarta, Indonesia',
  singapore: 'Republic of Singapore',
};

export const CITY_REGION_SHORT: Record<string, string> = {
  delhi: 'NCT',
  bangalore: 'Karnataka',
  yogyakarta: 'DIY',
  singapore: 'Singapore',
};

export const CITY_PHONE_DEFAULTS: Record<string, { code: string; placeholder: string }> = {
  delhi: { code: '+91', placeholder: '+91 XXXXX XXXXX' },
  bangalore: { code: '+91', placeholder: '+91 XXXXX XXXXX' },
  yogyakarta: { code: '+62', placeholder: '+62 XXX XXXX XXXX' },
  singapore: { code: '+65', placeholder: '+65 XXXX XXXX' },
};
