import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BrainCircuit, CloudRain, MapPin, Database, Sparkles, Navigation, ShieldCheck, Share2 } from 'lucide-react';

const RiskAnalysisSimulation = () => {
    const [step, setStep] = useState(0);

    useEffect(() => {
        const timer = setInterval(() => {
            setStep((prev) => (prev + 1) % 4);
        }, 3500);
        return () => clearInterval(timer);
    }, []);

    return (
        <div className="bg-white rounded-3xl shadow-2xl shadow-blue-900/5 border border-slate-100 p-6 relative overflow-hidden h-[350px] flex flex-col">

            <div className="flex items-center gap-3 mb-8 border-b border-slate-50 pb-4">
                <div className="w-10 h-10 bg-purple-100 rounded-xl flex items-center justify-center text-purple-600">
                    <BrainCircuit size={20} />
                </div>
                <div>
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">AI Model</div>
                    <div className="text-sm font-bold text-slate-900">Meta Llama 3 Inference</div>
                </div>
                <div className="ml-auto flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${step === 1 ? 'bg-green-500 animate-pulse' : 'bg-slate-300'}`} />
                    <span className="text-xs text-slate-400 font-mono">{step === 1 ? 'PROCESSING' : 'IDLE'}</span>
                </div>
            </div>

            <div className="flex-1 relative">

                <AnimatePresence>
                    {step === 0 && (
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="absolute inset-0"
                        >
                            <div className="text-xs font-bold text-slate-400 mb-2 uppercase">1. Ingesting Real-time Data</div>
                            <div className="space-y-2">
                                <div className="flex items-center gap-3 bg-slate-50 p-3 rounded-lg border border-slate-100">
                                    <Database size={14} className="text-slate-400" />
                                    <code className="text-xs text-slate-600 font-mono">Rain_Rate: 55mm/hr</code>
                                </div>
                                <div className="flex items-center gap-3 bg-slate-50 p-3 rounded-lg border border-slate-100">
                                    <MapPin size={14} className="text-slate-400" />
                                    <code className="text-xs text-slate-600 font-mono">Loc: Gejayan_St (Slope: 2&deg;)</code>
                                </div>
                                <div className="flex items-center gap-3 bg-slate-50 p-3 rounded-lg border border-slate-100">
                                    <CloudRain size={14} className="text-slate-400" />
                                    <code className="text-xs text-slate-600 font-mono">Soil_Saturation: 85%</code>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                <AnimatePresence>
                    {step === 1 && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 1.1 }}
                            className="absolute inset-0 flex flex-col items-center justify-center text-center"
                        >
                            <div className="w-16 h-16 bg-purple-50 rounded-full flex items-center justify-center mb-4 relative">
                                <div className="absolute inset-0 border-4 border-purple-100 rounded-full border-t-purple-600 animate-spin" />
                                <BrainCircuit size={24} className="text-purple-600" />
                            </div>
                            <div className="text-sm font-bold text-slate-800">Analyzing Risk Patterns...</div>
                            <div className="text-xs text-slate-500 mt-1">Comparing with historical flood data</div>
                        </motion.div>
                    )}
                </AnimatePresence>

                <AnimatePresence>
                    {step >= 2 && (
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="absolute inset-0"
                        >
                            <div className="text-xs font-bold text-purple-600 mb-2 uppercase flex items-center gap-2">
                                <Sparkles size={12} /> 3. Generated Insight
                            </div>

                            <div className="bg-white border border-purple-100 rounded-xl p-4 shadow-lg shadow-purple-50">
                                <div className="flex items-center gap-2 mb-2">
                                    <BrainCircuit size={16} className="text-purple-600" />
                                    <h4 className="font-bold text-slate-900 text-sm">AI Risk Insights</h4>
                                </div>
                                <p className="text-xs text-slate-500 mb-3 leading-relaxed">
                                    Personalized analysis based on current rainfall and topography.
                                </p>

                                <div className="bg-purple-50 border border-purple-100 rounded-lg p-3 flex gap-2 items-start">
                                    <p className="text-xs font-medium text-purple-900 leading-relaxed">
                                        <strong>High Risk:</strong> 20cm waterlogging predicted in Gejayan area within 1 hour. Consider alternate routes.
                                    </p>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

            </div>

            <div className="absolute bottom-0 left-0 h-1 bg-slate-100 w-full">
                <motion.div
                    animate={{ width: ["0%", "100%"] }}
                    transition={{ duration: 14, repeat: Infinity, ease: "linear" }}
                    className="h-full bg-purple-600"
                />
            </div>
        </div>
    );
};

export const HowItWorks = () => {
    return (
        <section id="technology" className="py-24 bg-white relative overflow-hidden">

            <div className="absolute top-1/2 left-0 -translate-y-1/2 w-[500px] h-[500px] bg-blue-50 rounded-full blur-3xl opacity-50 -z-10" />

            <div className="max-w-7xl mx-auto px-6">

                <div className="mb-20">
                    <div className="max-w-2xl">
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-bold uppercase tracking-wider mb-4"
                        >
                            Technology
                        </motion.div>
                        <motion.h2
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: 0.1 }}
                            className="text-3xl md:text-5xl font-bold text-slate-900 mb-6 leading-tight"
                        >
                            See the unseen. <br />
                            <span className="text-blue-600">Precision you can trust.</span>
                        </motion.h2>
                        <motion.p
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: 0.2 }}
                            className="text-slate-600 text-lg leading-relaxed"
                        >
                            Most weather apps just tell you "It's Raining". FloodSafe tells you
                            "Which road is flooded". See how our AI technology protects your journey.
                        </motion.p>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        className="relative"
                    >
                        <div className="absolute -inset-4 bg-gradient-to-tr from-purple-100 to-blue-50 rounded-[2rem] -z-10 blur-xl opacity-60" />
                        <RiskAnalysisSimulation />
                    </motion.div>

                    <div className="space-y-8">
                        <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }} className="flex gap-4 group">
                            <div className="w-12 h-12 bg-white border border-slate-100 shadow-sm rounded-xl flex items-center justify-center shrink-0 group-hover:border-blue-200 group-hover:shadow-blue-100 transition-all duration-300">
                                <Database size={24} className="text-blue-600" />
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 mb-1">1. Data Ingestion</h3>
                                <p className="text-slate-600 text-sm leading-relaxed">Aggregating real-time weather forecasts, IoT hardware metrics, and immediate community reports.</p>
                            </div>
                        </motion.div>

                        <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.3 }} className="flex gap-4 group">
                            <div className="w-12 h-12 bg-white border border-slate-100 shadow-sm rounded-xl flex items-center justify-center shrink-0 group-hover:border-purple-200 group-hover:shadow-purple-100 transition-all duration-300">
                                <BrainCircuit size={24} className="text-purple-600" />
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 mb-1">2. AI Risk Analysis</h3>
                                <p className="text-slate-600 text-sm leading-relaxed">Machine learning models rapidly evaluate ingested data to generate hyper-localized hazard scores.</p>
                            </div>
                        </motion.div>

                        <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.4 }} className="flex gap-4 group">
                            <div className="w-12 h-12 bg-white border border-slate-100 shadow-sm rounded-xl flex items-center justify-center shrink-0 group-hover:border-green-200 group-hover:shadow-green-100 transition-all duration-300">
                                <Share2 size={24} className="text-green-600" />
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 mb-1">3. Alert Distribution</h3>
                                <p className="text-slate-600 text-sm leading-relaxed">Pushing intelligent early warnings to users directly via our PWA and integrated WhatsApp bots in local languages.</p>
                            </div>
                        </motion.div>

                        <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.5 }} className="flex gap-4 group">
                            <div className="w-12 h-12 bg-white border border-slate-100 shadow-sm rounded-xl flex items-center justify-center shrink-0 group-hover:border-teal-200 group-hover:shadow-teal-100 transition-all duration-300">
                                <Navigation size={24} className="text-teal-600" />
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 mb-1">4. Safe Routing Guidance</h3>
                                <p className="text-slate-600 text-sm leading-relaxed">Recalculating navigation paths instantly to direct vehicles cleanly around emerging flood polygons.</p>
                            </div>
                        </motion.div>

                        <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.6 }} className="flex gap-4 group">
                            <div className="w-12 h-12 bg-white border border-slate-100 shadow-sm rounded-xl flex items-center justify-center shrink-0 group-hover:border-orange-200 group-hover:shadow-orange-100 transition-all duration-300">
                                <ShieldCheck size={24} className="text-orange-600" />
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 mb-1">5. Community Validation</h3>
                                <p className="text-slate-600 text-sm leading-relaxed">Closing the loop through crowdsourced verification, making the AI smarter and the predictions more resilient over time.</p>
                            </div>
                        </motion.div>
                    </div>

                </div>
            </div>
        </section>
    );
};

export default HowItWorks;
