import { Bell, User, Shield } from 'lucide-react';
import { Button } from './ui/button';
import { useUnreadAlertCount } from '../lib/api/hooks';
import { useUser } from '../contexts/UserContext';

interface TopNavProps {
    onNotificationClick: () => void;
    onProfileClick: () => void;
    notificationCount?: number; // Kept as fallback
}

export function TopNav({ onNotificationClick, onProfileClick, notificationCount: fallbackCount = 0 }: TopNavProps) {
    const { user } = useUser();
    const { data } = useUnreadAlertCount(user?.id);

    const notificationCount = data?.count ?? fallbackCount;

    return (
        <header className="fixed top-0 left-0 right-0 h-14 bg-card border-b z-50 px-4 pl-safe pr-safe flex items-center justify-between">
            <div className="flex items-center gap-2">
                <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-primary-foreground">
                    <Shield className="w-4 h-4" />
                </div>
                <span className="font-bold text-lg">FloodSafe</span>
            </div>

            <div className="flex items-center gap-2">
                {user?.username && (
                    <span className="text-sm text-muted-foreground font-medium max-w-[100px] truncate hidden sm:inline">
                        {user.username}
                    </span>
                )}
                <Button variant="ghost" size="icon" onClick={onNotificationClick} className="relative">
                    <Bell className="w-5 h-5 text-muted-foreground" />
                    {notificationCount > 0 && (
                        <span className="absolute -top-1 -right-1 w-5 h-5 bg-destructive rounded-full text-destructive-foreground text-xs flex items-center justify-center">
                            {notificationCount > 9 ? '9+' : notificationCount}
                        </span>
                    )}
                </Button>
                <Button variant="ghost" size="icon" onClick={onProfileClick}>
                    <User className="w-5 h-5 text-muted-foreground" />
                </Button>
            </div>
        </header>
    );
}
