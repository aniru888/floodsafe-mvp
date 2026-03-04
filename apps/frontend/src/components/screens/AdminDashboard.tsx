import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Shield, Users, FileText, Award, BarChart3, Settings, LogOut,
    Search, ChevronLeft, ChevronRight, CheckCircle, XCircle,
    Archive, Trash2, Ban, UserPlus, Star, Activity, Globe,
    RefreshCw, Eye, AlertTriangle, TrendingUp, Loader2,
    Clock, Database, Wifi, ChevronDown
} from 'lucide-react';
import {
    isAdminAuthenticated, clearAdminToken,
    useAdminDashboardStats, useAdminUsers, useAdminReports,
    useAdminBadges, useAdminAmbassadors, useAdminAuditLog,
    useAdminSystemHealth, useAdminAnalyticsReports, useAdminAnalyticsUsers,
    useAdminBanUser, useAdminUnbanUser, useAdminDeleteUser,
    useAdminUpdateRole, useAdminVerifyReport, useAdminArchiveReport,
    useAdminDeleteReport, useAdminCreateBadge, useAdminAwardBadge,
    useAdminPromoteAmbassador,
    type AdminUser, type AdminReport, type AdminBadge
} from '../../lib/api/admin-hooks';

type AdminTab = 'overview' | 'users' | 'reports' | 'badges' | 'analytics' | 'system';

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
                                        <td>{user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}</td>
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
    const [statusFilter, setStatusFilter] = useState('');
    const [search, setSearch] = useState('');
    const [searchInput, setSearchInput] = useState('');
    const [page, setPage] = useState(1);

    const { data, isLoading } = useAdminReports({ status: statusFilter || undefined, search: search || undefined, page });
    const verifyMutation = useAdminVerifyReport();
    const archiveMutation = useAdminArchiveReport();
    const deleteMutation = useAdminDeleteReport();

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        setSearch(searchInput);
        setPage(1);
    };

    const handleVerify = (report: AdminReport, verified: boolean) => {
        const reason = prompt(`Reason for ${verified ? 'verifying' : 'rejecting'} this report:`);
        if (reason) {
            verifyMutation.mutate({ reportId: report.id, verified, reason });
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
                <select
                    className="admin-filter-select"
                    value={statusFilter}
                    onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
                >
                    <option value="">All Reports</option>
                    <option value="unverified">Pending Verification</option>
                    <option value="verified">Verified</option>
                    <option value="archived">Archived</option>
                </select>
            </div>

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
                                        <td>{report.timestamp ? new Date(report.timestamp).toLocaleDateString() : '—'}</td>
                                        <td>
                                            <div className="admin-action-btns">
                                                {!report.verified && !report.archived_at && (
                                                    <button onClick={() => handleVerify(report, true)} title="Verify" className="admin-action-btn admin-action-verify">
                                                        <CheckCircle size={14} />
                                                    </button>
                                                )}
                                                {report.verified && !report.archived_at && (
                                                    <button onClick={() => handleVerify(report, false)} title="Reject" className="admin-action-btn admin-action-reject">
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
        createBadgeMutation.mutate(newBadge as any, {
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
                                        <td>{entry.created_at ? new Date(entry.created_at).toLocaleString() : '—'}</td>
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
