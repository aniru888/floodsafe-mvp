import { useState } from 'react';
import { Copy, Share2, Check } from 'lucide-react';
import { Button } from '../ui/button';
import { toast } from 'sonner';

interface InviteLinkShareProps {
    inviteCode: string;
    circleName: string;
}

export function InviteLinkShare({ inviteCode, circleName }: InviteLinkShareProps) {
    const [copied, setCopied] = useState(false);

    const inviteUrl = `${window.location.origin}?join=${inviteCode}`;

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(inviteCode);
            setCopied(true);
            toast.success('Invite code copied!');
            setTimeout(() => setCopied(false), 2000);
        } catch {
            toast.error('Failed to copy. Please copy manually.');
        }
    };

    const handleShare = async () => {
        if (!navigator.share) {
            handleCopy();
            return;
        }
        try {
            await navigator.share({
                title: `Join ${circleName} on FloodSafe`,
                text: `Join my Safety Circle "${circleName}" on FloodSafe! Use invite code: ${inviteCode}`,
                url: inviteUrl,
            });
        } catch (err) {
            // User cancelled share — not an error
            if ((err as DOMException).name !== 'AbortError') {
                toast.error('Failed to share');
            }
        }
    };

    return (
        <div className="bg-gray-50 rounded-lg p-3 space-y-2">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                Invite Code
            </p>
            <div className="flex items-center gap-2">
                <div className="flex-1 bg-white border rounded-md px-3 py-2 text-center font-mono text-lg tracking-widest select-all">
                    {inviteCode}
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCopy}
                    className="flex-shrink-0"
                >
                    {copied ? (
                        <Check className="w-4 h-4 text-green-500" />
                    ) : (
                        <Copy className="w-4 h-4" />
                    )}
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleShare}
                    className="flex-shrink-0"
                >
                    <Share2 className="w-4 h-4" />
                </Button>
            </div>
        </div>
    );
}
