import React, { useState, useEffect } from 'react';
import { tradesApi } from '../services/api';
import { ArrowUpCircle, ArrowDownCircle, Clock } from 'lucide-react';
import TradeHistory from './TradeHistory';

const LiveTrades = ({ strategyId, strategy }) => {
    const [pnlData, setPnlData] = useState(null);

    useEffect(() => {
        fetchPnl();
        const interval = setInterval(fetchPnl, 5000);
        return () => clearInterval(interval);
    }, [strategyId]);

    const fetchPnl = async () => {
        try {
            const { data } = await tradesApi.getPnl(strategyId);
            setPnlData(data);
        } catch (e) {
            console.error(e);
        }
    };

    if (!pnlData) return <div className="h-32 animate-pulse bg-surface/30 rounded-lg" />;

    const activeTrade = pnlData.active_trade;

    return (
        <div className="space-y-4">
            {/* Strategy Metrics & PnL Summary */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                <PnlCard label="Realized" value={pnlData.realized_pnl} />
                <PnlCard label="Unrealized" value={pnlData.unrealized_pnl} />
                <PnlCard label="Strategy PnL" value={pnlData.total_equity} highlight />

                {strategy && (
                    <>
                        <MetricCard
                            label="Strategy ROI"
                            value={`${pnlData.total_equity > 0 ? '+' : ''}${((pnlData.total_equity / strategy.fund_required) * 100).toFixed(2)}%`}
                            colorClass={pnlData.total_equity >= 0 ? 'text-green-400' : 'text-red-400'}
                            highlight
                        />
                        <MetricCard
                            label="Fund Required"
                            value={`₹${strategy.fund_required.toLocaleString('en-IN')}`}
                        />
                        <MetricCard
                            label="Lot Size"
                            value={strategy.lot_size}
                        />
                    </>
                )}
            </div>

            {/* Active Trade */}
            {activeTrade ? (
                <div className="glass-card p-4 border-l-4 border-primary">
                    <div className="flex items-center gap-2 mb-3">
                        {activeTrade.direction === 'BUY' ? (
                            <ArrowUpCircle size={20} className="text-green-400" />
                        ) : (
                            <ArrowDownCircle size={20} className="text-red-400" />
                        )}
                        <span className="font-bold text-sm">
                            ACTIVE: {activeTrade.direction}
                            {activeTrade.symbol && activeTrade.symbol !== 'NIFTY 50' && (
                                <span className="ml-2 px-2 py-0.5 bg-black/10 rounded text-xs font-mono font-normal">
                                    {activeTrade.symbol.replace('NFO:', '')}
                                </span>
                            )}
                        </span>
                        <span className="text-xs text-muted ml-auto">
                            <Clock size={12} className="inline mr-1" />
                            {new Date(activeTrade.entry_time).toLocaleTimeString('en-IN')}
                        </span>
                    </div>
                    <div className="grid grid-cols-4 gap-3 text-sm">
                        <div>
                            <span className="text-xs text-muted block">Entry</span>
                            <span className="font-mono">{activeTrade.entry_price}</span>
                        </div>
                        <div>
                            <span className="text-xs text-muted block">Current</span>
                            <span className="font-mono">{activeTrade.current_price}</span>
                        </div>
                        <div>
                            <span className="text-xs text-muted block">SL</span>
                            <span className="font-mono text-red-400">{activeTrade.sl_price || '—'}</span>
                        </div>
                        <div>
                            <span className="text-xs text-muted block">Target</span>
                            <span className="font-mono text-green-400">{activeTrade.target_price || '—'}</span>
                        </div>
                    </div>
                    <div className={`mt-3 text-lg font-bold ${activeTrade.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {activeTrade.unrealized_pnl >= 0 ? '+' : ''}₹{activeTrade.unrealized_pnl}
                    </div>
                </div>
            ) : (
                <div className="glass-card p-6 text-center text-muted text-sm">
                    No active trade — waiting for signal…
                </div>
            )}

            {/* Equity Curve */}
            {pnlData.equity_curve && pnlData.equity_curve.length > 0 && (
                <div className="text-xs text-muted text-center pt-2 pb-4 border-b border-black/5">
                    {pnlData.equity_curve.length} equity snapshots recorded
                </div>
            )}

            {/* Trade History */}
            <div>
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                    <Clock size={14} className="text-secondary" />
                    Recent Activity
                </h3>
                <TradeHistory strategyId={strategyId} />
            </div>
        </div>
    );
};

const PnlCard = ({ label, value, highlight }) => (
    <div className={`p-3 rounded-lg ${highlight ? 'bg-primary/5 border border-primary/20' : 'bg-surface/30'}`}>
        <span className="text-xs text-muted block mb-1">{label}</span>
        <span className={`text-lg font-bold ${value >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {value >= 0 ? '+' : ''}₹{value?.toLocaleString('en-IN')}
        </span>
    </div>
);

const MetricCard = ({ label, value, colorClass = "text-black", highlight }) => (
    <div className={`p-3 rounded-lg ${highlight ? 'bg-primary/5 border border-primary/20' : 'bg-surface/30'}`}>
        <span className="text-xs text-muted block mb-1">{label}</span>
        <span className={`text-lg font-bold ${colorClass}`}>
            {value}
        </span>
    </div>
);

export default LiveTrades;
