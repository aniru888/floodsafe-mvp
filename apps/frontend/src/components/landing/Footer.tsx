import React from 'react';
import { motion } from 'framer-motion';
import { Github, ArrowUpRight } from 'lucide-react';
import logoImage from '../../assets/landing/logo.png';

const FooterLink = ({ href, children }: { href: string, children: React.ReactNode }) => (
    <li>
        <a
            href={href}
            className="group flex items-center gap-2 text-slate-400 hover:text-white transition-colors duration-300"
        >
            <span className="relative overflow-hidden">
                <span className="block transition-transform duration-300 group-hover:-translate-y-full">
                    {children}
                </span>
                <span className="absolute top-0 left-0 block translate-y-full transition-transform duration-300 group-hover:translate-y-0 text-blue-400">
                    {children}
                </span>
            </span>
            <ArrowUpRight size={14} className="opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300 text-blue-400" />
        </a>
    </li>
);

const SocialButton = ({ icon: Icon, href, label }: { icon: React.ElementType, href: string, label: string }) => (
    <motion.a
        whileHover={{ scale: 1.1, rotate: 5 }}
        whileTap={{ scale: 0.95 }}
        href={href}
        aria-label={label}
        className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 hover:bg-blue-600 hover:text-white transition-colors border border-slate-700 hover:border-blue-500"
    >
        <Icon size={18} />
    </motion.a>
);

export const Footer = () => {
    return (
        <footer className="bg-[#0B1120] text-slate-300 pt-24 pb-10 relative z-50 shadow-[0_-20px_80px_-20px_rgba(0,0,0,0.1)]">

            <div className="absolute top-0 left-0 w-full h-[1px] bg-slate-800/50 shadow-[0_0_10px_rgba(59,130,246,0.5)]" />

            <div className="absolute inset-0 pointer-events-none overflow-hidden">
                <div className="absolute inset-0 opacity-[0.02]">
                    <div className="absolute inset-0 bg-[linear-gradient(white_1px,transparent_1px),linear-gradient(90deg,white_1px,transparent_1px)] bg-[size:3rem_3rem]" />
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-6 relative z-10">

                {/* Top section */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 mb-16 items-start">

                    {/* Brand */}
                    <div className="space-y-6">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-900/50">
                                <img src={logoImage} alt="FloodSafe" className="w-6 h-6 object-contain brightness-0 invert" />
                            </div>
                            <span className="font-bold text-2xl text-white tracking-tight">
                                FloodSafe<span className="text-blue-500">.</span>
                            </span>
                        </div>
                        <p className="text-slate-400 max-w-sm leading-relaxed text-lg">
                            Empowering communities with AI-driven flood intelligence. Stay safe, stay dry.
                        </p>
                        <div className="flex gap-4 pt-2">
                            <SocialButton icon={Github} href="https://github.com/FloodSafe-Delhi/floodsafe-mvp" label="GitHub" />
                        </div>
                    </div>

                    {/* Newsletter */}
                    <div className="bg-slate-800/40 rounded-3xl p-8 border border-slate-700/50 backdrop-blur-sm lg:ml-auto w-full max-w-md shadow-xl relative group hover:border-blue-500/20 transition-all duration-500">
                        <h4 className="text-white font-bold text-lg mb-2">Join the Community</h4>
                        <p className="text-slate-400 text-sm mb-4">Get the latest safety updates directly to your inbox.</p>
                        <div className="flex gap-2">
                            <input
                                type="email"
                                placeholder="Enter your email"
                                className="bg-slate-900/80 border border-slate-700 text-white px-4 py-3 rounded-xl w-full focus:outline-none focus:border-blue-500 transition-colors placeholder:text-slate-600"
                            />
                            <button className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-3 rounded-xl font-bold transition-colors shadow-lg shadow-blue-900/20">
                                Join
                            </button>
                        </div>
                    </div>
                </div>

                {/* Links grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-8 py-12 border-t border-slate-800/50">
                    <div>
                        <h4 className="text-white font-bold mb-6">Product</h4>
                        <ul className="space-y-4">
                            <FooterLink href="#">Flood Atlas</FooterLink>
                            <FooterLink href="#">Safety Circles</FooterLink>
                            <FooterLink href="#">Report Incident</FooterLink>
                            <FooterLink href="#">Mobile App</FooterLink>
                        </ul>
                    </div>
                    <div>
                        <h4 className="text-white font-bold mb-6">Resources</h4>
                        <ul className="space-y-4">
                            <FooterLink href="#">Documentation</FooterLink>
                            <FooterLink href="#">API Reference</FooterLink>
                            <FooterLink href="#">Community Guidelines</FooterLink>
                            <FooterLink href="#">Status Page</FooterLink>
                        </ul>
                    </div>
                    <div>
                        <h4 className="text-white font-bold mb-6">Company</h4>
                        <ul className="space-y-4">
                            <FooterLink href="#">About Us</FooterLink>
                            <FooterLink href="#">Careers</FooterLink>
                            <FooterLink href="#">Blog</FooterLink>
                            <FooterLink href="#">Partners</FooterLink>
                        </ul>
                    </div>
                    <div>
                        <h4 className="text-white font-bold mb-6">Legal</h4>
                        <ul className="space-y-4">
                            <FooterLink href="#">Privacy Policy</FooterLink>
                            <FooterLink href="#">Terms of Service</FooterLink>
                            <FooterLink href="#">Cookie Settings</FooterLink>
                        </ul>
                    </div>
                </div>

                {/* Bottom bar */}
                <div className="pt-8 border-t border-slate-800/50 flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-slate-500">
                    <p>&copy; 2026 FloodSafe. Open Source Project.</p>
                    <div className="flex items-center gap-2">
                        <span>Made with</span>
                        <span>by Team 10</span>
                    </div>
                </div>

            </div>
        </footer>
    );
};

export default Footer;
