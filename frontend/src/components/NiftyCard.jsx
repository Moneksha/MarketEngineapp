import React from 'react';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';

const NiftyCard = ({ data }) => {
    if (!data) return <div className="glass-panel h-36 flex items-center justify-center text-muted animate-pulse">Loading NIFTY Data...</div>;

    const isPositive = data.change >= 0;
    const vix = data.vix || {};
    const vixLtp = vix.ltp || 0;
    // VIX logic: normal coloring (red for down, green for up), with correct negative sign
    const vixChangePct = vix.change_pct || 0;
    const vixRising = vixChangePct >= 0;
    const vixLevel = vixLtp > 18 ? 'HIGH' : vixLtp > 13 ? 'MOD' : vixLtp > 0 ? 'LOW' : '--';
    const vixLevelColor = vixLtp > 18 ? 'text-danger' : vixLtp > 13 ? 'text-warning' : 'text-primary';

    return (
        <div className="relative overflow-hidden group">
            {/* Background Ambient Glow */}
            <div className={`absolute -right-20 -top-20 w-64 h-64 rounded-full blur-[100px] transition-colors duration-1000 ${isPositive ? 'bg-primary/20' : 'bg-danger/20'}`} />

            <div className="flex justify-between items-start mb-6">
                <div>
                    <h2 className="text-muted font-medium text-sm tracking-widest uppercase flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                        Index Overview
                    </h2>
                    <h3 className="text-3xl font-bold mt-2 tracking-tight text-white">{data.symbol}</h3>
                </div>
                <div className={`p-3 rounded-xl border backdrop-blur-md shadow-lg ${isPositive
                    ? 'bg-primary/10 border-primary/20 text-primary shadow-[0_4px_20px_rgba(5,224,125,0.15)]'
                    : 'bg-danger/10 border-danger/20 text-danger shadow-[0_4px_20px_rgba(255,51,75,0.15)]'
                    }`}>
                    {isPositive ? <TrendingUp size={28} /> : <TrendingDown size={28} />}
                </div>
            </div>

            {/* NIFTY Price + Change + VIX inline */}
            <div className="flex items-center gap-4 flex-wrap">
                <span className="text-5xl font-mono font-bold tracking-tight text-white drop-shadow-md">
                    {data.ltp.toLocaleString('en-IN')}
                </span>
                <div className={`flex items-center gap-2 px-3 py-1 rounded-md bg-white/5 border ${isPositive ? 'border-primary/20' : 'border-danger/20'}`}>
                    <span className={`text-xl font-mono font-bold ${isPositive ? 'text-primary drop-shadow-[0_0_8px_rgba(5,224,125,0.5)]' : 'text-danger drop-shadow-[0_0_8px_rgba(255,51,75,0.5)]'}`}>
                        {isPositive ? '▲' : '▼'} {Math.abs(data.change)}
                    </span>
                    <span className="text-muted font-mono font-medium">
                        ({data.change_pct}%)
                    </span>
                </div>
                {/* India VIX — right beside the change pill */}
                {vixLtp > 0 && (
                    <>
                        <span className="w-px h-8 bg-white/10" />
                        <div className="flex items-center gap-2">
                            <Activity size={13} className={vixLevelColor} />
                            <span className="text-muted text-xs tracking-widest uppercase font-medium">VIX</span>
                            <span className="font-mono font-bold text-white text-xl">{vixLtp.toFixed(4)}</span>
                            <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded-md ${vixRising ? 'bg-primary/10 text-primary' : 'bg-danger/10 text-danger'}`}>
                                {vixRising ? '▲' : '▼'} {(vixRising ? '+' : '')}{vixChangePct.toFixed(2)}%
                            </span>
                            <span className={`text-xs font-bold tracking-wider px-2 py-0.5 rounded border ${vixLtp > 18 ? 'border-danger/30 text-danger bg-danger/10' :
                                vixLtp > 13 ? 'border-warning/30 text-warning bg-warning/10' :
                                    'border-primary/30 text-primary bg-primary/10'
                                }`}>{vixLevel}</span>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default NiftyCard;

