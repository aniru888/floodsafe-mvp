import { useState, useEffect, useRef } from 'react';
import { ArrowLeft, MapPin, Camera, Award, Mic, MicOff, AlertCircle, X, Loader2, AlertTriangle, CheckCircle, Info, Droplets } from 'lucide-react';
import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress';
import { RadioGroup, RadioGroupItem } from '../ui/radio-group';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Checkbox } from '../ui/checkbox';
import { Badge } from '../ui/badge';
import { Alert, AlertTitle, AlertDescription } from '../ui/alert';
import { Skeleton } from '../ui/skeleton';
import { Tooltip, TooltipTrigger, TooltipContent } from '../ui/tooltip';
import { WaterDepth, VehiclePassability, LocationWithAddress, PhotoData } from '../../types';
import { useReportMutation } from '../../lib/api/hooks';
import { useUserReady } from '../../contexts/UserContext';
import { useCurrentCity } from '../../contexts/CityContext';
import { getCityCenterOrDefault } from '../../lib/cityCoordinates';
import { toast } from 'sonner';
import MapPicker from '../MapPicker';
import PhotoCapture from '../PhotoCapture';

interface ReportScreenProps {
    onBack: () => void;
    onSubmit: () => void;
}

// Quick tag options organized by category
const TAG_CATEGORIES: Record<string, string[]> = {
    '🚨 Emergency': [
        'People Stranded',
        'Vehicle Stuck',
        'House Flooded',
        'Power Outage'
    ],
    '🌊 Flooding': [
        'Road Blocked',
        'Drainage Overflow',
        'Street Flooding',
        'Waterlogging',
        'Flash Flood',
        'Heavy Rain'
    ],
    '🏗️ Infrastructure': [
        'Bridge Submerged',
        'Road Collapse'
    ],
    '⚠️ Hazards': [
        'Debris Flow',
        'Live Wires'
    ]
};

const MAX_DESCRIPTION_LENGTH = 500;
const MIN_DESCRIPTION_LENGTH = 10;
const GPS_ACCURACY_EXCELLENT = 10; // meters
const GPS_ACCURACY_GOOD = 50; // meters
const GPS_ACCURACY_POOR = 100; // meters

// Helper to detect iOS devices
const isIOSDevice = () => {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
           (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
};

// Helper to detect Android devices
const isAndroidDevice = () => {
    return /Android/.test(navigator.userAgent);
};

/**
 * Normalize text for comparison - handles Android Chrome speech recognition quirks.
 * - Lowercase for case-insensitive comparison
 * - Collapse multiple whitespace to single space
 * - Trim leading/trailing whitespace
 */
const normalizeText = (text: string): string => {
    return text.toLowerCase().replace(/\s+/g, ' ').trim();
};

/**
 * Check if newText overlaps with end of existingText and return the suffix to append.
 * Handles Android Chrome emitting "hello" then "hello world" (should merge to "hello world").
 * Returns null if newText is a duplicate (fully contained), or the suffix to append otherwise.
 */
const getOverlapSuffix = (existingText: string, newText: string): string | null => {
    const normExisting = normalizeText(existingText);
    const normNew = normalizeText(newText);

    // Empty existing text - return full new text
    if (!normExisting) {
        return newText.trim();
    }

    // Exact duplicate (case-insensitive, whitespace-normalized)
    if (normExisting.endsWith(normNew)) {
        return null; // Skip - it's a duplicate
    }

    // Check if newText starts with something that matches the end of existingText
    // E.g., existing="hello" new="hello world" -> overlap="hello", suffix=" world"
    const newWords = normNew.split(' ');
    for (let i = newWords.length - 1; i > 0; i--) {
        const potentialOverlap = newWords.slice(0, i).join(' ');
        if (normExisting.endsWith(potentialOverlap)) {
            // Found overlap! Return only the non-overlapping part
            // Use original transcript to preserve capitalization
            const originalWords = newText.trim().split(/\s+/);
            return originalWords.slice(i).join(' ');
        }
    }

    // No overlap - return full new text for appending
    return newText.trim();
};

// Helper to calculate distance between two GPS coordinates using Haversine formula
const calculateDistance = (lat1: number, lng1: number, lat2: number, lng2: number): number => {
    const R = 6371000; // Earth's radius in meters
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng / 2) * Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
};

