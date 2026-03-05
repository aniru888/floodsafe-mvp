import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAdminLogin, isAdminAuthenticated } from '../../lib/api/admin-hooks';
import '../../styles/admin.css';
import { Shield, Eye, EyeOff, AlertCircle, Loader2 } from 'lucide-react';
import { useEffect } from 'react';

export function AdminLoginScreen() {
    const navigate = useNavigate();
    const loginMutation = useAdminLogin();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');

    // Redirect if already authenticated
    useEffect(() => {
        if (isAdminAuthenticated()) {
            navigate('/admin', { replace: true });
        }
    }, [navigate]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        if (!email || !password) {
            setError('Please enter both email and password');
            return;
        }

        try {
            await loginMutation.mutateAsync({ email, password });
            navigate('/admin', { replace: true });
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Login failed');
        }
    };

    return (
        <div className="admin-login-container">
            <div className="admin-login-card">
                <div className="admin-login-header">
                    <div className="admin-login-icon">
                        <Shield size={32} />
                    </div>
                    <h1>FloodSafe Admin</h1>
                    <p>Platform Administration Panel</p>
                </div>

                <form onSubmit={handleSubmit} className="admin-login-form">
                    {error && (
                        <div className="admin-login-error">
                            <AlertCircle size={16} />
                            <span>{error}</span>
                        </div>
                    )}

                    <div className="admin-form-group">
                        <label htmlFor="admin-email">Email</label>
                        <input
                            id="admin-email"
                            type="email"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            placeholder="admin@floodsafe.app"
                            autoComplete="email"
                            autoFocus
                        />
                    </div>

                    <div className="admin-form-group">
                        <label htmlFor="admin-password">Password</label>
                        <div className="admin-password-field">
                            <input
                                id="admin-password"
                                type={showPassword ? 'text' : 'password'}
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                placeholder="••••••••"
                                autoComplete="current-password"
                            />
                            <button
                                type="button"
                                className="admin-password-toggle"
                                onClick={() => setShowPassword(!showPassword)}
                                aria-label={showPassword ? 'Hide password' : 'Show password'}
                            >
                                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>
                    </div>

                    <button
                        type="submit"
                        className="admin-login-btn"
                        disabled={loginMutation.isPending}
                    >
                        {loginMutation.isPending ? (
                            <>
                                <Loader2 size={18} className="animate-spin" />
                                Signing in...
                            </>
                        ) : (
                            <>
                                <Shield size={18} />
                                Sign In to Admin Panel
                            </>
                        )}
                    </button>
                </form>

                <div className="admin-login-footer">
                    <a href="/" className="admin-back-link">← Back to FloodSafe</a>
                </div>
            </div>
        </div>
    );
}
