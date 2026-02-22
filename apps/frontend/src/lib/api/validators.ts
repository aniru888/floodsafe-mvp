/**
 * Lightweight runtime validation helpers for API responses
 * These provide type safety at runtime without external dependencies
 */

import { User } from '../../types';
import { Sensor, Report } from './hooks';

/**
 * Type guard to check if value is a non-null object
 */
function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Type guard to check if value is a string
 */
function isString(value: unknown): value is string {
    return typeof value === 'string';
}

/**
 * Type guard to check if value is a number
 */
function isNumber(value: unknown): value is number {
    return typeof value === 'number' && !isNaN(value);
}

/**
 * Type guard to check if value is a boolean
 */
function isBoolean(value: unknown): value is boolean {
    return typeof value === 'boolean';
}

/**
 * Validates and normalizes a User object from API response
 */
export function validateUser(data: unknown): User | null {
    if (!isObject(data)) return null;

    // Required fields
    if (!isString(data.id) || !data.id) return null;
    if (!isString(data.username) || !data.username) return null;
    if (!isString(data.email) || !data.email) return null;
    if (!isString(data.role) || !data.role) return null;
    if (!isString(data.created_at) || !data.created_at) return null;
    if (!isNumber(data.points)) return null;
    if (!isNumber(data.level)) return null;
    if (!isNumber(data.reports_count)) return null;
    if (!isNumber(data.verified_reports_count)) return null;

    return {
        id: data.id,
        username: data.username,
        email: data.email,
        phone: isString(data.phone) ? data.phone : undefined,
        profile_photo_url: isString(data.profile_photo_url) ? data.profile_photo_url : undefined,
        role: data.role,
        created_at: data.created_at,
        points: data.points,
        level: data.level,
        reports_count: data.reports_count,
        verified_reports_count: data.verified_reports_count,
        badges: Array.isArray(data.badges) && data.badges.every(isString) ? data.badges : undefined,
        language: isString(data.language) ? data.language : undefined,
        notification_push: isBoolean(data.notification_push) ? data.notification_push : undefined,
        notification_sms: isBoolean(data.notification_sms) ? data.notification_sms : undefined,
        notification_whatsapp: isBoolean(data.notification_whatsapp) ? data.notification_whatsapp : undefined,
        notification_email: isBoolean(data.notification_email) ? data.notification_email : undefined,
        alert_preferences: validateAlertPreferences(data.alert_preferences),
    };
}

/**
 * Validates alert preferences object
 */
function validateAlertPreferences(data: unknown): User['alert_preferences'] {
    if (!isObject(data)) return undefined;

    // If any required field is missing or invalid, return undefined
    if (!isBoolean(data.watch)) return undefined;
    if (!isBoolean(data.advisory)) return undefined;
    if (!isBoolean(data.warning)) return undefined;
    if (!isBoolean(data.emergency)) return undefined;

    return {
        watch: data.watch,
        advisory: data.advisory,
        warning: data.warning,
        emergency: data.emergency,
    };
}

/**
 * Validates an array of users
 */
export function validateUsers(data: unknown): User[] {
    if (!Array.isArray(data)) return [];

    return data
        .map(validateUser)
        .filter((user): user is User => user !== null);
}

/**
 * Validates a Sensor object from API response
 */
export function validateSensor(data: unknown): Sensor | null {
    if (!isObject(data)) return null;

    if (!isString(data.id) || !data.id) return null;
    if (!isNumber(data.latitude)) return null;
    if (!isNumber(data.longitude)) return null;
    if (!isString(data.status)) return null;

    return {
        id: data.id,
        location_lat: isNumber(data.location_lat) ? data.location_lat : data.latitude,
        latitude: data.latitude,
        longitude: data.longitude,
        status: data.status,
        last_ping: isString(data.last_ping) ? data.last_ping : undefined,
    };
}

/**
 * Validates an array of sensors
 */
export function validateSensors(data: unknown): Sensor[] {
    if (!Array.isArray(data)) return [];

    return data
        .map(validateSensor)
        .filter((sensor): sensor is Sensor => sensor !== null);
}

/**
 * Validates a Report object from API response
 */
export function validateReport(data: unknown): Report | null {
    if (!isObject(data)) return null;

    if (!isString(data.id) || !data.id) return null;
    if (!isString(data.description)) return null;
    if (!isNumber(data.latitude)) return null;
    if (!isNumber(data.longitude)) return null;
    if (!isBoolean(data.verified)) return null;
    if (!isNumber(data.verification_score)) return null;
    if (!isNumber(data.upvotes)) return null;
    if (!isString(data.timestamp)) return null;

    return {
        id: data.id,
        description: data.description,
        latitude: data.latitude,
        longitude: data.longitude,
        media_url: isString(data.media_url) ? data.media_url : undefined,
        verified: data.verified,
        verification_score: data.verification_score,
        upvotes: data.upvotes,
        timestamp: data.timestamp,
        phone_verified: isBoolean(data.phone_verified) ? data.phone_verified : undefined,
        water_depth: isString(data.water_depth) ? data.water_depth : undefined,
        vehicle_passability: isString(data.vehicle_passability) ? data.vehicle_passability : undefined,
        iot_validation_score: isNumber(data.iot_validation_score) ? data.iot_validation_score : undefined,
        downvotes: isNumber(data.downvotes) ? data.downvotes : 0,
        quality_score: isNumber(data.quality_score) ? data.quality_score : undefined,
        verified_at: isString(data.verified_at) ? data.verified_at : undefined,
        comment_count: isNumber(data.comment_count) ? data.comment_count : undefined,
        user_vote: data.user_vote === 'upvote' || data.user_vote === 'downvote' ? data.user_vote : undefined,
        ml_classification: isString(data.ml_classification) ? data.ml_classification : undefined,
        ml_confidence: isNumber(data.ml_confidence) ? data.ml_confidence : undefined,
        ml_is_flood: isBoolean(data.ml_is_flood) ? data.ml_is_flood : undefined,
        ml_needs_review: isBoolean(data.ml_needs_review) ? data.ml_needs_review : undefined,
    };
}

/**
 * Validates an array of reports
 */
export function validateReports(data: unknown): Report[] {
    if (!Array.isArray(data)) return [];

    return data
        .map(validateReport)
        .filter((report): report is Report => report !== null);
}

/**
 * Generic error response validator
 */
export interface APIError {
    message: string;
    code?: string;
    details?: unknown;
}

export function isAPIError(data: unknown): data is APIError {
    return isObject(data) && isString(data.message);
}
