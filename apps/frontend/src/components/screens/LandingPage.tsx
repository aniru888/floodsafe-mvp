import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';

import { Navbar } from '../landing/Navbar';
import { Hero } from '../landing/Hero';
import { SupportedBy } from '../landing/SupportedBy';
import { HowItWorks } from '../landing/HowItWorks';
import { Features } from '../landing/Features';
import { TechStack } from '../landing/TechStack';
import { CTA } from '../landing/CTA';
import { Mission } from '../landing/Mission';
import { Footer } from '../landing/Footer';
import { Preloader } from '../landing/Preloader';
import { DotGrid } from '../landing/DotGrid';

export default function LandingPage() {
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    // Deep link forwarding: capture ?join=CODE and forward to /login
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const joinCode = params.get('join');
        if (joinCode) {
            sessionStorage.setItem('pendingInviteCode', joinCode);
            navigate('/login', { replace: true });
        }
    }, [navigate]);

    useEffect(() => {
        const timer = setTimeout(() => setLoading(false), 3000);
        return () => clearTimeout(timer);
    }, []);

    return (
        <div className="relative min-h-screen text-slate-900 overflow-x-hidden selection:bg-blue-200 selection:text-blue-900">
            <AnimatePresence>
                {loading && <Preloader />}
            </AnimatePresence>

            <div style={{ overflow: loading ? 'hidden' : 'auto', height: loading ? '100vh' : 'auto' }}>
                <DotGrid dotSize={2} gap={15} proximity={120} shockRadius={250} />
                <Navbar />
                <main>
                    <Hero />
                    <SupportedBy />
                    <HowItWorks />
                    <Features />
                    <TechStack />
                    <CTA />
                    <Mission />
                </main>
                <Footer />
            </div>
        </div>
    );
}
