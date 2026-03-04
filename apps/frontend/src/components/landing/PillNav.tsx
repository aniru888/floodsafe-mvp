import React, { useEffect, useRef, useState } from 'react';
import { gsap } from 'gsap';

interface NavItem {
    label: string;
    href: string;
    ariaLabel?: string;
    highlight?: boolean;
    initialColor?: string;
    onClick?: (e: React.MouseEvent) => void;
}

interface PillNavProps {
    logo: string;
    logoAlt?: string;
    items: NavItem[];
    activeHref?: string;
    className?: string;
    ease?: string;
    baseColor?: string;
    pillColor?: string;
    hoveredPillTextColor?: string;
    pillTextColor?: string;
    onMobileMenuClick?: () => void;
    initialLoadAnimation?: boolean;
}

export const PillNav: React.FC<PillNavProps> = ({
    logo,
    logoAlt = 'Logo',
    items,
    activeHref,
    className = '',
    ease = 'power3.easeOut',
    baseColor = '#fff',
    pillColor = '#060010',
    hoveredPillTextColor = '#060010',
    pillTextColor,
    onMobileMenuClick,
    initialLoadAnimation = true
}) => {
    const resolvedPillTextColor = pillTextColor ?? baseColor;
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const circleRefs = useRef<(HTMLSpanElement | null)[]>([]);
    const tlRefs = useRef<(gsap.core.Timeline | null)[]>([]);
    const activeTweenRefs = useRef<(gsap.core.Tween | null)[]>([]);
    const logoImgRef = useRef<HTMLImageElement>(null);
    const logoTweenRef = useRef<gsap.core.Tween | null>(null);
    const hamburgerRef = useRef<HTMLButtonElement>(null);
    const mobileMenuRef = useRef<HTMLDivElement>(null);
    const navItemsRef = useRef<HTMLDivElement>(null);
    const logoRef = useRef<HTMLAnchorElement>(null);

    useEffect(() => {
        const layout = () => {
            circleRefs.current.forEach((circle) => {
                if (!circle?.parentElement) return;

                const pill = circle.parentElement;
                const rect = pill.getBoundingClientRect();
                const { width: w, height: h } = rect;
                const R = ((w * w) / 4 + h * h) / (2 * h);
                const D = Math.ceil(2 * R) + 2;
                const delta = Math.ceil(R - Math.sqrt(Math.max(0, R * R - (w * w) / 4))) + 1;
                const originY = D - delta;

                circle.style.width = `${D}px`;
                circle.style.height = `${D}px`;
                circle.style.bottom = `-${delta}px`;

                gsap.set(circle, {
                    xPercent: -50,
                    scale: 0,
                    transformOrigin: `50% ${originY}px`
                });

                const label = pill.querySelector('.pill-label');
                const white = pill.querySelector('.pill-label-hover');

                if (label) gsap.set(label, { y: 0 });
                if (white) gsap.set(white, { y: h + 12, opacity: 0 });

                const index = circleRefs.current.indexOf(circle);
                if (index === -1) return;

                tlRefs.current[index]?.kill();
                const tl = gsap.timeline({ paused: true });

                tl.to(circle, { scale: 1.2, xPercent: -50, duration: 0.5, ease, overwrite: 'auto' }, 0);

                if (label) {
                    tl.to(label, { y: -(h + 8), duration: 0.5, ease, overwrite: 'auto' }, 0);
                }

                if (white) {
                    gsap.set(white, { y: Math.ceil(h + 100), opacity: 0 });
                    tl.to(white, { y: 0, opacity: 1, duration: 0.5, ease, overwrite: 'auto' }, 0);
                }

                tlRefs.current[index] = tl;
            });
        };

        layout();

        const onResize = () => layout();
        window.addEventListener('resize', onResize);

        if (document.fonts?.ready) {
            document.fonts.ready.then(layout).catch(() => { });
        }

        const menu = mobileMenuRef.current;
        if (menu) {
            gsap.set(menu, { visibility: 'hidden', opacity: 0, scaleY: 1, y: 0 });
        }

        if (initialLoadAnimation) {
            const logoEl = logoRef.current;
            const navItems = navItemsRef.current;

            if (logoEl) {
                gsap.set(logoEl, { scale: 0 });
                gsap.to(logoEl, {
                    scale: 1,
                    duration: 0.6,
                    ease
                });
            }

            if (navItems) {
                gsap.set(navItems, { width: 0, overflow: 'hidden' });
                gsap.to(navItems, {
                    width: 'auto',
                    duration: 0.6,
                    ease
                });
            }
        }

        return () => window.removeEventListener('resize', onResize);
    }, [items, ease, initialLoadAnimation]);

    const handleEnter = (i: number) => {
        const tl = tlRefs.current[i];
        if (!tl) return;
        activeTweenRefs.current[i]?.kill();
        activeTweenRefs.current[i] = tl.tweenTo(tl.duration(), {
            duration: 0.3,
            ease,
            overwrite: 'auto'
        });
    };

    const handleLeave = (i: number) => {
        const tl = tlRefs.current[i];
        if (!tl) return;
        activeTweenRefs.current[i]?.kill();
        activeTweenRefs.current[i] = tl.tweenTo(0, {
            duration: 0.2,
            ease,
            overwrite: 'auto'
        });
    };

    const handleLogoEnter = () => {
        const img = logoImgRef.current;
        if (!img) return;
        logoTweenRef.current?.kill();
        gsap.set(img, { rotate: 0 });
        logoTweenRef.current = gsap.to(img, {
            rotate: 360,
            duration: 0.5,
            ease,
            overwrite: 'auto'
        });
    };

    const toggleMobileMenu = () => {
        const newState = !isMobileMenuOpen;
        setIsMobileMenuOpen(newState);

        const hamburger = hamburgerRef.current;
        const menu = mobileMenuRef.current;

        if (hamburger) {
            const lines = hamburger.querySelectorAll('.hamburger-line');
            if (newState) {
                gsap.to(lines[0], { rotation: 45, y: 5, duration: 0.3, ease });
                gsap.to(lines[1], { rotation: -45, y: -5, duration: 0.3, ease });
            } else {
                gsap.to(lines[0], { rotation: 0, y: 0, duration: 0.3, ease });
                gsap.to(lines[1], { rotation: 0, y: 0, duration: 0.3, ease });
            }
        }

        if (menu) {
            if (newState) {
                gsap.set(menu, { visibility: 'visible' });
                gsap.fromTo(
                    menu,
                    { opacity: 0, y: 10, scaleY: 1 },
                    {
                        opacity: 1,
                        y: 0,
                        scaleY: 1,
                        duration: 0.3,
                        ease,
                        transformOrigin: 'top center'
                    }
                );
            } else {
                gsap.to(menu, {
                    opacity: 0,
                    y: 10,
                    scaleY: 1,
                    duration: 0.2,
                    ease,
                    transformOrigin: 'top center',
                    onComplete: () => {
                        gsap.set(menu, { visibility: 'hidden' });
                    }
                });
            }
        }

        onMobileMenuClick?.();
    };

    const handleItemClick = (item: NavItem, e: React.MouseEvent) => {
        if (item.onClick) {
            e.preventDefault();
            item.onClick(e);
        }
    };

    const cssVars = {
        '--base': baseColor,
        '--pill-bg': pillColor,
        '--hover-text': hoveredPillTextColor,
        '--pill-text': resolvedPillTextColor,
        '--nav-h': '50px',
        '--logo': '40px',
        '--pill-pad-x': '20px',
        '--pill-gap': '4px'
    } as React.CSSProperties;

    return (
        <div className="fixed top-4 left-0 w-full z-50 flex justify-center pointer-events-none">
            <nav
                className={`pointer-events-auto flex items-center justify-between md:justify-start box-border px-4 md:px-0 bg-transparent ${className}`}
                aria-label="Primary"
                style={cssVars}
            >
                {/* Logo */}
                <a
                    href="/"
                    aria-label="Home"
                    onMouseEnter={handleLogoEnter}
                    ref={logoRef}
                    className="rounded-full p-2 inline-flex items-center justify-center overflow-hidden shadow-sm border border-slate-100/10"
                    style={{
                        width: 'var(--nav-h)',
                        height: 'var(--nav-h)',
                        background: 'var(--base, #fff)'
                    }}
                >
                    <img src={logo} alt={logoAlt} ref={logoImgRef} className="w-full h-full object-contain block" />
                </a>

                {/* Desktop menu pill */}
                <div
                    ref={navItemsRef}
                    className="relative items-center rounded-full hidden md:flex ml-3 shadow-lg shadow-slate-200/50 border border-slate-100"
                    style={{
                        height: 'var(--nav-h)',
                        background: 'var(--base, #fff)'
                    }}
                >
                    <ul
                        role="menubar"
                        className="list-none flex items-center m-0 p-[4px] h-full"
                        style={{ gap: 'var(--pill-gap)' }}
                    >
                        {items.map((item, i) => {
                            const isActive = activeHref === item.href;
                            const isHighlighted = item.highlight;

                            const pillStyle = {
                                background: isHighlighted ? 'var(--hover-text, #000)' : 'transparent',
                                color: isHighlighted ? '#fff' : (item.initialColor || 'var(--pill-text, #000)'),
                                paddingLeft: 'var(--pill-pad-x)',
                                paddingRight: 'var(--pill-pad-x)',
                                fontWeight: isHighlighted ? '700' : '500',
                            };

                            const PillContent = (
                                <>
                                    <span
                                        className="hover-circle absolute left-1/2 bottom-0 rounded-full z-[1] block pointer-events-none"
                                        style={{
                                            background: isHighlighted ? '#1e40af' : 'var(--pill-bg, #000)',
                                            willChange: 'transform'
                                        }}
                                        aria-hidden="true"
                                        ref={(el) => {
                                            circleRefs.current[i] = el;
                                        }}
                                    />
                                    <span className="label-stack relative inline-block leading-[1] z-[2]">
                                        <span
                                            className="pill-label relative z-[2] inline-block leading-[1]"
                                            style={{ willChange: 'transform' }}
                                        >
                                            {item.label}
                                        </span>
                                        <span
                                            className="pill-label-hover absolute left-0 top-0 z-[3] inline-block"
                                            style={{
                                                color: isHighlighted ? '#fff' : 'var(--hover-text, #fff)',
                                                willChange: 'transform, opacity'
                                            }}
                                            aria-hidden="true"
                                        >
                                            {item.label}
                                        </span>
                                    </span>
                                    {isActive && !isHighlighted && (
                                        <span
                                            className="absolute left-1/2 -bottom-[6px] -translate-x-1/2 w-1 h-1 rounded-full z-[4]"
                                            style={{ background: 'var(--pill-bg, #000)' }}
                                            aria-hidden="true"
                                        />
                                    )}
                                </>
                            );

                            const basePillClasses =
                                'relative overflow-hidden inline-flex items-center justify-center h-full no-underline rounded-full box-border text-[15px] leading-[0] whitespace-nowrap cursor-pointer px-0 select-none';

                            return (
                                <li key={item.href} role="none" className="flex h-full">
                                    <a
                                        role="menuitem"
                                        href={item.href}
                                        className={basePillClasses}
                                        style={pillStyle}
                                        aria-label={item.ariaLabel || item.label}
                                        onMouseEnter={() => handleEnter(i)}
                                        onMouseLeave={() => handleLeave(i)}
                                        onClick={(e) => handleItemClick(item, e)}
                                    >
                                        {PillContent}
                                    </a>
                                </li>
                            );
                        })}
                    </ul>
                </div>

                {/* Mobile hamburger */}
                <button
                    ref={hamburgerRef}
                    onClick={toggleMobileMenu}
                    aria-label="Toggle menu"
                    aria-expanded={isMobileMenuOpen}
                    className="md:hidden rounded-full border border-slate-100 flex flex-col items-center justify-center gap-1.5 cursor-pointer p-0 relative ml-auto shadow-sm"
                    style={{
                        width: 'var(--nav-h)',
                        height: 'var(--nav-h)',
                        background: 'var(--base, #fff)'
                    }}
                >
                    <span
                        className="hamburger-line w-5 h-0.5 rounded-full origin-center transition-all duration-[10ms] ease-[cubic-bezier(0.25,0.1,0.25,1)]"
                        style={{ background: '#1e293b' }}
                    />
                    <span
                        className="hamburger-line w-5 h-0.5 rounded-full origin-center transition-all duration-[10ms] ease-[cubic-bezier(0.25,0.1,0.25,1)]"
                        style={{ background: '#1e293b' }}
                    />
                </button>
            </nav>

            {/* Mobile dropdown */}
            <div
                ref={mobileMenuRef}
                className="md:hidden absolute top-[calc(var(--nav-h)+1rem)] right-4 rounded-[20px] shadow-xl z-[998] origin-top-right overflow-hidden w-48 border border-slate-100"
                style={{
                    background: 'var(--base, #fff)'
                }}
            >
                <ul className="list-none m-0 p-2 flex flex-col gap-1">
                    {items.map((item) => {
                        const defaultStyle = {
                            background: 'transparent',
                            color: 'var(--pill-text, #000)'
                        };
                        const hoverIn = (e: React.MouseEvent<HTMLAnchorElement>) => {
                            e.currentTarget.style.background = 'var(--pill-bg)';
                            e.currentTarget.style.color = 'var(--hover-text, #fff)';
                        };
                        const hoverOut = (e: React.MouseEvent<HTMLAnchorElement>) => {
                            e.currentTarget.style.background = 'transparent';
                            e.currentTarget.style.color = 'var(--pill-text, #000)';
                        };

                        const linkClasses =
                            'block py-3 px-4 text-[15px] font-medium rounded-xl transition-all duration-200';

                        return (
                            <li key={item.href}>
                                <a
                                    href={item.href}
                                    className={linkClasses}
                                    style={defaultStyle}
                                    onMouseEnter={hoverIn}
                                    onMouseLeave={hoverOut}
                                    onClick={(e) => {
                                        setIsMobileMenuOpen(false);
                                        onMobileMenuClick?.();
                                        toggleMobileMenu();
                                        handleItemClick(item, e);
                                    }}
                                >
                                    {item.label}
                                </a>
                            </li>
                        );
                    })}
                </ul>
            </div>
        </div>
    );
};

export default PillNav;
