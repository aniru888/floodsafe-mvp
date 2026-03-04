import { motion } from 'framer-motion';
import { Layers, Server, BrainCircuit, MessageCircle, Map as MapIcon } from 'lucide-react';

const TechStackCard = ({ icon: Icon, title, desc, delay }: { icon: React.ElementType, title: string, desc: string, delay: number }) => (
    <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay }}
        className="bg-white rounded-3xl p-6 shadow-sm border border-slate-100 hover:border-blue-200 hover:shadow-lg transition-all"
    >
        <div className="w-12 h-12 bg-slate-50 rounded-2xl flex items-center justify-center text-blue-600 mb-6 border border-slate-100">
            <Icon size={24} />
        </div>
        <h3 className="font-bold text-lg text-slate-900 mb-2">{title}</h3>
        <p className="text-slate-500 text-sm leading-relaxed">{desc}</p>
    </motion.div>
);

export const TechStack = () => {
    return (
        <section id="techstack" className="py-24 bg-slate-50 relative overflow-hidden border-t border-slate-100">
            <div className="absolute top-1/2 right-0 -translate-y-1/2 w-[600px] h-[600px] bg-blue-100/50 rounded-full blur-3xl opacity-50 -z-10" />

            <div className="max-w-7xl mx-auto px-6 relative z-10">
                <div className="text-center max-w-2xl mx-auto mb-16">
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-bold uppercase tracking-wider mb-4 border border-slate-200"
                    >
                        <Layers size={14} />
                        Powered By Modern Tech
                    </motion.div>

                    <motion.h2
                        initial={{ opacity: 0, y: 10 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.1 }}
                        className="text-3xl md:text-5xl font-bold text-slate-900 mb-6"
                    >
                        Enterprise-Grade <br />
                        <span className="text-blue-600">Disaster Infrastructure.</span>
                    </motion.h2>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                    <TechStackCard
                        icon={Layers}
                        title="Frontend"
                        desc="React + Offline-First Progressive Web App (PWA) built for low-bandwidth environments."
                        delay={0.1}
                    />
                    <TechStackCard
                        icon={Server}
                        title="Backend"
                        desc="FastAPI + PostGIS enabling high-performance spatial queries and robust data streaming."
                        delay={0.2}
                    />
                    <TechStackCard
                        icon={BrainCircuit}
                        title="Machine Learning"
                        desc="Advanced AI models & TensorFlow Lite (TFLite) for rapid, on-device flood hotspot predictions."
                        delay={0.3}
                    />
                    <TechStackCard
                        icon={MessageCircle}
                        title="Alerts & Comms"
                        desc="Meta WhatsApp API & Twilio integration for instant multi-language emergency broadcasts."
                        delay={0.4}
                    />
                    <TechStackCard
                        icon={MapIcon}
                        title="Mapping"
                        desc="Advanced Geospatial mapping visualizing dynamic flood polygons and safe routing layers."
                        delay={0.5}
                    />
                </div>
            </div>
        </section>
    );
};

export default TechStack;
