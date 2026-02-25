import React, { useState, useEffect } from 'react';
import { tradesApi } from '../services/api';
import { ArrowUpCircle, ArrowDownCircle, CheckCircle, XCircle, Clock } from 'lucide-react';

const TradeHistory = ({ strategyId }) => {
    const [trades, setTrades] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchTrades();
        const interval = setInterval(fetchTrades, 5000); // Auto-refresh trade history
        return () => clearInterval(interval);
    }, [strategyId]);

    const fetchTrades = async () => {
        try {
            const { data } = await tradesApi.getTrades(50, strategyId);
            setTrades(data.trades || []);
        } catch (e) {
            console.error("Failed to fetch trades", e);
        } finally {
            setLoading(false);
        }
    };

    if (loading) return <div className="h-40 animate-pulse bg-surface/30 rounded-lg" />;

    if (trades.length === 0) {
        return (
            <div className="text-center py-8 text-muted text-sm">
                No closed trades yet.
            </div>
        );
    }

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
                <thead>
                    <tr className="text-xs text-muted border-b border-black/5">
                        <th className="py-3 px-2">Type</th>
                        <th className="py-3 px-2">Time</th>
                        <th className="py-3 px-2">Entry</th>
                        <th className="py-3 px-2">Exit</th>
                        <th className="py-3 px-2 text-right">PnL</th>
                        <th className="py-3 px-2 text-right">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {trades.map((trade) => (
                        <tr key={trade.id} className="border-b border-black/5 hover:bg-black/5 transition-colors text-sm">
                            <td className="py-3 px-2">
                                <div className={`flex items-center gap-1.5 font-medium ${trade.direction === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                                    {trade.direction === 'BUY' ? <ArrowUpCircle size={14} /> : <ArrowDownCircle size={14} />}
                                    {trade.direction}
                                </div>
                                {trade.symbol && trade.symbol !== 'NIFTY 50' && (
                                    <div className="text-[10px] text-muted mt-1 max-w-[140px] truncate" title={trade.symbol}>
                                        {trade.symbol.replace('NFO:', '')}
                                    </div>
                                )}
                            </td>
                            <td className="py-3 px-2 text-muted text-xs">
                                {new Date(trade.entry_time).toLocaleString('en-IN', {
                                    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                                })}
                            </td>
                            <td className="py-3 px-2 font-mono">{trade.entry_price}</td>
                            <td className="py-3 px-2 font-mono">{trade.exit_price || '-'}</td>
                            <td className={`py-3 px-2 text-right font-medium ${trade.pnl > 0 ? 'text-green-400' : trade.pnl < 0 ? 'text-red-400' : 'text-muted'
                                }`}>
                                {trade.pnl ? `₹${trade.pnl}` : '-'}
                            </td>
                            <td className="py-3 px-2 text-right text-xs">
                                <StatusBadge status={trade.status} />
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

const StatusBadge = ({ status }) => {
    let color = "text-muted bg-black/5";
    if (status === "TARGET_HIT") color = "text-green-400 bg-green-400/10";
    if (status === "SL_HIT") color = "text-red-400 bg-red-400/10";
    if (status === "EOD") color = "text-yellow-400 bg-yellow-400/10";
    if (status === "ACTIVE") color = "text-blue-400 bg-blue-400/10 animate-pulse";

    return (
        <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide ${color}`}>
            {status.replace('_', ' ')}
        </span>
    );
};

export default TradeHistory;
