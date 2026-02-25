import React, { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { marketApi } from '../services/api';
import { BarChart3, ChevronUp, ChevronDown } from 'lucide-react';

const intervals = ['3minute', '5minute', '15minute', '30minute'];

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <div className="glass-panel p-3 border border-primary/20 shadow-2xl">
                <p className="text-muted text-xs mb-2 font-mono">{label}</p>
                <div className="space-y-1">
                    <p className="text-white font-mono text-sm"><span className="text-muted mr-2">Close:</span> ₹{payload[0].value.toLocaleString('en-IN')}</p>
                    {payload[1] && <p className="text-primary/80 font-mono text-xs"><span className="text-muted mr-2">High:</span>  ₹{payload[1].value.toLocaleString('en-IN')}</p>}
                    {payload[2] && <p className="text-danger/80 font-mono text-xs"><span className="text-muted mr-2">Low:</span>   ₹{payload[2].value.toLocaleString('en-IN')}</p>}
                </div>
            </div>
        );
    }
    return null;
};

const PriceChart = () => {
    const [data, setData] = useState([]);
    const [interval, setInterval_] = useState('5minute');
    const [loading, setLoading] = useState(true);
    const [isMinimized, setIsMinimized] = useState(false);

    useEffect(() => {
        fetchOHLC();
    }, [interval]);

    const fetchOHLC = async () => {
        setLoading(true);
        try {
            const { data: res } = await marketApi.getOHLC('NIFTY 50', interval, 5);
            if (res.candles) {
                const formatted = res.candles.map((c) => ({
                    time: new Date(c.date).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                    volume: c.volume,
                })).slice(-60);
                setData(formatted);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-2 relative w-full h-full">
            <div className="flex items-center justify-between mb-4 px-4 pt-2">
                <div className="flex items-center gap-4">
                    <h3 className="text-sm font-bold text-white tracking-wider flex items-center gap-2">
                        <BarChart3 size={18} className="text-primary" />
                        NIFTY 50 INTRADAY
                    </h3>
                    <button
                        onClick={() => setIsMinimized(!isMinimized)}
                        className="text-muted hover:text-white transition-colors p-1 rounded-md hover:bg-white/5"
                        title={isMinimized ? "Show Chart" : "Hide Chart"}
                    >
                        {isMinimized ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
                    </button>
                </div>

                {!isMinimized && (
                    <div className="flex gap-1.5 bg-surface border border-border p-1 rounded-xl shadow-inner">
                        {intervals.map((iv) => (
                            <button
                                key={iv}
                                onClick={() => setInterval_(iv)}
                                className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all ${interval === iv
                                    ? 'bg-primary/20 text-primary shadow-[0_0_10px_rgba(5,224,125,0.2)]'
                                    : 'text-muted hover:text-white hover:bg-white/5'
                                    }`}
                            >
                                {iv.replace('minute', 'm')}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {/* Render nothing below header if minimized */}
            {!isMinimized && (
                <>
                    {loading ? (
                        <div className="h-72 flex items-center justify-center text-muted animate-pulse">
                            <div className="w-8 h-8 rounded-full border-t-2 border-r-2 border-primary animate-spin"></div>
                        </div>
                    ) : data.length === 0 ? (
                        <div className="h-72 flex items-center justify-center text-muted font-mono">
                            Awaiting Market Data
                        </div>
                    ) : (
                        <div className="h-[340px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="colorClose" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#05E07D" stopOpacity={0.4} />
                                            <stop offset="95%" stopColor="#05E07D" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                                    <XAxis
                                        dataKey="time"
                                        tick={{ fill: '#8B95A5', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                                        tickLine={false}
                                        axisLine={false}
                                        minTickGap={30}
                                    />
                                    <YAxis
                                        type="number"
                                        domain={['dataMin - 10', 'dataMax + 10']}
                                        tick={{ fill: '#8B95A5', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                                        tickLine={false}
                                        axisLine={false}
                                        orientation="right"
                                    />
                                    <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.2)', strokeWidth: 1, strokeDasharray: '4 4' }} />

                                    {/* High/Low bounds (subtle) */}
                                    <Area type="monotone" dataKey="high" stroke="#05E07D" strokeWidth={1} strokeDasharray="2 2" fill="none" opacity={0.3} />
                                    <Area type="monotone" dataKey="low" stroke="#FF334B" strokeWidth={1} strokeDasharray="2 2" fill="none" opacity={0.3} />

                                    {/* Main Price Line with Gradient Fill */}
                                    <Area
                                        type="monotone"
                                        dataKey="close"
                                        stroke="#05E07D"
                                        strokeWidth={3}
                                        fillOpacity={1}
                                        fill="url(#colorClose)"
                                        activeDot={{ r: 6, fill: '#05E07D', stroke: '#131826', strokeWidth: 2 }}
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </>
            )}

            {isMinimized && (
                <div className="px-4 pb-4 text-xs font-mono text-muted/50 italic">
                    Chart is minimized.
                </div>
            )}
        </div>
    );
};

export default PriceChart;
