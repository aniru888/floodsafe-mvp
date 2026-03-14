import { useState, useEffect } from 'react';
import '../../styles/admin.css';

/** Parse backend timestamps (stored without 'Z' suffix) as UTC */
const parseUTC = (ts: string | null | undefined): Date | null => {
    if (!ts) return null;
    if (!ts.endsWith('Z') && !ts.includes('+')) return new Date(ts + 'Z');
    return new Date(ts);
};
import { useNavigate } from 'react-router-dom';
import {
    Shield, Users, FileText, Award, BarChart3, Settings, LogOut,
    Search, ChevronLeft, ChevronRight, CheckCircle, XCircle,
    Archive, Trash2, Ban, UserPlus, Star, Activity, Globe,
    RefreshCw, Eye, AlertTriangle, TrendingUp, Loader2,
    Clock, Database, Wifi, ChevronDown, Link2, Copy, UserPlus2
} from 'lucide-react';
import {
    isAdminAuthenticated, clearAdminToken,
    useAdminDashboardStats, useAdminUsers, useAdminReports,
    useAdminBadges, useAdminAmbassadors, useAdminAuditLog,
    useAdminSystemHealth, useAdminAnalyticsReports, useAdminAnalyticsUsers,
    useAdminBanUser, useAdminUnbanUser, useAdminDeleteUser,
    useAdminUpdateRole, useAdminVerifyReportWithNotes,
    useAdminArchiveReport,
    useAdminDeleteReport, useAdminCreateReport, useAdminCreateBadge,
    useAdminAwardBadge, useAdminPromoteAmbassador,
    useAdminInvites, useAdminCreateInvite, useAdminRevokeInvite,
    useAdminClusters, useAdminPromoteCluster, useAdminDismissCluster, useAdminPins,
    type AdminUser, type AdminReport, type AdminBadge,
    type AdminCreateReportRequest, type AdminInvite as AdminInviteType,
    type AdminCluster, type AdminPin,
} from '../../lib/api/admin-hooks';

type AdminTab = 'overview' | 'users' | 'reports' | 'badges' | 'analytics' | 'system' | 'discovery' | 'pins';

export function AdminDashboard() {
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState<AdminTab>('overview');

    useEffect(() => {
        if (!isAdminAuthenticated()) {
            navigate('/admin/login', { replace: true });
        }
    }, [navigate]);

    const handleLogout = () => {
        clearAdminToken();
        navigate('/admin/login', { replace: true });
    };

    const tabs: { key: AdminTab; label: string; icon: React.ReactNode }[] = [
        { key: 'overview', label: 'Overview', icon: <Activity size={18} /> },
        { key: 'users', label: 'Users', icon: <Users size={18} /> },
        { key: 'reports', label: 'Reports', icon: <FileText size={18} /> },
        { key: 'badges', label: 'Badges', icon: <Award size={18} /> },
        { key: 'analytics', label: 'Analytics', icon: <BarChart3 size={18} /> },
        { key: 'system', label: 'System', icon: <Settings size={18} /> },
        { key: 'discovery', label: 'Discovery', icon: <Globe size={18} /> },
        { key: 'pins', label: 'Pins', icon: <Eye size={18} /> },
    ];

    return (
        <div className="admin-layout">
            {/* Sidebar */}
            <aside className="admin-sidebar">
                <div className="admin-sidebar-header">
                    <Shield size={24} />
                    <span>FloodSafe Admin</span>
                </div>
                <nav className="admin-sidebar-nav">
                    {tabs.map(tab => (
                        <button
                            key={tab.key}
                            className={`admin-nav-item ${activeTab === tab.key ? 'active' : ''}`}
                            onClick={() => setActiveTab(tab.key)}
                        >
                            {tab.icon}
                            <span>{tab.label}</span>
                        </button>
                    ))}
                </nav>
                <div className="admin-sidebar-footer">
                    <button className="admin-nav-item admin-logout-btn" onClick={handleLogout}>
                        <LogOut size={18} />
                        <span>Logout</span>
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="admin-main">
                <div className="admin-topbar">
                    <h1 className="admin-page-title">
                        {tabs.find(t => t.key === activeTab)?.icon}
                        {tabs.find(t => t.key === activeTab)?.label}
                    </h1>
                    <a href="/app" className="admin-back-to-app">← Back to App</a>
                </div>
                <div className="admin-content">
                    {activeTab === 'overview' && <OverviewPanel />}
                    {activeTab === 'users' && <UsersPanel />}
                    {activeTab === 'reports' && <ReportsPanel />}
                    {activeTab === 'badges' && <BadgesPanel />}
                    {activeTab === 'analytics' && <AnalyticsPanel />}
                    {activeTab === 'system' && <SystemPanel />}
                    {activeTab === 'discovery' && <DiscoveryPanel />}
                    {activeTab === 'pins' && <PinsPanel />}
                </div>
            </main>
        </div>
    );
}

// =============================================================================
// OVERVIEW PANEL
// =============================================================================

