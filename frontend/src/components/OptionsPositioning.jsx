import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts';

const OptionsPositioning = ({ data }) => {
    if (!data || !data.pcr) {
        return (
            <div className="glass-card p-6 h-full flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-primary mx-auto mb-2"></div>
                    <div className="text-xs text-muted">Loading Options Chain...</div>
                </div>
            </div>
        );
    }

    const { pcr, total_ce_oi, total_pe_oi, atm_strike, strikes } = data;

    // PCR Sentiment Color
    let pcrColor = "text-yellow-400";
    let sentiment = "NEUTRAL";
    if (pcr >= 1) { pcrColor = "text-green-400"; sentiment = "BULLISH"; }
    else if (pcr <= 0.7) { pcrColor = "text-red-400"; sentiment = "BEARISH"; }

    // Chart Data Preparation
    const chartData = [
        { name: 'Call OI (Res)', value: total_ce_oi, color: '#f87171' }, // Red for Resistance
        { name: 'Put OI (Sup)', value: total_pe_oi, color: '#4ade80' },  // Green for Support
    ];

    return (
        <div className="glass-card p-6 h-full flex flex-col relative overflow-hidden">
            {/* Background Glow */}
            <div className={`absolute -right-10 -top-10 w-32 h-32 rounded-full blur-[80px] opacity-20 ${pcr >= 1 ? 'bg-green-500' : 'bg-red-500'}`} />

            <div className="flex justify-between items-start mb-6 z-10">
                <div>
                    <h2 className="text-muted font-medium text-xs tracking-wider uppercase">NIFTY Options Positioning</h2>
                    <div className="flex items-baseline gap-2 mt-1">
                        <span className={`text-2xl font-bold ${pcrColor}`}>{pcr} PCR</span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-black/5 border border-black/10 text-muted">
                            {sentiment}
                        </span>
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-xs text-muted">ATM Strike</div>
                    <div className="text-lg font-mono font-bold text-black">{atm_strike}</div>
                </div>
            </div>

            {/* Total OI Comparison */}
            <div className="h-32 w-full mb-4">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart layout="vertical" data={chartData} margin={{ top: 0, right: 30, left: 40, bottom: 0 }}>
                        <XAxis type="number" hide />
                        <YAxis dataKey="name" type="category" width={80} tick={{ fill: '#9ca3af', fontSize: 10 }} axisLine={false} tickLine={false} />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#1e1e1e', borderColor: '#333', borderRadius: '8px' }}
                            itemStyle={{ color: '#fff' }}
                            formatter={(value) => value.toLocaleString()}
                        />
                        <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                            {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>

            {/* Strike-wise Breakdown */}
            <div className="flex-1 overflow-y-auto pr-2">
                <table className="w-full text-xs">
                    <thead>
                        <tr className="text-muted border-b border-black/5">
                            <th className="text-left py-2 font-normal">Strike</th>
                            <th className="text-right py-2 font-normal text-red-400">Call OI</th>
                            <th className="text-right py-2 font-normal text-green-400">Put OI</th>
                        </tr>
                    </thead>
                    <tbody>
                        {strikes && strikes.map((s) => (
                            <tr key={s.strike} className={`border-b border-black/5 ${s.strike === atm_strike ? 'bg-black/5' : ''}`}>
                                <td className="py-2 font-mono text-black">
                                    {s.strike}
                                    {s.strike === atm_strike && <span className="ml-2 text-[10px] text-blue-400">(ATM)</span>}
                                </td>
                                <td className="py-2 text-right font-mono text-gray-300">{s.ce_oi.toLocaleString()}</td>
                                <td className="py-2 text-right font-mono text-gray-300">{s.pe_oi.toLocaleString()}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="mt-2 text-[10px] text-center text-muted opacity-60">
                Tracking ATM ± 50 Strikes • Nearest Weekly Expiry
            </div>
        </div>
    );
};

export default OptionsPositioning;
