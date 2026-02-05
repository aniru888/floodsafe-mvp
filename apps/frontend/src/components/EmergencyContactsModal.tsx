import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from './ui/dialog';
import {
    Phone,
    AlertTriangle,
    Shield,
    Flame,
    Heart,
    Waves,
    Building,
    Building2,
    PhoneCall,
} from 'lucide-react';
import { useCityContext } from '../contexts/CityContext';
import {
    getContactsByCategory,
    sanitizePhoneNumber,
    EmergencyContact,
} from '../lib/constants/emergencyContacts';
import { cn } from '../lib/utils';

interface EmergencyContactsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

/**
 * Map icon names to Lucide components
 */
const iconMap = {
    AlertTriangle,
    Shield,
    Flame,
    Ambulance: Heart, // Using Heart as Ambulance might not exist in v0.290.0
    Heart,
    Waves,
    Building,
    Building2,
} as const;

/**
 * Category color schemes for visual hierarchy
 */
const categoryColors = {
    critical: {
        bg: 'bg-red-50',
        iconBg: 'bg-red-500',
        iconText: 'text-white',
        text: 'text-red-700',
        number: 'text-red-600',
        border: 'border-red-200',
        hover: 'hover:bg-red-100 active:bg-red-150',
    },
    'police-fire': {
        bg: 'bg-blue-50',
        iconBg: 'bg-blue-500',
        iconText: 'text-white',
        text: 'text-blue-700',
        number: 'text-blue-600',
        border: 'border-blue-200',
        hover: 'hover:bg-blue-100',
    },
    medical: {
        bg: 'bg-green-50',
        iconBg: 'bg-green-500',
        iconText: 'text-white',
        text: 'text-green-700',
        number: 'text-green-600',
        border: 'border-green-200',
        hover: 'hover:bg-green-100',
    },
    flood: {
        bg: 'bg-cyan-50',
        iconBg: 'bg-cyan-500',
        iconText: 'text-white',
        text: 'text-cyan-700',
        number: 'text-cyan-600',
        border: 'border-cyan-200',
        hover: 'hover:bg-cyan-100',
    },
    'city-specific': {
        bg: 'bg-purple-50',
        iconBg: 'bg-purple-500',
        iconText: 'text-white',
        text: 'text-purple-700',
        number: 'text-purple-600',
        border: 'border-purple-200',
        hover: 'hover:bg-purple-100',
    },
};

/**
 * Critical contact button - Large, prominent for panic situations
 */
function CriticalContactButton({ contact }: { contact: EmergencyContact }) {
    const Icon = iconMap[contact.icon];
    const colors = categoryColors.critical;

    return (
        <a
            href={`tel:${sanitizePhoneNumber(contact.number)}`}
            className={cn(
                'flex items-center gap-4 p-4 rounded-xl border-2 transition-all min-h-[88px]',
                colors.bg,
                colors.border,
                colors.hover,
                'shadow-sm hover:shadow-md'
            )}
            aria-label={`Call ${contact.name} at ${contact.number}`}
        >
            <div className={cn(
                'w-14 h-14 rounded-full flex items-center justify-center flex-shrink-0',
                colors.iconBg
            )}>
                <Icon className={cn('w-7 h-7', colors.iconText)} />
            </div>
            <div className="flex-1 min-w-0">
                <div className={cn('font-bold text-lg', colors.text)}>
                    {contact.name}
                </div>
                <div className="text-sm text-gray-600">
                    {contact.description}
                </div>
            </div>
            <div className="text-right flex-shrink-0">
                <div className={cn('text-2xl font-bold', colors.number)}>
                    {contact.number}
                </div>
                <div className="text-xs text-gray-500 flex items-center gap-1 justify-end">
                    <PhoneCall className="w-3 h-3" />
                    Tap to call
                </div>
            </div>
        </a>
    );
}

/**
 * Regular contact button - Smaller, for secondary contacts
 */
