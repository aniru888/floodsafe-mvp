/**
 * Admin panel API hooks for FloodSafe.
 * Completely separate from main app hooks — zero impact on existing code.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { API_BASE_URL } from './config';

// ============================================================================
// ADMIN AUTH — uses sessionStorage (more secure: closes on tab close)
// ============================================================================

const ADMIN_TOKEN_KEY = 'floodsafe_admin_token';

export function getAdminToken(): string | null {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

export function setAdminToken(token: string) {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearAdminToken() {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

export function isAdminAuthenticated(): boolean {
    return !!getAdminToken();
}

// Base API fetch (non-admin-prefixed endpoints like /reports/{id}/verify)
async function apiBaseFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const token = getAdminToken();
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            ...options?.headers,
        },
    });

    if (response.status === 401 || response.status === 403) {
        clearAdminToken();
        window.location.href = '/admin/login';
        throw new Error('Admin session expired');
    }

    if (!response.ok) {
        let errorMessage = `API Error: ${response.statusText}`;
        try {
            const errorData = await response.json();
            if (errorData.detail) {
                errorMessage = typeof errorData.detail === 'string'
                    ? errorData.detail : JSON.stringify(errorData.detail);
            }
        } catch { /* ignore */ }
        throw new Error(errorMessage);
    }

    return response.json();
}

// Admin-specific fetch wrapper
async function adminFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const token = getAdminToken();
    const response = await fetch(`${API_BASE_URL}/admin${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            ...options?.headers,
        },
    });

    if (response.status === 401 || response.status === 403) {
        clearAdminToken();
        window.location.href = '/admin/login';
        throw new Error('Admin session expired');
    }

    if (!response.ok) {
        let errorMessage = `API Error: ${response.statusText}`;
        try {
            const errorData = await response.json();
            if (errorData.detail) {
                errorMessage = typeof errorData.detail === 'string'
                    ? errorData.detail : JSON.stringify(errorData.detail);
            }
        } catch { /* ignore */ }
        throw new Error(errorMessage);
    }

    return response.json();
}

// ============================================================================
// TYPES
// ============================================================================

export interface AdminUser {
    id: string;
    username: string;
    email: string;
    phone: string | null;
    role: string;
    auth_provider: string;
    points: number;
    level: number;
    reputation_score: number;
    reports_count: number;
    verified_reports_count: number;
    streak_days: number;
    city_preference: string | null;
    profile_complete: boolean;
    leaderboard_visible: boolean;
    profile_photo_url: string | null;
    created_at: string | null;
    updated_at: string | null;
}

export interface AdminReport {
    id: string;
    user_id: string | null;
    description: string;
    media_url: string | null;
    verified: boolean;
    verification_score: number;
    upvotes: number;
    downvotes: number;
    quality_score: number;
    water_depth: string | null;
    vehicle_passability: string | null;
    timestamp: string | null;
    verified_at: string | null;
    archived_at: string | null;
}

export interface AdminBadge {
    id: string;
    key: string;
    name: string;
    description: string;
    icon: string;
    category: string;
    requirement_type: string;
    requirement_value: number;
    points_reward: number;
    is_active: boolean;
}

export interface DashboardStats {
    users: {
        total: number;
        new_7d: number;
        roles: Record<string, number>;
        active_reporters_7d: number;
    };
    reports: {
        total: number;
        new_7d: number;
        verified: number;
        pending_verification: number;
    };
    community: {
        safety_circles: number;
        badges_awarded: number;
        comments: number;
    };
    generated_at: string;
}

export interface PaginatedResponse<T> {
    users?: T[];
    reports?: T[];
    entries?: T[];
    total: number;
    page: number;
    per_page: number;
    total_pages?: number;
}

export interface AuditLogEntry {
    id: string;
    admin_id: string | null;
    admin_username: string;
    action: string;
    target_type: string | null;
    target_id: string | null;
    details: string | null;
    created_at: string | null;
}

export interface AnalyticsData {
    period_days: number;
    daily: Array<{ date: string; count: number; verified?: number }>;
}

// ============================================================================
// LOGIN
// ============================================================================

export function useAdminLogin() {
    return useMutation({
        mutationFn: async (creds: { email: string; password: string }) => {
            const response = await fetch(`${API_BASE_URL}/admin/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(creds),
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({ detail: 'Login failed' }));
                throw new Error(err.detail || 'Invalid credentials');
            }

            const data = await response.json();
            setAdminToken(data.access_token);
            return data;
        },
    });
}

// ============================================================================
// DASHBOARD
// ============================================================================

export function useAdminDashboardStats() {
    return useQuery<DashboardStats>({
        queryKey: ['admin', 'dashboard', 'stats'],
        queryFn: () => adminFetch('/dashboard/stats'),
        staleTime: 30_000,
        enabled: isAdminAuthenticated(),
    });
}

// ============================================================================
// USERS
// ============================================================================

