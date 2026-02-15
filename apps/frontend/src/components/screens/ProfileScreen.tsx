import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Switch } from '../ui/switch';
import { Label } from '../ui/label';
import { Separator } from '../ui/separator';
import { Avatar, AvatarFallback } from '../ui/avatar';
import { MapPin, Bell, Globe, Settings, LogOut, Edit, Trash2, FileText, Route, ShieldCheck, Shield, UserCheck, Eye, Plus, Download, Phone, HelpCircle } from 'lucide-react';
import { useInstallPrompt } from '../../contexts/InstallPromptContext';
import { useUserReports, Report, useDailyRoutes, useDeleteDailyRoute } from '../../lib/api/hooks';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { RadioGroup, RadioGroupItem } from '../ui/radio-group';
import { Checkbox } from '../ui/checkbox';
import { toast } from 'sonner';
import { User } from '../../types';
import { useAuth } from '../../contexts/AuthContext';
import { fetchJson } from '../../lib/api/client';
import { CITY_REGION_SHORT } from '../../lib/cityUtils';
import { cn } from '../../lib/utils';
import { CITIES } from '../../lib/map/cityConfigs';
import { parseReportDescription } from '../../lib/tagParser';
import { ReportTagList } from '../ReportTagBadge';
import { ReportDetailModal } from '../ReportDetailModal';
import { EmergencyContactsModal } from '../EmergencyContactsModal';
import {
  StreakWidget,
  ReputationDashboard,
  LevelProgressCard,
  BadgeGrid,
  BadgeCatalogModal,
  LeaderboardSection,
  LeaderboardModal
} from '../gamification';
import AddDailyRouteDialog from '../AddDailyRouteDialog';
import AddWatchAreaDialog from '../AddWatchAreaDialog';
import { useOnboardingBot } from '../../contexts/OnboardingBotContext';
import { t } from '../../lib/onboarding-bot/translations';

interface WatchArea {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  radius: number;
  created_at: string;
}

// Helper function to normalize user data with defaults
const normalizeUserData = (userData: User): User => {
  return {
    ...userData,
    language: userData.language || 'english',
    notification_push: userData.notification_push ?? true,
    notification_sms: userData.notification_sms ?? false,
    notification_whatsapp: userData.notification_whatsapp ?? false,
    notification_email: userData.notification_email ?? true,
    alert_preferences: userData.alert_preferences || {
      watch: true,
      advisory: true,
      warning: true,
      emergency: true,
    },
  };
};

interface ProfileScreenProps {
  onNavigate?: (screen: 'privacy' | 'terms') => void;
}

