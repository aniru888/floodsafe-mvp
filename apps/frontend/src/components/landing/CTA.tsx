import { motion } from 'framer-motion';
import { ArrowRight, Github, Smartphone } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const CTA = () => {
    const navigate = useNavigate();

    return (
        <section className="py-20 px-6 relative overflow-hidden bg-white/40">

            <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 20 }}
                whileInView={{ opacity: 1, scale: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="max-w-7xl mx-auto bg-blue-600 rounded-[3rem] p-10 md:p-24 relative overflow-hidden text-center shadow-2xl shadow-blue-200"
            >

                {/* Background decoration */}
                <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
                    <div className="absolute top-[-50%] left-[-20%] w-[800px] h-[800px] bg-blue-500 rounded-full blur-3xl opacity-50" />
                    <div className="absolute bottom-[-50%] right-[-20%] w-[600px] h-[600px] bg-blue-400 rounded-full blur-3xl opacity-40" />
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.1)_1px,transparent_1px)] bg-[size:4rem_4rem]" />
                </div>

                <div className="relative z-10 max-w-3xl mx-auto">

                    <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/10 border border-white/20 text-white text-xs font-bold uppercase tracking-wider mb-8 backdrop-blur-md shadow-sm">
                        <Smartphone size={14} />
                        Available on Web & Mobile
                    </div>

                    <h2 className="text-4xl md:text-6xl font-bold text-white mb-6 tracking-tight leading-tight">
                        Floods Don't Wait. <br /> Neither Should Safety.
                    </h2>

                    <p className="text-blue-50 text-lg md:text-xl mb-10 leading-relaxed opacity-90">
                        Join the growing community in Delhi, Bangalore, Yogyakarta, Singapore & Indore.
                        Get real-time flood intelligence directly on your phone without complex installations.
                    </p>

                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4 flex-wrap">

                        <button
                            onClick={() => navigate('/login')}
                            className="w-full sm:w-auto px-8 py-4 bg-white text-blue-600 rounded-full font-bold text-lg hover:bg-blue-50 hover:scale-105 transition-all shadow-lg flex items-center justify-center gap-2 group cursor-pointer"
                        >
                            Join With Us!
                            <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
                        </button>

                        <a
                            href="https://github.com/FloodSafe-Delhi/floodsafe-mvp"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="w-full sm:w-auto px-8 py-4 bg-blue-700/40 border border-blue-400/30 text-white rounded-full font-bold text-lg hover:bg-blue-700/60 transition-all flex items-center justify-center gap-2 backdrop-blur-sm cursor-pointer hover:border-blue-300"
                        >
                            <Github size={20} />
                            Contribute on GitHub
                        </a>
                    </div>

                    <p className="mt-8 text-sm text-blue-200 opacity-70">
                        *Compatible with iOS & Android directly from Chrome/Safari.
                    </p>
                </div>

            </motion.div>
        </section>
    );
};

export default CTA;