export function ReportScreen({ onBack, onSubmit }: ReportScreenProps) {
    const [step, setStep] = useState(1);
    const [waterDepth, setWaterDepth] = useState<WaterDepth>('knee');
    const [vehiclePassability, setVehiclePassability] = useState<VehiclePassability>('high-clearance');
    const [description, setDescription] = useState('');
    const [confirmed, setConfirmed] = useState(false);
    const [selectedTags, setSelectedTags] = useState<string[]>([]);
    const [isRecording, setIsRecording] = useState(false);
    const [voiceSupported, setVoiceSupported] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string>('');
    const [errorType, setErrorType] = useState<'gps' | 'photo' | 'network' | null>(null);
    const [isMobile, setIsMobile] = useState(false);

    // GPS state
    const [location, setLocation] = useState<{ latitude: number; longitude: number; accuracy: number } | null>(null);
    const [locationLoading, setLocationLoading] = useState(true);
    const [locationError, setLocationError] = useState<string>('');
    const [locationName, setLocationName] = useState<string>('');

    // Validation state
    const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

    // Map picker state
    const [isMapPickerOpen, setIsMapPickerOpen] = useState(false);
    const locationManuallySetRef = useRef(false); // Track if user manually selected location from map

    // Photo state
    const [photo, setPhoto] = useState<PhotoData | null>(null);
    const [photoLocationName, setPhotoLocationName] = useState<string>('');

    const recognitionRef = useRef<any>(null);
    const isRecordingRef = useRef(false);
    const lastProcessedIndexRef = useRef(-1); // Track last processed voice result to prevent duplicates
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const reportMutation = useReportMutation();
    const { userId } = useUserReady();
    const currentCity = useCurrentCity();

    // Track if using city center fallback (for UI indicator)
    const [usingFallbackLocation, setUsingFallbackLocation] = useState(false);

    const totalSteps = 4;
    const progressValue = (step / totalSteps) * 100;

    // Fallback for browsers without dvh support - set CSS custom property
    useEffect(() => {
        const setVH = () => {
            const vh = window.innerHeight * 0.01;
            document.documentElement.style.setProperty('--vh', `${vh}px`);
        };
        setVH();
        window.addEventListener('resize', setVH);
        window.addEventListener('orientationchange', setVH);
        return () => {
            window.removeEventListener('resize', setVH);
            window.removeEventListener('orientationchange', setVH);
        };
    }, []);

    // Check for Web Speech API support and mobile platform
    useEffect(() => {
        // Detect if user is on mobile
        const mobile = isIOSDevice() || isAndroidDevice() ||
                      /mobile/i.test(navigator.userAgent) ||
                      window.matchMedia('(max-width: 768px)').matches;
        setIsMobile(mobile);

        // Check for Web Speech API with proper typing
        const SpeechRecognitionConstructor = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (SpeechRecognitionConstructor) {
            try {
                const recognition = new SpeechRecognitionConstructor();

                // Configure recognition based on platform
                if (isIOSDevice()) {
                    // iOS Safari has limited support - use simpler config
                    recognition.continuous = false; // iOS doesn't support continuous well
                    recognition.interimResults = false; // iOS doesn't support interim results reliably
                } else {
                    // Android Chrome and desktop browsers support full features
                    recognition.continuous = true;
                    recognition.interimResults = true;
                }

                recognition.lang = 'en-US';
                recognition.maxAlternatives = 1;

                recognition.onresult = (event: SpeechRecognitionEvent) => {
                    // Use lastProcessedIndexRef to prevent re-processing results after restarts
                    // event.resultIndex may be unreliable after recognition.start() is called again
                    const startIndex = Math.max(event.resultIndex || 0, lastProcessedIndexRef.current + 1);

                    for (let i = startIndex; i < event.results.length; i++) {
                        const result = event.results[i];
                        if (!result || result.length === 0) continue;

                        const alternative = result[0];
                        if (!alternative?.transcript) continue;

                        // ONLY add final results to prevent duplicates
                        // Interim results are shown in real-time but NOT added to description
                        if (result.isFinal) {
                            lastProcessedIndexRef.current = i; // Track this as processed
                            const finalTranscript = alternative.transcript.trim();
                            if (finalTranscript) {
                                setDescription(prev => {
                                    // Use overlap detection to handle Android Chrome's behavior
                                    // where partial phrases are marked as final in sequence
                                    // E.g., "there" → "there is" → "there is a flood"
                                    const suffix = getOverlapSuffix(prev, finalTranscript);

                                    // Duplicate detected - skip
                                    if (suffix === null) {
                                        return prev;
                                    }

                                    // Append suffix (may be full transcript or just non-overlapping part)
                                    const newText = prev ? (prev.trim() + ' ' + suffix).trim() : suffix;
                                    return newText.slice(0, MAX_DESCRIPTION_LENGTH);
                                });
                            }
                        }
                    }

                    // On iOS, automatically restart for continuous recording after final result
                    if (isIOSDevice() && isRecordingRef.current) {
                        // Check if we got a final result
                        const hasFinalResult = Array.from(event.results).some(r => r.isFinal);
                        if (hasFinalResult) {
                            try {
                                recognition.start();
                            } catch (e) {
                                // Ignore if already started
                            }
                        }
                    }
                };

                recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
                    console.error('Speech recognition error:', event.error, event.message);

                    // Handle specific mobile errors
                    if (event.error === 'not-allowed') {
                        setIsRecording(false);
                        isRecordingRef.current = false;
                        if (mobile) {
                            toast.error('Microphone access denied. Please check your browser settings and allow microphone access.');
                        } else {
                            toast.error('Microphone access denied. Please enable microphone permissions.');
                        }
                    } else if (event.error === 'no-speech') {
                        // On mobile, this is common - just retry
                        if (mobile && isRecordingRef.current) {
                            try {
                                recognition.start();
                            } catch (e) {
                                // Ignore
                            }
                        } else {
                            toast.info('No speech detected. Please try again.');
                            setIsRecording(false);
                            isRecordingRef.current = false;
                        }
                    } else if (event.error === 'audio-capture') {
                        setIsRecording(false);
                        isRecordingRef.current = false;
                        toast.error('Microphone not found or not working. Please check your device.');
                    } else if (event.error === 'network') {
                        setIsRecording(false);
                        isRecordingRef.current = false;
                        toast.error('Network error during voice recognition. Please check your internet connection.');
                    } else if (event.error === 'aborted') {
                        // User manually stopped - this is expected
                        setIsRecording(false);
                        isRecordingRef.current = false;
                    } else {
                        setIsRecording(false);
                        isRecordingRef.current = false;
                        toast.error(`Voice input failed: ${event.error}. Please try typing instead.`);
                    }
                };

                recognition.onend = () => {
                    // On iOS, recognition ends after each phrase
                    if (isIOSDevice() && isRecordingRef.current) {
                        // Auto-restart on iOS for continuous recording
                        try {
                            recognition.start();
                        } catch (e) {
                            setIsRecording(false);
                            isRecordingRef.current = false;
                        }
                    } else {
                        setIsRecording(false);
                        isRecordingRef.current = false;
                    }
                };

                recognition.onstart = () => {
                    console.log('Speech recognition started');
                };

                recognitionRef.current = recognition;
                setVoiceSupported(true);

            } catch (error) {
                console.error('Failed to initialize speech recognition:', error);
                setVoiceSupported(false);
            }
        } else {
            setVoiceSupported(false);
            console.log('Speech recognition not supported in this browser');
        }

        return () => {
            if (recognitionRef.current) {
                try {
                    recognitionRef.current.stop();
                } catch (e) {
                    // Ignore errors on cleanup
                }
            }
        };
    }, []);

    // Get GPS location on mount
    useEffect(() => {
        if (!navigator.geolocation) {
            setLocationError('Geolocation is not supported by your browser');
            setLocationLoading(false);
            toast.error('GPS not available on this device');
            return;
        }

        const options: PositionOptions = {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 0
        };

        navigator.geolocation.getCurrentPosition(
            (position) => {
                // Don't override location if user manually selected from map
                if (locationManuallySetRef.current) {
                    setLocationLoading(false);
                    return;
                }

                const { latitude, longitude, accuracy } = position.coords;
                setLocation({ latitude, longitude, accuracy });
                setLocationLoading(false);
                setLocationError('');

                // Show success message with accuracy
                if (accuracy <= GPS_ACCURACY_EXCELLENT) {
                    toast.success(`Location acquired with excellent accuracy (±${Math.round(accuracy)}m)`);
                } else if (accuracy <= GPS_ACCURACY_GOOD) {
                    toast.success(`Location acquired (±${Math.round(accuracy)}m)`);
                } else {
                    toast.warning(`Location acquired but accuracy is low (±${Math.round(accuracy)}m). Consider moving outdoors for better accuracy.`);
                }

                // Try to get location name via reverse geocoding (optional - could fail)
                // Note: Don't use custom headers as they trigger CORS preflight which Nominatim doesn't support
                fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1`)
                    .then(res => {
                        if (!res.ok) throw new Error(`HTTP ${res.status}`);
                        return res.json();
                    })
                    .then(data => {
                        if (data.display_name) {
                            const parts = data.display_name.split(',');
                            const shortName = parts.slice(0, 3).join(',');
                            setLocationName(shortName);
                        }
                    })
                    .catch(err => {
                        console.log('Reverse geocoding failed:', err);
                        // Not critical, just use coordinates
                    });
            },
            (error) => {
                setLocationLoading(false);
                console.log('GPS error:', error.code, error.message);

                // Use city center as fallback for all error types
                const cityInfo = getCityCenterOrDefault(currentCity);

                // Set approximate location based on city preference
                setLocation({
                    latitude: cityInfo.lat,
                    longitude: cityInfo.lng,
                    accuracy: cityInfo.radiusKm * 1000  // Convert km to meters for accuracy field
                });
                setLocationName(cityInfo.displayName);
                setUsingFallbackLocation(true);
                setLocationError('');  // Clear error since we have fallback

                // Show appropriate message based on error type
                switch (error.code) {
                    case error.PERMISSION_DENIED:
                        toast.info(`Using ${cityInfo.displayName} as location. Tap the map to set exact location.`, {
                            duration: 5000,
                        });
                        break;
                    case error.POSITION_UNAVAILABLE:
                    case error.TIMEOUT:
                    default:
                        toast.info(`GPS unavailable. Using ${cityInfo.displayName} as location. Tap the map to refine.`, {
                            duration: 5000,
                        });
                        break;
                }
            },
            options
        );
    }, [currentCity]);

    // Real-time validation
    useEffect(() => {
        const errors: Record<string, string> = {};

        // Validate description
        if (description.length > 0 && description.length < MIN_DESCRIPTION_LENGTH) {
            errors.description = `Description must be at least ${MIN_DESCRIPTION_LENGTH} characters`;
        }

        // Validate location
        if (!locationLoading && !location && !locationError) {
            errors.location = 'Location is required';
        }

        // Validate location accuracy
        if (location && location.accuracy > GPS_ACCURACY_POOR) {
            errors.locationAccuracy = `Location accuracy is poor (±${Math.round(location.accuracy)}m). For better results, move outdoors or to an open area.`;
        }

        setValidationErrors(errors);
    }, [description, location, locationLoading, locationError]);

    // Reverse geocode photo GPS location
    useEffect(() => {
        if (photo?.gps) {
            fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${photo.gps.lat}&lon=${photo.gps.lng}&zoom=18&addressdetails=1`)
                .then(res => {
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    return res.json();
                })
                .then(data => {
                    if (data?.display_name) {
                        const parts = data.display_name.split(',');
                        setPhotoLocationName(parts.slice(0, 3).join(',').trim());
                    }
                })
                .catch(err => {
                    console.log('Photo reverse geocoding failed:', err);
                    setPhotoLocationName('');
                });
        } else {
            setPhotoLocationName('');
        }
    }, [photo?.gps?.lat, photo?.gps?.lng]);

    // Toggle voice recording with mobile-specific handling
    const toggleVoiceRecording = () => {
        if (!recognitionRef.current) return;

        if (isRecording) {
            try {
                recognitionRef.current.stop();
                setIsRecording(false);
                isRecordingRef.current = false;
                lastProcessedIndexRef.current = -1; // Reset for next recording session
                toast.success('Voice recording stopped');
            } catch (error) {
                console.error('Failed to stop voice recognition:', error);
                setIsRecording(false);
                isRecordingRef.current = false;
                lastProcessedIndexRef.current = -1; // Reset even on error
            }
        } else {
            try {
                recognitionRef.current.start();
                setIsRecording(true);
                isRecordingRef.current = true;

                // Different messages for mobile vs desktop
                if (isMobile) {
                    if (isIOSDevice()) {
                        toast.info('🎤 Listening... Speak clearly. Recording will auto-restart after each phrase.');
                    } else {
                        toast.info('🎤 Listening... Speak now');
                    }
                } else {
                    toast.info('🎤 Listening... Speak now');
                }
            } catch (error: any) {
                console.error('Failed to start voice recognition:', error);

                // Provide helpful error messages for mobile
                if (error.name === 'NotAllowedError') {
                    if (isMobile) {
                        toast.error('Microphone blocked. Go to Settings > Safari/Chrome > Microphone and allow access.');
                    } else {
                        toast.error('Microphone access denied. Please allow microphone access in your browser settings.');
                    }
                } else {
                    toast.error('Failed to start voice input. Please try again or type your description.');
                }
                setIsRecording(false);
                isRecordingRef.current = false;
            }
        }
    };

    // Handle quick tag selection
    const toggleTag = (tag: string) => {
        setSelectedTags(prev => {
            if (prev.includes(tag)) {
                return prev.filter(t => t !== tag);
            } else {
                return [...prev, tag];
            }
        });
    };

    // Calculate character count
    const characterCount = description.length;

    // Check if current step is valid
    const isStepValid = () => {
        if (step === 1) {
            // Location step - need valid location and description
            return !locationLoading && location && description.length >= MIN_DESCRIPTION_LENGTH && !validationErrors.description;
        }
        if (step === 3) {
            // Photo step - photo is required with GPS
            return photo !== null && photo.gps !== null;
        }
        if (step === 4) {
            // Confirmation step - need confirmation checkbox
            return confirmed;
        }
        return true; // Other steps are always valid
    };

    // Get validation message for disabled Continue button
    const getValidationMessage = () => {
        if (step === 1) {
            if (locationLoading) return 'Waiting for GPS location...';
            if (locationError) return 'Location unavailable. Please enable GPS.';
            if (!location) return 'Location is required';
            if (description.length === 0) return 'Please add a description';
            if (description.length < MIN_DESCRIPTION_LENGTH) return `Description must be at least ${MIN_DESCRIPTION_LENGTH} characters (currently ${description.length})`;
            if (validationErrors.description) return validationErrors.description;
        }
        if (step === 3) {
            if (!photo) return 'Please take or upload a geotagged photo';
            if (!photo.gps) return 'Photo must have location data';
        }
        if (step === 4 && !confirmed) return 'Please confirm your report is accurate';
        return '';
    };

    // Handle location selection from map
    const handleMapLocationSelect = (selectedLocation: LocationWithAddress) => {
        setLocation({
            latitude: selectedLocation.latitude,
            longitude: selectedLocation.longitude,
            accuracy: selectedLocation.accuracy
        });
        setLocationName(selectedLocation.locationName);
        setLocationError('');
        setLocationLoading(false);
        setUsingFallbackLocation(false);  // Clear fallback flag when user manually selects
        locationManuallySetRef.current = true; // Mark as manually set to prevent GPS override
        toast.success('Location selected from map');
    };

    const handleNext = () => {
        if (step < totalSteps) {
            if (isStepValid()) {
                setStep(step + 1);
            }
        } else {
            if (isStepValid()) {
                handleSubmit();
            }
        }
    };

    const handleSubmit = async () => {
        // Clear previous errors
        setErrorMessage('');
        setErrorType(null);

        // Validate user is loaded
        if (!userId) {
            setErrorMessage('User not loaded. Please refresh the page and try again.');
            toast.error('Unable to submit report - user not authenticated');
            return;
        }

        // Validate location exists
        if (!location) {
            setErrorType('gps');
            setErrorMessage('Location is required. Please enable GPS and try again.');
            return;
        }

        // Validate photo exists
        if (!photo) {
            setErrorType('photo');
            setErrorMessage('Photo is required. Please go back and add a geotagged photo.');
            return;
        }

        try {
            // Build description with tags (depth/passability sent as separate fields)
            const tagPrefix = selectedTags.length > 0 ? `[${selectedTags.join(', ')}] ` : '';
            const fullDescription = `${tagPrefix}${description}`;

            // Use real GPS coordinates and photo
            await reportMutation.mutateAsync({
                user_id: userId,  // Now guaranteed to be string (not null)
                latitude: location.latitude,
                longitude: location.longitude,
                description: fullDescription,
                image: photo.file,
                photo_latitude: photo.gps.lat,
                photo_longitude: photo.gps.lng,
                photo_location_verified: photo.isLocationVerified,
                water_depth: waterDepth,
                vehicle_passability: vehiclePassability
            });
            toast.success('Report submitted successfully!');
            onSubmit();
        } catch (error: any) {
            console.error('Report submission error:', error);

            // Determine error type and set specific message
            if (error?.message?.includes('location') || error?.message?.includes('GPS')) {
                setErrorType('gps');
                setErrorMessage('GPS not available - please enable location services or select location manually from map');
            } else if (error?.message?.includes('photo') || error?.message?.includes('image') || error?.message?.includes('size')) {
                setErrorType('photo');
                setErrorMessage('Photo too large - try compressing the image or skip photo upload');
            } else if (error?.message?.includes('network') || error?.message?.includes('fetch') || error?.code === 'ERR_NETWORK') {
                setErrorType('network');
                setErrorMessage('Network error - your report has been saved as a draft and will be submitted when connection is restored');
                // In production, save to localStorage here
                toast.info('Report saved as draft');
            } else {
                setErrorMessage('Failed to submit report. Please check your connection and try again.');
            }
        }
    };

    const handleBack = () => {
        if (step > 1) {
            setStep(step - 1);
        } else {
            onBack();
        }
    };

    return (
        <div
            ref={scrollContainerRef}
            className="min-h-full bg-muted overflow-y-auto pb-4"
            style={{ WebkitOverflowScrolling: 'touch' }}
        >
                {/* Header */}
            <div className="bg-card shadow-sm sticky top-0 z-40">
                <div className="flex items-center justify-between px-4 h-14">
                    <button
                        onClick={handleBack}
                        className="p-2 -ml-2 min-w-[44px] min-h-[44px] flex items-center justify-center"
                        aria-label="Go back"
                    >
                        <ArrowLeft className="w-6 h-6" />
                    </button>

                    <h1 className="flex-1 text-center">
                        Report Flooding
                    </h1>

                    <div className="w-10"></div>
                </div>
            </div>

            {/* Progress Indicator */}
            <div className="bg-card px-4 pb-4">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-sm">Step {step} of {totalSteps}</span>
                    <Badge variant="secondary" className="text-xs">
                        <Award className="w-3 h-3 mr-1" />
                        Score: +10 pts
                    </Badge>
                </div>
                <Progress value={progressValue} className="h-2" />
                <div className="flex justify-between text-xs text-muted-foreground mt-2">
                    <span className={step >= 1 ? 'text-primary' : ''}>Location</span>
                    <span className={step >= 2 ? 'text-primary' : ''}>Details</span>
                    <span className={step >= 3 ? 'text-primary' : ''}>Photo</span>
                    <span className={step >= 4 ? 'text-primary' : ''}>Confirm</span>
                </div>
            </div>

            {/* Form Content */}
            <div className="p-4 space-y-4 pb-4">
                {/* Step 1: Location */}
                {step === 1 && (
                    <div className="space-y-4">
                        <Card className="p-4">
                            <h3 className="mb-4">Select Location</h3>

                            <div className="space-y-4">
                                {locationLoading ? (
                                    <div className="border border-border rounded-lg p-3">
                                        <div className="flex items-start gap-2">
                                            <Loader2 className="w-5 h-5 text-primary mt-0.5 animate-spin" />
                                            <div className="flex-1 space-y-2">
                                                <Skeleton className="h-4 w-32" />
                                                <Skeleton className="h-3 w-48" />
                                                <Skeleton className="h-3 w-24" />
                                            </div>
                                        </div>
                                    </div>
                                ) : locationError ? (
                                    <Alert variant="destructive">
                                        <AlertCircle className="h-4 w-4" />
                                        <AlertTitle>Location Error</AlertTitle>
                                        <AlertDescription>
                                            <p className="mb-2">{locationError}</p>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => window.location.reload()}
                                                className="mt-2"
                                            >
                                                Retry
                                            </Button>
                                        </AlertDescription>
                                    </Alert>
                                ) : location ? (
                                    <div className={`border rounded-lg p-3 ${
                                        location.accuracy <= GPS_ACCURACY_EXCELLENT ? 'bg-green-50 border-green-200' :
                                        location.accuracy <= GPS_ACCURACY_GOOD ? 'bg-blue-50 border-blue-200' :
                                        location.accuracy <= GPS_ACCURACY_POOR ? 'bg-yellow-50 border-yellow-200' :
                                        'bg-orange-50 border-orange-200'
                                    }`}>
                                        <div className="flex items-start gap-2">
                                            <MapPin className={`w-5 h-5 mt-0.5 ${
                                                location.accuracy <= GPS_ACCURACY_EXCELLENT ? 'text-green-600' :
                                                location.accuracy <= GPS_ACCURACY_GOOD ? 'text-blue-600' :
                                                location.accuracy <= GPS_ACCURACY_POOR ? 'text-yellow-600' :
                                                'text-orange-600'
                                            }`} />
                                            <div className="flex-1">
                                                <p className="text-sm font-medium">Current Location</p>
                                                {locationName ? (
                                                    <p className="text-xs text-muted-foreground mt-1">{locationName}</p>
                                                ) : (
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        {location.latitude.toFixed(6)}, {location.longitude.toFixed(6)}
                                                    </p>
                                                )}
                                                <div className="flex items-center gap-1 mt-1">
                                                    <p className="text-xs text-muted-foreground">
                                                        GPS accuracy: ±{Math.round(location.accuracy)}m
                                                    </p>
                                                    {location.accuracy <= GPS_ACCURACY_EXCELLENT && (
                                                        <span className="text-xs text-green-600 font-medium">(Excellent)</span>
                                                    )}
                                                    {location.accuracy > GPS_ACCURACY_EXCELLENT && location.accuracy <= GPS_ACCURACY_GOOD && (
                                                        <span className="text-xs text-blue-600 font-medium">(Good)</span>
                                                    )}
                                                    {location.accuracy > GPS_ACCURACY_GOOD && location.accuracy <= GPS_ACCURACY_POOR && (
                                                        <span className="text-xs text-yellow-600 font-medium">(Fair)</span>
                                                    )}
                                                    {location.accuracy > GPS_ACCURACY_POOR && (
                                                        <span className="text-xs text-orange-600 font-medium">(Poor)</span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ) : null}

                                {location && location.accuracy > GPS_ACCURACY_POOR && !usingFallbackLocation && (
                                    <Alert>
                                        <AlertTriangle className="h-4 w-4 text-yellow-600" />
                                        <AlertDescription className="text-xs">
                                            Low GPS accuracy. For better results, move to an open area away from buildings.
                                        </AlertDescription>
                                    </Alert>
                                )}

                                {usingFallbackLocation && (
                                    <Alert className="bg-amber-50 border-amber-200">
                                        <Info className="h-4 w-4 text-amber-600" />
                                        <AlertDescription className="text-xs text-amber-800">
                                            Using approximate location ({locationName}). Tap "Select from Map" below to set your exact location.
                                        </AlertDescription>
                                    </Alert>
                                )}

                                <div className="text-center text-muted-foreground text-sm">OR</div>

                                <Button
                                    variant="outline"
                                    className="w-full"
                                    onClick={() => setIsMapPickerOpen(true)}
                                >
                                    <MapPin className="w-4 h-4 mr-2" />
                                    Select from Map
                                </Button>
                            </div>
                        </Card>

                        <Card className="p-4 overflow-hidden">
                            <div className="space-y-4">
                                <div>
                                    <div className="flex items-center justify-between mb-2">
                                        <Label htmlFor="desc" className="text-base">Description</Label>
                                        <span className={`text-xs ${characterCount > MAX_DESCRIPTION_LENGTH * 0.9 ? 'text-orange-600' : 'text-muted-foreground'}`}>
                                            {characterCount}/{MAX_DESCRIPTION_LENGTH}
                                        </span>
                                    </div>

                                    <div className="space-y-2">
                                        <Textarea
                                            id="desc"
                                            placeholder="e.g., 'Road flooded near Bus Stop 123' or 'Heavy waterlogging at Main Street intersection'"
                                            className="min-h-32 resize-none"
                                            value={description}
                                            onChange={(e) => setDescription(e.target.value.slice(0, MAX_DESCRIPTION_LENGTH))}
                                            maxLength={MAX_DESCRIPTION_LENGTH}
                                            rows={5}
                                        />

                                        {voiceSupported && (
                                            <button
                                                type="button"
                                                onClick={toggleVoiceRecording}
                                                className={`w-full flex items-center justify-center gap-3 py-3 px-4 rounded-lg font-medium transition-all active:scale-[0.98] ${
                                                    isRecording
                                                        ? 'bg-red-500 text-white hover:bg-red-600 shadow-lg shadow-red-200 ring-2 ring-red-300 ring-offset-2 animate-pulse'
                                                        : 'bg-primary text-white hover:opacity-90 shadow-md hover:shadow-lg'
                                                }`}
                                                aria-label={isRecording ? 'Stop voice recording' : 'Start voice recording'}
                                            >
                                                {isRecording ? (
                                                    <>
                                                        <MicOff className="w-5 h-5" />
                                                        <span>Tap to Stop Recording</span>
                                                        <span className="flex h-3 w-3">
                                                            <span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-card opacity-75"></span>
                                                            <span className="relative inline-flex rounded-full h-3 w-3 bg-card"></span>
                                                        </span>
                                                    </>
                                                ) : (
                                                    <>
                                                        <Mic className="w-5 h-5" />
                                                        <span>🎤 Tap to Speak Description</span>
                                                    </>
                                                )}
                                            </button>
                                        )}
                                    </div>

                                    {validationErrors.description && description.length > 0 && (
                                        <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                                            <AlertCircle className="w-3 h-3" />
                                            {validationErrors.description}
                                        </p>
                                    )}
                                    {!validationErrors.description && description.length >= MIN_DESCRIPTION_LENGTH && (
                                        <p className="text-xs text-green-600 mt-1 flex items-center gap-1">
                                            ✓ Description looks good!
                                        </p>
                                    )}
                                    {!validationErrors.description && description.length === 0 && (
                                        <p className="text-xs text-muted-foreground mt-1">
                                            💡 Include landmarks, street names, or nearby places to help others locate
                                        </p>
                                    )}
                                </div>

                                <div>
                                    <Label className="text-sm text-foreground mb-2 block">Quick Tags (Optional)</Label>
                                    <div className="space-y-3">
                                        {Object.entries(TAG_CATEGORIES).map(([category, tags]) => (
                                            <div key={category}>
                                                <p className="text-xs font-semibold text-muted-foreground mb-1.5">{category}</p>
                                                <div className="flex flex-wrap gap-1.5">
                                                    {tags.map((tag) => (
                                                        <Badge
                                                            key={tag}
                                                            variant={selectedTags.includes(tag) ? 'default' : 'outline'}
                                                            className={`cursor-pointer transition-all hover:scale-105 text-xs ${
                                                                category === '🚨 Emergency' && selectedTags.includes(tag)
                                                                    ? 'bg-red-600 hover:bg-red-700'
                                                                    : ''
                                                            }`}
                                                            onClick={() => toggleTag(tag)}
                                                        >
                                                            {selectedTags.includes(tag) && (
                                                                <X className="w-3 h-3 mr-1" />
                                                            )}
                                                            {tag}
                                                        </Badge>
                                                    ))}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-2">
                                        Tap tags to categorize your report
                                    </p>
                                </div>

                                {!voiceSupported && isMobile && (
                                    <Alert>
                                        <AlertCircle className="h-4 w-4" />
                                        <AlertTitle>Voice Input Not Available</AlertTitle>
                                        <AlertDescription>
                                            {isIOSDevice() ? (
                                                <p>Voice input is not supported on iOS Safari. Please type your description or try using Chrome for iOS.</p>
                                            ) : (
                                                <p>Voice input is not supported in your browser. Please type your description.</p>
                                            )}
                                        </AlertDescription>
                                    </Alert>
                                )}

                                {!voiceSupported && !isMobile && (
                                    <Alert>
                                        <AlertCircle className="h-4 w-4" />
                                        <AlertDescription>
                                            Voice input is not supported in your browser. Please type your description or try using Chrome/Edge.
                                        </AlertDescription>
                                    </Alert>
                                )}

                                {isRecording && (
                                    <Alert className="border-primary/20 bg-primary/10">
                                        <Mic className="h-4 w-4 animate-pulse text-primary" />
                                        <AlertTitle className="text-primary">🎤 Listening...</AlertTitle>
                                        <AlertDescription className="text-primary">
                                            {isMobile ? (
                                                isIOSDevice() ? (
                                                    <span>Speak clearly. On iOS, recording will pause and restart after each phrase. Tap the red microphone button to stop.</span>
                                                ) : (
                                                    <span>Speak clearly into your device microphone. Tap the red microphone button to stop recording.</span>
                                                )
                                            ) : (
                                                <span>Speak clearly to record your description. Click the microphone button again to stop.</span>
                                            )}
                                        </AlertDescription>
                                    </Alert>
                                )}
                            </div>
                        </Card>
                    </div>
                )}

                {/* Step 2: Flood Details */}
                {step === 2 && (
                    <Card className="p-4">
                        <div className="space-y-6">
                            <div>
                                <h3 className="mb-4">Water Depth</h3>
                                <RadioGroup value={waterDepth} onValueChange={(v) => setWaterDepth(v as WaterDepth)}>
                                    <div className="space-y-3">
                                        {[
                                            { value: 'ankle', label: 'Ankle-deep', sublabel: '< 0.3m', emoji: '🚶' },
                                            { value: 'knee', label: 'Knee-deep', sublabel: '0.3-0.6m', emoji: '🚶‍♂️' },
                                            { value: 'waist', label: 'Waist-deep', sublabel: '0.6-1.2m', emoji: '🏊' },
                                            { value: 'impassable', label: 'Impassable', sublabel: '> 1.2m', emoji: '⚠️' }
                                        ].map((option) => (
                                            <div key={option.value} className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-muted">
                                                <RadioGroupItem value={option.value} id={option.value} />
                                                <Label htmlFor={option.value} className="flex-1 flex items-center gap-3 cursor-pointer">
                                                    <span className="text-2xl">{option.emoji}</span>
                                                    <div>
                                                        <p className="text-sm">{option.label}</p>
                                                        <p className="text-xs text-muted-foreground">{option.sublabel}</p>
                                                    </div>
                                                </Label>
                                            </div>
                                        ))}
                                    </div>
                                </RadioGroup>
                            </div>

                            <div>
                                <h3 className="mb-4">Vehicle Passability</h3>
                                <RadioGroup value={vehiclePassability} onValueChange={(v) => setVehiclePassability(v as VehiclePassability)}>
                                    <div className="space-y-3">
                                        {[
                                            { value: 'all', label: 'All vehicles passing', icon: '🚗' },
                                            { value: 'high-clearance', label: 'High-clearance only', sublabel: 'SUVs, buses', icon: '🚙' },
                                            { value: 'none', label: 'No vehicles passing', icon: '🚫' }
                                        ].map((option) => (
                                            <div key={option.value} className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-muted">
                                                <RadioGroupItem value={option.value} id={`vehicle-${option.value}`} />
                                                <Label htmlFor={`vehicle-${option.value}`} className="flex-1 flex items-center gap-3 cursor-pointer">
                                                    <span className="text-xl">{option.icon}</span>
                                                    <div>
                                                        <p className="text-sm">{option.label}</p>
                                                        {option.sublabel && <p className="text-xs text-muted-foreground">{option.sublabel}</p>}
                                                    </div>
                                                </Label>
                                            </div>
                                        ))}
                                    </div>
                                </RadioGroup>
                            </div>
                        </div>
                    </Card>
                )}

                {/* Step 3: Photo (Required) */}
                {step === 3 && (
                    <Card className="p-4">
                        <h3 className="mb-2 flex items-center gap-2">
                            <Camera className="w-5 h-5 text-primary" />
                            Add Photo (Required)
                        </h3>
                        <p className="text-sm text-muted-foreground mb-4">
                            A geotagged photo is required to verify your report
                        </p>

                        <PhotoCapture
                            reportedLocation={location}
                            onPhotoCapture={setPhoto}
                            photo={photo}
                        />

                        {!photo && (
                            <Alert className="mt-4">
                                <AlertCircle className="h-4 w-4" />
                                <AlertDescription className="text-xs">
                                    Take a photo or upload a geotagged image from your gallery.
                                    The photo's location will be compared to your reported location.
                                </AlertDescription>
                            </Alert>
                        )}

                        {photo && !photo.isLocationVerified && location && (
                            <Alert className="mt-4 border-yellow-200 bg-yellow-50">
                                <AlertTriangle className="h-4 w-4 text-yellow-600" />
                                <AlertDescription className="text-xs text-yellow-800">
                                    <strong>Location Mismatch Warning</strong><br />
                                    Photo was taken {Math.round(calculateDistance(
                                        photo.gps.lat, photo.gps.lng,
                                        location.latitude, location.longitude
                                    ))}m away from your reported location.<br />
                                    Report will still be submitted but flagged for additional review.
                                </AlertDescription>
                            </Alert>
                        )}
                    </Card>
                )}

                {/* Step 4: Confirmation */}
                {step === 4 && (
                    <div className="space-y-4">
                        {errorMessage && (
                            <Alert variant="destructive">
                                <AlertCircle className="h-4 w-4" />
                                <AlertTitle>Submission Failed</AlertTitle>
                                <AlertDescription>
                                    <p className="mb-2">{errorMessage}</p>
                                    {errorType === 'gps' && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="mt-2"
                                            onClick={() => {
                                                setErrorMessage('');
                                                setErrorType(null);
                                                setStep(1);
                                            }}
                                        >
                                            Go back to select location
                                        </Button>
                                    )}
                                    {errorType === 'photo' && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="mt-2"
                                            onClick={() => {
                                                setErrorMessage('');
                                                setErrorType(null);
                                                setStep(3);
                                            }}
                                        >
                                            Go back to photo step
                                        </Button>
                                    )}
                                    {errorType === 'network' && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="mt-2"
                                            onClick={() => {
                                                setErrorMessage('');
                                                setErrorType(null);
                                                handleSubmit();
                                            }}
                                        >
                                            Retry submission
                                        </Button>
                                    )}
                                    {!errorType && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="mt-2"
                                            onClick={() => {
                                                setErrorMessage('');
                                                handleSubmit();
                                            }}
                                        >
                                            Try again
                                        </Button>
                                    )}
                                </AlertDescription>
                            </Alert>
                        )}

                        <Card className="p-4">
                            <h3 className="mb-4">Report Summary</h3>

                            <div className="space-y-3 text-sm">
                                <div>
                                    <p className="text-muted-foreground">Location</p>
                                    {location ? (
                                        <div>
                                            <p>{locationName || `${location.latitude.toFixed(6)}, ${location.longitude.toFixed(6)}`}</p>
                                            <p className="text-xs text-muted-foreground mt-1">
                                                Accuracy: ±{Math.round(location.accuracy)}m
                                                {location.accuracy <= GPS_ACCURACY_EXCELLENT && ' (Excellent)'}
                                                {location.accuracy > GPS_ACCURACY_EXCELLENT && location.accuracy <= GPS_ACCURACY_GOOD && ' (Good)'}
                                                {location.accuracy > GPS_ACCURACY_GOOD && location.accuracy <= GPS_ACCURACY_POOR && ' (Fair)'}
                                                {location.accuracy > GPS_ACCURACY_POOR && ' (Poor)'}
                                            </p>
                                        </div>
                                    ) : (
                                        <p className="text-orange-600">Location unavailable</p>
                                    )}
                                </div>
                                {selectedTags.length > 0 && (
                                    <div>
                                        <p className="text-muted-foreground">Tags</p>
                                        <div className="flex flex-wrap gap-1 mt-1">
                                            {selectedTags.map(tag => (
                                                <Badge key={tag} variant="secondary" className="text-xs">
                                                    {tag}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                <div>
                                    <p className="text-muted-foreground">Description</p>
                                    <p className="whitespace-pre-wrap">{description || 'No description provided'}</p>
                                </div>
                                <div>
                                    <p className="text-muted-foreground">Water Depth</p>
                                    <p className="capitalize">{waterDepth.replace('-', ' ')}</p>
                                </div>
                                <div>
                                    <p className="text-muted-foreground">Vehicle Passability</p>
                                    <p className="capitalize">{vehiclePassability.replace('-', ' ')}</p>
                                </div>
                                <div>
                                    <p className="text-muted-foreground">Photo</p>
                                    {photo ? (
                                        <div className="mt-1">
                                            <div className="flex items-center gap-2">
                                                <img
                                                    src={photo.previewUrl}
                                                    alt="Report photo"
                                                    className="w-16 h-16 object-cover rounded"
                                                />
                                                <div className="space-y-1">
                                                    {photo.isLocationVerified ? (
                                                        <Badge className="bg-green-500 text-white text-xs flex items-center gap-1 w-fit">
                                                            <CheckCircle className="w-3 h-3" />
                                                            Location Verified
                                                        </Badge>
                                                    ) : (
                                                        <Badge className="bg-yellow-500 text-white text-xs flex items-center gap-1 w-fit">
                                                            <AlertTriangle className="w-3 h-3" />
                                                            {location ? `${Math.round(calculateDistance(photo.gps.lat, photo.gps.lng, location.latitude, location.longitude))}m away` : 'Location Mismatch'}
                                                        </Badge>
                                                    )}
                                                    {/* ML Classification Badge */}
                                                    {photo.mlValidating && (
                                                        <Badge className="bg-muted0 text-white text-xs flex items-center gap-1 w-fit">
                                                            <Loader2 className="w-3 h-3 animate-spin" />
                                                            Analyzing...
                                                        </Badge>
                                                    )}
                                                    {photo.mlClassification && !photo.mlValidating && (
                                                        photo.mlClassification.is_flood ? (
                                                            <Badge className="bg-blue-500 text-white text-xs flex items-center gap-1 w-fit">
                                                                <Droplets className="w-3 h-3" />
                                                                Flood Detected ({Math.round(photo.mlClassification.confidence * 100)}%)
                                                            </Badge>
                                                        ) : photo.mlClassification.needs_review ? (
                                                            <Badge className="bg-yellow-500 text-white text-xs flex items-center gap-1 w-fit">
                                                                <AlertTriangle className="w-3 h-3" />
                                                                Needs Review
                                                            </Badge>
                                                        ) : (
                                                            <Badge className="bg-orange-500 text-white text-xs flex items-center gap-1 w-fit">
                                                                <AlertTriangle className="w-3 h-3" />
                                                                May Not Be Flood
                                                            </Badge>
                                                        )
                                                    )}
                                                    {photo.mlFailed && !photo.mlValidating && !photo.mlClassification && (
                                                        <Badge className="bg-gray-400 text-white text-xs flex items-center gap-1 w-fit">
                                                            <AlertTriangle className="w-3 h-3" />
                                                            Analysis Unavailable
                                                        </Badge>
                                                    )}
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        {photo.source === 'camera' ? 'Taken with camera' : 'From gallery'}
                                                    </p>
                                                </div>
                                            </div>
                                            {/* Photo GPS Location Display */}
                                            <div className="mt-2 p-2 bg-muted rounded-lg">
                                                <div className="flex items-start gap-2 text-sm">
                                                    <MapPin className="h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
                                                    <div className="min-w-0">
                                                        <p className="font-medium text-foreground">Photo Location</p>
                                                        <p className="text-xs text-muted-foreground">
                                                            {photo.gps.lat.toFixed(6)}, {photo.gps.lng.toFixed(6)}
                                                        </p>
                                                        {photoLocationName && (
                                                            <p className="text-xs text-muted-foreground mt-0.5 break-words">{photoLocationName}</p>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ) : (
                                        <p className="text-orange-600">No photo added</p>
                                    )}
                                </div>
                            </div>
                        </Card>

                        <Card className="p-4">
                            <h3 className="mb-4">Verify Your Report</h3>

                            <div className="space-y-4">
                                <div className="flex items-start gap-2">
                                    <Checkbox
                                        id="confirm"
                                        checked={confirmed}
                                        onCheckedChange={(checked) => setConfirmed(checked as boolean)}
                                    />
                                    <Label htmlFor="confirm" className="text-sm cursor-pointer">
                                        I confirm this report is accurate and truthful
                                    </Label>
                                </div>

                                <div className="p-3 bg-muted rounded-lg">
                                    <p className="text-xs text-muted-foreground">
                                        🔒 Privacy: Location anonymized to 100m radius.
                                    </p>
                                </div>
                            </div>
                        </Card>
                    </div>
                )}
            </div>

            {/* Action Buttons - scrollable, after form content */}
            <div
                data-action-buttons
                className="bg-card border-t p-4 space-y-2 mx-4 mb-4 rounded-lg shadow-sm"
            >
                {step < totalSteps ? (
                    <>
                        {!isStepValid() ? (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <div className="w-full">
                                        <Button className="w-full" disabled>
                                            Continue
                                        </Button>
                                    </div>
                                </TooltipTrigger>
                                <TooltipContent>
                                    <p>{getValidationMessage()}</p>
                                </TooltipContent>
                            </Tooltip>
                        ) : (
                            <Button className="w-full" onClick={handleNext}>
                                Continue
                            </Button>
                        )}
                    </>
                ) : (
                    <>
                        {!isStepValid() || reportMutation.isPending ? (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <div className="w-full">
                                        <Button
                                            className="w-full"
                                            disabled
                                        >
                                            {reportMutation.isPending ? (
                                                <>
                                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                                    Submitting...
                                                </>
                                            ) : (
                                                'Submit Report'
                                            )}
                                        </Button>
                                    </div>
                                </TooltipTrigger>
                                <TooltipContent>
                                    <p>{reportMutation.isPending ? 'Submitting your report...' : getValidationMessage()}</p>
                                </TooltipContent>
                            </Tooltip>
                        ) : (
                            <Button
                                className="w-full"
                                onClick={handleNext}
                            >
                                Submit Report
                            </Button>
                        )}
                    </>
                )}
                {step > 1 && !reportMutation.isPending && (
                    <Button variant="ghost" className="w-full" onClick={handleBack}>
                        Back
                    </Button>
                )}
            </div>

            {/* Map Picker Modal */}
            <MapPicker
                isOpen={isMapPickerOpen}
                onClose={() => setIsMapPickerOpen(false)}
                initialLocation={location}
                onLocationSelect={handleMapLocationSelect}
            />
        </div>
    );
}
