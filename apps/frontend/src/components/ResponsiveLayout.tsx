import { ReactNode } from 'react';
import { BottomNav } from './BottomNav';
import { TopNav } from './TopNav';
import { Sidebar } from './Sidebar';

interface ResponsiveLayoutProps {
    children: ReactNode;
    activeTab: string;
    onTabChange: (tab: string) => void;
    onNotificationClick: () => void;
    onProfileClick: () => void;
}

export function ResponsiveLayout({
    children,
    activeTab,
    onTabChange,
    onNotificationClick,
    onProfileClick
}: ResponsiveLayoutProps) {
    return (
        <div className="min-h-screen bg-background text-foreground">
            {/* Desktop Sidebar — hidden on mobile, fixed left on md+ */}
            <Sidebar activeTab={activeTab} onTabChange={onTabChange} />

            {/* Mobile TopNav — hidden on desktop */}
            <div className="md:hidden">
                <TopNav
                    onNotificationClick={onNotificationClick}
                    onProfileClick={onProfileClick}
                />
            </div>

            {/* Main content area
                - md:ml-64: offset past sidebar on desktop
                - pt-14 md:pt-0: space for TopNav on mobile, none on desktop
                - pb-16 md:pb-0: space for BottomNav on mobile, none on desktop
                - No max-w here: screens like FloodAtlas need full width */}
            <main className="md:ml-64 pt-14 md:pt-0 pb-16 md:pb-0 relative">
                {children}
            </main>

            {/* Mobile BottomNav — hidden on desktop */}
            <div className="md:hidden">
                <BottomNav activeTab={activeTab} onTabChange={onTabChange} />
            </div>
        </div>
    );
}