export function useAdminUsers(params: {
    role?: string;
    search?: string;
    page?: number;
    per_page?: number;
} = {}) {
    const { role, search, page = 1, per_page = 20 } = params;
    const queryParams = new URLSearchParams();
    if (role) queryParams.set('role', role);
    if (search) queryParams.set('search', search);
    queryParams.set('page', String(page));
    queryParams.set('per_page', String(per_page));

    return useQuery<PaginatedResponse<AdminUser>>({
        queryKey: ['admin', 'users', role, search, page],
        queryFn: () => adminFetch(`/users?${queryParams}`),
        staleTime: 15_000,
        enabled: isAdminAuthenticated(),
    });
}

export function useAdminUserDetail(userId: string | null) {
    return useQuery({
        queryKey: ['admin', 'user', userId],
        queryFn: () => adminFetch(`/users/${userId}`),
        enabled: !!userId && isAdminAuthenticated(),
    });
}

export function useAdminBanUser() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ userId, reason }: { userId: string; reason: string }) =>
            adminFetch(`/users/${userId}/ban`, {
                method: 'PATCH',
                body: JSON.stringify({ reason }),
            }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'users'] }),
        onError: (err: Error) => { toast.error(err.message || 'Failed to ban user'); },
    });
}

export function useAdminUnbanUser() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (userId: string) =>
            adminFetch(`/users/${userId}/unban`, { method: 'PATCH' }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'users'] }),
        onError: (err: Error) => { toast.error(err.message || 'Failed to unban user'); },
    });
}

export function useAdminDeleteUser() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ userId, reason }: { userId: string; reason: string }) =>
            adminFetch(`/users/${userId}`, {
                method: 'DELETE',
                body: JSON.stringify({ reason }),
            }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'users'] }),
        onError: (err: Error) => { toast.error(err.message || 'Failed to delete user'); },
    });
}

export function useAdminUpdateRole() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ userId, new_role, reason }: { userId: string; new_role: string; reason: string }) =>
            adminFetch(`/users/${userId}/role`, {
                method: 'PATCH',
                body: JSON.stringify({ new_role, reason }),
            }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'users'] }),
        onError: (err: Error) => { toast.error(err.message || 'Failed to update role'); },
    });
}

// ============================================================================
// REPORTS
// ============================================================================

export function useAdminReports(params: {
    status?: string;
    search?: string;
    page?: number;
    per_page?: number;
} = {}) {
    const { status, search, page = 1, per_page = 20 } = params;
    const queryParams = new URLSearchParams();
    if (status) queryParams.set('status', status);
    if (search) queryParams.set('search', search);
    queryParams.set('page', String(page));
    queryParams.set('per_page', String(per_page));

    return useQuery<PaginatedResponse<AdminReport>>({
        queryKey: ['admin', 'reports', status, search, page],
        queryFn: () => adminFetch(`/reports?${queryParams}`),
        staleTime: 15_000,
        enabled: isAdminAuthenticated(),
    });
}

export function useAdminVerifyReport() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ reportId, verified, reason }: { reportId: string; verified: boolean; reason?: string }) =>
            adminFetch(`/reports/${reportId}/verify`, {
                method: 'PATCH',
                body: JSON.stringify({ verified, reason }),
            }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'reports'] }),
        onError: (err: Error) => { toast.error(err.message || 'Failed to verify report'); },
    });
}

export function useAdminArchiveReport() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (reportId: string) =>
            adminFetch(`/reports/${reportId}/archive`, { method: 'PATCH' }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'reports'] }),
        onError: (err: Error) => { toast.error(err.message || 'Failed to archive report'); },
    });
}

export function useAdminDeleteReport() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ reportId, reason }: { reportId: string; reason: string }) =>
            adminFetch(`/reports/${reportId}`, {
                method: 'DELETE',
                body: JSON.stringify({ reason }),
            }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'reports'] }),
        onError: (err: Error) => { toast.error(err.message || 'Failed to delete report'); },
    });
}

export function useAdminVerifyReportWithNotes() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (args: { reportId: string; verified: boolean; quality_score: number; notes?: string }) =>
            apiBaseFetch(`/reports/${args.reportId}/verify`, {
                method: 'PATCH',
                body: JSON.stringify({
                    verified: args.verified,
                    quality_score: args.quality_score,
                    notes: args.notes,
                }),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['admin', 'reports'] });
            toast.success('Report verification updated');
        },
        onError: (err: Error) => {
            toast.error(err.message || 'Failed to update verification');
        },
    });
}

export interface AdminCreateReportRequest {
    description: string;
    latitude: number;
    longitude: number;
    city: string;
    water_depth?: string;
    vehicle_passability?: string;
    source: string;
    admin_notes?: string;
}

export function useAdminCreateReport() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (data: AdminCreateReportRequest) =>
            adminFetch('/reports', {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['admin', 'reports'] });
            toast.success('Report created successfully');
        },
        onError: (err: Error) => {
            toast.error(err.message || 'Failed to create report');
        },
    });
}

// ============================================================================
// BADGES
// ============================================================================

export function useAdminBadges() {
    return useQuery<AdminBadge[]>({
        queryKey: ['admin', 'badges'],
        queryFn: () => adminFetch('/badges'),
        staleTime: 60_000,
        enabled: isAdminAuthenticated(),
    });
}