export function ProfileScreen({ onNavigate }: ProfileScreenProps) {
  const queryClient = useQueryClient();
  const { logout, user: authUser } = useAuth();
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [badgeCatalogOpen, setBadgeCatalogOpen] = useState(false);
  const [leaderboardModalOpen, setLeaderboardModalOpen] = useState(false);
  const [addRouteDialogOpen, setAddRouteDialogOpen] = useState(false);
  const [addWatchAreaDialogOpen, setAddWatchAreaDialogOpen] = useState(false);
  const [emergencyModalOpen, setEmergencyModalOpen] = useState(false);

  // PWA install prompt
  const { canInstall, promptInstall, isPrompting, isInstalled } = useInstallPrompt();

  // Fetch user profile using secure endpoint
  const { data: rawUser, isLoading } = useQuery<User>({
    queryKey: ['user', 'profile', authUser?.id],
    queryFn: async () => {
      // Use secure /users/me/profile endpoint (requires auth)
      const userData = await fetchJson<User>('/users/me/profile');
      return normalizeUserData(userData);
    },
    enabled: !!authUser, // Only fetch when authenticated
  });

  const user = rawUser;

  // Fetch watch areas
  const { data: watchAreas = [] } = useQuery<WatchArea[]>({
    queryKey: ['watchAreas', user?.id],
    queryFn: async () => {
      if (!user?.id) return [];
      try {
        return await fetchJson<WatchArea[]>(`/watch-areas/user/${user.id}`);
      } catch {
        return [];
      }
    },
    enabled: !!user?.id,
  });

  // Fetch user's reports
  const { data: userReports = [], isLoading: reportsLoading } = useUserReports(user?.id);

  // Fetch daily routes
  const { data: dailyRoutes = [] } = useDailyRoutes(user?.id);
  const deleteRouteMutation = useDeleteDailyRoute();

  // Delete watch area mutation
  const deleteWatchAreaMutation = useMutation({
    mutationFn: async (watchAreaId: string) => {
      return fetchJson(`/watch-areas/${watchAreaId}`, {
        method: 'DELETE',
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchAreas'] });
      toast.success('Watch area deleted');
    },
    onError: () => {
      toast.error('Failed to delete watch area');
    },
  });

  // Update user mutation - uses secure /users/me/profile endpoint
  const updateUserMutation = useMutation({
    mutationFn: async (updates: Partial<User>) => {
      // Use secure endpoint that validates auth token
      return fetchJson<User>('/users/me/profile', {
        method: 'PATCH',
        body: JSON.stringify(updates),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user', 'profile'] });
      toast.success('Profile updated successfully!');
    },
    onError: () => {
      toast.error('Failed to update profile');
    },
  });

  const handleNotificationToggle = (field: string, value: boolean) => {
    if (!user) return;
    updateUserMutation.mutate({ [field]: value } as Partial<User>);
  };

  const handleAlertPreferenceToggle = (alertType: string, value: boolean) => {
    if (!user || !user.alert_preferences) return;
    const newPreferences = { ...user.alert_preferences, [alertType]: value };
    updateUserMutation.mutate({
      alert_preferences: newPreferences
    } as Partial<User>);
  };

  const handleLanguageChange = (language: string) => {
    if (!user) return;
    updateUserMutation.mutate({ language } as Partial<User>);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-full">
        <div className="text-lg">Loading profile...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-full">
        <div className="text-center">
          <h2 className="text-xl font-semibold mb-2">No User Found</h2>
          <p className="text-muted-foreground">Please run the database seed script</p>
        </div>
      </div>
    );
  }

  const getInitials = (name: string | undefined) => {
    if (!name) return '??';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  const _progressToNextLevel = ((user.points % 100) / 100) * 100;
  const _pointsNeeded = 100 - (user.points % 100);
  const memberSince = user.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
    : 'Recently';
  const _reportsCount = user.reports_count ?? 0;
  const _verifiedReportsCount = user.verified_reports_count ?? 0;

  return (
    <div className="pb-4 min-h-full bg-muted">
      {/* Profile Header */}
      <div className="bg-primary text-primary-foreground p-6 md:mx-auto md:max-w-4xl md:mt-6 md:rounded-xl">
        <div className="flex items-center gap-4 mb-4">
          <Avatar className="w-16 h-16 bg-primary-foreground text-primary">
            <AvatarFallback className="text-2xl font-semibold bg-primary-foreground text-primary">
              {getInitials(user.username)}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-xl font-semibold truncate">{user.username}</h2>
              <Badge
                variant="secondary"
                className={cn(
                  "text-xs flex items-center gap-1",
                  user.role === "admin" && "bg-purple-100 text-purple-800",
                  user.role === "moderator" && "bg-blue-100 text-blue-800",
                  user.role === "verified_reporter" && "bg-green-100 text-green-800",
                  user.role === "user" && "bg-secondary text-secondary-foreground"
                )}
              >
                {user.role === "admin" && <ShieldCheck className="w-3 h-3" />}
                {user.role === "moderator" && <Shield className="w-3 h-3" />}
                {user.role === "verified_reporter" && <UserCheck className="w-3 h-3" />}
                {user.role === "verified_reporter" ? "Verified Reporter" : user.role}
              </Badge>
            </div>
            <p className="text-sm opacity-90">{user.email}</p>
            {user.phone && <p className="text-xs opacity-75 mt-1">{user.phone}</p>}
            <p className="text-xs opacity-75 mt-1">Joined {memberSince}</p>
          </div>
          <div className="flex-shrink-0">
            <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="secondary" size="sm">
                  <Edit className="w-4 h-4 mr-1" />
                  Edit
                </Button>
              </DialogTrigger>
              <EditProfileDialog user={user} onSave={(updates) => {
                updateUserMutation.mutate(updates);
                setEditDialogOpen(false);
              }} />
            </Dialog>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-4 md:max-w-4xl md:mx-auto">
        {/* Profile Completion Card */}
        {!user.profile_complete && (
          <Card className="p-4 bg-primary/5 border-primary/20">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-lg flex items-center gap-2">
                <Settings className="w-5 h-5 text-primary" />
                Complete Your Profile
              </h3>
              <Badge variant="secondary" className="text-xs">
                Step {user.onboarding_step || 1} of 5
              </Badge>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm mb-1">
                <span className="text-foreground">Profile Completion</span>
                <span className="text-primary font-medium">
                  {Math.round(((user.onboarding_step || 0) / 5) * 100)}%
                </span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${((user.onboarding_step || 0) / 5) * 100}%` }}
                />
              </div>

              <p className="text-xs text-muted-foreground mt-2">
                Complete your profile to unlock all features and personalized flood alerts
              </p>
            </div>
          </Card>
        )}

        {/* Two Column Desktop Grid */}
        <div className="md:grid md:grid-cols-2 md:gap-6">
          {/* LEFT COLUMN: Gamification / Progress */}
          <div className="space-y-4" data-tour-id="gamification-badges">
            <h2 className="text-lg font-semibold text-foreground px-1">Your Progress</h2>

            {/* Streak Widget */}
            <StreakWidget />

            {/* Reputation Dashboard */}
            <ReputationDashboard />

            {/* Level Progress */}
            {user && <LevelProgressCard user={user} />}

            {/* Badge Grid with View All */}
            <BadgeGrid
              limit={6}
              onViewAll={() => setBadgeCatalogOpen(true)}
            />

            {/* Leaderboard Section */}
            {user && (
              <LeaderboardSection
                userId={user.id}
                onViewFull={() => setLeaderboardModalOpen(true)}
              />
            )}
          </div>

          {/* RIGHT COLUMN: Settings / Areas */}
          <div className="space-y-4 mt-4 md:mt-0">
            <h2 className="text-lg font-semibold text-foreground px-1">Settings & Preferences</h2>

        {/* Watch Areas */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-lg flex items-center gap-2">
              <MapPin className="w-5 h-5 text-muted-foreground" />
              Watch Areas ({watchAreas.length})
            </h3>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setAddWatchAreaDialogOpen(true)}
              className="flex items-center gap-1"
            >
              <Plus className="w-4 h-4" />
              Add
            </Button>
          </div>

          {watchAreas.length > 0 ? (
            <div className="space-y-2">
              {watchAreas.map((area) => (
                <div key={area.id} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                  <div className="flex items-center gap-2 flex-1">
                    <MapPin className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <div className="text-sm font-medium">{area.name}</div>
                      <div className="text-xs text-muted-foreground">
                        Radius: {(area.radius / 1000).toFixed(1)}km
                      </div>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => deleteWatchAreaMutation.mutate(area.id)}
                    disabled={deleteWatchAreaMutation.isPending}
                  >
                    <Trash2 className="w-4 h-4 text-destructive" />
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-muted-foreground">
              <MapPin className="w-12 h-12 mx-auto mb-2 text-muted-foreground/40" />
              <p className="text-sm">No watch areas yet</p>
              <p className="text-xs mt-1">Add locations to monitor for alerts</p>
            </div>
          )}
        </Card>

        {/* City Preference */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-lg flex items-center gap-2">
              <MapPin className="w-5 h-5 text-muted-foreground" />
              City Preference
            </h3>
          </div>

          <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
            <div>
              <div className="text-sm font-medium">
                {user.city_preference ? (
                  CITIES[user.city_preference as keyof typeof CITIES]?.displayName || user.city_preference
                ) : (
                  'Not set'
                )}
              </div>
              <div className="text-xs text-muted-foreground">
                Your primary city for flood alerts
              </div>
            </div>
            {user.city_preference && (
              <Badge variant="outline" className="text-xs">
                {CITY_REGION_SHORT[user.city_preference || 'delhi'] || user.city_preference}
              </Badge>
            )}
          </div>

          {!user.city_preference && (
            <p className="text-xs text-muted-foreground mt-2">
              Set your city preference during onboarding or in settings
            </p>
          )}
        </Card>

        {/* Daily Routes */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-lg flex items-center gap-2">
              <Route className="w-5 h-5 text-muted-foreground" />
              Daily Routes ({dailyRoutes.length})
            </h3>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setAddRouteDialogOpen(true)}
              className="flex items-center gap-1"
            >
              <Plus className="w-4 h-4" />
              Add
            </Button>
          </div>

          {dailyRoutes.length > 0 ? (
            <div className="space-y-2">
              {dailyRoutes.map((route) => (
                <div key={route.id} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                  <div className="flex items-center gap-2 flex-1">
                    <Route className="w-4 h-4 text-muted-foreground" />
                    <div className="flex-1">
                      <div className="text-sm font-medium">{route.name}</div>
                      <div className="text-xs text-muted-foreground capitalize">
                        {route.transport_mode} • Flood alerts: {route.notify_on_flood ? 'On' : 'Off'}
                      </div>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      if (confirm(`Delete route "${route.name}"?`)) {
                        deleteRouteMutation.mutate(route.id, {
                          onSuccess: () => toast.success('Route deleted'),
                          onError: () => toast.error('Failed to delete route'),
                        });
                      }
                    }}
                  >
                    <Trash2 className="w-4 h-4 text-destructive" />
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-muted-foreground">
              <Route className="w-12 h-12 mx-auto mb-2 text-muted-foreground/40" />
              <p className="text-sm">No daily routes yet</p>
              <p className="text-xs mt-1">Add routes to get flood alerts along your commute</p>
            </div>
          )}
        </Card>

        {/* My Reports */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-lg flex items-center gap-2">
              <FileText className="w-5 h-5 text-muted-foreground" />
              My Reports ({userReports.length})
            </h3>
          </div>

          {reportsLoading ? (
            <div className="text-center py-6 text-muted-foreground">
              <div className="text-sm">Loading reports...</div>
            </div>
          ) : userReports.length > 0 ? (
            <div className="space-y-2 max-h-[clamp(150px,30vh,350px)] overflow-y-auto">
              {userReports.slice(0, 10).map((report: Report) => (
                <div key={report.id} className="p-3 bg-muted rounded-lg">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      {(() => {
                        const { tags, description } = parseReportDescription(report.description);
                        return (
                          <>
                            <ReportTagList tags={tags} />
                            <div className="text-sm font-medium line-clamp-2">{description}</div>
                          </>
                        );
                      })()}
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-muted-foreground">
                          {new Date(report.timestamp).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric'
                          })}
                        </span>
                        {report.verified ? (
                          <Badge variant="secondary" className="text-xs bg-green-100 text-green-800">
                            Verified
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="text-xs bg-yellow-100 text-yellow-800">
                            Pending
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <div className="text-right text-xs text-muted-foreground">
                        <div>{report.upvotes} upvotes</div>
                        {report.water_depth && (
                          <div className="capitalize">{report.water_depth}</div>
                        )}
                      </div>
                      <button
                        onClick={() => setSelectedReport(report)}
                        className="flex items-center gap-1 px-2 py-1 text-xs bg-primary/10 text-primary rounded hover:bg-primary/20 transition-colors"
                      >
                        <Eye className="w-3 h-3" />
                        View
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              {userReports.length > 10 && (
                <div className="text-center text-sm text-muted-foreground pt-2">
                  And {userReports.length - 10} more reports...
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-6 text-muted-foreground">
              <FileText className="w-12 h-12 mx-auto mb-2 text-muted-foreground/40" />
              <p className="text-sm">No reports yet</p>
              <p className="text-xs mt-1">Submit your first flood report to help your community</p>
            </div>
          )}
        </Card>

        {/* Notification Preferences */}
        <Card className="p-6">
          <h3 className="font-semibold text-lg flex items-center gap-2 mb-4">
            <Bell className="w-5 h-5 text-muted-foreground" />
            Notification Preferences
          </h3>

          <div className="space-y-4">
            {/* Channels */}
            <div className="bg-muted rounded-xl p-4 space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Channels</p>
              <div className="flex items-center justify-between">
                <Label htmlFor="push" className="cursor-pointer font-normal">
                  Push notifications
                </Label>
                <Switch
                  id="push"
                  checked={user.notification_push ?? true}
                  onCheckedChange={(checked) => handleNotificationToggle('notification_push', checked)}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="sms" className="cursor-pointer font-normal">
                  SMS alerts
                </Label>
                <Switch
                  id="sms"
                  checked={user.notification_sms ?? false}
                  onCheckedChange={(checked) => handleNotificationToggle('notification_sms', checked)}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="whatsapp" className="cursor-pointer font-normal">
                  WhatsApp updates
                </Label>
                <Switch
                  id="whatsapp"
                  checked={user.notification_whatsapp ?? false}
                  onCheckedChange={(checked) => handleNotificationToggle('notification_whatsapp', checked)}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="email" className="cursor-pointer font-normal">
                  Email notifications
                </Label>
                <Switch
                  id="email"
                  checked={user.notification_email ?? true}
                  onCheckedChange={(checked) => handleNotificationToggle('notification_email', checked)}
                />
              </div>
            </div>

            {/* Alert Types */}
            <div className="bg-muted rounded-xl p-4">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Alert Types</p>
              <div className="space-y-2">
                {[
                  { id: 'watch', label: 'Yellow Watch alerts', icon: '🟡' },
                  { id: 'advisory', label: 'Orange Advisory', icon: '🟠' },
                  { id: 'warning', label: 'Red Warning', icon: '🔴' },
                  { id: 'emergency', label: 'Emergency alerts', icon: '⚫' }
                ].map((alert) => (
                  <div key={alert.id} className="flex items-center gap-2">
                    <Checkbox
                      id={alert.id}
                      checked={user.alert_preferences?.[alert.id as keyof typeof user.alert_preferences] ?? true}
                      onCheckedChange={(checked) =>
                        handleAlertPreferenceToggle(alert.id, checked as boolean)
                      }
                    />
                    <Label htmlFor={alert.id} className="flex items-center gap-2 cursor-pointer font-normal">
                      <span>{alert.icon}</span>
                      <span className="text-sm">{alert.label}</span>
                    </Label>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>

        {/* Language Selection */}
        <Card className="p-6">
          <h3 className="font-semibold text-lg flex items-center gap-2 mb-4">
            <Globe className="w-5 h-5 text-muted-foreground" />
            Language
          </h3>

          <RadioGroup value={user.language || 'english'} onValueChange={handleLanguageChange}>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="english" id="english" />
              <Label htmlFor="english" className="cursor-pointer font-normal">English</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="hindi" id="hindi" />
              <Label htmlFor="hindi" className="cursor-pointer font-normal">हिन्दी (Hindi)</Label>
            </div>
          </RadioGroup>
        </Card>

        {/* Privacy Settings */}
        <Card className="p-6">
          <h3 className="font-semibold text-lg flex items-center gap-2 mb-3">
            <Settings className="w-5 h-5 text-muted-foreground" />
            Privacy Settings
          </h3>

          <div className="space-y-4">
            <div className="bg-muted rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <Label>Show on Leaderboard</Label>
                  <p className="text-xs text-muted-foreground">Display your profile on public leaderboards</p>
                </div>
                <Switch
                  checked={user.leaderboard_visible !== false}
                  onCheckedChange={(checked) => updateUserMutation.mutate({ leaderboard_visible: checked } as Partial<User>)}
                />
              </div>

              <Separator className="bg-border" />

              <div className="flex items-center justify-between">
                <div>
                  <Label>Public Profile</Label>
                  <p className="text-xs text-muted-foreground">Allow others to view your profile</p>
                </div>
                <Switch
                  checked={user.profile_public !== false}
                  onCheckedChange={(checked) => updateUserMutation.mutate({ profile_public: checked } as Partial<User>)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Display Name</Label>
              <p className="text-xs text-muted-foreground">Optional name shown instead of username</p>
              <Input
                placeholder="Enter display name"
                defaultValue={user.display_name || ''}
                onBlur={(e) => {
                  const value = e.target.value.trim();
                  if (value !== (user.display_name || '')) {
                    updateUserMutation.mutate({ display_name: value || null } as Partial<User>);
                  }
                }}
              />
            </div>
          </div>
        </Card>

        {/* Help & Tutorials */}
        <TourAgainButton />

        {/* About Section */}
        <Card className="p-6">
          <h3 className="font-semibold text-lg flex items-center gap-2 mb-3">
            <Settings className="w-5 h-5 text-muted-foreground" />
            About
          </h3>

          <div className="space-y-4 text-sm">
            <p className="text-xs text-muted-foreground">Version 1.0.0 (MVP)</p>

            {/* Links */}
            <div className="bg-muted rounded-xl p-4 space-y-1">
              <Button
                variant="ghost"
                className="w-full justify-start px-2 h-9 text-primary hover:text-primary/80 hover:bg-card font-normal rounded-lg"
                onClick={() => window.open('https://github.com/anthropics/floodsafe', '_blank')}
              >
                About FloodSafe
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start px-2 h-9 text-primary hover:text-primary/80 hover:bg-card font-normal rounded-lg"
                onClick={() => onNavigate?.('privacy')}
              >
                Privacy Policy
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start px-2 h-9 text-primary hover:text-primary/80 hover:bg-card font-normal rounded-lg"
                onClick={() => onNavigate?.('terms')}
              >
                Terms of Service
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start px-2 h-9 text-primary hover:text-primary/80 hover:bg-card font-normal rounded-lg"
                onClick={() => window.location.href = 'mailto:support@floodsafe.app?subject=FloodSafe Support Request'}
              >
                Contact Support
              </Button>
            </div>

            {/* Emergency Contacts — prominent */}
            <Button
              variant="ghost"
              className="w-full justify-start px-2 h-9 text-destructive hover:text-destructive/80 hover:bg-destructive/10 font-medium rounded-lg"
              onClick={() => setEmergencyModalOpen(true)}
            >
              <Phone className="w-4 h-4 mr-2" />
              Emergency Contacts
            </Button>

            {/* Install App button - only shown when PWA is installable */}
            {canInstall && !isInstalled && (
              <Button
                variant="ghost"
                className="w-full justify-start px-2 h-9 text-primary hover:text-primary/80 hover:bg-card font-normal rounded-lg"
                onClick={async () => {
                  const accepted = await promptInstall();
                  if (accepted) {
                    toast.success('FloodSafe installed! Check your apps.');
                  }
                }}
                disabled={isPrompting}
              >
                <Download className="w-4 h-4 mr-2" />
                {isPrompting ? 'Installing...' : 'Install App'}
              </Button>
            )}

            {/* Show "App Installed" indicator if already installed */}
            {isInstalled && (
              <p className="text-muted-foreground flex items-center gap-2 px-2">
                <Download className="w-4 h-4" />
                App Installed
              </p>
            )}
          </div>
        </Card>
          </div>{/* End RIGHT COLUMN */}
        </div>{/* End Two Column Grid */}

        {/* Logout */}
        <Button
          variant="destructive"
          className="w-full"
          onClick={async () => {
            try {
              await logout();
              toast.success('Logged out successfully');
            } catch (error) {
              toast.error('Failed to logout');
            }
          }}
        >
          <LogOut className="w-4 h-4 mr-2" />
          Logout
        </Button>
      </div>

      {/* Report Detail Modal */}
      <ReportDetailModal
        report={selectedReport}
        isOpen={selectedReport !== null}
        onClose={() => setSelectedReport(null)}
      />

      {/* Badge Catalog Modal */}
      <BadgeCatalogModal
        open={badgeCatalogOpen}
        onOpenChange={setBadgeCatalogOpen}
      />

      {/* Leaderboard Modal */}
      {user && (
        <LeaderboardModal
          open={leaderboardModalOpen}
          onOpenChange={setLeaderboardModalOpen}
          userId={user.id}
        />
      )}

      {/* Add Watch Area Dialog */}
      <AddWatchAreaDialog
        open={addWatchAreaDialogOpen}
        onOpenChange={setAddWatchAreaDialogOpen}
      />

      {/* Add Daily Route Dialog */}
      <AddDailyRouteDialog
        open={addRouteDialogOpen}
        onOpenChange={setAddRouteDialogOpen}
      />

      {/* Emergency Contacts Modal */}
      <EmergencyContactsModal
        isOpen={emergencyModalOpen}
        onClose={() => setEmergencyModalOpen(false)}
      />
    </div>
  );
}

// Tour the App Again button
function TourAgainButton() {
  const { startTour, state: botState } = useOnboardingBot();

  return (
    <Card className="p-6">
      <h3 className="font-semibold text-lg flex items-center gap-2 mb-3">
        <HelpCircle className="w-5 h-5 text-muted-foreground" />
        Help & Tutorials
      </h3>
      <Button
        variant="outline"
        className="w-full justify-start"
        onClick={() => startTour('app-tour')}
      >
        <span className="mr-2">💧</span>
        {t(botState.language, 'bot.tourAgain')}
      </Button>
    </Card>
  );
}

// Edit Profile Dialog Component
function EditProfileDialog({ user, onSave }: { user: User; onSave: (updates: Partial<User>) => void }) {
  const [username, setUsername] = useState(user.username);
  const [email, setEmail] = useState(user.email);
  const [phone, setPhone] = useState(user.phone || '');

  const handleSave = () => {
    const updates: Partial<User> = {};
    if (username !== user.username) updates.username = username;
    if (email !== user.email) updates.email = email;
    if (phone !== user.phone) updates.phone = phone;

    if (Object.keys(updates).length > 0) {
      onSave(updates);
    }
  };

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Edit Profile</DialogTitle>
      </DialogHeader>
      <div className="space-y-4 py-4">
        <div className="space-y-2">
          <Label htmlFor="edit-username">Username</Label>
          <Input
            id="edit-username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Enter username"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="edit-email">Email</Label>
          <Input
            id="edit-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Enter email"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="edit-phone">Phone Number</Label>
          <Input
            id="edit-phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="Enter phone number"
          />
        </div>
        <Button onClick={handleSave} className="w-full">
          Save Changes
        </Button>
      </div>
    </DialogContent>
  );
}
