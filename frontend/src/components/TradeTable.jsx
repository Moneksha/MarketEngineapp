import React from 'react';
import { ArrowUp, ArrowDown } from 'lucide-react';

const statusStyles = {
    ACTIVE: 'bg-blue-500/10 text-blue-400',
    CLOSED: 'bg-gray-500/10 text-gray-400',
    SL_HIT: 'bg-red-500/10 text-red-400',
    TARGET_HIT: 'bg-green-500/10 text-green-400',
    EOD: 'bg-yellow-500/10 text-yellow-400',
};

const TradeTable = ({ trades }) => {
    if (!trades || trades.length === 0) {
        return (
            <div className="glass-card p-8 text-center text-muted">
                <p>No trades recorded yet</p>
            </div>
        );
    }

    return (
        <div className="glass-card overflow-hidden">
            <div className="overflow-x-auto">
                <table className="w-full">
                    <thead>
                        <tr className="border-b border-black/5">
                            {['Strategy', 'Instrument', 'Dir', 'Entry', 'Exit', 'PnL', 'Status', 'Time'].map((h) => (
                                <th key={h} className="text-xs text-muted font-medium text-left px-4 py-3">{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {trades.map((t) => (
                            <tr key={t.id} className="border-b border-black/5 hover:bg-white/[0.02] transition-colors">
                                <td className="px-4 py-3 text-sm font-medium">{t.strategy_id}</td>
                                <td className="px-4 py-3 text-xs font-mono text-muted">{t.symbol ? t.symbol.replace('NFO:', '') : '—'}</td>
                                <td className="px-4 py-3">
                                    <span className={`flex items-center gap-1 text-sm font-bold ${(t.market_bias === 'LONG' || t.market_bias === 'BULLISH' || (!t.market_bias && t.direction === 'BUY'))
                                        ? 'text-green-400'
                                        : 'text-red-400'
                                        }`}>
                                        {(t.market_bias === 'LONG' || t.market_bias === 'BULLISH' || (!t.market_bias && t.direction === 'BUY'))
                                            ? <ArrowUp size={14} />
                                            : <ArrowDown size={14} />
                                        }
                                        {t.market_bias || t.direction}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-sm font-mono">{t.entry_price}</td>
                                <td className="px-4 py-3 text-sm font-mono">{t.exit_price || '—'}</td>
                                <td className={`px-4 py-3 text-sm font-bold ${(t.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {t.pnl != null ? `₹${t.pnl}` : '—'}
                                </td>
                                <td className="px-4 py-3">
                                    <span className={`text-xs px-2 py-1 rounded-full ${statusStyles[t.status] || statusStyles.CLOSED}`}>
                                        {t.status}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-xs text-muted">
                                    {t.entry_time ? new Date(t.entry_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—'}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default TradeTable;
