import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Loader2, Settings, UserPlus, Users } from 'lucide-react';
import { useCircleDetail } from '../../lib/api/hooks';
import { useAuth } from '../../contexts/AuthContext';
import { CircleMemberList } from './CircleMemberList';
import { AddMemberModal } from './AddMemberModal';
import { InviteLinkShare } from './InviteLinkShare';
import { CircleSettingsSheet } from './CircleSettingsSheet';
import type { CircleType } from '../../types';

interface CircleDetailModalProps {
    isOpen: boolean;
    onClose: () => void;
    circleId: string | null;
}

const TYPE_LABELS: Record<CircleType, string> = {
    family: 'Family',
    school: 'School',
    apartment: 'Apartment',
    neighborhood: 'Neighborhood',
    custom: 'Custom',
};

export function CircleDetailModal({ isOpen, onClose, circleId }: CircleDetailModalProps) {
    const { user } = useAuth();
    const { data: circle, isLoading, error } = useCircleDetail(circleId);
    const [addMemberOpen, setAddMemberOpen] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);

    if (!circleId) return null;

    const canManage = circle && (circle.user_role === 'creator' || circle.user_role === 'admin');
    const currentMember = circle?.members.find((m) => m.user_id === user?.id);

    return (
        <>
            <Dialog open={isOpen} onOpenChange={onClose}>
                <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto p-0">
                    {isLoading ? (
                        <div className="flex items-center justify-center py-16">
                            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                        </div>
                    ) : error ? (
                        <div className="p-6 text-center">
                            <p className="text-red-500">Failed to load circle details</p>
                            <p className="text-sm text-gray-500 mt-1">{(error as Error).message}</p>
                        </div>
                    ) : circle ? (
                        <>
                            <DialogHeader className="p-4 pb-3 border-b">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <DialogTitle className="text-lg">{circle.name}</DialogTitle>
                                        <div className="flex items-center gap-2 mt-1">
                                            <Badge variant="outline" className="text-xs">
                                                {TYPE_LABELS[circle.circle_type]}
                                            </Badge>
                                            <span className="text-xs text-gray-500">
                                                <Users className="w-3 h-3 inline mr-0.5" />
                                                {circle.member_count}/{circle.max_members}
                                            </span>
                                        </div>
                                    </div>
                                    {currentMember && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => setSettingsOpen(true)}
                                        >
                                            <Settings className="w-4 h-4" />
                                        </Button>
                                    )}
                                </div>
                                {circle.description && (
                                    <p className="text-sm text-gray-600 mt-2">{circle.description}</p>
                                )}
                            </DialogHeader>

                            <div className="p-4 space-y-4">
                                {/* Invite Code */}
                                <InviteLinkShare
                                    inviteCode={circle.invite_code}
                                    circleName={circle.name}
                                />

                                {/* Members Section */}
                                <div>
                                    <div className="flex items-center justify-between mb-2">
                                        <p className="text-sm font-medium text-gray-700">
                                            Members ({circle.member_count})
                                        </p>
                                        {canManage && (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => setAddMemberOpen(true)}
                                                className="h-7 text-xs"
                                            >
                                                <UserPlus className="w-3 h-3 mr-1" />
                                                Add
                                            </Button>
                                        )}
                                    </div>
                                    <CircleMemberList
                                        members={circle.members}
                                        circleId={circle.id}
                                        userRole={circle.user_role}
                                        currentUserId={user?.id || ''}
                                    />
                                </div>
                            </div>
                        </>
                    ) : null}
                </DialogContent>
            </Dialog>

            {/* Sub-modals */}
            {circleId && (
                <AddMemberModal
                    isOpen={addMemberOpen}
                    onClose={() => setAddMemberOpen(false)}
                    circleId={circleId}
                />
            )}

            {circle && currentMember && (
                <CircleSettingsSheet
                    isOpen={settingsOpen}
                    onClose={() => setSettingsOpen(false)}
                    circleId={circle.id}
                    circleName={circle.name}
                    member={currentMember}
                    userRole={circle.user_role}
                />
            )}
        </>
    );
}
