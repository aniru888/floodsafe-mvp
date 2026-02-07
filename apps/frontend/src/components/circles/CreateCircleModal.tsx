import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { useCreateCircle } from '../../lib/api/hooks';
import type { CircleType } from '../../types';
import { toast } from 'sonner';

interface CreateCircleModalProps {
    isOpen: boolean;
    onClose: () => void;
}

const CIRCLE_TYPES: { value: CircleType; label: string; desc: string }[] = [
    { value: 'family', label: 'Family', desc: 'Up to 20 members' },
    { value: 'apartment', label: 'Apartment', desc: 'Up to 200 members' },
    { value: 'school', label: 'School', desc: 'Up to 500 members' },
    { value: 'neighborhood', label: 'Neighborhood', desc: 'Up to 1000 members' },
    { value: 'custom', label: 'Custom', desc: 'Up to 50 members' },
];

export function CreateCircleModal({ isOpen, onClose }: CreateCircleModalProps) {
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [circleType, setCircleType] = useState<CircleType>('family');

    const createCircle = useCreateCircle();

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!name.trim()) {
            toast.error('Please enter a circle name');
            return;
        }

        createCircle.mutate(
            {
                name: name.trim(),
                description: description.trim() || undefined,
                circle_type: circleType,
            },
            {
                onSuccess: (circle) => {
                    toast.success(`"${circle.name}" created! Share the invite code with members.`);
                    setName('');
                    setDescription('');
                    setCircleType('family');
                    onClose();
                },
                onError: (err: Error) => {
                    toast.error(err.message || 'Failed to create circle');
                },
            }
        );
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-md">
                <DialogHeader>
                    <DialogTitle>Create Safety Circle</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="text-sm font-medium text-foreground block mb-1">
                            Circle Name
                        </label>
                        <Input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="e.g., Sharma Family, Block A Residents"
                            maxLength={100}
                            autoFocus
                        />
                    </div>

                    <div>
                        <label className="text-sm font-medium text-foreground block mb-1">
                            Description (optional)
                        </label>
                        <Input
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Brief description of this circle"
                            maxLength={500}
                        />
                    </div>

                    <div>
                        <label className="text-sm font-medium text-foreground block mb-2">
                            Circle Type
                        </label>
                        <div className="grid grid-cols-2 gap-2">
                            {CIRCLE_TYPES.map((type) => (
                                <button
                                    key={type.value}
                                    type="button"
                                    onClick={() => setCircleType(type.value)}
                                    className={`text-left p-2.5 rounded-xl border transition-colors ${
                                        circleType === type.value
                                            ? 'border-primary bg-primary/5 text-primary'
                                            : 'border-border hover:border-border/80'
                                    }`}
                                >
                                    <p className="text-sm font-medium">{type.label}</p>
                                    <p className="text-xs text-muted-foreground">{type.desc}</p>
                                </button>
                            ))}
                        </div>
                    </div>

                    <Button
                        type="submit"
                        className="w-full"
                        disabled={createCircle.isPending || !name.trim()}
                    >
                        {createCircle.isPending ? 'Creating...' : 'Create Circle'}
                    </Button>
                </form>
            </DialogContent>
        </Dialog>
    );
}
