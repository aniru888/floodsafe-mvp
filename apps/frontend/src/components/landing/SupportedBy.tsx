import { VelocityText } from './ScrollVelocity';
import metaLogo from '../../assets/landing/logo-meta.png';
import waLogo from '../../assets/landing/logo-wa.png';
import sl2Logo from '../../assets/landing/logo-sl2.png';
import floodsafeLogo from '../../assets/landing/logo.png';

const partners = [
    { name: "Sustainable Living Lab", sub: "Incubated by", logo: sl2Logo },
    { name: "Meta", sub: "Supported by", logo: metaLogo },
    { name: "WhatsApp API", sub: "Integrated with", logo: waLogo },
    { name: "FloodSafe AI", sub: "Powered by", logo: floodsafeLogo }
];

const MarqueeStrip = ({ theme = 'light' }: { theme?: 'light' | 'dark' }) => (
    <div className="flex items-center gap-16 px-8">
        {partners.map((partner, i) => (
            <div key={i} className={`flex items-center gap-3 ${theme === 'light' ? 'opacity-90' : 'opacity-100'}`}>
                <div className={`p-1.5 rounded-lg ${theme === 'light' ? 'bg-white shadow-sm border border-slate-100' : 'bg-white/10 backdrop-blur-sm border border-white/10'}`}>
                    <img
                        src={partner.logo}
                        alt={partner.name}
                        className="h-6 w-auto object-contain"
                    />
                </div>
                <div className="flex items-center gap-2 whitespace-nowrap">
                    <span className={`text-xs font-bold uppercase tracking-wider ${theme === 'light' ? 'text-slate-400' : 'text-blue-200'}`}>
                        {partner.sub}
                    </span>
                    <span className={`text-lg font-bold ${theme === 'light' ? 'text-slate-800' : 'text-white'}`}>
                        {partner.name}
                    </span>
                </div>
            </div>
        ))}
    </div>
);

export const SupportedBy = () => {
    return (
        <section className="py-24 relative z-20 overflow-hidden bg-transparent">

            <div className="rotate-[-3deg] scale-105 origin-center transform-gpu">

                {/* Strip 1: White theme (left to right) */}
                <div className="bg-white/95 backdrop-blur-sm py-4 border-y border-slate-200 shadow-sm relative z-10">
                    <VelocityText baseVelocity={-5} className="flex items-center">
                        <MarqueeStrip theme="light" />
                    </VelocityText>
                </div>

                {/* Strip 2: Dark blue theme (right to left) */}
                <div className="bg-blue-950/95 backdrop-blur-md py-4 border-y border-blue-900 shadow-xl relative z-20 -mt-1 -ml-8">
                    <VelocityText baseVelocity={5} className="flex items-center">
                        <MarqueeStrip theme="dark" />
                    </VelocityText>
                </div>

            </div>

        </section>
    );
};

export default SupportedBy;
