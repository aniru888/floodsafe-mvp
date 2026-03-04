import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

export const Preloader = () => {
    const [percent, setPercent] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setPercent((prev) => {
                if (prev >= 100) {
                    clearInterval(interval);
                    return 100;
                }
                return prev + 1;
            });
        }, 20);
        return () => clearInterval(interval);
    }, []);

    return (
        <motion.div
            initial={{ opacity: 1 }}
            exit={{ y: "-100%", transition: { duration: 0.8, ease: "easeInOut" } }}
            className="fixed inset-0 z-[9999] bg-white flex flex-col items-center justify-center overflow-hidden font-sans"
        >

            {/* Main text (percentage) */}
            <div className="relative z-20 text-center mix-blend-difference text-white">
                <h1 className="text-8xl md:text-9xl font-bold tracking-tighter mb-2">
                    {percent}%
                </h1>
                <div className="flex items-center gap-2 justify-center text-sm uppercase tracking-[0.2em] font-medium opacity-80">
                    <span className="w-2 h-2 rounded-full bg-current animate-pulse"></span>
                    Calibrating Sensors
                </div>
            </div>

            {/* Water animation (waves) */}
            <div className="absolute inset-0 z-10 flex flex-col justify-end">
                <motion.div
                    initial={{ height: "0%" }}
                    animate={{ height: "100%" }}
                    transition={{ duration: 2.5, ease: "easeInOut" }}
                    className="relative w-full bg-blue-600"
                >
                    {/* Wave 1 (Front - Light) */}
                    <div className="absolute top-[-40px] w-[200%] h-16 bg-blue-500 opacity-50 animate-[wave_3s_linear_infinite]"
                        style={{ backgroundImage: "url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNDQwIDMyMCI+PHBhdGggZmlsbD0iIzNiODJmNiIgZmlsbC1vcGFjaXR5PSIxIiBkPSJNMCAyMjRMODAgMjEzLjNDMTYwIDIwMyAyNDAgMTgxIDMyMCAxODEuM0M0MDAgMTgyIDQ4MCAyMDIgNTYwIDIwOC43QzY0MCAyMTUgNzIwIDIwNyA4MDAgMTg2LjdDODgwIDE2NiA5NjAgMTMzIDEwNDAgMTMzLjNDMTEyMCAxMzMgMTIwMCAxNjYgMTI4MCAxODIuN0MxMzYwIDE5OSAxNDQwIDE5OSAxNDQwIDE5OVYzMjBIMHoiPjwvcGF0aD48L3N2Zz4=')", backgroundSize: "50% 100%" }}
                    />

                    {/* Wave 2 (Back - Dark) */}
                    <div className="absolute top-[-60px] w-[200%] h-24 bg-blue-600 animate-[wave_5s_linear_infinite_reverse]"
                        style={{ left: "-100%", backgroundImage: "url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNDQwIDMyMCI+PHBhdGggZmlsbD0iIzI1NjNlYiIgZmlsbC1vcGFjaXR5PSIxIiBkPSJNMCA5Nkw4MCAxMTJDNjQwIDEyOCAyNDAgMTYwIDMyMCAxNjBDNDAwIDE2MCA0ODAgMTI4IDU2MCAxMTJDNjQwIDk2IDcyMCA5NiA4MDAgMTEyQzg4MCAxMjggOTYwIDE2MCAxMDQwIDE2MEMxMTIwIDE2MCAxMjAwIDEyOCAxMjgwIDExMkMxMzYwIDk2IDE0NDAgOTYgMTQ0MCA5NlYzMjBIMHoiPjwvcGF0aD48L3N2Zz4=')", backgroundSize: "50% 100%" }}
                    />
                </motion.div>
            </div>

        </motion.div>
    );
};

export default Preloader;
