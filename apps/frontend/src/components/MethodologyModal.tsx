import { useState, Fragment } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Dialog,
    DialogContent,
    DialogTitle,
    DialogDescription,
} from './ui/dialog';
import {
    Zap, Camera, BarChart3, XCircle, Archive, Mountain,
    Users, ChevronDown, ArrowRight, FileSearch, Beaker,
} from 'lucide-react';

// --- Animation variants ---
const fadeUp = {
    hidden: { opacity: 0, y: 16 },
    show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

const stagger = {
    hidden: {},
    show: { transition: { staggerChildren: 0.08 } },
};

// --- Status badge ---
type BadgeStatus = 'active' | 'static' | 'retired' | 'shelved' | 'failed';

const statusStyles: Record<BadgeStatus, string> = {
    active: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    static: 'bg-amber-50 text-amber-700 border-amber-200',
    retired: 'bg-red-50 text-red-700 border-red-200',
    shelved: 'bg-slate-100 text-slate-500 border-slate-200',
    failed: 'bg-red-50 text-red-700 border-red-200',
};

const StatusBadge = ({ status }: { status: BadgeStatus }) => (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${statusStyles[status]}`}>
        {status}
    </span>
);

// --- Active model card ---
const ActiveCard = ({ icon: Icon, title, status, children, color = 'blue' }: {
    icon: React.ElementType;
    title: string;
    status: BadgeStatus;
    children: React.ReactNode;
    color?: string;
}) => {
    const colorMap: Record<string, string> = {
        blue: 'bg-blue-50 text-blue-600 border-blue-100',
        amber: 'bg-amber-50 text-amber-600 border-amber-100',
        emerald: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    };
    return (
        <motion.div variants={fadeUp} className="rounded-2xl border border-slate-200 p-5 bg-white hover:border-blue-200 hover:shadow-md transition-all duration-200 overflow-hidden">
            <div className="flex items-start justify-between mb-3">
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center border ${colorMap[color] || colorMap.blue}`}>
                    <Icon size={18} />
                </div>
                <StatusBadge status={status} />
            </div>
            <h4 className="font-semibold text-slate-900 text-sm mb-1.5">{title}</h4>
            <div className="text-slate-500 text-xs leading-relaxed">{children}</div>
        </motion.div>
    );
};

