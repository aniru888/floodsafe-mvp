/**
 * Email Verified Screen
 *
 * Landing page shown after user clicks the verification link in their email.
 * Parses URL parameters to show success or error state.
 *
 * URL parameters:
 * - success: "true" or "false"
 * - message: Optional error message (URL encoded)
 */

import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export function EmailVerifiedScreen() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { refreshUser, isAuthenticated } = useAuth();

    const success = searchParams.get('success') === 'true';
    const message = searchParams.get('message') || '';
    const alreadyVerified = searchParams.get('already') === 'true';

    const [countdown, setCountdown] = useState(5);
    const [isRefreshing, setIsRefreshing] = useState(false);

    // Refresh user profile on success to update verification status
    useEffect(() => {
        if (success && isAuthenticated) {
            setIsRefreshing(true);
            refreshUser().finally(() => setIsRefreshing(false));
        }
    }, [success, isAuthenticated, refreshUser]);

    // Auto-redirect countdown on success
    useEffect(() => {
        if (!success) return;

        const timer = setInterval(() => {
            setCountdown((prev) => {
                if (prev <= 1) {
                    clearInterval(timer);
                    navigate('/app', { replace: true });
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(timer);
    }, [success, navigate]);

    const handleContinue = () => {
        navigate('/app', { replace: true });
    };

    const handleResend = () => {
        navigate('/login', { replace: true });
    };

    return (
        <div className="min-h-screen bg-muted flex items-center justify-center p-4">
            <Card className="w-full max-w-md p-8 text-center">
                {success ? (
                    // Success state
                    <>
                        <div className="mb-6">
                            <CheckCircle className="w-20 h-20 text-green-500 mx-auto" />
                        </div>
                        <h1 className="text-2xl font-bold text-foreground mb-2">
                            {alreadyVerified ? 'Email Already Verified' : 'Email Verified!'}
                        </h1>
                        <p className="text-muted-foreground mb-6">
                            {alreadyVerified
                                ? 'Your email was already verified. You can continue using FloodSafe.'
                                : 'Your email has been successfully verified. You now have full access to FloodSafe.'}
                        </p>

                        {isRefreshing ? (
                            <div className="flex items-center justify-center gap-2 text-muted-foreground mb-4">
                                <Loader2 className="w-4 h-4 animate-spin" />
                                <span>Updating your profile...</span>
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground mb-4">
                                Redirecting in {countdown} second{countdown !== 1 ? 's' : ''}...
                            </p>
                        )}

                        <Button onClick={handleContinue} className="w-full">
                            Continue to FloodSafe
                        </Button>
                    </>
                ) : (
                    // Error state
                    <>
                        <div className="mb-6">
                            <XCircle className="w-20 h-20 text-red-500 mx-auto" />
                        </div>
                        <h1 className="text-2xl font-bold text-foreground mb-2">
                            Verification Failed
                        </h1>
                        <p className="text-muted-foreground mb-6">
                            {decodeURIComponent(message) || 'The verification link is invalid or has expired.'}
                        </p>
                        <div className="space-y-3">
                            <Button onClick={handleResend} className="w-full">
                                Request New Verification Email
                            </Button>
                            <Button variant="outline" onClick={handleContinue} className="w-full">
                                Continue to FloodSafe
                            </Button>
                        </div>
                    </>
                )}
            </Card>
        </div>
    );
}
