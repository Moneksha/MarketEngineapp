import React from 'react';
import { Play, Pause, BarChart3, Zap, Target, Clock, TrendingUp } from 'lucide-react';

const strategyIcons = {
    'ema_9_21': Zap,
    'ema_20': Target,
    'vwap_reversal': BarChart3,
    'breakout': TrendingUp,
    'option_selling': Clock,
};

const StrategySelector = ({ strategies, activeId, onSelect, onToggle, pnlMap }) => {
    if (!strategies || strategies.length === 0) {
        return (
            <div className="glass-panel p-12 text-center text-muted border-border border-dashed">
                <BarChart3 size={48} className="mx-auto mb-4 opacity-30" />
                <p>Loading strategies or none available…</p>
            </div>
        );
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {strategies.map((s) => {
                const isActive = activeId === s.id;
                const pnl = pnlMap?.[s.id];
                const Icon = strategyIcons[s.id] || BarChart3;
                const totalPnl = pnl?.total_equity || 0;
                const isPnlPositive = totalPnl >= 0;

                return (
                    <div
                        key={s.id}
                        onClick={() => onSelect(s.id)}
                        className={`glass-panel p-6 cursor-pointer transition-all duration-300 group
              ${isActive ? 'border-primary shadow-[0_0_30px_rgba(5,224,125,0.15)] scale-[1.02]' : 'hover:border-primary/30'}
              ${s.is_running ? 'strategy-live' : ''}`}
                    >
                        <div className="flex justify-between items-start mb-4">
                            <div className="flex items-center gap-4">
                                <div className={`p-3 rounded-xl transition-colors ${s.is_running
                                    ? 'bg-primary/20 text-primary shadow-[0_0_15px_rgba(5,224,125,0.4)]'
                                    : 'bg-surface border border-border text-muted group-hover:text-white'
                                    }`}>
                                    <Icon size={24} />
                                </div>
                                <div>
                                    <h4 className="font-bold text-base text-white">{s.name}</h4>
                                    <span className="text-xs text-muted mt-0.5 block font-mono bg-white/5 px-2 py-0.5 rounded w-fit border border-border">{s.timeframe}</span>
                                </div>
                            </div>

                            <button
                                onClick={(e) => { e.stopPropagation(); onToggle(s.id); }}
                                className={`p-2.5 rounded-xl transition-all shadow-md active:scale-95 ${s.is_running
                                    ? 'bg-danger/20 hover:bg-danger/40 text-danger border border-danger/30 hover:shadow-[0_0_15px_rgba(255,51,75,0.4)]'
                                    : 'bg-primary/20 hover:bg-primary/40 text-primary border border-primary/30 hover:shadow-[0_0_15px_rgba(5,224,125,0.4)]'
                                    }`}
                            >
                                {s.is_running ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
                            </button>
                        </div>

                        <p className="text-sm text-muted line-clamp-2 mb-5 leading-relaxed">{s.description}</p>

                        <div className="flex justify-between items-center pt-4 border-t border-border">
                            <div>
                                <span className="text-xs text-muted block mb-1 uppercase tracking-wider">Live PnL</span>
                                <div className="flex items-baseline gap-2">
                                    <span className={`text-xl font-mono font-bold tracking-tight ${isPnlPositive
                                        ? 'text-primary drop-shadow-[0_0_8px_rgba(5,224,125,0.5)]'
                                        : 'text-danger drop-shadow-[0_0_8px_rgba(255,51,75,0.5)]'
                                        }`}>
                                        {isPnlPositive ? '+' : ''}₹{totalPnl.toLocaleString('en-IN')}
                                    </span>
                                    <span className={`text-xs font-mono font-semibold ${isPnlPositive ? 'text-primary/80' : 'text-danger/80'}`}>
                                        ({isPnlPositive ? '+' : ''}{(pnl?.roi || 0).toFixed(2)}%)
                                    </span>
                                </div>
                            </div>
                            <div>
                                <span className="text-xs text-muted block mb-1 uppercase tracking-wider">Trades</span>
                                <span className="text-lg font-mono font-bold text-white">{pnl?.trade_count || 0}</span>
                            </div>

                            {/* Live/Paused Status indicator with pulse */}
                            <div className={`flex items-center gap-2 text-xs font-bold px-3 py-1.5 rounded-full border tracking-wide
                                ${s.is_running
                                    ? 'bg-primary/10 border-primary/30 text-primary uppercase shadow-[0_0_10px_rgba(5,224,125,0.2)]'
                                    : 'bg-surface border-border text-muted uppercase'
                                }`}
                            >
                                {s.is_running && <span className="w-2 h-2 rounded-full bg-primary animate-pulse shadow-[0_0_5px_#05E07D]"></span>}
                                {s.is_running ? 'LIVE' : 'PAUSED'}
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
};

export default StrategySelector;
