import React from 'react';
import { ArrowUp, ArrowDown } from 'lucide-react';

const HeavyweightCards = ({ stocks }) => {
    if (!stocks || stocks.length === 0) return null;

    return (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {stocks.map((stock) => {
                const isPos = stock.change >= 0;
                return (
                    <div key={stock.symbol} className="glass-panel p-5 relative overflow-hidden group">

                        {/* Hover glow effect */}
                        <div className={`absolute inset-0 opacity-0 group-hover:opacity-10 transition-opacity duration-300 ${isPos ? 'bg-primary' : 'bg-danger'
                            }`}></div>

                        <div className="flex justify-between items-center mb-3">
                            <span className="font-bold text-sm tracking-wide text-white">{stock.symbol}</span>
                            <span className={`text-xs px-2 py-0.5 rounded font-mono font-medium border ${isPos
                                    ? 'bg-primary/10 text-primary border-primary/20'
                                    : 'bg-danger/10 text-danger border-danger/20'
                                }`}>
                                {isPos ? '+' : ''}{stock.change_pct}%
                            </span>
                        </div>

                        <div className="flex items-end justify-between mt-2">
                            <div>
                                <div className="text-xl font-mono text-white tracking-tight">
                                    {stock.ltp.toLocaleString('en-IN')}
                                </div>
                                <div className={`text-xs font-mono font-medium mt-1 ${isPos ? 'text-primary/80' : 'text-danger/80'}`}>
                                    Impact: {stock.nifty_impact} pts
                                </div>
                            </div>
                            <div className={`p-1.5 rounded-md bg-white/5 border ${isPos ? 'border-primary/20' : 'border-danger/20'}`}>
                                {isPos ? <ArrowUp size={16} className="text-primary" /> : <ArrowDown size={16} className="text-danger" />}
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
};

export default HeavyweightCards;
