import React, { useState } from 'react';
import { useReportMutation } from '../lib/api/hooks';
import { useUser } from '../contexts/UserContext';
import { X } from 'lucide-react';

interface ReportModalProps {
    isOpen: boolean;
    onClose: () => void;
    userLocation: { lat: number; lng: number } | null;
}

export const ReportModal: React.FC<ReportModalProps> = ({ isOpen, onClose, userLocation }) => {
    const [description, setDescription] = useState('');
    const [image, setImage] = useState<File | null>(null);
    const mutation = useReportMutation();
    const { userId } = useUser();

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!userLocation) {
            alert("Location not available");
            return;
        }

        if (!userId) {
            alert("Please log in to submit a report");
            return;
        }

        if (!image) {
            alert("Please attach a photo of the flood");
            return;
        }

        try {
            await mutation.mutateAsync({
                user_id: userId,
                description,
                latitude: userLocation.lat,
                longitude: userLocation.lng,
                image: image
            });
            alert("Report submitted successfully!");
            onClose();
            setDescription('');
            setImage(null);
        } catch (error) {
            alert("Failed to submit report");
            console.error(error);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-card rounded-lg p-6 w-full max-w-md relative">
                <button onClick={onClose} className="absolute top-4 right-4 text-muted-foreground hover:text-foreground">
                    <X size={24} />
                </button>

                <h2 className="text-xl font-bold mb-4">Report Flood</h2>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label htmlFor="report-description" className="block text-sm font-medium text-foreground">Description</label>
                        <textarea
                            id="report-description"
                            name="description"
                            className="mt-1 block w-full rounded-md border-border shadow-sm focus:border-primary focus:ring-ring border p-2"
                            rows={3}
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="report-photo" className="block text-sm font-medium text-foreground">
                            Photo <span className="text-red-500">*</span>
                        </label>
                        <input
                            id="report-photo"
                            name="photo"
                            type="file"
                            accept="image/*"
                            onChange={(e) => setImage(e.target.files?.[0] || null)}
                            className="mt-1 block w-full"
                            required
                        />
                    </div>

                    <div className="text-sm text-muted-foreground">
                        Location: {userLocation ? `${userLocation.lat.toFixed(4)}, ${userLocation.lng.toFixed(4)}` : 'Locating...'}
                    </div>

                    <button
                        type="submit"
                        disabled={mutation.isPending || !userLocation}
                        className="w-full bg-primary text-primary-foreground py-2 px-4 rounded hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground"
                    >
                        {mutation.isPending ? 'Submitting...' : 'Submit Report'}
                    </button>
                </form>
            </div>
        </div>
    );
};
