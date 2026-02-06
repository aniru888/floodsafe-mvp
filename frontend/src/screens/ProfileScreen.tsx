import { useAuth } from '../context/AuthContext';
import { User, Mail, Shield, Award } from 'lucide-react';

export function ProfileScreen() {
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* Profile Header */}
      <div className="bg-card border rounded-xl p-6 shadow-sm flex items-center gap-6">
        <div className="h-20 w-20 rounded-full bg-primary/10 flex items-center justify-center text-primary">
          <User className="h-10 w-10" />
        </div>
        <div>
          <h2 className="text-2xl font-bold">{user.full_name || 'FloodSafe User'}</h2>
          <div className="flex items-center gap-2 text-muted-foreground mt-1">
            <Mail className="h-4 w-4" />
            <span>{user.email}</span>
          </div>
        </div>
      </div>

      {/* Stats / Info */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="bg-card border rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-blue-100 text-blue-600 rounded-lg">
              <Shield className="h-5 w-5" />
            </div>
            <h3 className="font-semibold">Account Status</h3>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Member Since</span>
              <span className="font-medium">Jan 2026</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Verification</span>
              <span className="text-green-600 font-medium">Verified</span>
            </div>
          </div>
        </div>

        <div className="bg-card border rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-purple-100 text-purple-600 rounded-lg">
              <Award className="h-5 w-5" />
            </div>
            <h3 className="font-semibold">Contributions</h3>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Reports Submitted</span>
              <span className="font-medium">0</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Impact Score</span>
              <span className="font-medium">0</span>
            </div>
          </div>
        </div>
      </div>

      <button 
        onClick={logout}
        className="w-full md:w-auto px-6 py-2 bg-destructive/10 text-destructive hover:bg-destructive/20 rounded-lg transition-colors font-medium"
      >
        Sign Out
      </button>
    </div>
  );
}