function ContactButton({ contact }: { contact: EmergencyContact }) {
    const Icon = iconMap[contact.icon];
    const colors = categoryColors[contact.category];

    return (
        <a
            href={`tel:${sanitizePhoneNumber(contact.number)}`}
            className={cn(
                'flex items-center gap-3 p-3 rounded-lg border transition-all min-h-[64px]',
                colors.bg,
                colors.border,
                colors.hover
            )}
            aria-label={`Call ${contact.name} at ${contact.number}`}
        >
            <div className={cn(
                'w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0',
                colors.iconBg
            )}>
                <Icon className={cn('w-5 h-5', colors.iconText)} />
            </div>
            <div className="flex-1 min-w-0">
                <div className={cn('font-semibold text-sm', colors.text)}>
                    {contact.name}
                </div>
            </div>
            <div className={cn('text-lg font-bold flex-shrink-0', colors.number)}>
                {contact.number}
            </div>
        </a>
    );
}

/**
 * Section header with divider
 */
function SectionHeader({ title }: { title: string }) {
    return (
        <div className="flex items-center gap-2 py-2">
            <div className="flex-1 h-px bg-gray-200" />
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                {title}
            </span>
            <div className="flex-1 h-px bg-gray-200" />
        </div>
    );
}

/**
 * Emergency Contacts Modal
 *
 * Priority-first layout optimized for panic situations:
 * - Critical numbers (112, 1070) displayed prominently at top
 * - One-tap dialing via tel: protocol
 * - City-aware filtering (Delhi vs Bangalore)
 * - Large touch targets (88px for critical, 64px for others)
 */
export function EmergencyContactsModal({ isOpen, onClose }: EmergencyContactsModalProps) {
    const { city } = useCityContext();
    const contacts = getContactsByCategory(city);

    const cityLabel = city === 'delhi' ? 'Delhi' : city === 'bangalore' ? 'Bangalore' : '';

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto p-0">
                {/* Header */}
                <DialogHeader className="p-4 pb-2 border-b bg-red-50">
                    <DialogTitle className="text-red-600 flex items-center gap-2 text-lg">
                        <Phone className="w-5 h-5" />
                        Emergency Contacts
                    </DialogTitle>
                    <p className="text-sm text-gray-600 mt-1">
                        Tap any number to call immediately
                    </p>
                </DialogHeader>

                {/* Content */}
                <div className="p-4 space-y-4">
                    {/* Critical Section - Always visible, no scrolling needed */}
                    <div className="space-y-3">
                        {contacts.critical.map(contact => (
                            <CriticalContactButton key={contact.id} contact={contact} />
                        ))}
                    </div>

                    {/* Police & Fire */}
                    {contacts.policeFire.length > 0 && (
                        <>
                            <SectionHeader title="Police & Fire" />
                            <div className="grid grid-cols-2 gap-2">
                                {contacts.policeFire.map(contact => (
                                    <ContactButton key={contact.id} contact={contact} />
                                ))}
                            </div>
                        </>
                    )}

                    {/* Medical */}
                    {contacts.medical.length > 0 && (
                        <>
                            <SectionHeader title="Medical" />
                            <div className="grid grid-cols-2 gap-2">
                                {contacts.medical.map(contact => (
                                    <ContactButton key={contact.id} contact={contact} />
                                ))}
                            </div>
                        </>
                    )}

                    {/* Flood Helpline */}
                    {contacts.flood.length > 0 && (
                        <>
                            <SectionHeader title="Flood Helpline" />
                            <div className="space-y-2">
                                {contacts.flood.map(contact => (
                                    <ContactButton key={contact.id} contact={contact} />
                                ))}
                            </div>
                        </>
                    )}

                    {/* City-Specific */}
                    {contacts.citySpecific.length > 0 && (
                        <>
                            <SectionHeader title={`${cityLabel} Helplines`} />
                            <div className="space-y-2">
                                {contacts.citySpecific.map(contact => (
                                    <ContactButton key={contact.id} contact={contact} />
                                ))}
                            </div>
                        </>
                    )}

                    {/* Footer note */}
                    <p className="text-xs text-gray-400 text-center pt-2">
                        All helplines available 24/7
                    </p>
                </div>
            </DialogContent>
        </Dialog>
    );
}
