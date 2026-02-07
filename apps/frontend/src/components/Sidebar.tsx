import { Home, Map as MapIcon, PlusCircle, Bell, User, LogOut, Shield } from 'lucide-react';
import { cn } from '../lib/utils';
import { useAuth } from '../contexts/AuthContext';
import { useUser } from '../contexts/UserContext';

interface SidebarProps {
    activeTab: string;
    onTabChange: (tab: string) => void;
}

const navItems = [
    { id: 'home', icon: Home, label: 'Home' },
    { id: 'map', icon: MapIcon, label: 'Flood Atlas' },
    { id: 'report', icon: PlusCircle, label: 'Report Flood', isCTA: true },
    { id: 'alerts', icon: Bell, label: 'Alerts' },
    { id: 'profile', icon: User, label: 'Profile' },
];

export function Sidebar({ activeTab, onTabChange }: SidebarProps) {
    const { logout } = useAuth();
    const { user } = useUser();

    return (
        <aside data-sidebar className="hidden md:flex flex-col w-64 h-screen bg-card border-r fixed left-0 top-0 z-50">
            {/* Branding */}
            <div className="h-16 flex items-center px-6 border-b shrink-0">
                <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-primary-foreground mr-3">
                    <Shield className="w-4 h-4" />
                </div>
                <span className="font-bold text-lg">FloodSafe</span>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
                {navItems.map((item) => {
                    const Icon = item.icon;
                    const isActive = activeTab === item.id;

                    if (item.isCTA) {
                        return (
                            <button
                                key={item.id}
                                onClick={() => onTabChange(item.id)}
                                className={cn(
                                    "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors mt-2",
                                    "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm"
                                )}
                            >
                                <Icon className="w-5 h-5" />
                                <span className="font-medium text-sm">{item.label}</span>
                            </button>
                        );
                    }

                    return (
                        <button
                            key={item.id}
                            onClick={() => onTabChange(item.id)}
                            className={cn(
                                "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm",
                                isActive
                                    ? "bg-secondary text-foreground font-medium"
                                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                            )}
                        >
                            <Icon className="w-5 h-5" />
                            {item.label}
                        </button>
                    );
                })}
            </nav>

            {/* User section + Logout */}
            <div className="p-3 border-t shrink-0 space-y-1">
                {user && (
                    <div className="flex items-center gap-3 px-3 py-2">
                        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-sm font-medium shrink-0">
                            {(user.username || user.email || '?')[0].toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{user.username || 'User'}</p>
                            <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                        </div>
                    </div>
                )}
                <button
                    onClick={() => logout()}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-destructive hover:bg-destructive/10 transition-colors"
                >
                    <LogOut className="w-4 h-4" />
                    Logout
                </button>
            </div>
        </aside>
    );
}
