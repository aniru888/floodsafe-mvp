import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { useAddCircleMember } from '../../lib/api/hooks';
import { toast } from 'sonner';

interface AddMemberModalProps {
    isOpen: boolean;
    onClose: () => void;
    circleId: string;
}

export function AddMemberModal({ isOpen, onClose, circleId }: AddMemberModalProps) {
    const [phone, setPhone] = useState('');
    const [displayName, setDisplayName] = useState('');
    const [email, setEmail] = useState('');

    const addMember = useAddCircleMember(circleId);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        if (!phone.trim() && !email.trim()) {
            toast.error('Please enter a phone number or email');
            return;
        }

        addMember.mutate(
            {
                phone: phone.trim() || undefined,
                email: email.trim() || undefined,
                display_name: displayName.trim() || undefined,
            },
            {
                onSuccess: () => {
                    toast.success(`${displayName.trim() || 'Member'} added to circle`);
                    setPhone('');
                    setDisplayName('');
                    setEmail('');
                    onClose();
                },
                onError: (err: Error) => {
                    toast.error(err.message || 'Failed to add member');
                },
            }
        );
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <DialogTitle>Add Member</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="text-sm font-medium text-foreground block mb-1">
                            Display Name
                        </label>
                        <Input
                            value={displayName}
                            onChange={(e) => setDisplayName(e.target.value)}
                            placeholder="e.g., Mom, Neighbour Rajesh"
                            maxLength={100}
                            autoFocus
                        />
                    </div>

                    <div>
                        <label className="text-sm font-medium text-foreground block mb-1">
                            Phone Number
                        </label>
                        <Input
                            value={phone}
                            onChange={(e) => setPhone(e.target.value)}
                            placeholder="+91 98765 43210"
                            type="tel"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                            WhatsApp/SMS alerts will be sent to this number
                        </p>
                    </div>

                    <div>
                        <label className="text-sm font-medium text-foreground block mb-1">
                            Email (optional)
                        </label>
                        <Input
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="name@example.com"
                            type="email"
                        />
                    </div>

                    <Button
                        type="submit"
                        className="w-full"
                        disabled={addMember.isPending || (!phone.trim() && !email.trim())}
                    >
                        {addMember.isPending ? 'Adding...' : 'Add Member'}
                    </Button>
                </form>
            </DialogContent>
        </Dialog>
    );
}
