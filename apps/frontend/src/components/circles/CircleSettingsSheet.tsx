import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Switch } from '../ui/switch';
import { Button } from '../ui/button';
import { useUpdateCircleMember, useLeaveCircle, useDeleteCircle } from '../../lib/api/hooks';
import type { CircleMember, CircleRole } from '../../types';
import { toast } from 'sonner';
import { LogOut, Trash2 } from 'lucide-react';

interface CircleSettingsSheetProps {
    isOpen: boolean;
    onClose: () => void;
    circleId: string;
    circleName: string;
    member: CircleMember;
    userRole: CircleRole;
}

export function CircleSettingsSheet({
    isOpen,
    onClose,
    circleId,
    circleName,
    member,
    userRole,
}: CircleSettingsSheetProps) {
    const updateMember = useUpdateCircleMember(circleId);
    const leaveCircle = useLeaveCircle();
    const deleteCircle = useDeleteCircle();

    const handleToggle = (field: 'is_muted' | 'notify_whatsapp' | 'notify_sms', value: boolean) => {
        updateMember.mutate(
            { memberId: member.id, data: { [field]: value } },
            {
                onError: (err: Error) => {
                    toast.error(err.message || 'Failed to update settings');
                },
            }
        );
    };

    const handleLeave = () => {
        if (!confirm(`Leave "${circleName}"? You'll stop receiving alerts from this circle.`)) return;
        leaveCircle.mutate(circleId, {
            onSuccess: () => {
                toast.success(`Left "${circleName}"`);
                onClose();
            },
            onError: (err: Error) => {
                toast.error(err.message || 'Failed to leave circle');
            },
        });
    };

    const handleDelete = () => {
        if (!confirm(`Delete "${circleName}"? This will remove all members and cannot be undone.`)) return;
        deleteCircle.mutate(circleId, {
            onSuccess: () => {
                toast.success(`"${circleName}" deleted`);
                onClose();
            },
            onError: (err: Error) => {
                toast.error(err.message || 'Failed to delete circle');
            },
        });
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <DialogTitle>Circle Settings</DialogTitle>
                </DialogHeader>
                <div className="space-y-5">
                    {/* Notification Preferences */}
                    <div className="space-y-3">
                        <p className="text-sm font-medium text-gray-700">Notifications</p>

                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm">Mute this circle</p>
                                <p className="text-xs text-gray-500">Stop all alerts from this circle</p>
                            </div>
                            <Switch
                                checked={member.is_muted}
                                onCheckedChange={(checked) => handleToggle('is_muted', checked)}
                            />
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm">WhatsApp alerts</p>
                                <p className="text-xs text-gray-500">Receive via WhatsApp</p>
                            </div>
                            <Switch
                                checked={member.notify_whatsapp}
                                onCheckedChange={(checked) => handleToggle('notify_whatsapp', checked)}
                                disabled={member.is_muted}
                            />
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm">SMS alerts</p>
                                <p className="text-xs text-gray-500">Receive via SMS</p>
                            </div>
                            <Switch
                                checked={member.notify_sms}
                                onCheckedChange={(checked) => handleToggle('notify_sms', checked)}
                                disabled={member.is_muted}
                            />
                        </div>
                    </div>

                    {/* Danger Zone */}
                    <div className="border-t pt-4 space-y-2">
                        <Button
                            variant="outline"
                            className="w-full text-red-600 border-red-200 hover:bg-red-50"
                            onClick={handleLeave}
                            disabled={userRole === 'creator' || leaveCircle.isPending}
                        >
                            <LogOut className="w-4 h-4 mr-2" />
                            {userRole === 'creator' ? 'Creator cannot leave' : 'Leave Circle'}
                        </Button>

                        {userRole === 'creator' && (
                            <Button
                                variant="outline"
                                className="w-full text-red-600 border-red-200 hover:bg-red-50"
                                onClick={handleDelete}
                                disabled={deleteCircle.isPending}
                            >
                                <Trash2 className="w-4 h-4 mr-2" />
                                Delete Circle
                            </Button>
                        )}
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
