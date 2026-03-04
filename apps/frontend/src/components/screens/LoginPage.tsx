import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LoginScreen } from './LoginScreen';
import { useAuth } from '../../contexts/AuthContext';
import { Toaster } from '../ui/sonner';

export function LoginPage() {
    const { isAuthenticated, isLoading } = useAuth();
    const navigate = useNavigate();

    // Redirect to /app if already authenticated (replace:true prevents back-button loop)
    useEffect(() => {
        if (!isLoading && isAuthenticated) {
            navigate('/app', { replace: true });
        }
    }, [isAuthenticated, isLoading, navigate]);

    return (
        <>
            <LoginScreen />
            <Toaster position="top-center" />
        </>
    );
}
