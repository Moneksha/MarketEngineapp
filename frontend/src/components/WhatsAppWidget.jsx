import React, { useState, useEffect } from 'react';
import { X, MessageCircle } from 'lucide-react';

const WhatsAppIcon = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51a12.8 12.8 0 0 0-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413z" />
    </svg>
);

const WhatsAppWidget = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [showBubble, setShowBubble] = useState(false);
    const [pulse, setPulse] = useState(false);
    const [isMounted, setIsMounted] = useState(false);

    // Contact details
    const phoneNumber = "919372225072";
    const message = "Hello, I visited Market Engine and would like to know more about your trading strategy development, backtesting, and automation services.";
    const waUrl = `https://wa.me/${phoneNumber}?text=${encodeURIComponent(message)}`;

    useEffect(() => {
        // Initial fade in for the whole widget
        setIsMounted(true);

        // Show chat bubble preview after 5 seconds
        const bubbleTimer = setTimeout(() => {
            setShowBubble(true);
        }, 5000);

        return () => clearTimeout(bubbleTimer);
    }, []);

    useEffect(() => {
        // Pulse animation every 10 seconds
        const pulseTimer = setInterval(() => {
            setPulse(true);
            setTimeout(() => setPulse(false), 1500); // Pulse duration 1.5s
        }, 10000);

        return () => clearInterval(pulseTimer);
    }, []);

    const toggleWidget = () => {
        setIsOpen(!isOpen);
        if (!isOpen) {
            setShowBubble(false); // Hide the bubble if card is opened
        }
    };

    return (
        <div
            className={`fixed bottom-6 right-6 z-50 flex flex-col items-end transition-opacity duration-1000 ${isMounted ? 'opacity-100' : 'opacity-0'}`}
        >
            {/* Expanded Support Card */}
            <div
                className={`mb-4 transition-all duration-300 origin-bottom-right transform ${isOpen ? 'scale-100 opacity-100' : 'scale-50 opacity-0 pointer-events-none'
                    }`}
            >
                <div className="bg-surface border border-border shadow-2xl rounded-2xl w-[320px] overflow-hidden">
                    {/* Support Header */}
                    <div className="bg-[#10141d] p-4 border-b border-border flex justify-between items-center relative overflow-hidden">
                        <div className="absolute inset-0 bg-gradient-to-r from-primary/5 to-transparent"></div>
                        <div className="flex items-center gap-3 relative z-10">
                            <div className="w-2.5 h-2.5 rounded-full bg-[#25D366] shadow-[0_0_8px_rgba(37,211,102,0.8)] animate-pulse"></div>
                            <span className="text-sm font-semibold text-white tracking-wide">Market Engine Support</span>
                        </div>
                        <button
                            onClick={() => setIsOpen(false)}
                            className="text-muted hover:text-white transition-colors relative z-10"
                            aria-label="Close"
                        >
                            <X size={18} />
                        </button>
                    </div>

                    {/* Card Body */}
                    <div className="p-6">
                        <div className="flex items-center gap-4 mb-5">
                            <div className="w-12 h-12 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary font-bold text-xl shadow-inner">
                                M
                            </div>
                            <div className="flex-1">
                                <h3 className="text-white font-medium text-lg leading-tight">Moneksha Dangat</h3>
                                <p className="text-xs text-muted mt-0.5">Strategy Development & Support</p>
                            </div>
                        </div>

                        <div className="bg-white/5 border border-white/10 rounded-xl p-4 mb-6 relative">
                            <p className="text-sm text-gray-300 leading-relaxed">
                                Chat with us on WhatsApp for tailored algorithms and automated strategies.
                            </p>
                            <span className="flex items-center gap-1.5 text-[11px] text-primary/80 mt-3 font-medium tracking-wide uppercase">
                                <div className="w-1.5 h-1.5 rounded-full bg-primary/80"></div>
                                Usually replies within minutes
                            </span>
                        </div>

                        <a
                            href={waUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="w-full flex items-center justify-center gap-2.5 bg-[#25D366] hover:bg-[#20b858] text-white py-3 px-4 rounded-xl font-medium transition-all duration-300 shadow-[0_4px_14px_rgba(37,211,102,0.3)] hover:shadow-[0_6px_20px_rgba(37,211,102,0.4)] hover:-translate-y-0.5"
                        >
                            <WhatsAppIcon className="w-5 h-5" />
                            Chat on WhatsApp
                        </a>
                    </div>
                </div>
            </div>

            {/* Preview Bubble (Shown after 5s if not opened) */}
            {!isOpen && showBubble && (
                <div className="mb-4 bg-surface border border-primary/20 p-4 rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.4)] w-[260px] mr-2 relative animate-[slideIn_0.4s_ease-out_forwards]">
                    <style dangerouslySetInnerHTML={{
                        __html: `
            @keyframes slideIn {
              0% { opacity: 0; transform: translateY(15px) scale(0.95); }
              100% { opacity: 1; transform: translateY(0) scale(1); }
            }
          `}} />
                    <button
                        onClick={() => setShowBubble(false)}
                        className="absolute -top-2 -right-2 bg-[#1c2233] text-muted hover:text-white rounded-full p-1 border border-border shadow-md transition-colors z-10"
                        aria-label="Close bubble"
                    >
                        <X size={12} />
                    </button>
                    <div className="flex gap-3 mb-4">
                        <div className="text-2xl mt-1">👋</div>
                        <p className="text-sm text-gray-200 leading-relaxed">
                            <span className="font-semibold text-white block mb-0.5">Hi there!</span>
                            Need help building or automating a trading strategy?
                        </p>
                    </div>
                    <a
                        href={waUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="w-full flex justify-center items-center gap-2 text-xs bg-[#25D366]/10 hover:bg-[#25D366]/20 text-[#25D366] py-2 rounded-lg font-semibold transition-colors border border-[#25D366]/20"
                        onClick={() => setShowBubble(false)}
                    >
                        <WhatsAppIcon className="w-3.5 h-3.5" />
                        Chat on WhatsApp
                    </a>
                    {/* Arrow pointing to icon */}
                    <div className="absolute -bottom-2 right-4 w-4 h-4 bg-surface border-b border-r border-primary/20 transform rotate-45"></div>
                </div>
            )}

            {/* Main Floating Button */}
            <button
                onClick={toggleWidget}
                className={`w-14 h-14 rounded-full flex items-center justify-center bg-[#25D366] text-white transition-all duration-300 focus:outline-none focus:ring-4 focus:ring-[#25D366]/30 z-50 shadow-[0_4px_15px_rgba(37,211,102,0.4)] 
        ${pulse ? 'scale-110 shadow-[0_0_25px_rgba(37,211,102,0.6)]' : 'scale-100'} 
        hover:scale-110 hover:shadow-[0_8px_25px_rgba(37,211,102,0.5)]`}
                aria-label="Contact us on WhatsApp"
            >
                <div className={`transition-all duration-300 absolute ${isOpen ? 'rotate-90 scale-0 opacity-0' : 'rotate-0 scale-100 opacity-100'}`}>
                    <WhatsAppIcon className="w-7 h-7" />
                </div>
                <div className={`transition-all duration-300 absolute ${isOpen ? 'rotate-0 scale-100 opacity-100' : '-rotate-90 scale-0 opacity-0'}`}>
                    <X size={26} />
                </div>
            </button>

        </div>
    );
};

export default WhatsAppWidget;
