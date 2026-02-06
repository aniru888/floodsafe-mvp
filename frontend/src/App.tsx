import { useState, useEffect } from 'react'
import { AlertCircle, Map as MapIcon, Menu, Shield, User, LogOut, Plus } from 'lucide-react'
import { MapComponent } from './components/map/MapComponent'
import type { Report } from './components/map/MapComponent'
import { useAuth, AuthProvider } from './context/AuthContext'
import { LoginScreen } from './screens/LoginScreen'
import { AlertsScreen } from './screens/AlertsScreen'
import { ProfileScreen } from './screens/ProfileScreen'
import { ReportModal } from './components/reports/ReportModal'
import { NavigationPanel } from './components/map/NavigationPanel'
import { api } from './lib/api'

function AppContent() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const { isAuthenticated, user, logout, isLoading } = useAuth()
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [currentLocation, setCurrentLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [route, setRoute] = useState<GeoJSON.FeatureCollection<GeoJSON.LineString> | null>(null);

  // Auto-detect location for reporting
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.watchPosition(
        (position) => {
          setCurrentLocation({
            lat: position.coords.latitude,
            lng: position.coords.longitude
          });
        },
        (error) => console.log("GPS Error", error),
        { enableHighAccuracy: true }
      );
    }
  }, []);

  // Fetch reports and risk data
  const fetchReports = async () => {
    try {
      const { data } = await api.get<Report[]>('/reports/');
      setReports(data);
    } catch (error) {
      console.error("Failed to fetch reports", error);
    }
  };

  const [floodRisk, setFloodRisk] = useState({ level: 'Low', score: 0 });

  useEffect(() => {
    if (isAuthenticated) {
      fetchReports();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (!currentLocation) return;
    const fetchRisk = async () => {
      try {
        const { data } = await api.post<{ risk_level?: string; risk_score?: number }>('/predictions/predict', {
          latitude: currentLocation.lat,
          longitude: currentLocation.lng,
          horizon_days: 0
        });
        setFloodRisk({
          level: data.risk_level || 'Low',
          score: data.risk_score || 0
        });
      } catch (error) {
        console.error("Failed to fetch risk", error);
      }
    };
    fetchRisk();
  }, [currentLocation]);

  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center">Loading...</div>
  }

  if (!isAuthenticated) {
    return <LoginScreen />
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col md:flex-row">
      {/* Sidebar / Navigation */}
      <nav className="w-full md:w-64 border-r bg-card p-4 flex flex-col gap-4">
        <div className="flex items-center gap-2 px-2 py-4">
          <Shield className="h-8 w-8 text-primary" />
          <h1 className="text-2xl font-bold tracking-tight">FloodSafe</h1>
        </div>
        
        <div className="space-y-1 flex-1">
          <Button 
            active={activeTab === 'dashboard'} 
            onClick={() => setActiveTab('dashboard')} 
            icon={<MapIcon className="h-4 w-4" />}
          >
            Flood Map
          </Button>
          <Button 
            active={activeTab === 'alerts'} 
            onClick={() => setActiveTab('alerts')} 
            icon={<AlertCircle className="h-4 w-4" />}
          >
            Alerts
          </Button>
          <Button 
            active={activeTab === 'profile'} 
            onClick={() => setActiveTab('profile')} 
            icon={<User className="h-4 w-4" />}
          >
            Profile
          </Button>
        </div>

        <div className="border-t pt-4">
          <div className="px-4 py-2 text-xs text-muted-foreground">
            Signed in as <br/>
            <span className="font-medium text-foreground">{user?.email}</span>
          </div>
          <Button onClick={logout} icon={<LogOut className="h-4 w-4" />}>
            Sign Out
          </Button>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 p-6 overflow-auto h-screen flex flex-col">
        <header className="mb-6 flex items-center justify-between shrink-0">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">
              {activeTab === 'dashboard' ? 'Dashboard' : 
               activeTab === 'alerts' ? 'Alerts' : 'Profile'}
            </h2>
            <p className="text-muted-foreground">
              {activeTab === 'dashboard' ? 'Real-time flood monitoring and safe routing.' : 
               activeTab === 'alerts' ? 'Manage your watch areas and notifications.' : 'Manage your account settings.'}
            </p>
          </div>
          <button className="md:hidden p-2 border rounded-md">
            <Menu className="h-6 w-6" />
          </button>
        </header>

        {activeTab === 'dashboard' && (
          <div className="flex flex-col gap-6 flex-1 min-h-0">
            {/* Stats Row */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 shrink-0">
              <Card title="Flood Risk" value={floodRisk.level} description="Current risk level in your area" className="bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-900" />
              <Card title="Active Alerts" value="0" description="No active warnings nearby" />
              <Card title="Community Reports" value={reports.length.toString()} description="Reports in the last 24h" />
            </div>

            {/* Map Container - takes remaining height */}
            <div className="flex-1 rounded-xl border bg-card shadow-sm overflow-hidden relative min-h-[500px]">
              <MapComponent reports={reports} route={route} currentLocation={currentLocation} className="absolute inset-0" />
              
              <NavigationPanel 
                currentLocation={currentLocation}
                onRouteCalculated={setRoute}
              />

              {/* Report Button */}
              <div className="absolute bottom-6 right-6 z-10">
                <button
                  onClick={() => setIsReportModalOpen(true)}
                  className="flex items-center gap-2 bg-destructive text-destructive-foreground px-4 py-3 rounded-full shadow-lg hover:bg-destructive/90 transition-all font-semibold"
                >
                  <Plus className="h-5 w-5" />
                  Report Flood
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'alerts' && <AlertsScreen />}
        
        {activeTab === 'profile' && <ProfileScreen />}
      </main>

      <ReportModal 
        isOpen={isReportModalOpen} 
        onClose={() => setIsReportModalOpen(false)}
        currentLocation={currentLocation}
        onSuccess={() => {
          fetchReports();
          alert("Report submitted successfully!");
        }}
      />
    </div>
  )
}

function Button({ children, active, onClick, icon }: { children: React.ReactNode, active?: boolean, onClick?: () => void, icon?: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors
        ${active 
          ? 'bg-primary text-primary-foreground' 
          : 'hover:bg-accent hover:text-accent-foreground text-muted-foreground'
        }`}
    >
      {icon}
      {children}
    </button>
  )
}

function Card({ title, value, description, className }: { title: string, value: string, description: string, className?: string }) {
  return (
    <div className={`rounded-xl border bg-card text-card-foreground shadow-sm p-6 ${className}`}>
      <div className="flex flex-col space-y-1.5">
        <h3 className="font-semibold leading-none tracking-tight">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="p-0 pt-4">
        <div className="text-2xl font-bold">{value}</div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}
