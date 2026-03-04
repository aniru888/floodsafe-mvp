import { motion } from 'framer-motion';
import { Map, MessageCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { TextType } from './TextType';
import navigateImage from '../../assets/landing/navigate.png';

export const Hero = () => {
    const navigate = useNavigate();

    return (
        <section className="relative min-h-screen flex items-center pt-20 overflow-hidden bg-transparent">

            <div className="max-w-7xl mx-auto px-6 relative z-10 w-full grid lg:grid-cols-2 gap-12 items-center mt-10">

                {/* Left column */}
                <div className="text-center lg:text-left">
                    {/* Badge */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5 }}
                        className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-blue-200 bg-white/50 backdrop-blur-sm shadow-sm text-blue-700 text-xs font-medium mb-6"
                    >
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-600"></span>
                        </span>
                        Live in Delhi, Bangalore, Yogyakarta, Singapore & Indore
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.1 }}
                        className="mb-6 min-h-[160px] md:min-h-[220px]"
                    >
                        <TextType
                            text={[
                                "AI-Powered Flood Intelligence",
                                "Predict. Alert. Navigate. Stay Safe.",
                                "For Safer City Resilience"
                            ]}
                            typingSpeed={75}
                            deletingSpeed={40}
                            pauseDuration={2000}
                            loop={true}
                            cursorCharacter="_"
                            className="text-5xl md:text-7xl font-bold tracking-tight leading-[1.1]"
                            textColors={['#0f172a', '#2563eb', '#0f172a']}
                        />
                    </motion.div>

                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.2 }}
                        className="text-lg text-slate-600 mb-8 max-w-2xl mx-auto lg:mx-0 leading-relaxed font-medium"
                    >
                        Real-time flood risk prediction, verified community reporting, and localized WhatsApp alerts. Protect your journey with AI-powered safety.
                    </motion.p>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.3 }}
                        className="flex flex-wrap items-center gap-4 justify-center lg:justify-start"
                    >
                        <button
                            onClick={() => navigate('/login')}
                            className="w-full sm:w-auto px-6 py-3 bg-blue-600 text-white rounded-full font-bold hover:bg-blue-700 transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-200 hover:shadow-blue-300 hover:-translate-y-1"
                        >
                            <Map size={18} />
                            View Live Risk Map
                        </button>

                        <button
                            onClick={() => window.open('https://wa.me/message/FLOODSAFE', '_blank')}
                            className="w-full sm:w-auto px-6 py-3 bg-[#25D366] text-white rounded-full font-bold hover:bg-[#128C7E] transition-all flex items-center justify-center gap-2 shadow-lg shadow-green-200 hover:-translate-y-1"
                        >
                            <MessageCircle size={18} />
                            Get Alerts on WhatsApp
                        </button>
                    </motion.div>
                </div>

                {/* Right column - app preview */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.9, rotate: 5 }}
                    animate={{ opacity: 1, scale: 1, rotate: 0 }}
                    transition={{ duration: 0.8, delay: 0.4 }}
                    className="relative hidden lg:block"
                >
                    <div className="relative z-10 bg-white border border-slate-200 rounded-3xl p-4 shadow-2xl shadow-blue-100 rotate-[-5deg] hover:rotate-0 transition-transform duration-500">
                        <div className="flex items-center justify-between mb-4 px-2">
                            <div className="flex gap-2">
                                <div className="w-3 h-3 rounded-full bg-slate-200" />
                                <div className="w-3 h-3 rounded-full bg-slate-200" />
                            </div>
                            <div className="text-xs text-slate-400 font-mono">floodsafe.live</div>
                        </div>

                        <div className="w-full h-[400px] bg-slate-50 rounded-2xl overflow-hidden relative group border border-slate-100">
                            <div className="absolute inset-0">
                                <img src={navigateImage} alt="Live Navigation" className="w-full h-full object-cover opacity-90" />
                            </div>

                            <div className="absolute bottom-6 left-6 right-6 bg-white/95 backdrop-blur-md border border-blue-100 p-4 rounded-xl flex items-center justify-between shadow-lg shadow-blue-50">
                                <div>
                                    <div className="text-xs text-slate-500">Current Route</div>
                                    <div className="text-slate-900 font-bold flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                                        Safe from Floods
                                    </div>
                                </div>
                                <div className="text-blue-600 font-mono text-xl font-bold">12 min</div>
                            </div>
                        </div>
                    </div>
                    <div className="absolute -inset-4 bg-gradient-to-tr from-blue-200 via-blue-100 to-white rounded-3xl blur-3xl opacity-60 -z-10" />
                </motion.div>

            </div>
        </section>
    );
};

export default Hero;
