import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { useJoinCircle } from '../../lib/api/hooks';
import { toast } from 'sonner';

interface JoinCircleModalProps {
    isOpen: boolean;
    onClose: () => void;
    initialCode?: string;
}

export function JoinCircleModal({ isOpen, onClose, initialCode = '' }: JoinCircleModalProps) {
    const [code, setCode] = useState(initialCode);
    const joinCircle = useJoinCircle();

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const trimmed = code.trim();
        if (!trimmed) {
            toast.error('Please enter an invite code');
            return;
        }

        joinCircle.mutate(
            { invite_code: trimmed },
            {
                onSuccess: (circle) => {
                    toast.success(`Joined "${circle.name}"!`);
                    setCode('');
                    onClose();
                },
                onError: (err: Error) => {
                    toast.error(err.message || 'Invalid invite code');
                },
            }
        );
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <DialogTitle>Join a Safety Circle</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-1">
                            Invite Code
                        </label>
                        <Input
                            value={code}
                            onChange={(e) => setCode(e.target.value.toUpperCase())}
                            placeholder="Enter 8-character code"
                            maxLength={12}
                            className="text-center font-mono text-lg tracking-widest"
                            autoFocus
                        />
                        <p className="text-xs text-gray-500 mt-1">
                            Ask the circle creator for the invite code
                        </p>
                    </div>

                    <Button
                        type="submit"
                        className="w-full"
                        disabled={joinCircle.isPending || !code.trim()}
                    >
                        {joinCircle.isPending ? 'Joining...' : 'Join Circle'}
                    </Button>
                </form>
            </DialogContent>
        </Dialog>
    );
}
