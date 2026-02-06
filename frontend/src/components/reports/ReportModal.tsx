import { useState, useRef } from 'react';
import { Camera, MapPin, X, Loader2 } from 'lucide-react';
import { api } from '../../lib/api';

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentLocation: { lat: number; lng: number } | null;
  onSuccess: () => void;
}

export function ReportModal({ isOpen, onClose, currentLocation, onSuccess }: ReportModalProps) {
  const [description, setDescription] = useState('');
  const [waterLevel, setWaterLevel] = useState(0);
  const [image, setImage] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentLocation) {
      alert("Location is required. Please enable GPS.");
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('latitude', currentLocation.lat.toString());
    formData.append('longitude', currentLocation.lng.toString());
    formData.append('description', description);
    formData.append('water_level', waterLevel.toString());
    if (image) {
      formData.append('image', image);
    }

    try {
      await api.post('/reports/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      onSuccess();
      onClose();
    } catch (error) {
      console.error('Failed to submit report', error);
      alert('Failed to submit report. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setImage(e.target.files[0]);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-card w-full max-w-md rounded-xl shadow-lg border animate-in fade-in zoom-in duration-200">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Report Flood</h2>
          <button onClick={onClose} className="p-1 hover:bg-muted rounded-full">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Location Status */}
          <div className="flex items-center gap-2 text-sm p-3 bg-muted/50 rounded-lg">
            <MapPin className={`h-4 w-4 ${currentLocation ? 'text-green-500' : 'text-red-500'}`} />
            <span>
              {currentLocation 
                ? `Location detected: ${currentLocation.lat.toFixed(4)}, ${currentLocation.lng.toFixed(4)}` 
                : 'Waiting for GPS location...'}
            </span>
          </div>

          {/* Water Level Selector */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Water Level Severity</label>
            <div className="grid grid-cols-4 gap-2">
              {['None', 'Low', 'Medium', 'High'].map((level, index) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => setWaterLevel(index)}
                  className={`py-2 px-1 text-xs sm:text-sm rounded-md border transition-colors ${
                    waterLevel === index
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'hover:bg-accent'
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>
          </div>

          {/* Photo Upload */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Photo Evidence</label>
            <div 
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center cursor-pointer hover:bg-muted/50 transition-colors"
            >
              {image ? (
                <div className="text-center">
                  <p className="text-sm font-medium text-primary truncate max-w-[200px]">{image.name}</p>
                  <p className="text-xs text-muted-foreground">Click to change</p>
                </div>
              ) : (
                <>
                  <Camera className="h-8 w-8 text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">Tap to upload photo</p>
                </>
              )}
              <input 
                ref={fileInputRef}
                type="file" 
                accept="image/*" 
                className="hidden" 
                onChange={handleFileChange}
              />
            </div>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the situation..."
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          <button
            type="submit"
            disabled={loading || !currentLocation}
            className="w-full inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-destructive text-destructive-foreground hover:bg-destructive/90 h-10 px-4 py-2"
          >
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : 'Submit Report'}
          </button>
        </form>
      </div>
    </div>
  );
}
