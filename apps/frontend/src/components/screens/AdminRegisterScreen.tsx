import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAdminRegister } from '../../lib/api/admin-hooks';
import '../../styles/admin.css';
import { Shield, Loader2, CheckCircle, AlertCircle } from 'lucide-react';

export function AdminRegisterScreen() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const code = searchParams.get('code') ?? '';

    const registerMutation = useAdminRegister();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState(false);

    // Guard: no invite code in URL
    if (!code) {
        return (
            <div className="admin-login-container">
                <div className="admin-login-card">
                    <div className="admin-login-header">
                        <div className="admin-login-icon">
                            <AlertCircle size={32} />
                        </div>
                        <h1>Invalid Invite Link</h1>
                        <p>This invite link is missing a code.</p>
                    </div>
                    <div className="admin-login-footer">
                        <a href="/admin/login" className="admin-back-link">← Go to Admin Login</a>
                    </div>
                </div>
            </div>
        );
    }

    if (success) {
        return (
            <div className="admin-login-container">
                <div className="admin-login-card">
                    <div className="admin-login-header">
                        <div className="admin-login-icon" style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}>
                            <CheckCircle size={32} />
                        </div>
                        <h1>Admin Access Granted</h1>
                        <p>Your admin account has been set up successfully.</p>
                    </div>
                    <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
                        <button
                            className="admin-login-btn"
                            onClick={() => navigate('/admin/login', { replace: true })}
                        >
                            <Shield size={18} />
                            Sign In to Admin Panel
                        </button>
                    </div>
                    <div className="admin-login-footer">
                        <a href="/" className="admin-back-link">← Back to FloodSafe</a>
                    </div>
                </div>
            </div>
        );
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        if (!email || !password || !confirmPassword) {
            setError('Please fill in all fields');
            return;
        }

        if (password.length < 8) {
            setError('Password must be at least 8 characters');
            return;
        }

        if (password !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }

        try {
            await registerMutation.mutateAsync({ code, email, password });
            setSuccess(true);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Registration failed');
        }
    };

    return (
        <div className="admin-login-container">
            <div className="admin-login-card">
                <div className="admin-login-header">
                    <div className="admin-login-icon">
                        <Shield size={32} />
                    </div>
                    <h1>You've been invited</h1>
                    <p>Set up your FloodSafe Admin access</p>
                </div>

                <form onSubmit={handleSubmit} className="admin-login-form">
                    {error && (
                        <div className="admin-login-error">
                            <AlertCircle size={16} />
                            <span>{error}</span>
                        </div>
                    )}

                    <div className="admin-form-group">
                        <label htmlFor="register-email">Email</label>
                        <input
                            id="register-email"
                            type="email"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            placeholder="your@email.com"
                            autoComplete="email"
                            autoFocus
                        />
                    </div>

                    <div className="admin-form-group">
                        <label htmlFor="register-password">Password</label>
                        <input
                            id="register-password"
                            type="password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            placeholder="Min. 8 characters"
                            autoComplete="new-password"
                        />
                    </div>

                    <div className="admin-form-group">
                        <label htmlFor="register-confirm-password">Confirm Password</label>
                        <input
                            id="register-confirm-password"
                            type="password"
                            value={confirmPassword}
                            onChange={e => setConfirmPassword(e.target.value)}
                            placeholder="Re-enter password"
                            autoComplete="new-password"
                        />
                    </div>

                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: '0.5rem',
                            padding: '0.75rem 1rem',
                            background: 'rgba(59, 130, 246, 0.08)',
                            border: '1px solid rgba(59, 130, 246, 0.25)',
                            borderRadius: '0.5rem',
                            color: '#93c5fd',
                            fontSize: '0.8125rem',
                            lineHeight: '1.4',
                        }}
                    >
                        <Shield size={15} style={{ flexShrink: 0, marginTop: '1px' }} />
                        <span>This sets an admin password for your existing FloodSafe account</span>
                    </div>

                    <button
                        type="submit"
                        className="admin-login-btn"
                        disabled={registerMutation.isPending}
                    >
                        {registerMutation.isPending ? (
                            <>
                                <Loader2 size={18} className="animate-spin" />
                                Setting up access...
                            </>
                        ) : (
                            <>
                                <Shield size={18} />
                                Activate Admin Access
                            </>
                        )}
                    </button>
                </form>

                <div className="admin-login-footer">
                    <a href="/admin/login" className="admin-back-link">Already have access? Sign in</a>
                </div>
            </div>
        </div>
    );
}
