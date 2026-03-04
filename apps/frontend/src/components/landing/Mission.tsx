import { motion } from 'framer-motion';
import { Heart, Target, Zap } from 'lucide-react';

export const Mission = () => {
    return (
        <section id="mission" className="py-24 bg-slate-50 relative border-t border-slate-200 overflow-hidden">

            <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-blue-100/40 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />

            <div className="max-w-7xl mx-auto px-6 relative z-10">

                <div className="grid grid-cols-1 md:grid-cols-2 gap-16 items-center">

                    <div>
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-100 text-orange-700 text-xs font-bold uppercase tracking-wider mb-6"
                        >
                            <Target size={12} />
                            The Urban Challenge
                        </motion.div>

                        <motion.h2
                            initial={{ opacity: 0, y: 10 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: 0.1 }}
                            className="text-3xl md:text-5xl font-bold text-slate-900 mb-6 leading-tight"
                        >
                            Urban flooding is <br />
                            <span className="text-blue-600">faster than you think.</span>
                        </motion.h2>

                        <motion.p
                            initial={{ opacity: 0, y: 10 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: 0.2 }}
                            className="text-slate-600 text-lg leading-relaxed mb-8"
                        >
                            High-risk cities face severe challenges during monsoons. Lack of real-time localized risk awareness leads to poor routing decisions. FloodSafe solves this fragmented emergency communication by bringing AI-driven civic-tech right to your pocket.
                        </motion.p>

                        <div className="flex gap-8 border-t border-slate-200 pt-8">
                            <div>
                                <div className="text-3xl font-bold text-slate-900">Scalable</div>
                                <div className="text-xs text-slate-500 uppercase tracking-wide mt-1">For Smart Cities</div>
                            </div>
                            <div>
                                <div className="text-3xl font-bold text-slate-900">Resilient</div>
                                <div className="text-xs text-slate-500 uppercase tracking-wide mt-1">Disaster-Ready</div>
                            </div>
                        </div>
                    </div>

                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.3 }}
                        className="relative"
                    >
                        <div className="bg-white p-8 rounded-3xl shadow-xl border border-slate-100 relative z-10">

                            <div className="flex items-start gap-5 mb-8">
                                <div className="w-12 h-12 bg-blue-100 rounded-2xl flex items-center justify-center text-blue-600 shrink-0">
                                    <Target size={24} />
                                </div>
                                <div>
                                    <h3 className="font-bold text-xl text-slate-900">Community-Driven Intelligence</h3>
                                    <p className="text-slate-500 mt-2 leading-relaxed text-sm">
                                        Empowering citizens to report and verify flood hotspots, creating a trusted crowdsourced safety network.
                                    </p>
                                </div>
                            </div>

                            <div className="flex items-start gap-5">
                                <div className="w-12 h-12 bg-red-100 rounded-2xl flex items-center justify-center text-red-600 shrink-0">
                                    <Heart size={24} />
                                </div>
                                <div>
                                    <h3 className="font-bold text-xl text-slate-900">Built for Resilience</h3>
                                    <p className="text-slate-500 mt-2 leading-relaxed text-sm">
                                        Designed to operate in low-bandwidth disaster scenarios, ensuring critical information flows when it matters most.
                                    </p>
                                </div>
                            </div>

                            <div className="mt-10 pt-6 border-t border-slate-50 flex justify-between items-center">
                                <div className="flex items-center gap-2 text-xs text-slate-400 uppercase font-bold tracking-widest">
                                    <Zap size={12} className="text-yellow-500 fill-yellow-500" />
                                    Powered by Passion
                                </div>
                                <span className="text-2xl text-slate-400 rotate-[-5deg] inline-block font-bold opacity-50">
                                    FloodSafe
                                </span>
                            </div>
                        </div>

                        <div className="absolute top-4 right-[-10px] w-full h-full bg-slate-200/50 rounded-3xl -z-10" />
                    </motion.div>

                </div>
            </div>
        </section>
    );
};

export default Mission;
