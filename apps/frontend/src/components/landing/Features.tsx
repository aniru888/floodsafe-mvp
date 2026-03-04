import React from 'react';
import { motion } from 'framer-motion';
import { BrainCircuit, Map as MapIcon, ShieldCheck, AlertTriangle, ArrowRight, Navigation, MessageSquarePlus, Smartphone, WifiOff } from 'lucide-react';

const FeatureCard = ({ children, className = "", delay = 0 }: { children: React.ReactNode, className?: string, delay?: number }) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-50px" }}
        transition={{ duration: 0.5, delay }}
        className={`relative overflow-hidden rounded-3xl border border-slate-200 p-8 hover:border-blue-300 hover:shadow-xl hover:shadow-blue-100/50 transition-all duration-300 group flex flex-col ${className}`}
    >
        {children}
    </motion.div>
);

export const Features = () => {
    return (
        <section id="features" className="py-24 bg-transparent relative overflow-hidden">

            <div className="max-w-7xl mx-auto px-6 relative z-10">

                {/* Header */}
                <div className="text-center max-w-3xl mx-auto mb-16">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-blue-50 border border-blue-100 text-blue-700 text-xs font-bold uppercase tracking-wider mb-4"
                    >
                        Why FloodSafe?
                    </motion.div>
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.1 }}
                        className="text-3xl md:text-5xl font-bold text-slate-900 mb-6"
                    >
                        More than a map. <br />
                        <span className="text-blue-600">Your flood survival toolkit.</span>
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.2 }}
                        className="text-slate-600 text-lg"
                    >
                        Combining AI technology, satellite data, and community power to help you avoid flood hazards.
                    </motion.p>
                </div>

                {/* Bento grid */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">

                    {/* 1. Maps (2 columns) */}
                    <FeatureCard className="md:col-span-2 min-h-[350px] bg-white bg-gradient-to-br from-white to-blue-50 border-blue-100 justify-between overflow-hidden">
                        <div className="relative z-10">
                            <div className="flex items-center justify-between mb-6">
                                <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-blue-200">
                                    <MapIcon size={24} />
                                </div>
                                <span className="bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-xs font-bold">Flood Hazard Index</span>
                            </div>

                            <h3 className="text-2xl font-bold text-slate-900 mb-2">Live Flood Atlas & Hazard Index</h3>
                            <p className="text-slate-600 max-w-md mb-6">
                                Real-time AI-based flood risk scoring visualizing immediate threat levels and hotspot activity on your map.
                            </p>

                            <button className="flex items-center gap-2 text-blue-600 font-bold text-sm group-hover:gap-3 transition-all mt-auto">
                                Explore Map <ArrowRight size={16} />
                            </button>
                        </div>

                        {/* Map animation */}
                        <div className="absolute right-[-20px] bottom-[-20px] w-[60%] h-[80%] bg-white rounded-tl-3xl border-t border-l border-blue-100 shadow-2xl overflow-hidden hidden md:block group-hover:scale-105 transition-transform duration-500">
                            <div className="absolute inset-0 bg-slate-50 opacity-50" />
                            <svg className="absolute inset-0 w-full h-full" viewBox="0 0 200 150">
                                <path d="M20 120 C 60 100, 80 40, 180 30" stroke="#3B82F6" strokeWidth="4" fill="none" strokeLinecap="round" strokeDasharray="8 4" className="animate-[dash_20s_linear_infinite]" />
                                <circle cx="180" cy="30" r="5" fill="#3B82F6" className="animate-ping" />
                                <circle cx="90" cy="90" r="25" fill="rgba(239, 68, 68, 0.1)" />
                                <circle cx="90" cy="90" r="8" fill="#EF4444" className="animate-pulse" />
                            </svg>
                        </div>
                    </FeatureCard>

                    {/* 2. AI Insight (2 columns) */}
                    <FeatureCard className="md:col-span-2 bg-white hover:border-purple-200" delay={0.1}>
                        <div className="flex justify-between items-start mb-4">
                            <div className="w-10 h-10 bg-purple-100 text-purple-600 rounded-xl flex items-center justify-center">
                                <BrainCircuit size={20} />
                            </div>
                            <span className="text-[10px] font-bold bg-purple-50 text-purple-700 px-2 py-1 rounded-full border border-purple-100">
                                AI MODEL
                            </span>
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Machine Learning Prediction</h3>
                        <p className="text-sm text-slate-600 mb-4">
                            Advanced machine learning models translate rainfall data into accurate, localized risk narratives.
                        </p>
                        <div className="bg-purple-50 p-3 rounded-lg border border-purple-100 text-xs text-purple-800 font-medium italic">
                            "20cm waterlogging predicted in Gejayan area within 1 hour."
                        </div>
                    </FeatureCard>

                    {/* 3. Navigation */}
                    <FeatureCard className="bg-white hover:border-teal-200" delay={0.2}>
                        <div className="w-10 h-10 bg-teal-100 text-teal-600 rounded-xl flex items-center justify-center mb-4">
                            <Navigation size={20} />
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Safe Routing Engine</h3>
                        <p className="text-sm text-slate-600">
                            Don't get stranded. Dynamic routing algorithms find safe, unflooded roads.
                        </p>
                    </FeatureCard>

                    {/* 4. Community reporting */}
                    <FeatureCard className="bg-white hover:border-orange-200" delay={0.3}>
                        <div className="w-10 h-10 bg-orange-100 text-orange-600 rounded-xl flex items-center justify-center mb-4">
                            <MessageSquarePlus size={20} />
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Community Reporting</h3>
                        <p className="text-sm text-slate-600">
                            Crowdsource safety. Spot a flood and report it instantly.
                        </p>
                    </FeatureCard>

                    {/* 5. WhatsApp bot */}
                    <FeatureCard className="bg-white hover:border-green-200" delay={0.4}>
                        <div className="flex justify-between items-start mb-4">
                            <div className="w-10 h-10 bg-green-100 text-green-600 rounded-xl flex items-center justify-center">
                                <Smartphone size={20} />
                            </div>
                            <span className="text-[10px] font-bold bg-green-50 text-green-700 px-2 py-1 rounded-full border border-green-100">
                                HINDI + NLU
                            </span>
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">WhatsApp AI Bot</h3>
                        <p className="text-sm text-slate-600">
                            Get immediate alerts and ask for safe routes directly through WhatsApp.
                        </p>
                    </FeatureCard>

                    {/* 6. Alerts */}
                    <FeatureCard className="bg-white hover:border-red-200" delay={0.5}>
                        <div className="flex justify-between items-start mb-4">
                            <div className="w-10 h-10 bg-red-100 text-red-600 rounded-xl flex items-center justify-center">
                                <AlertTriangle size={20} />
                            </div>
                            <span className="text-[10px] font-bold bg-red-50 text-red-700 px-2 py-1 rounded-full border border-red-100">
                                URGENT
                            </span>
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Smart Alerts & Monitors</h3>
                        <p className="text-sm text-slate-600">
                            Emergency broadcasts to family circles using live location tracking.
                        </p>
                    </FeatureCard>

                    {/* 7. Offline PWA (2 columns) */}
                    <FeatureCard className="md:col-span-2 bg-white hover:border-blue-300" delay={0.6}>
                        <div className="flex justify-between items-start mb-4">
                            <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-xl flex items-center justify-center">
                                <WifiOff size={20} />
                            </div>
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Offline-Ready PWA</h3>
                        <p className="text-sm text-slate-600">
                            Built as a Progressive Web App capable of operating effectively even during poor network conditions common in disaster scenarios.
                        </p>
                    </FeatureCard>

                    {/* 8. IoT sensors (2 columns) */}
                    <FeatureCard className="md:col-span-2 bg-white hover:border-slate-300" delay={0.7}>
                        <div className="flex justify-between items-start mb-4">
                            <div className="w-10 h-10 bg-slate-100 text-slate-600 rounded-xl flex items-center justify-center">
                                <MapIcon size={20} />
                            </div>
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">IoT Sensor Integration</h3>
                        <p className="text-sm text-slate-600">
                            Experimental integration with on-ground hardware water level sensors to continuously validate ML predictions locally.
                        </p>
                    </FeatureCard>

                </div>

                {/* Community trust section */}
                <div className="mt-24">
                    <FeatureCard className="bg-blue-950 text-white border-blue-900 relative overflow-visible" delay={0.5}>

                        <div className="absolute top-[-50%] left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-blue-600 blur-[150px] opacity-20 rounded-full pointer-events-none" />

                        <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-10 text-center md:text-left">

                            <div className="flex-1">
                                <div className="flex items-center justify-center md:justify-start gap-3 mb-4">
                                    <div className="w-12 h-12 bg-white/10 rounded-2xl flex items-center justify-center text-blue-400 border border-white/10 shadow-[0_0_15px_rgba(59,130,246,0.3)]">
                                        <ShieldCheck size={24} />
                                    </div>
                                    <div>
                                        <div className="text-blue-400 font-bold tracking-widest text-xs uppercase">Community Trust</div>
                                        <div className="text-white font-bold text-lg">Anti-Hoax System</div>
                                    </div>
                                </div>

                                <h3 className="text-3xl md:text-4xl font-bold mb-4 leading-tight">
                                    Verified Reports Only. <br />
                                    <span className="text-slate-400">Because trust saves lives.</span>
                                </h3>
                                <p className="text-slate-400 max-w-2xl text-lg">
                                    We know the danger of hoaxes during disasters. Every report is double-verified by AI and community voting before appearing on the map.
                                </p>
                            </div>

                            <div className="flex gap-8 md:gap-16 border-t md:border-t-0 md:border-l border-white/10 pt-8 md:pt-0 md:pl-12">
                                <div>
                                    <div className="text-4xl font-bold text-white mb-1">10k+</div>
                                    <div className="text-sm text-slate-500 font-medium uppercase tracking-wide">Reporters</div>
                                </div>
                                <div>
                                    <div className="text-4xl font-bold text-blue-400 mb-1">98%</div>
                                    <div className="text-sm text-slate-500 font-medium uppercase tracking-wide">Accuracy</div>
                                </div>
                            </div>

                        </div>
                    </FeatureCard>
                </div>

            </div>
        </section>
    );
};

export default Features;
