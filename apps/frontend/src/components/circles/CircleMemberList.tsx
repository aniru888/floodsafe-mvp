import { User, Phone, Mail, Shield, Crown, UserMinus, MoreVertical } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { useRemoveCircleMember } from '../../lib/api/hooks';
import type { CircleMember, CircleRole } from '../../types';
import { toast } from 'sonner';

interface CircleMemberListProps {
    members: CircleMember[];
    circleId: string;
    userRole: CircleRole;
    currentUserId: string;
}

function getRoleBadge(role: CircleRole) {
    switch (role) {
        case 'creator':
            return (
                <Badge variant="default" className="bg-amber-500 text-xs px-1.5 py-0">
                    <Crown className="w-3 h-3 mr-0.5" />
                    Creator
                </Badge>
            );
        case 'admin':
            return (
                <Badge variant="default" className="bg-blue-500 text-xs px-1.5 py-0">
                    <Shield className="w-3 h-3 mr-0.5" />
                    Admin
                </Badge>
            );
        default:
            return null;
    }
}

export function CircleMemberList({ members, circleId, userRole, currentUserId }: CircleMemberListProps) {
    const removeMember = useRemoveCircleMember(circleId);
    const canManage = userRole === 'creator' || userRole === 'admin';

    const handleRemove = (memberId: string, displayName: string | null) => {
        if (!confirm(`Remove ${displayName || 'this member'} from the circle?`)) return;
        removeMember.mutate(memberId, {
            onSuccess: () => {
                toast.success(`${displayName || 'Member'} removed`);
            },
            onError: (err: Error) => {
                toast.error(err.message || 'Failed to remove member');
            },
        });
    };

    if (members.length === 0) {
        return (
            <div className="text-center py-6 text-gray-500 text-sm">
                No members yet. Add members to get started.
            </div>
        );
    }

    return (
        <div className="space-y-1">
            {members.map((member) => {
                const isCurrentUser = member.user_id === currentUserId;
                const displayName = member.display_name || member.email || member.phone || 'Unknown';

                return (
                    <div
                        key={member.id}
                        className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                        <div className="w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                            {member.user_id ? (
                                <User className="w-4 h-4 text-blue-600" />
                            ) : member.phone ? (
                                <Phone className="w-4 h-4 text-green-600" />
                            ) : (
                                <Mail className="w-4 h-4 text-purple-600" />
                            )}
                        </div>

                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5">
                                <span className="text-sm font-medium text-gray-900 truncate">
                                    {displayName}
                                    {isCurrentUser && (
                                        <span className="text-gray-400 font-normal"> (you)</span>
                                    )}
                                </span>
                                {getRoleBadge(member.role)}
                            </div>
                            <div className="flex items-center gap-2 text-xs text-gray-400 mt-0.5">
                                {member.user_id ? (
                                    <span>Registered user</span>
                                ) : member.phone ? (
                                    <span>{member.phone}</span>
                                ) : member.email ? (
                                    <span>{member.email}</span>
                                ) : null}
                                {member.is_muted && (
                                    <span className="text-orange-500">Muted</span>
                                )}
                            </div>
                        </div>

                        {canManage && !isCurrentUser && member.role !== 'creator' && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="text-red-400 hover:text-red-600 hover:bg-red-50 flex-shrink-0 h-8 w-8 p-0"
                                onClick={() => handleRemove(member.id, member.display_name)}
                                disabled={removeMember.isPending}
                            >
                                <UserMinus className="w-4 h-4" />
                            </Button>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