function OverviewPanel() {
    const { data: stats, isLoading } = useAdminDashboardStats();

    if (isLoading) return <LoadingSpinner />;

    return (
        <div className="admin-overview">
            <div className="admin-kpi-grid">
                <KPICard
                    title="Total Users"
                    value={stats?.users.total ?? 0}
                    subtitle={`+${stats?.users.new_7d ?? 0} this week`}
                    icon={<Users size={24} />}
                    color="blue"
                />
                <KPICard
                    title="Total Reports"
                    value={stats?.reports.total ?? 0}
                    subtitle={`+${stats?.reports.new_7d ?? 0} this week`}
                    icon={<FileText size={24} />}
                    color="emerald"
                />
                <KPICard
                    title="Pending Verification"
                    value={stats?.reports.pending_verification ?? 0}
                    subtitle={`${stats?.reports.verified ?? 0} verified`}
                    icon={<AlertTriangle size={24} />}
                    color="amber"
                />
                <KPICard
                    title="Active Reporters"
                    value={stats?.users.active_reporters_7d ?? 0}
                    subtitle="Last 7 days"
                    icon={<TrendingUp size={24} />}
                    color="purple"
                />
                <KPICard
                    title="Safety Circles"
                    value={stats?.community.safety_circles ?? 0}
                    subtitle="Active groups"
                    icon={<Globe size={24} />}
                    color="cyan"
                />
                <KPICard
                    title="Badges Awarded"
                    value={stats?.community.badges_awarded ?? 0}
                    subtitle={`${stats?.community.comments ?? 0} comments`}
                    icon={<Award size={24} />}
                    color="rose"
                />
            </div>

            {/* Role Distribution */}
            {stats?.users.roles && (
                <div className="admin-card">
                    <h3 className="admin-card-title">User Roles Distribution</h3>
                    <div className="admin-role-grid">
                        {Object.entries(stats.users.roles).map(([role, count]) => (
                            <div key={role} className="admin-role-item">
                                <span className={`admin-role-badge admin-role-${role}`}>{role}</span>
                                <span className="admin-role-count">{count as number}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// =============================================================================
// USERS PANEL
// =============================================================================

function UsersPanel() {
    const [search, setSearch] = useState('');
    const [roleFilter, setRoleFilter] = useState('');
    const [page, setPage] = useState(1);
    const [searchInput, setSearchInput] = useState('');

    const { data, isLoading } = useAdminUsers({ role: roleFilter || undefined, search: search || undefined, page });
    const banMutation = useAdminBanUser();
    const unbanMutation = useAdminUnbanUser();
    const deleteMutation = useAdminDeleteUser();
    const roleMutation = useAdminUpdateRole();

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        setSearch(searchInput);
        setPage(1);
    };

    const handleBan = (user: AdminUser) => {
        const reason = prompt(`Reason for banning ${user.username}:`);
        if (reason && reason.length >= 5) {
            banMutation.mutate({ userId: user.id, reason });
        } else if (reason) {
            alert('Reason must be at least 5 characters');
        }
    };

    const handleUnban = (user: AdminUser) => {
        if (confirm(`Unban ${user.username}?`)) {
            unbanMutation.mutate(user.id);
        }
    };

    const handleDelete = (user: AdminUser) => {
        const reason = prompt(`Reason for deleting ${user.username} (this is permanent!):`);
        if (reason && reason.length >= 5) {
            if (confirm(`Are you sure you want to permanently delete ${user.username}? This cannot be undone.`)) {
                deleteMutation.mutate({ userId: user.id, reason });
            }
        } else if (reason) {
            alert('Reason must be at least 5 characters');
        }
    };

    const handleRoleChange = (user: AdminUser) => {
        const newRole = prompt(`New role for ${user.username}? (user, verified_reporter, moderator, admin)`);
        if (newRole && ['user', 'verified_reporter', 'moderator', 'admin'].includes(newRole)) {
            const reason = prompt('Reason for role change:');
            if (reason && reason.length >= 5) {
                roleMutation.mutate({ userId: user.id, new_role: newRole, reason });
            } else if (reason) {
                alert('Reason must be at least 5 characters');
            }
        } else if (newRole) {
            alert('Invalid role');
        }
    };

    const users = data?.users ?? [];

    return (
        <div className="admin-panel">
            <div className="admin-panel-header">
                <form onSubmit={handleSearch} className="admin-search-bar">
                    <Search size={18} />
                    <input
                        type="text"
                        placeholder="Search users by name or email..."
                        value={searchInput}
                        onChange={e => setSearchInput(e.target.value)}
                    />
                    <button type="submit" className="admin-search-btn">Search</button>
                </form>
                <select
                    className="admin-filter-select"
                    value={roleFilter}
                    onChange={e => { setRoleFilter(e.target.value); setPage(1); }}
                >
                    <option value="">All Roles</option>
                    <option value="user">User</option>
                    <option value="verified_reporter">Verified Reporter</option>
                    <option value="moderator">Moderator</option>
                    <option value="admin">Admin</option>
                    <option value="banned">Banned</option>
                </select>
            </div>

            {isLoading ? <LoadingSpinner /> : (
                <>
                    <div className="admin-table-container">
                        <table className="admin-table">
                            <thead>
                                <tr>
                                    <th>User</th>
                                    <th>Role</th>
                                    <th>Rep</th>
                                    <th>Reports</th>
                                    <th>City</th>
                                    <th>Joined</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((user: AdminUser) => (
                                    <tr key={user.id}>
                                        <td>
                                            <div className="admin-user-cell">
                                                <div className="admin-user-avatar">
                                                    {user.profile_photo_url
                                                        ? <img src={user.profile_photo_url} alt="" />
                                                        : <span>{(user.username || '?')[0].toUpperCase()}</span>
                                                    }
                                                </div>
                                                <div>
                                                    <div className="admin-user-name">{user.username}</div>
                                                    <div className="admin-user-email">{user.email}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td><span className={`admin-role-badge admin-role-${user.role}`}>{user.role}</span></td>
                                        <td>{user.reputation_score}</td>
                                        <td>{user.reports_count}</td>
                                        <td>{user.city_preference || '—'}</td>
                                        <td>{parseUTC(user.created_at)?.toLocaleDateString() ?? '—'}</td>
                                        <td>
                                            <div className="admin-action-btns">
                                                <button onClick={() => handleRoleChange(user)} title="Change Role" className="admin-action-btn admin-action-role">
                                                    <UserPlus size={14} />
                                                </button>
                                                {user.role === 'banned' ? (
                                                    <button onClick={() => handleUnban(user)} title="Unban" className="admin-action-btn admin-action-unban">
                                                        <CheckCircle size={14} />
                                                    </button>
                                                ) : user.role !== 'admin' ? (
                                                    <button onClick={() => handleBan(user)} title="Ban" className="admin-action-btn admin-action-ban">
                                                        <Ban size={14} />
                                                    </button>
                                                ) : null}
                                                {user.role !== 'admin' && (
                                                    <button onClick={() => handleDelete(user)} title="Delete" className="admin-action-btn admin-action-delete">
                                                        <Trash2 size={14} />
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                                {users.length === 0 && (
                                    <tr><td colSpan={7} className="admin-empty-row">No users found</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                    <Pagination page={page} totalPages={data?.total_pages ?? 1} onPageChange={setPage} />
                </>
            )}
        </div>
    );
}

// =============================================================================
// REPORTS PANEL
// =============================================================================

function ReportsPanel() {
    const [reportFilter, setReportFilter] = useState<'pending' | 'verified' | 'rejected' | 'all'>('pending');
    const [search, setSearch] = useState('');
    const [searchInput, setSearchInput] = useState('');
    const [page, setPage] = useState(1);
    const [showCreateReport, setShowCreateReport] = useState(false);
    const [newReport, setNewReport] = useState<AdminCreateReportRequest>({
        description: '',
        latitude: 0,
        longitude: 0,
        city: 'delhi',
        source: 'field_observation',
    });

    const reportStatus = reportFilter === 'pending' ? 'unverified'
        : reportFilter === 'verified' ? 'verified'
        : reportFilter === 'rejected' ? 'archived'
        : undefined;

    const { data, isLoading } = useAdminReports({ status: reportStatus, search: search || undefined, page });
    const verifyMutation = useAdminVerifyReportWithNotes();
    const archiveMutation = useAdminArchiveReport();
    const deleteMutation = useAdminDeleteReport();
    const createReportMutation = useAdminCreateReport();

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        setSearch(searchInput);
        setPage(1);
    };

    const handleVerify = (report: AdminReport) => {
        const quality = prompt('Quality score (0-100):', '75');
        const notes = prompt('Verification notes (optional):');
        if (quality !== null) {
            verifyMutation.mutate({
                reportId: report.id,
                verified: true,
                quality_score: parseInt(quality) || 75,
                notes: notes || undefined,
            });
        }
    };

    const handleReject = (report: AdminReport) => {
        const reason = prompt('Rejection reason (required):');
        if (reason && reason.length >= 5) {
            verifyMutation.mutate({
                reportId: report.id,
                verified: false,
                quality_score: 0,
                notes: reason,
            });
        } else if (reason) {
            alert('Reason must be at least 5 characters');
        }
    };

    const handleArchive = (report: AdminReport) => {
        if (confirm('Archive this report?')) {
            archiveMutation.mutate(report.id);
        }
    };

    const handleDelete = (report: AdminReport) => {
        const reason = prompt('Reason for deleting this report (permanent!):');
        if (reason && reason.length >= 5) {
            if (confirm('Are you sure? This cannot be undone.')) {
                deleteMutation.mutate({ reportId: report.id, reason });
            }
        } else if (reason) {
            alert('Reason must be at least 5 characters');
        }
    };

    const reports = data?.reports ?? [];

    return (
        <div className="admin-panel">
            <div className="admin-panel-header">
                <form onSubmit={handleSearch} className="admin-search-bar">
                    <Search size={18} />
                    <input
                        type="text"
                        placeholder="Search report descriptions..."
                        value={searchInput}
                        onChange={e => setSearchInput(e.target.value)}
                    />
                    <button type="submit" className="admin-search-btn">Search</button>
                </form>
                <div className="admin-tabs" style={{ display: 'flex', gap: '0.5rem' }}>
                    {(['pending', 'verified', 'rejected', 'all'] as const).map(tab => (
                        <button
                            key={tab}
                            className={`admin-btn ${reportFilter === tab ? 'admin-btn-primary' : ''}`}
                            onClick={() => { setReportFilter(tab); setPage(1); }}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                    ))}
                </div>
                <button
                    className="admin-btn admin-btn-primary"
                    onClick={() => setShowCreateReport(!showCreateReport)}
                >
                    {showCreateReport ? '✕ Cancel' : '+ Create Report'}
                </button>
            </div>

            {showCreateReport && (
                <div className="admin-card" style={{ marginBottom: '1rem' }}>
                    <h4>Create Official Report</h4>
                    <div style={{ display: 'grid', gap: '0.75rem' }}>
                        <textarea
                            className="admin-input"
                            placeholder="Description (10-500 chars)"
                            value={newReport.description}
                            onChange={e => setNewReport(p => ({ ...p, description: e.target.value }))}
                            rows={3}
                        />
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem' }}>
                            <select
                                className="admin-input"
                                value={newReport.city}
                                onChange={e => setNewReport(p => ({ ...p, city: e.target.value }))}
                            >
                                <option value="delhi">Delhi</option>
                                <option value="bangalore">Bangalore</option>
                                <option value="yogyakarta">Yogyakarta</option>
                                <option value="singapore">Singapore</option>
                                <option value="indore">Indore</option>
                            </select>
                            <input
                                className="admin-input"
                                type="number"
                                step="0.0001"
                                placeholder="Latitude"
                                value={newReport.latitude || ''}
                                onChange={e => setNewReport(p => ({ ...p, latitude: parseFloat(e.target.value) || 0 }))}
                            />
                            <input
                                className="admin-input"
                                type="number"
                                step="0.0001"
                                placeholder="Longitude"
                                value={newReport.longitude || ''}
                                onChange={e => setNewReport(p => ({ ...p, longitude: parseFloat(e.target.value) || 0 }))}
                            />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem' }}>
                            <select
                                className="admin-input"
                                value={newReport.source}
                                onChange={e => setNewReport(p => ({ ...p, source: e.target.value }))}
                            >
                                <option value="field_observation">Field Observation</option>
                                <option value="government_data">Government Data</option>
                                <option value="phone_report">Phone Report</option>
                            </select>
                            <select
                                className="admin-input"
                                value={newReport.water_depth || ''}
                                onChange={e => setNewReport(p => ({ ...p, water_depth: e.target.value || undefined }))}
                            >
                                <option value="">Water Depth (optional)</option>
                                <option value="ankle">Ankle</option>
                                <option value="knee">Knee</option>
                                <option value="waist">Waist</option>
                                <option value="chest">Chest</option>
                            </select>
                            <select
                                className="admin-input"
                                value={newReport.vehicle_passability || ''}
                                onChange={e => setNewReport(p => ({ ...p, vehicle_passability: e.target.value || undefined }))}
                            >
                                <option value="">Passability (optional)</option>
                                <option value="all">All Vehicles</option>
                                <option value="large_vehicles">Large Only</option>
                                <option value="none">None</option>
                            </select>
                        </div>
                        <textarea
                            className="admin-input"
                            placeholder="Admin notes (optional)"
                            value={newReport.admin_notes || ''}
                            onChange={e => setNewReport(p => ({ ...p, admin_notes: e.target.value || undefined }))}
                            rows={2}
                        />
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <button
                                className="admin-btn admin-btn-primary"
                                disabled={createReportMutation.isPending || newReport.description.length < 10}
                                onClick={() => createReportMutation.mutate(newReport, {
                                    onSuccess: () => {
                                        setShowCreateReport(false);
                                        setNewReport({ description: '', latitude: 0, longitude: 0, city: 'delhi', source: 'field_observation' });
                                    },
                                })}
                            >
                                {createReportMutation.isPending ? 'Creating...' : 'Create Report'}
                            </button>
                            <button
                                className="admin-btn"
                                onClick={() => setShowCreateReport(false)}
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {isLoading ? <LoadingSpinner /> : (
                <>
                    <div className="admin-table-container">
                        <table className="admin-table">
                            <thead>
                                <tr>
                                    <th>Description</th>
                                    <th>Status</th>
                                    <th>Votes</th>
                                    <th>Depth</th>
                                    <th>Date</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {reports.map((report: AdminReport) => (
                                    <tr key={report.id}>
                                        <td>
                                            <div className="admin-report-desc">
                                                {report.media_url && (
                                                    <img src={report.media_url} alt="" className="admin-report-thumb" />
                                                )}
                                                <span>{report.description?.slice(0, 80)}{(report.description?.length ?? 0) > 80 ? '...' : ''}</span>
                                            </div>
                                        </td>
                                        <td>
                                            {report.archived_at ? (
                                                <span className="admin-status-badge admin-status-archived">Archived</span>
                                            ) : report.verified ? (
                                                <span className="admin-status-badge admin-status-verified">Verified</span>
                                            ) : (
                                                <span className="admin-status-badge admin-status-pending">Pending</span>
                                            )}
                                        </td>
                                        <td>
                                            <span className="admin-votes">+{report.upvotes} / -{report.downvotes}</span>
                                        </td>
                                        <td>{report.water_depth || '—'}</td>
                                        <td>{parseUTC(report.timestamp)?.toLocaleDateString() ?? '—'}</td>
                                        <td>
                                            <div className="admin-action-btns">
                                                {!report.verified && !report.archived_at && (
                                                    <button onClick={() => handleVerify(report)} title="Verify" className="admin-action-btn admin-action-verify">
                                                        <CheckCircle size={14} />
                                                    </button>
                                                )}
                                                {!report.archived_at && (
                                                    <button onClick={() => handleReject(report)} title="Reject" className="admin-action-btn admin-action-reject">
                                                        <XCircle size={14} />
                                                    </button>
                                                )}
                                                {!report.archived_at && (
                                                    <button onClick={() => handleArchive(report)} title="Archive" className="admin-action-btn admin-action-archive">
                                                        <Archive size={14} />
                                                    </button>
                                                )}
                                                <button onClick={() => handleDelete(report)} title="Delete" className="admin-action-btn admin-action-delete">
                                                    <Trash2 size={14} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                                {reports.length === 0 && (
                                    <tr><td colSpan={6} className="admin-empty-row">No reports found</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                    <Pagination page={page} totalPages={data?.total_pages ?? 1} onPageChange={setPage} />
                </>
            )}
        </div>
    );
}

// =============================================================================
// BADGES PANEL
// =============================================================================

function BadgesPanel() {
    const { data: badges, isLoading: badgesLoading } = useAdminBadges();
    const { data: ambassadors, isLoading: ambassadorsLoading } = useAdminAmbassadors();
    const createBadgeMutation = useAdminCreateBadge();
    const awardBadgeMutation = useAdminAwardBadge();
    const promoteMutation = useAdminPromoteAmbassador();
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [newBadge, setNewBadge] = useState({
        key: '', name: '', description: '', icon: '🏆',
        category: 'achievement', requirement_type: 'manual',
        requirement_value: 0, points_reward: 10,
    });

    const handleCreateBadge = (e: React.FormEvent) => {
        e.preventDefault();
        createBadgeMutation.mutate(newBadge, {
            onSuccess: () => {
                setShowCreateForm(false);
                setNewBadge({ key: '', name: '', description: '', icon: '🏆', category: 'achievement', requirement_type: 'manual', requirement_value: 0, points_reward: 10 });
            }
        });
    };

    const handleAwardBadge = (badge: AdminBadge) => {
        const userId = prompt(`Enter user ID to award "${badge.name}" badge to:`);
        if (userId) {
            awardBadgeMutation.mutate({ user_id: userId, badge_id: badge.id });
        }
    };

    const handlePromote = (user: AdminUser) => {
        if (confirm(`Promote ${user.username} to Ambassador (Verified Reporter)?`)) {
            promoteMutation.mutate(user.id);
        }
    };

    return (
        <div className="admin-panel">
            {/* Badges Section */}
            <div className="admin-card">
                <div className="admin-card-header">
                    <h3 className="admin-card-title"><Award size={18} /> Badges</h3>
                    <button className="admin-btn admin-btn-primary" onClick={() => setShowCreateForm(!showCreateForm)}>
                        + New Badge
                    </button>
                </div>

                {showCreateForm && (
                    <form onSubmit={handleCreateBadge} className="admin-create-form">
                        <div className="admin-form-row">
                            <input placeholder="Key (e.g. flood_hero)" value={newBadge.key} onChange={e => setNewBadge({ ...newBadge, key: e.target.value })} required />
                            <input placeholder="Name" value={newBadge.name} onChange={e => setNewBadge({ ...newBadge, name: e.target.value })} required />
                            <input placeholder="Icon emoji" value={newBadge.icon} onChange={e => setNewBadge({ ...newBadge, icon: e.target.value })} style={{ width: '60px' }} />
                        </div>
                        <div className="admin-form-row">
                            <input placeholder="Description" value={newBadge.description} onChange={e => setNewBadge({ ...newBadge, description: e.target.value })} style={{ flex: 2 }} />
                            <input type="number" placeholder="Points Reward" value={newBadge.points_reward} onChange={e => setNewBadge({ ...newBadge, points_reward: parseInt(e.target.value) || 0 })} style={{ width: '120px' }} />
                            <button type="submit" className="admin-btn admin-btn-primary" disabled={createBadgeMutation.isPending}>
                                {createBadgeMutation.isPending ? 'Creating...' : 'Create'}
                            </button>
                        </div>
                    </form>
                )}

                {badgesLoading ? <LoadingSpinner /> : (
                    <div className="admin-badge-grid">
                        {(badges ?? []).map((badge: AdminBadge) => (
                            <div key={badge.id} className={`admin-badge-card ${!badge.is_active ? 'inactive' : ''}`}>
                                <div className="admin-badge-icon">{badge.icon}</div>
                                <div className="admin-badge-info">
                                    <div className="admin-badge-name">{badge.name}</div>
                                    <div className="admin-badge-desc">{badge.description}</div>
                                    <div className="admin-badge-meta">
                                        {badge.category} • {badge.points_reward} pts
                                    </div>
                                </div>
                                <button className="admin-btn admin-btn-sm" onClick={() => handleAwardBadge(badge)} title="Award to user">
                                    <Star size={14} /> Award
                                </button>
                            </div>
                        ))}
                        {(badges ?? []).length === 0 && <p className="admin-empty-text">No badges created yet</p>}
                    </div>
                )}
            </div>

            {/* Ambassador Candidates */}
            <div className="admin-card" style={{ marginTop: '1.5rem' }}>
                <h3 className="admin-card-title"><UserPlus size={18} /> Ambassador Candidates</h3>
                <p className="admin-card-subtitle">Users with high reputation who can be promoted to Verified Reporter</p>

                {ambassadorsLoading ? <LoadingSpinner /> : (
                    <div className="admin-table-container">
                        <table className="admin-table">
                            <thead>
                                <tr>
                                    <th>User</th>
                                    <th>Reputation</th>
                                    <th>Reports</th>
                                    <th>Level</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(ambassadors ?? []).map((user: AdminUser) => (
                                    <tr key={user.id}>
                                        <td>
                                            <div className="admin-user-cell">
                                                <div className="admin-user-avatar">
                                                    <span>{(user.username || '?')[0].toUpperCase()}</span>
                                                </div>
                                                <div>
                                                    <div className="admin-user-name">{user.username}</div>
                                                    <div className="admin-user-email">{user.email}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td><span className="admin-rep-score">{user.reputation_score}</span></td>
                                        <td>{user.reports_count}</td>
                                        <td>{user.level}</td>
                                        <td>
                                            <button className="admin-btn admin-btn-primary admin-btn-sm" onClick={() => handlePromote(user)}>
                                                <UserPlus size={14} /> Promote
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                {(ambassadors ?? []).length === 0 && (
                                    <tr><td colSpan={5} className="admin-empty-row">No candidates meet the criteria yet</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// ANALYTICS PANEL
// =============================================================================

function AnalyticsPanel() {
    const [days, setDays] = useState(30);
    const { data: reportData, isLoading: reportsLoading } = useAdminAnalyticsReports(days);
    const { data: userData, isLoading: usersLoading } = useAdminAnalyticsUsers(days);

    return (
        <div className="admin-panel">
            <div className="admin-panel-header">
                <h3>Platform Analytics</h3>
                <select className="admin-filter-select" value={days} onChange={e => setDays(parseInt(e.target.value))}>
                    <option value={7}>Last 7 days</option>
                    <option value={30}>Last 30 days</option>
                    <option value={90}>Last 90 days</option>
                </select>
            </div>

            <div className="admin-analytics-grid">
                {/* Reports Chart */}
                <div className="admin-card">
                    <h3 className="admin-card-title"><FileText size={18} /> Reports Over Time</h3>
                    {reportsLoading ? <LoadingSpinner /> : (
                        <div className="admin-chart">
                            {(reportData?.daily ?? []).length > 0 ? (
                                <div className="admin-bar-chart">
                                    {reportData!.daily.map((d, i) => {
                                        const maxCount = Math.max(...reportData!.daily.map(x => x.count), 1);
                                        return (
                                            <div key={i} className="admin-bar-col" title={`${d.date}: ${d.count} reports (${d.verified ?? 0} verified)`}>
                                                <div className="admin-bar-wrapper">
                                                    <div className="admin-bar" style={{ height: `${(d.count / maxCount) * 100}%` }} />
                                                    {(d.verified ?? 0) > 0 && (
                                                        <div className="admin-bar admin-bar-verified" style={{ height: `${((d.verified ?? 0) / maxCount) * 100}%` }} />
                                                    )}
                                                </div>
                                                {i % Math.ceil(reportData!.daily.length / 7) === 0 && (
                                                    <span className="admin-bar-label">{d.date.slice(5)}</span>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            ) : (
                                <p className="admin-empty-text">No data for this period</p>
                            )}
                            <div className="admin-chart-legend">
                                <span><span className="admin-legend-dot admin-legend-reports" /> Reports</span>
                                <span><span className="admin-legend-dot admin-legend-verified" /> Verified</span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Users Chart */}
                <div className="admin-card">
                    <h3 className="admin-card-title"><Users size={18} /> User Registrations</h3>
                    {usersLoading ? <LoadingSpinner /> : (
                        <div className="admin-chart">
                            {(userData?.daily ?? []).length > 0 ? (
                                <div className="admin-bar-chart">
                                    {userData!.daily.map((d, i) => {
                                        const maxCount = Math.max(...userData!.daily.map(x => x.count), 1);
                                        return (
                                            <div key={i} className="admin-bar-col" title={`${d.date}: ${d.count} users`}>
                                                <div className="admin-bar-wrapper">
                                                    <div className="admin-bar admin-bar-users" style={{ height: `${(d.count / maxCount) * 100}%` }} />
                                                </div>
                                                {i % Math.ceil(userData!.daily.length / 7) === 0 && (
                                                    <span className="admin-bar-label">{d.date.slice(5)}</span>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            ) : (
                                <p className="admin-empty-text">No data for this period</p>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// SYSTEM PANEL
// =============================================================================

function SystemPanel() {
    const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useAdminSystemHealth();
    const { data: auditData, isLoading: auditLoading } = useAdminAuditLog();
    const { data: invites, isLoading: invitesLoading } = useAdminInvites();
    const createInvite = useAdminCreateInvite();
    const revokeInvite = useAdminRevokeInvite();
    const [emailHint, setEmailHint] = useState('');
    const [copiedCode, setCopiedCode] = useState<string | null>(null);

    const healthData = health as Record<string, unknown> | undefined;
    const configData = healthData?.config as Record<string, boolean> | undefined;

    return (
        <div className="admin-panel">
            {/* Health Check */}
            <div className="admin-card">
                <div className="admin-card-header">
                    <h3 className="admin-card-title"><Activity size={18} /> System Health</h3>
                    <button className="admin-btn admin-btn-sm" onClick={() => refetchHealth()}>
                        <RefreshCw size={14} /> Refresh
                    </button>
                </div>

                {healthLoading ? <LoadingSpinner /> : healthData ? (
                    <div className="admin-health-grid">
                        <div className={`admin-health-item ${healthData.status === 'healthy' ? 'healthy' : 'degraded'}`}>
                            <Wifi size={18} />
                            <span>Status: {String(healthData.status)}</span>
                        </div>
                        <div className={`admin-health-item ${healthData.database === 'connected' ? 'healthy' : 'degraded'}`}>
                            <Database size={18} />
                            <span>Database: {String(healthData.database)}</span>
                        </div>
                        {configData && Object.entries(configData).map(([key, value]) => (
                            <div key={key} className={`admin-health-item ${value ? 'healthy' : 'neutral'}`}>
                                <Settings size={16} />
                                <span>{key.replace(/_/g, ' ')}: {value ? '✓' : '✗'}</span>
                            </div>
                        ))}
                    </div>
                ) : null}
            </div>

            {/* Admin Invites */}
            <div className="admin-card" style={{ marginTop: '1.5rem' }}>
                <div className="admin-card-header">
                    <h3 className="admin-card-title"><UserPlus2 size={18} /> Admin Invites</h3>
                </div>

                {/* Create invite */}
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', alignItems: 'center' }}>
                    <input
                        type="email"
                        className="admin-input"
                        placeholder="Email hint (optional — restrict to specific email)"
                        value={emailHint}
                        onChange={(e) => setEmailHint(e.target.value)}
                        style={{ flex: 1 }}
                    />
                    <button
                        className="admin-btn admin-btn-primary admin-btn-sm"
                        onClick={() => {
                            createInvite.mutate(
                                { email_hint: emailHint || undefined },
                                { onSuccess: () => setEmailHint('') }
                            );
                        }}
                        disabled={createInvite.isPending}
                    >
                        <Link2 size={14} /> Create Invite
                    </button>
                </div>

                {invitesLoading ? <LoadingSpinner /> : (
                    <div className="admin-table-container">
                        <table className="admin-table admin-table-compact">
                            <thead>
                                <tr>
                                    <th>Code</th>
                                    <th>Email Hint</th>
                                    <th>Created By</th>
                                    <th>Status</th>
                                    <th>Expires</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(invites ?? []).map((inv: AdminInviteType) => {
                                    const statusColor = inv.is_used ? '#6b7280' : inv.is_expired ? '#ef4444' : '#22c55e';
                                    const statusLabel = inv.is_used ? `Used by ${inv.used_by_username}` : inv.is_expired ? 'Expired' : 'Active';
                                    return (
                                        <tr key={inv.id}>
                                            <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                                                {inv.code.slice(0, 12)}...
                                            </td>
                                            <td>{inv.email_hint || '—'}</td>
                                            <td>{inv.created_by_username}</td>
                                            <td>
                                                <span style={{ color: statusColor, fontWeight: 600, fontSize: '0.85rem' }}>
                                                    {statusLabel}
                                                </span>
                                            </td>
                                            <td>{parseUTC(inv.expires_at)?.toLocaleString() ?? '—'}</td>
                                            <td>
                                                <div className="admin-action-btns">
                                                    {!inv.is_used && !inv.is_expired && (
                                                        <>
                                                            <button
                                                                className="admin-btn admin-btn-sm"
                                                                title="Copy invite link"
                                                                onClick={() => {
                                                                    const url = `${window.location.origin}/admin/register?code=${inv.code}`;
                                                                    navigator.clipboard.writeText(url);
                                                                    setCopiedCode(inv.code);
                                                                    setTimeout(() => setCopiedCode(null), 2000);
                                                                }}
                                                            >
                                                                {copiedCode === inv.code ? <CheckCircle size={14} /> : <Copy size={14} />}
                                                            </button>
                                                            <button
                                                                className="admin-btn admin-btn-sm admin-btn-danger"
                                                                title="Revoke invite"
                                                                onClick={() => revokeInvite.mutate(inv.code)}
                                                                disabled={revokeInvite.isPending}
                                                            >
                                                                <XCircle size={14} />
                                                            </button>
                                                        </>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                                {(invites ?? []).length === 0 && (
                                    <tr><td colSpan={6} className="admin-empty-row">No invites created yet</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Audit Log */}
            <div className="admin-card" style={{ marginTop: '1.5rem' }}>
                <h3 className="admin-card-title"><Clock size={18} /> Admin Audit Log</h3>

                {auditLoading ? <LoadingSpinner /> : (
                    <div className="admin-table-container">
                        <table className="admin-table admin-table-compact">
                            <thead>
                                <tr>
                                    <th>Time</th>
                                    <th>Admin</th>
                                    <th>Action</th>
                                    <th>Target</th>
                                    <th>Details</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(auditData?.entries ?? []).map((entry) => (
                                    <tr key={entry.id}>
                                        <td>{parseUTC(entry.created_at)?.toLocaleString() ?? '—'}</td>
                                        <td>{entry.admin_username}</td>
                                        <td><span className="admin-action-tag">{entry.action}</span></td>
                                        <td>{entry.target_type ? `${entry.target_type}` : '—'}</td>
                                        <td className="admin-details-cell">{entry.details ? entry.details.slice(0, 50) : '—'}</td>
                                    </tr>
                                ))}
                                {(auditData?.entries ?? []).length === 0 && (
                                    <tr><td colSpan={5} className="admin-empty-row">No audit log entries yet</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}


// =============================================================================
// DISCOVERY PANEL — Groundsource clusters pending review
// =============================================================================

function DiscoveryPanel() {
    const [cityFilter, setCityFilter] = useState('');
    const [statusFilter, setStatusFilter] = useState('pending');

    const { data: clusters, isLoading } = useAdminClusters({
        status: statusFilter || undefined,
        city: cityFilter || undefined,
    });
    const promoteMutation = useAdminPromoteCluster();
    const dismissMutation = useAdminDismissCluster();

    const CITIES = ['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore'];

    const overlapColor = (status: string) => {
        if (status === 'CONFIRMED') return '#3b82f6';
        if (status === 'PERIPHERAL') return '#f59e0b';
        if (status === 'MISSED') return '#ef4444';
        return '#9ca3af';
    };

    const confidenceBadge = (confidence: string) => {
        if (confidence === 'high') return 'admin-status-verified';
        if (confidence === 'medium') return 'admin-status-pending';
        return 'admin-status-archived';
    };

    const clusterList = clusters ?? [];

    return (
        <div className="admin-panel">
            <div className="admin-panel-header">
                <h3 style={{ margin: 0, fontWeight: 600 }}>Groundsource Cluster Review</h3>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <select
                        className="admin-filter-select"
                        value={cityFilter}
                        onChange={e => setCityFilter(e.target.value)}
                    >
                        <option value="">All Cities</option>
                        {CITIES.map(c => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                    <select
                        className="admin-filter-select"
                        value={statusFilter}
                        onChange={e => setStatusFilter(e.target.value)}
                    >
                        <option value="pending">Pending</option>
                        <option value="promoted">Promoted</option>
                        <option value="dismissed">Dismissed</option>
                        <option value="">All</option>
                    </select>
                </div>
            </div>

            {isLoading ? <LoadingSpinner /> : (
                <>
                    {clusterList.length === 0 ? (
                        <div className="admin-card">
                            <p className="admin-empty-text">No clusters match the current filters.</p>
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gap: '0.75rem' }}>
                            {clusterList.map((cluster: AdminCluster) => (
                                <div key={cluster.id} className="admin-card" style={{ padding: '1rem' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem', flexWrap: 'wrap' }}>
                                        <div style={{ flex: 1, minWidth: '200px' }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                                                <div style={{
                                                    width: '10px', height: '10px', borderRadius: '50%',
                                                    backgroundColor: overlapColor(cluster.overlap_status),
                                                    flexShrink: 0,
                                                }} />
                                                <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>
                                                    {cluster.label || `Cluster ${cluster.id.slice(0, 8)}`}
                                                </span>
                                                <span className={`admin-status-badge ${confidenceBadge(cluster.confidence)}`}>
                                                    {cluster.confidence}
                                                </span>
                                            </div>
                                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '0.25rem 1rem', fontSize: '0.8rem', color: '#6b7280' }}>
                                                <span><strong>City:</strong> {cluster.city}</span>
                                                <span><strong>Episodes:</strong> {cluster.episode_count}</span>
                                                <span><strong>Overlap:</strong> {cluster.overlap_status}</span>
                                                <span><strong>Nearest:</strong> {cluster.nearest_hotspot_name || '—'}</span>
                                                {cluster.date_first && (
                                                    <span><strong>First:</strong> {parseUTC(cluster.date_first)?.toLocaleDateString() ?? '—'}</span>
                                                )}
                                                {cluster.date_last && (
                                                    <span><strong>Last:</strong> {parseUTC(cluster.date_last)?.toLocaleDateString() ?? '—'}</span>
                                                )}
                                                <span><strong>Coords:</strong> {cluster.latitude.toFixed(4)}, {cluster.longitude.toFixed(4)}</span>
                                            </div>
                                        </div>
                                        {(!cluster.status || cluster.status === 'pending') && (
                                            <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
                                                <button
                                                    className="admin-btn admin-btn-primary admin-btn-sm"
                                                    disabled={promoteMutation.isPending}
                                                    onClick={() => promoteMutation.mutate(cluster.id)}
                                                    title="Promote to hotspot"
                                                >
                                                    <CheckCircle size={14} /> Promote
                                                </button>
                                                <button
                                                    className="admin-btn admin-btn-sm"
                                                    disabled={dismissMutation.isPending}
                                                    onClick={() => dismissMutation.mutate(cluster.id)}
                                                    title="Dismiss cluster"
                                                >
                                                    <XCircle size={14} /> Dismiss
                                                </button>
                                            </div>
                                        )}
                                        {cluster.status && cluster.status !== 'pending' && (
                                            <span className={`admin-status-badge ${cluster.status === 'promoted' ? 'admin-status-verified' : 'admin-status-archived'}`}>
                                                {cluster.status}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

// =============================================================================
// PINS PANEL — All user personal watch-area pins (admin view)
// =============================================================================

function PinsPanel() {
    const [cityFilter, setCityFilter] = useState('');
    const [sortBy, setSortBy] = useState('created_at');

    const { data: pins, isLoading } = useAdminPins({
        city: cityFilter || undefined,
        sort: sortBy,
    });

    const CITIES = ['delhi', 'bangalore', 'yogyakarta', 'singapore', 'indore'];
    const SORT_OPTIONS = [
        { value: 'created_at', label: 'Creation Date' },
        { value: 'fhi_score', label: 'FHI Score' },
        { value: 'city', label: 'City' },
    ];

    const fhiColor = (level?: string) => {
        if (!level) return '#9ca3af';
        if (level === 'extreme') return '#ef4444';
        if (level === 'high') return '#f97316';
        if (level === 'moderate') return '#f59e0b';
        if (level === 'low') return '#22c55e';
        return '#9ca3af';
    };

    const pinList = pins ?? [];

    return (
        <div className="admin-panel">
            <div className="admin-panel-header">
                <h3 style={{ margin: 0, fontWeight: 600 }}>Personal Watch-Area Pins</h3>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <select
                        className="admin-filter-select"
                        value={cityFilter}
                        onChange={e => setCityFilter(e.target.value)}
                    >
                        <option value="">All Cities</option>
                        {CITIES.map(c => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                    <select
                        className="admin-filter-select"
                        value={sortBy}
                        onChange={e => setSortBy(e.target.value)}
                    >
                        {SORT_OPTIONS.map(o => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                    </select>
                </div>
            </div>

            {isLoading ? <LoadingSpinner /> : (
                <>
                    <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '1rem' }}>
                        {pinList.length} pin{pinList.length !== 1 ? 's' : ''} total
                    </p>
                    <div className="admin-table-container">
                        <table className="admin-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>User</th>
                                    <th>City</th>
                                    <th>FHI</th>
                                    <th>Episodes</th>
                                    <th>Visibility</th>
                                    <th>Created</th>
                                </tr>
                            </thead>
                            <tbody>
                                {pinList.map((pin: AdminPin) => (
                                    <tr key={pin.id}>
                                        <td>
                                            <div style={{ fontWeight: 500, fontSize: '0.85rem' }}>{pin.name}</div>
                                            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
                                                {pin.latitude.toFixed(4)}, {pin.longitude.toFixed(4)}
                                            </div>
                                        </td>
                                        <td>{pin.username || pin.user_id.slice(0, 8)}</td>
                                        <td>{pin.city || '—'}</td>
                                        <td>
                                            {pin.fhi_score != null ? (
                                                <span style={{ color: fhiColor(pin.fhi_level), fontWeight: 600 }}>
                                                    {Math.round(pin.fhi_score * 100)}%
                                                    {pin.fhi_level ? ` (${pin.fhi_level})` : ''}
                                                </span>
                                            ) : '—'}
                                        </td>
                                        <td>{pin.historical_episode_count}</td>
                                        <td>
                                            <span className={`admin-status-badge ${pin.visibility === 'public' ? 'admin-status-verified' : 'admin-status-pending'}`}>
                                                {pin.visibility}
                                            </span>
                                        </td>
                                        <td>{parseUTC(pin.created_at)?.toLocaleDateString() ?? '—'}</td>
                                    </tr>
                                ))}
                                {pinList.length === 0 && (
                                    <tr><td colSpan={7} className="admin-empty-row">No pins found</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </>
            )}
        </div>
    );
}

// =============================================================================
// SHARED COMPONENTS
// =============================================================================

function KPICard({ title, value, subtitle, icon, color }: {
    title: string; value: number; subtitle: string; icon: React.ReactNode; color: string;
}) {
    return (
        <div className={`admin-kpi-card admin-kpi-${color}`}>
            <div className="admin-kpi-icon">{icon}</div>
            <div className="admin-kpi-body">
                <div className="admin-kpi-value">{value.toLocaleString()}</div>
                <div className="admin-kpi-title">{title}</div>
                <div className="admin-kpi-subtitle">{subtitle}</div>
            </div>
        </div>
    );
}

function LoadingSpinner() {
    return (
        <div className="admin-loading">
            <Loader2 size={24} className="animate-spin" />
            <span>Loading...</span>
        </div>
    );
}

function Pagination({ page, totalPages, onPageChange }: {
    page: number; totalPages: number; onPageChange: (p: number) => void;
}) {
    if (totalPages <= 1) return null;
    return (
        <div className="admin-pagination">
            <button disabled={page <= 1} onClick={() => onPageChange(page - 1)} className="admin-page-btn">
                <ChevronLeft size={16} /> Prev
            </button>
            <span className="admin-page-info">Page {page} of {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => onPageChange(page + 1)} className="admin-page-btn">
                Next <ChevronRight size={16} />
            </button>
        </div>
    );
}