export function useAdminCreateBadge() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (badge: Omit<AdminBadge, 'id' | 'is_active'>) =>
            adminFetch('/badges', {
                method: 'POST',
                body: JSON.stringify(badge),
            }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'badges'] }),
        onError: (err: Error) => { toast.error(err.message || 'Failed to create badge'); },
    });
}

export function useAdminAwardBadge() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ user_id, badge_id }: { user_id: string; badge_id: string }) =>
            adminFetch('/badges/award', {
                method: 'POST',
                body: JSON.stringify({ user_id, badge_id }),
            }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['admin'] }),
        onError: (err: Error) => { toast.error(err.message || 'Failed to award badge'); },
    });
}

// ============================================================================
// AMBASSADORS
// ============================================================================

export function useAdminAmbassadors(minReputation = 50) {
    return useQuery<AdminUser[]>({
        queryKey: ['admin', 'ambassadors', minReputation],
        queryFn: () => adminFetch(`/ambassadors?min_reputation=${minReputation}`),
        staleTime: 30_000,
        enabled: isAdminAuthenticated(),
    });
}

export function useAdminPromoteAmbassador() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (userId: string) =>
            adminFetch(`/ambassadors/${userId}/promote`, { method: 'POST' }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['admin', 'ambassadors'] });
            qc.invalidateQueries({ queryKey: ['admin', 'users'] });
        },
        onError: (err: Error) => { toast.error(err.message || 'Failed to promote ambassador'); },
    });
}

// ============================================================================
// ANALYTICS
// ============================================================================

export function useAdminAnalyticsReports(days = 30) {
    return useQuery<AnalyticsData>({
        queryKey: ['admin', 'analytics', 'reports', days],
        queryFn: () => adminFetch(`/analytics/reports?days=${days}`),
        staleTime: 60_000,
        enabled: isAdminAuthenticated(),
    });
}

export function useAdminAnalyticsUsers(days = 30) {
    return useQuery<AnalyticsData>({
        queryKey: ['admin', 'analytics', 'users', days],
        queryFn: () => adminFetch(`/analytics/users?days=${days}`),
        staleTime: 60_000,
        enabled: isAdminAuthenticated(),
    });
}

export function useAdminAnalyticsCities() {
    return useQuery({
        queryKey: ['admin', 'analytics', 'cities'],
        queryFn: () => adminFetch('/analytics/cities'),
        staleTime: 60_000,
        enabled: isAdminAuthenticated(),
    });
}

// ============================================================================
// SYSTEM & AUDIT
// ============================================================================

export function useAdminSystemHealth() {
    return useQuery({
        queryKey: ['admin', 'system', 'health'],
        queryFn: () => adminFetch('/system/health'),
        staleTime: 10_000,
        enabled: isAdminAuthenticated(),
    });
}

export function useAdminAuditLog(page = 1, perPage = 50) {
    return useQuery<PaginatedResponse<AuditLogEntry>>({
        queryKey: ['admin', 'audit-log', page],
        queryFn: () => adminFetch(`/audit-log?page=${page}&per_page=${perPage}`),
        staleTime: 15_000,
        enabled: isAdminAuthenticated(),
    });
}

// ============================================================================
// INVITES
// ============================================================================

export interface AdminInvite {
    id: string;
    code: string;
    email_hint: string | null;
    created_by_username: string;
    used_by_username: string | null;
    expires_at: string;
    created_at: string;
    is_expired: boolean;
    is_used: boolean;
}

export interface CreateInviteResponse {
    code: string;
    invite_url: string;
    email_hint: string | null;
    expires_at: string;
}

export function useAdminInvites() {
    return useQuery<AdminInvite[]>({
        queryKey: ['admin', 'invites'],
        queryFn: () => adminFetch('/invites'),
        staleTime: 15_000,
        enabled: isAdminAuthenticated(),
    });
}

export function useAdminCreateInvite() {
    const qc = useQueryClient();
    return useMutation<CreateInviteResponse, Error, { email_hint?: string }>({
        mutationFn: (data) =>
            adminFetch('/invites', {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['admin', 'invites'] });
            toast.success('Invite created');
        },
        onError: (err) => { toast.error(err.message || 'Failed to create invite'); },
    });
}

export function useAdminRevokeInvite() {
    const qc = useQueryClient();
    return useMutation<unknown, Error, string>({
        mutationFn: (code) =>
            adminFetch(`/invites/${code}`, { method: 'DELETE' }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['admin', 'invites'] });
            toast.success('Invite revoked');
        },
        onError: (err) => { toast.error(err.message || 'Failed to revoke invite'); },
    });
}

export function useAdminRegister() {
    return useMutation({
        mutationFn: async (data: { code: string; email: string; password: string }) => {
            const response = await fetch(`${API_BASE_URL}/admin/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({ detail: 'Registration failed' }));
                throw new Error(err.detail || 'Registration failed');
            }
            return response.json();
        },
    });
}
