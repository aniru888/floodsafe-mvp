import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { PillNav } from './PillNav';
import logoImage from '../../assets/landing/logo.png';

export const Navbar = () => {
    const [activeSection, setActiveSection] = useState('#home');
    const navigate = useNavigate();
    const { isAuthenticated } = useAuth();

    useEffect(() => {
        const handleScroll = () => {
            const sections = ['home', 'mission', 'features', 'technology'];
            const scrollPosition = window.scrollY + 100;

            for (const section of sections) {
                const element = document.getElementById(section);
                if (element && element.offsetTop <= scrollPosition && (element.offsetTop + element.offsetHeight) > scrollPosition) {
                    setActiveSection(`#${section} `);
                }
            }
        };

        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const authItems = isAuthenticated
        ? [{
            label: 'Dashboard',
            href: '/app',
            onClick: (e: React.MouseEvent) => { e.preventDefault(); navigate('/app'); },
            initialColor: '#3b82f6'
        }]
        : [
            {
                label: 'Sign In',
                href: '/login',
                onClick: (e: React.MouseEvent) => { e.preventDefault(); navigate('/login'); },
                initialColor: '#3b82f6'
            },
            {
                label: 'Register',
                href: '/login?mode=register',
                onClick: (e: React.MouseEvent) => { e.preventDefault(); navigate('/login?mode=register'); },
                ariaLabel: "Register Account",
                highlight: true
            }
        ];

    return (
        <PillNav
            logo={logoImage}
            logoAlt="FloodSafe"
            items={[
                { label: 'About Us', href: '#mission' },
                { label: 'Technology', href: '#technology' },
                { label: 'Features', href: '#features' },
                { label: 'Community', href: '#community' },
                ...authItems
            ]}
            activeHref={activeSection}
            className="custom-nav fixed top-4 left-1/2 -translate-x-1/2 z-50"
            ease="power2.easeOut"
            baseColor="#ffffff"
            pillColor="#eff6ff"
            hoveredPillTextColor="#2563eb"
            pillTextColor="#1e293b"
            initialLoadAnimation={true}
        />
    );
};

export default Navbar;
