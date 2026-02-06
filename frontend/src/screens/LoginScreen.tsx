import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { LoginForm } from '../components/auth/LoginForm';
import { RegisterForm } from '../components/auth/RegisterForm';
import { Shield } from 'lucide-react';

export function LoginScreen() {
  const [view, setView] = useState<'login' | 'register'>('login');
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p>You are already logged in.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-muted/20 p-4">
      <div className="mb-8 flex flex-col items-center">
        <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
          <Shield className="h-8 w-8 text-primary" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-center">FloodSafe</h1>
        <p className="text-muted-foreground text-center mt-2">
          Community-powered flood monitoring and safe routing
        </p>
      </div>

      {view === 'login' ? (
        <>
          <LoginForm />
          <p className="mt-4 text-sm text-muted-foreground">
            Don't have an account?{' '}
            <button 
              onClick={() => setView('register')}
              className="font-medium text-primary hover:underline"
            >
              Sign up
            </button>
          </p>
        </>
      ) : (
        <>
          <RegisterForm onSuccess={() => {}} />
          <p className="mt-4 text-sm text-muted-foreground">
            Already have an account?{' '}
            <button 
              onClick={() => setView('login')}
              className="font-medium text-primary hover:underline"
            >
              Sign in
            </button>
          </p>
        </>
      )}
    </div>
  );
}
