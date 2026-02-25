import React from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { TrendingUp, BarChart3 } from 'lucide-react';

const BacktestChart = ({ result }) => {
    if (!result) return null;

    const isProfit = result.total_pnl >= 0;

    return (
        <div className="space-y-6">
            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard label="Total PnL" value={`₹${result.total_pnl?.toLocaleString('en-IN')}`} positive={isProfit} />
                <StatCard label="Win Rate" value={`${result.win_rate}%`} positive={result.win_rate >= 50} />
                <StatCard label="Trades" value={result.total_trades} />
                <StatCard label="Max Drawdown" value={`₹${result.max_drawdown?.toLocaleString('en-IN')}`} positive={false} />
                <StatCard label="Winners" value={result.winning_trades} positive={true} />
                <StatCard label="Losers" value={result.losing_trades} positive={false} />
                <StatCard label="Max Profit" value={`₹${result.max_profit?.toLocaleString('en-IN')}`} positive={true} />
                <StatCard label="Max Loss" value={`₹${result.max_loss?.toLocaleString('en-IN')}`} positive={false} />
            </div>

            {/* Equity Curve */}
            {result.equity_curve && result.equity_curve.length > 0 && (
                <div className="glass-card p-4">
                    <h4 className="text-sm font-semibold text-muted mb-4 flex items-center gap-2">
                        <TrendingUp size={16} className="text-primary" />
                        EQUITY CURVE
                    </h4>
                    <ResponsiveContainer width="100%" height={250}>
                        <AreaChart data={result.equity_curve}>
                            <defs>
                                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#00d4ff" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#00d4ff" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="index" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                            <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                            <Tooltip
                                contentStyle={{ background: '#111827', border: '1px solid #1e293b', borderRadius: '8px' }}
                                labelStyle={{ color: '#94a3b8' }}
                            />
                            <Area type="monotone" dataKey="equity" stroke="#00d4ff" fill="url(#equityGrad)" strokeWidth={2} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            )}
        </div>
    );
};

const StatCard = ({ label, value, positive }) => (
    <div className="bg-surface/30 rounded-lg p-3">
        <span className="text-xs text-muted block mb-1">{label}</span>
        <span className={`text-lg font-bold ${positive === undefined ? 'text-text' : positive ? 'text-green-400' : 'text-red-400'
            }`}>
            {value}
        </span>
    </div>
);

export default BacktestChart;
