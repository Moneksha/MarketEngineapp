import React, { useEffect, useRef } from 'react';

// Weight lookup — used for display only
const WEIGHTS = {
    HDFCBANK: '13.5%', RELIANCE: '9.8%', ICICIBANK: '7.9%',
    INFY: '5.8%', ITC: '4.5%', TCS: '4.1%',
    LARSEN: '3.4%', AXISBANK: '3.2%', SBIN: '2.9%',
    KOTAKBANK: '2.8%',
};

const TickerItem = ({ stock }) => {
    const isPos = parseFloat(stock.change_pct) >= 0;
    return (
        <div className="flex items-center space-x-3 px-6 py-2 border-r border-border/50 hover:bg-white/5 transition-colors cursor-default">
            {/* Symbol + weight */}
            <div className="flex flex-col">
                <span className="text-sm font-semibold text-text">{stock.symbol}</span>
                <span className="text-xs text-muted">{WEIGHTS[stock.symbol] || ''}</span>
            </div>

            {/* LTP + change */}
            <div className="flex flex-col items-end min-w-[70px]">
                <span className="text-sm font-mono text-text">
                    {typeof stock.ltp === 'number' ? stock.ltp.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : stock.ltp}
                </span>
                <span className={`text-xs font-mono font-semibold ${isPos
                    ? 'text-primary drop-shadow-[0_0_4px_rgba(5,224,125,0.4)]'
                    : 'text-danger drop-shadow-[0_0_4px_rgba(255,51,75,0.4)]'
                    }`}>
                    {isPos ? '▲' : '▼'} {Math.abs(stock.change_pct).toFixed(2)}%
                </span>
            </div>

            {/* Impact pill */}
            <div className={`px-2 py-0.5 rounded text-xs font-mono ${isPos
                ? 'bg-primary/10 border border-primary/20 text-primary'
                : 'bg-danger/10 border border-danger/20 text-danger'
                }`}>
                {stock.nifty_impact >= 0 ? '+' : ''}{(stock.nifty_impact || 0).toFixed(1)} pts
            </div>
        </div>
    );
};

const NiftyTicker = ({ heavyweights = [] }) => {
    const stocks = heavyweights.length > 0 ? heavyweights : [];

    if (stocks.length === 0) {
        return (
            <div className="w-full bg-surface border-b border-border h-14 flex items-center px-6 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="h-6 w-28 bg-white/5 rounded animate-pulse" />
                ))}
            </div>
        );
    }

    return (
        <div className="w-full bg-surface border-b border-border overflow-hidden h-14 flex items-center relative z-20">
            {/* Edge fade */}
            <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-surface to-transparent z-10 pointer-events-none" />
            <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-surface to-transparent z-10 pointer-events-none" />

            {/* Two copies for seamless infinite scroll */}
            <div className="flex w-full overflow-hidden">
                {[1, 2].map((id) => (
                    <div key={id} className="flex min-w-max animate-marquee items-center px-4">
                        {stocks.map((stock) => (
                            <TickerItem key={`${id}-${stock.symbol}`} stock={stock} />
                        ))}
                    </div>
                ))}
            </div>
        </div>
    );
};

export default NiftyTicker;