// --- Collapsible tried section ---
const TriedSection = ({ title, status, children }: {
    title: string;
    status: BadgeStatus;
    children: React.ReactNode;
}) => {
    const [open, setOpen] = useState(false);
    return (
        <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
            <button
                onClick={() => setOpen(!open)}
                className="w-full flex items-center justify-between px-5 py-3.5 text-left hover:bg-slate-50 transition-colors"
            >
                <div className="flex items-center gap-3">
                    <ChevronDown size={14} className={`text-slate-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
                    <span className="font-medium text-slate-900 text-sm">{title}</span>
                </div>
                <StatusBadge status={status} />
            </button>
            <AnimatePresence>
                {open && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25 }}
                        className="overflow-hidden"
                    >
                        <div className="px-5 pb-4 text-xs text-slate-600 leading-relaxed border-t border-slate-100 pt-3">
                            {children}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

// --- Smoking gun animated bar ---
const SmokingGunBar = ({ label, value, color, delay }: {
    label: string;
    value: number;
    color: string;
    delay: number;
}) => {
    const width = Math.abs(value) * 100;
    const sign = value >= 0 ? '+' : '';
    return (
        <div className="flex items-center gap-3">
            <span className="text-[11px] text-slate-500 w-24 text-right shrink-0">{label}</span>
            <div className="flex-1 h-6 bg-slate-100 rounded-full overflow-hidden relative">
                <motion.div
                    initial={{ width: 0 }}
                    whileInView={{ width: `${width}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8, delay, ease: 'easeOut' }}
                    className={`h-full rounded-full ${color}`}
                />
            </div>
            <span className={`font-mono text-sm font-bold w-12 ${value >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                {sign}{value.toFixed(2)}
            </span>
        </div>
    );
};

// --- Section header ---
const SectionHeader = ({ children }: { children: React.ReactNode }) => (
    <motion.h3
        variants={fadeUp}
        className="text-base font-bold text-slate-900 mt-8 mb-4 flex items-center gap-2"
    >
        <div className="w-1 h-5 bg-blue-500 rounded-full" />
        {children}
    </motion.h3>
);

// --- Main component ---
interface MethodologyModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export const MethodologyModal = ({ open, onOpenChange }: MethodologyModalProps) => {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto p-0 gap-0 rounded-3xl border-slate-200">
                {/* Header */}
                <div className="sticky top-0 z-10 bg-white/95 backdrop-blur-sm border-b border-slate-100 px-6 pt-6 pb-4 rounded-t-3xl">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-100 text-blue-700 text-[10px] font-bold uppercase tracking-wider mb-3">
                        <FileSearch size={12} />
                        Transparency Report
                    </div>
                    <DialogTitle className="text-xl md:text-2xl font-bold text-slate-900 leading-tight">
                        How FloodSafe Calculates Risk
                    </DialogTitle>
                    <DialogDescription className="text-slate-500 text-sm mt-1">
                        An honest look at what works, what we tried, and what's next.
                    </DialogDescription>
                </div>

                <div className="px-6 pb-8">
                    {/* === What Powers Your Risk Score === */}
                    <SectionHeader>What Powers Your Risk Score</SectionHeader>

                    <motion.div
                        variants={stagger}
                        initial="hidden"
                        whileInView="show"
                        viewport={{ once: true, margin: '-30px' }}
                        className="grid grid-cols-1 md:grid-cols-3 gap-3"
                    >
                        <ActiveCard icon={Zap} title="Flood Hazard Index" status="active" color="blue">
                            <p>Real-time weather formula combining 6 factors:</p>
                            <p className="font-mono text-[10px] mt-1 text-slate-700">
                                P(35%) + I(18%) + S(12%) + A(12%) + R(8%) + E(15%)
                            </p>
                            <p className="mt-1.5 italic text-slate-400">This is "Live Flood Risk" — the only signal that differentiates between hotspots.</p>
                        </ActiveCard>

                        <ActiveCard icon={Camera} title="Photo Verification" status="active" color="emerald">
                            <p>MobileNet flood image classifier. Pre-trained, safety-first threshold (0.3) — catches 98%+ of real floods.</p>
                            <p className="mt-1.5 italic text-slate-400">Used for community report validation, not risk scoring.</p>
                        </ActiveCard>

                        <ActiveCard icon={BarChart3} title="Historical Severity" status="static" color="amber">
                            <p>Government-reported severity levels from official flood records.</p>
                            <p className="mt-1.5 italic text-slate-400">3 of 5 cities have all hotspots as "high" — no differentiation.</p>
                        </ActiveCard>
                    </motion.div>

                    {/* === What We Tried & Learned === */}
                    <SectionHeader>What We Tried &amp; Learned</SectionHeader>

                    <motion.div
                        variants={stagger}
                        initial="hidden"
                        whileInView="show"
                        viewport={{ once: true, margin: '-30px' }}
                        className="space-y-2"
                    >
                        <motion.div variants={fadeUp}>
                            <TriedSection title="XGBoost Classifier — Delhi" status="retired">
                                <p>Trained on 270 hotspots vs 300 random points across Delhi. Achieved <span className="font-mono font-bold text-slate-900">AUC 0.98</span> — but random points included farmland and forest.</p>
                                <div className="grid grid-cols-3 gap-3 my-3">
                                    <div className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
                                        <div className="font-mono text-lg font-bold text-slate-900">0.952</div>
                                        <div className="text-[10px] text-slate-400 mt-0.5">Mean Score</div>
                                    </div>
                                    <div className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
                                        <div className="font-mono text-lg font-bold text-red-500">~0</div>
                                        <div className="text-[10px] text-slate-400 mt-0.5">Differentiation</div>
                                    </div>
                                    <div className="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
                                        <div className="font-mono text-xs font-bold text-slate-700 leading-tight">built_up<br/>_pct</div>
                                        <div className="text-[10px] text-slate-400 mt-0.5">Top Feature</div>
                                    </div>
                                </div>
                                <p className="text-slate-500">89/90 hotspots scored 0.75-1.0. The model learned "is this urban?" not "will this flood?"</p>
                            </TriedSection>
                        </motion.div>

                        <motion.div variants={fadeUp}>
                            <TriedSection title="Deep Learning Ensembles" status="shelved">
                                <p>ConvLSTM + GNN + LightGBM — architectures designed but never trained. Requires daily flood occurrence labels that don't exist for any of our cities.</p>
                                <p className="mt-2 text-slate-400">The fundamental challenge: you need "flood happened here on this date" at point-level resolution. No public dataset provides this.</p>
                            </TriedSection>
                        </motion.div>

                        <motion.div variants={fadeUp}>
                            <TriedSection title="Terrain Analysis — 5 Cities" status="failed">
                                <p>GEE feature extraction (elevation, slope, TWI, land cover) across 5 cities. Rigorous statistical analysis with Cliff's Delta effect sizes.</p>
                                <div className="mt-2 overflow-x-auto">
                                    <table className="w-full text-[10px] font-mono">
                                        <thead>
                                            <tr className="text-slate-400">
                                                <th className="text-left py-1 pr-3">City</th>
                                                <th className="text-right py-1 pr-3">All BG</th>
                                                <th className="text-right py-1 pr-3">Urban-only</th>
                                                <th className="text-right py-1">Lost</th>
                                            </tr>
                                        </thead>
                                        <tbody className="text-slate-700">
                                            <tr><td className="py-0.5 pr-3">Delhi</td><td className="text-right pr-3">4</td><td className="text-right pr-3">1</td><td className="text-right text-red-500">75%</td></tr>
                                            <tr><td className="py-0.5 pr-3">Singapore</td><td className="text-right pr-3">9</td><td className="text-right pr-3">0</td><td className="text-right text-red-500">100%</td></tr>
                                            <tr className="text-emerald-700"><td className="py-0.5 pr-3">Yogyakarta</td><td className="text-right pr-3">6</td><td className="text-right pr-3">5</td><td className="text-right">17%</td></tr>
                                        </tbody>
                                    </table>
                                </div>
                                <p className="mt-2 text-slate-400">Features with large effect sizes in "all background" comparison collapsed when restricted to urban-only points. Urban flooding is an infrastructure problem, not a terrain one.</p>
                            </TriedSection>
                        </motion.div>
                    </motion.div>

                    {/* === The Smoking Gun === */}
                    <SectionHeader>The Smoking Gun</SectionHeader>

                    <motion.div
                        initial="hidden"
                        whileInView="show"
                        viewport={{ once: true, margin: '-30px' }}
                        variants={fadeUp}
                        className="rounded-2xl bg-slate-50 p-6 border border-slate-200"
                    >
                        <div className="flex items-center gap-2 mb-4">
                            <Beaker size={16} className="text-slate-400" />
                            <span className="text-xs font-medium text-slate-600">Delhi: built_up_pct (urbanization proxy)</span>
                        </div>

                        <div className="space-y-3">
                            <SmokingGunBar label="All background" value={0.53} color="bg-emerald-400" delay={0.1} />
                            <SmokingGunBar label="Urban-only" value={-0.15} color="bg-red-400" delay={0.4} />
                        </div>

                        <p className="text-xs text-slate-500 mt-4 leading-relaxed border-t border-slate-200 pt-3">
                            When we compared hotspots to <em>all</em> random points, they looked special (Cliff's Delta +0.53).
                            When we compared to <em>other urban points</em>... the signal disappeared (-0.15).
                            The model wasn't finding flood-prone locations — it was finding cities.
                        </p>
                    </motion.div>

                    {/* === The Path Forward === */}
                    <SectionHeader>The Path Forward</SectionHeader>

                    <motion.div
                        initial="hidden"
                        whileInView="show"
                        viewport={{ once: true, margin: '-30px' }}
                        variants={fadeUp}
                        className="rounded-2xl bg-gradient-to-br from-emerald-50 to-white p-6 border border-emerald-200"
                    >
                        <div className="flex items-center gap-2 mb-4">
                            <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-emerald-100 text-emerald-600 border border-emerald-200">
                                <Users size={18} />
                            </div>
                            <h4 className="font-semibold text-slate-900 text-sm">Community Reporting</h4>
                        </div>

                        {/* Step flow */}
                        <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] items-center gap-1.5 mb-4">
                            {[
                                { emoji: '📱', label: 'Report', sub: 'photo + GPS' },
                                { emoji: '🛣️', label: 'Road Snap', sub: 'OSM matching' },
                                { emoji: '📊', label: 'Cluster', sub: '3+ = candidate' },
                                { emoji: '✅', label: 'Verify', sub: 'human review' },
                            ].map((step, i) => (
                                <Fragment key={step.label}>
                                    <div className="bg-white rounded-xl px-2 py-2 border border-emerald-100 text-center">
                                        <div className="text-base">{step.emoji}</div>
                                        <div className="text-[10px] font-semibold text-slate-700 mt-0.5">{step.label}</div>
                                        <div className="text-[9px] text-slate-400 leading-tight">{step.sub}</div>
                                    </div>
                                    {i < 3 && <ArrowRight size={12} className="text-emerald-300 shrink-0 mx-0.5" />}
                                </Fragment>
                            ))}
                        </div>

                        <p className="text-xs text-slate-600 leading-relaxed">
                            Each verified report is one ground-truth data point. After 2-3 monsoon seasons,
                            we'll have enough data to train genuine event-based models. No negative sampling needed —
                            density-based discovery is scientifically sound.
                        </p>
                    </motion.div>

                    {/* Footer CTA */}
                    <motion.div
                        variants={fadeUp}
                        initial="hidden"
                        whileInView="show"
                        viewport={{ once: true }}
                        className="mt-6 text-center"
                    >
                        <p className="text-xs text-slate-400 mb-3">
                            Want to help? Submit a flood report during the next heavy rain. Every report strengthens our prediction capability.
                        </p>
                        <button
                            onClick={() => onOpenChange(false)}
                            className="px-5 py-2 rounded-full bg-slate-900 text-white text-xs font-medium hover:bg-slate-800 transition-colors"
                        >
                            Got it
                        </button>
                    </motion.div>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default MethodologyModal;
