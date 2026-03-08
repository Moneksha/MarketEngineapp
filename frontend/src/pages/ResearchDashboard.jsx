import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
    LineChart, Line, AreaChart, Area, XAxis, YAxis, BarChart, Bar, Cell,
    CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine
} from 'recharts';
import { ArrowLeft, TrendingUp, TrendingDown, Activity, BarChart2, Target, Zap, RefreshCw, Calendar, Layers, Search, ChevronDown, Clock } from 'lucide-react';
import api from '../services/api';
import { enforceTimeframeLimit, getMaxYears } from '../utils/timeframeLimits';

// ── Colour constants matching Market Engine theme ─────────────────────────
const C = {
    primary: '#05E07D',
    danger: '#FF334B',
    warning: '#FFB020',
    muted: '#8B95A5',
    surface: '#131826',
    border: 'rgba(255,255,255,0.1)',
};

// ── Formatters ────────────────────────────────────────────────────────────────
const fmtDate = (iso, includeTime = false) => {
    if (!iso) return '';
    // iso may be "YYYY-MM-DD HH:MM" (IST string) or a full ISO timestamp
    const parts = iso.split(/[T\s]/);
    const datePart = parts[0]; // "YYYY-MM-DD"
    const timePart = parts[1] ? parts[1].slice(0, 5) : null; // "HH:MM"
    const [year, month, day] = datePart.split('-').map(Number);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const dateStr = `${String(day).padStart(2, '0')} ${months[month - 1]} ${String(year).slice(-2)}`;
    if (includeTime && timePart) return `${dateStr} ${timePart}`;
    return dateStr;
};

const fmtNum = (v, dp = 2) => (v == null || isNaN(v) ? '—' : Number(v).toFixed(dp));

const fmtPct = (v) => {
    if (v == null || isNaN(v)) return '—';
    const n = Number(v);
    return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
};

// ── Sub-components ────────────────────────────────────────────────────────────

const MetricCard = ({ icon: Icon, label, value, suffix = '', color = 'text-text', sub }) => (
    <div className="glass-panel p-4 flex flex-col gap-1 hover:border-primary/30 transition-all">
        <div className="flex items-center gap-2 text-muted text-xs font-semibold uppercase tracking-wider mb-1">
            <Icon size={13} />
            {label}
        </div>
        <div className={`text-2xl font-bold font-mono ${color}`}>
            {value}{suffix && <span className="text-sm ml-1 text-muted">{suffix}</span>}
        </div>
        {sub && <div className="text-xs text-muted mt-0.5">{sub}</div>}
    </div>
);

const TradeTag = ({ win }) => (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-bold ${win ? 'bg-primary/10 text-primary' : 'bg-danger/10 text-danger'}`}>
        {win ? 'WIN' : 'LOSS'}
    </span>
);

// ── Custom Tooltip ────────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || !payload.length) return null;
    return (
        <div className="glass-panel p-3 text-xs min-w-[140px]">
            <p className="text-muted mb-1">{fmtDate(label)}</p>
            {payload.map((p, i) => (
                <p key={i} style={{ color: p.color }} className="font-mono">
                    {p.name}: {fmtNum(p.value, 4)}
                </p>
            ))}
        </div>
    );
};

// ── Symbol Search Dropdown ───────────────────────────────────────────────────
function SymbolSearchDropdown({ options, value, onChange }) {
    const [isOpen, setIsOpen] = useState(false);
    const [search, setSearch] = useState('');
    const [highlightedIndex, setHighlightedIndex] = useState(0);
    const wrapperRef = useRef(null);
    const inputRef = useRef(null);

    const filteredOptions = options.filter(opt =>
        opt.toLowerCase().includes(search.toLowerCase())
    );

    useEffect(() => {
        function handleClickOutside(event) {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        }
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleOpen = () => {
        setIsOpen(true);
        setSearch('');
        setHighlightedIndex(0);
        setTimeout(() => inputRef.current?.focus(), 0);
    };

    const handleKeyDown = (e) => {
        if (!isOpen) {
            if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
                e.preventDefault();
                handleOpen();
            }
            return;
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setHighlightedIndex(prev => (prev < filteredOptions.length - 1 ? prev + 1 : prev));
                break;
            case 'ArrowUp':
                e.preventDefault();
                setHighlightedIndex(prev => (prev > 0 ? prev - 1 : prev));
                break;
            case 'Enter':
                e.preventDefault();
                if (filteredOptions[highlightedIndex]) {
                    onChange(filteredOptions[highlightedIndex]);
                    setIsOpen(false);
                }
                break;
            case 'Escape':
                e.preventDefault();
                setIsOpen(false);
                break;
            default:
                break;
        }
    };

    return (
        <div ref={wrapperRef} className="relative min-w-[140px]">
            <button
                type="button"
                onClick={() => isOpen ? setIsOpen(false) : handleOpen()}
                onKeyDown={handleKeyDown}
                className="w-full flex items-center justify-between gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5 text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-primary/50"
            >
                <div className="flex items-center gap-1.5 overflow-hidden">
                    <Layers size={13} className="text-muted shrink-0" />
                    <span className="truncate">{value}</span>
                </div>
                <ChevronDown size={13} className="text-muted shrink-0" />
            </button>

            {isOpen && (
                <div className="absolute top-full left-0 mt-1 w-full min-w-[200px] bg-surface border border-border rounded-lg shadow-xl shadow-black/50 overflow-hidden z-50">
                    <div className="p-2 border-b border-border flex items-center gap-2">
                        <Search size={13} className="text-muted shrink-0" />
                        <input
                            ref={inputRef}
                            type="text"
                            value={search}
                            onChange={(e) => {
                                setSearch(e.target.value);
                                setHighlightedIndex(0);
                            }}
                            onKeyDown={handleKeyDown}
                            placeholder="Search symbol..."
                            className="bg-transparent text-text text-xs focus:outline-none w-full"
                        />
                    </div>
                    <div className="max-h-60 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
                        {filteredOptions.length > 0 ? (
                            filteredOptions.map((opt, idx) => (
                                <button
                                    key={opt}
                                    onClick={() => {
                                        onChange(opt);
                                        setIsOpen(false);
                                    }}
                                    className={`w-full text-left px-3 py-2 text-xs transition-colors ${idx === highlightedIndex ? 'bg-primary/20 text-primary' : 'text-text hover:bg-white/5'}`}
                                >
                                    {opt}
                                </button>
                            ))
                        ) : (
                            <div className="px-3 py-4 text-center text-xs text-muted">
                                No instruments found
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

// ── Timeframe Dropdown ────────────────────────────────────────────────────────
function TimeframeDropdown({ value, onChange }) {
    const [isOpen, setIsOpen] = useState(false);
    const [inputValue, setInputValue] = useState(value);
    const wrapperRef = useRef(null);
    const inputRef = useRef(null);

    const presets = [
        { label: 'Minutes', options: ['1m', '2m', '3m', '5m', '10m', '15m', '20m', '30m', '45m'] },
        { label: 'Hours', options: ['1h', '2h', '3h', '4h'] },
        { label: 'Days/Weeks', options: ['1D', '1W', '1M'] }
    ];

    useEffect(() => {
        function handleClickOutside(event) {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
                setIsOpen(false);
                // Reset input to current value if closed without submitting a valid custom one
                setInputValue(value);
            }
        }
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [value]);

    useEffect(() => {
        setInputValue(value);
    }, [value]);

    const handleOpen = () => {
        setIsOpen(true);
        setTimeout(() => inputRef.current?.focus(), 0);
    };

    const submitValue = (val) => {
        const trimmed = val.trim();
        // Regex validation: numbers followed by m, h, D, W, or M
        if (/^\d+[mhDWM]$/.test(trimmed)) {
            onChange(trimmed);
            setIsOpen(false);
        } else {
            // Revert on invalid
            setInputValue(value);
            setIsOpen(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            submitValue(inputValue);
        } else if (e.key === 'Escape') {
            e.preventDefault();
            setInputValue(value);
            setIsOpen(false);
        }
    };

    return (
        <div ref={wrapperRef} className="relative min-w-[90px]">
            <button
                type="button"
                onClick={() => isOpen ? setIsOpen(false) : handleOpen()}
                className="w-full flex items-center justify-between gap-1.5 bg-background/60 border border-border rounded-lg px-2.5 py-1.5 text-xs font-bold focus:outline-none focus:ring-1 focus:ring-primary/50 transition-colors"
                style={{ color: isOpen ? C.primary : 'inherit' }}
            >
                <div className="flex items-center gap-1.5">
                    <Clock size={13} className={isOpen ? "text-primary" : "text-muted"} />
                    <span>{value}</span>
                </div>
                <ChevronDown size={13} className={isOpen ? "text-primary" : "text-muted"} />
            </button>

            {isOpen && (
                <div className="absolute top-full left-0 mt-1 w-[220px] bg-surface border border-border rounded-lg shadow-xl shadow-black/50 overflow-hidden z-50">
                    <div className="p-2 border-b border-border bg-black/20">
                        <label className="text-[10px] uppercase text-muted font-bold tracking-wider mb-1.5 block px-1">Custom Timeframe</label>
                        <div className="flex items-center gap-2">
                            <input
                                ref={inputRef}
                                type="text"
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="e.g. 7m, 2h"
                                className="bg-background/80 border border-border rounded px-2 py-1.5 w-full text-text text-xs font-mono focus:outline-none focus:border-primary/50"
                            />
                            <button
                                onClick={() => submitValue(inputValue)}
                                className="bg-primary/20 text-primary hover:bg-primary hover:text-background transition-colors rounded px-2.5 py-1.5 text-xs font-bold"
                            >
                                OK
                            </button>
                        </div>
                    </div>
                    <div className="max-h-[300px] overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
                        {presets.map(group => (
                            <div key={group.label} className="py-1">
                                <div className="px-3 py-1.5 text-[10px] font-bold text-muted uppercase tracking-wider bg-white/5">
                                    {group.label}
                                </div>
                                <div className="grid grid-cols-3 gap-1 px-2 py-1.5">
                                    {group.options.map(opt => (
                                        <button
                                            key={opt}
                                            onClick={() => {
                                                setInputValue(opt);
                                                onChange(opt);
                                                setIsOpen(false);
                                            }}
                                            className={`py-1.5 rounded text-xs font-bold transition-all ${value === opt ? 'bg-primary text-background' : 'text-text hover:bg-white/10'}`}
                                        >
                                            {opt}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function ResearchDashboard({ onBack }) {
    const [params, setParams] = useState({
        symbol: 'NIFTY50',
        strategy_id: 'ema_trend', // 'ema_trend' | 'ema_crossover' | 'supertrend' | 'rsi' | 'macd'
        ema: 20,
        fast_ema: 20,
        slow_ema: 50,
        atr_period: 10,
        factor: 3,
        rsi_length: 14,
        oversold: 30,
        overbought: 70,
        macd_fast: 12,
        macd_slow: 26,
        macd_signal: 9,
        bb_length: 20,
        bb_mult: 2,
        from: '2016-03-01',
        to: '2025-01-01',
        timeframe: '1h',
    });
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [rangeWarning, setRangeWarning] = useState(null);
    const [availableSymbols, setAvailableSymbols] = useState(['NIFTY50', 'RELIANCE']);

    useEffect(() => {
        api.get('/research/symbols')
            .then(res => {
                if (res.data && res.data.symbols) {
                    setAvailableSymbols(res.data.symbols.map(s => s.symbol));
                }
            })
            .catch(err => console.error("Failed to fetch symbols", err));
    }, []);

    const setDatePreset = useCallback((years) => {
        const toDate = new Date();
        const fromDate = new Date();
        fromDate.setFullYear(toDate.getFullYear() - years);
        setParams(p => ({
            ...p,
            to: toDate.toISOString().split('T')[0],
            from: fromDate.toISOString().split('T')[0]
        }));
    }, []);

    const setAllData = useCallback(() => {
        const toDate = new Date();
        const fromDate = new Date('2015-01-01');
        setParams(p => ({
            ...p,
            to: toDate.toISOString().split('T')[0],
            from: fromDate.toISOString().split('T')[0]
        }));
    }, []);

    // ── Auto-enforce timeframe range limits when timeframe or dates change ──
    useEffect(() => {
        const check = enforceTimeframeLimit(params.timeframe, params.from, params.to);
        if (!check.ok) {
            setRangeWarning(check.message);
            setParams(p => ({ ...p, from: check.adjustedFrom, to: check.adjustedTo }));
        } else {
            setRangeWarning(null);
        }
    }, [params.timeframe, params.from, params.to]);

    const runBacktest = useCallback(async () => {
        if (!params.symbol || !params.timeframe || !params.from || !params.to) {
            console.warn("Backtest parameters missing");
            setError("Backtest parameters missing");
            return;
        }

        // Validate timeframe format
        let validTimeframe = params.timeframe;
        if (!/^\d+[mhDWM]$/.test(validTimeframe)) {
            console.warn("Unsupported timeframe format:", validTimeframe);
            validTimeframe = "1h";
            setParams(p => ({ ...p, timeframe: "1h" }));
        }

        const formatDate = (dateStr) => {
            try {
                return new Date(dateStr).toISOString().split("T")[0];
            } catch (e) {
                return dateStr;
            }
        };

        let fromDate = formatDate(params.from);
        let toDate = formatDate(params.to);

        // ── Enforce timeframe range limit before calling API ──
        const rangeCheck = enforceTimeframeLimit(validTimeframe, fromDate, toDate);
        if (!rangeCheck.ok) {
            fromDate = rangeCheck.adjustedFrom;
            toDate = rangeCheck.adjustedTo;
            setRangeWarning(rangeCheck.message);
            setParams(p => ({ ...p, from: fromDate, to: toDate }));
        }

        setLoading(true);
        setError(null);

        const buildApiParams = (tf, start, end) => ({
            symbol: params.symbol,
            strategy_id: params.strategy_id,
            ema_period: parseInt(params.ema, 10) || 20,
            fast_ema: parseInt(params.fast_ema, 10) || 20,
            slow_ema: parseInt(params.slow_ema, 10) || 50,
            atr_period: parseInt(params.atr_period, 10) || 10,
            factor: parseFloat(params.factor) || 3,
            rsi_length: parseInt(params.rsi_length, 10) || 14,
            oversold: parseInt(params.oversold, 10) || 30,
            overbought: parseInt(params.overbought, 10) || 70,
            fast_length: parseInt(params.macd_fast, 10) || 12,
            slow_length: parseInt(params.macd_slow, 10) || 26,
            macd_length: parseInt(params.macd_signal, 10) || 9,
            bb_length: parseInt(params.bb_length, 10) || 20,
            bb_mult: parseFloat(params.bb_mult) || 2,
            from: start,
            to: end,
            timeframe: tf,
        });

        try {
            const { data } = await api.get('/research/run-backtest', {
                params: buildApiParams(validTimeframe, fromDate, toDate),
            });
            setResult(data);
        } catch (error) {
            console.error("Backtest failed:", error);
            console.warn("Using fallback backtest settings");
            setError("Backtest failed. Reverting to default settings.");

            try {
                // Automatic fallback to safe working settings
                const fallbackTf = "1h";
                const fallbackFrom = "2016-03-01";
                const fallbackTo = "2025-01-01";

                setParams(p => ({ ...p, timeframe: fallbackTf, from: fallbackFrom, to: fallbackTo }));

                const { data } = await api.get('/research/run-backtest', {
                    params: buildApiParams(fallbackTf, fallbackFrom, fallbackTo),
                });
                setResult(data);
            } catch (fallbackError) {
                console.error("Fallback backtest also failed:", fallbackError);
                setError("Strategy failed to run even with fallback settings.");
                setResult(null);
            }
        } finally {
            setLoading(false);
        }
    }, [params]);

    const metrics = result ? [
        {
            icon: Target,
            label: 'Win Rate',
            value: fmtNum(result.win_rate),
            suffix: '%',
            color: 'text-primary',
            sub: `${result.winners_count} of ${result.total_trades} trades`,
        },
        {
            icon: TrendingDown,
            label: 'Loss Rate',
            value: fmtNum(result.loss_rate),
            suffix: '%',
            color: 'text-danger',
            sub: `${result.losers_count} of ${result.total_trades} trades`,
        },
        {
            icon: TrendingUp,
            label: 'Avg Win (Pts)',
            value: fmtNum(result.avg_win_pts),
            color: 'text-primary',
            sub: 'per winning trade',
        },
        {
            icon: TrendingDown,
            label: 'Avg Loss (Pts)',
            value: fmtNum(result.avg_loss_pts),
            color: 'text-danger',
            sub: 'per losing trade',
        },
        {
            icon: Activity,
            label: 'Total PnL (Pts)',
            value: (result.total_return_pts >= 0 ? '+' : '') + fmtNum(result.total_return_pts),
            color: result.total_return_pts >= 0 ? 'text-primary' : 'text-warning',
            sub: 'cumulative points',
        },
        {
            icon: Zap,
            label: 'Max Drawdown',
            value: fmtNum(result.max_drawdown_pts),
            color: 'text-danger',
            sub: 'pts from peak',
        },
    ] : [];

    // Down-sample equity curve for chart performance
    const chartData = result?.equity_curve
        ? (result.equity_curve.length > 500
            ? result.equity_curve.filter((_, i) => i % Math.ceil(result.equity_curve.length / 500) === 0)
            : result.equity_curve)
        : [];

    return (
        <div className="min-h-screen bg-background text-text font-sans">

            {/* ── Header Bar ── */}
            <div className="sticky top-0 z-30 bg-surface/80 backdrop-blur border-b border-border">
                <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <button
                            onClick={onBack}
                            className="flex items-center gap-1.5 text-muted hover:text-text transition-colors text-sm"
                        >
                            <ArrowLeft size={16} /> Back
                        </button>
                        <div className="w-px h-4 bg-border" />
                        <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-primary shadow-[0_0_8px_rgba(5,224,125,0.8)]" />
                            <h1 className="text-sm font-bold text-text uppercase tracking-wider">Equity Research</h1>
                            <span className="text-muted text-xs">· Strategy Tester</span>
                        </div>
                    </div>

                    {/* ── Controls ── */}
                    <div className="flex items-center gap-2 flex-wrap">
                        {/* Symbol */}
                        <SymbolSearchDropdown
                            options={availableSymbols}
                            value={params.symbol}
                            onChange={(val) => setParams(p => ({ ...p, symbol: val }))}
                        />

                        {/* Timeframe */}
                        <TimeframeDropdown
                            value={params.timeframe}
                            onChange={(val) => setParams(p => ({ ...p, timeframe: val }))}
                        />

                        {/* Strategy + Parameters (grouped together) */}
                        <div className="flex items-center gap-2">
                            <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                <Zap size={13} className="text-primary" />
                                <select
                                    value={params.strategy_id}
                                    onChange={(e) => setParams(p => ({ ...p, strategy_id: e.target.value }))}
                                    className="bg-transparent text-text text-xs font-semibold focus:outline-none"
                                >
                                    <option value="ema_trend">EMA TREND</option>
                                    <option value="ema_crossover">EMA CROSSOVER</option>
                                    <option value="supertrend">SUPERTREND</option>
                                    <option value="rsi">RSI</option>
                                    <option value="macd">MACD</option>
                                    <option value="bollinger">BOLLINGER BAND</option>
                                </select>
                            </div>

                            {/* Strategy Parameters (Conditional — directly beside strategy) */}
                            {params.strategy_id === 'ema_trend' && (
                                <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                    <span className="text-muted text-xs">EMA</span>
                                    <input
                                        type="number"
                                        value={params.ema}
                                        onChange={(e) => {
                                            const v = e.target.value;
                                            if (v === '') setParams(p => ({ ...p, ema: '' }));
                                            else {
                                                const num = parseInt(v, 10);
                                                if (!isNaN(num)) setParams(p => ({ ...p, ema: num }));
                                            }
                                        }}
                                        className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                        placeholder="20"
                                    />
                                </div>
                            )}
                            {params.strategy_id === 'ema_crossover' && (
                                <>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <Activity size={13} className="text-primary opacity-70" />
                                        <span className="text-muted text-xs">FAST</span>
                                        <input
                                            type="number"
                                            value={params.fast_ema}
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, fast_ema: '' }));
                                                else {
                                                    const num = parseInt(v, 10);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, fast_ema: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="20"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <Activity size={13} className="text-danger opacity-70" />
                                        <span className="text-muted text-xs">SLOW</span>
                                        <input
                                            type="number"
                                            value={params.slow_ema}
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, slow_ema: '' }));
                                                else {
                                                    const num = parseInt(v, 10);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, slow_ema: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="50"
                                        />
                                    </div>
                                </>
                            )}
                            {params.strategy_id === 'supertrend' && (
                                <>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <Activity size={13} className="text-warning opacity-70" />
                                        <span className="text-muted text-xs">ATR</span>
                                        <input
                                            type="number"
                                            value={params.atr_period}
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, atr_period: '' }));
                                                else {
                                                    const num = parseInt(v, 10);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, atr_period: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="10"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <Zap size={13} className="text-warning opacity-70" />
                                        <span className="text-muted text-xs">FACTOR</span>
                                        <input
                                            type="number"
                                            value={params.factor}
                                            step="0.5"
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, factor: '' }));
                                                else {
                                                    const num = parseFloat(v);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, factor: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="3"
                                        />
                                    </div>
                                </>
                            )}
                            {params.strategy_id === 'rsi' && (
                                <>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <Activity size={13} className="text-purple-400 opacity-70" />
                                        <span className="text-muted text-xs">LEN</span>
                                        <input
                                            type="number"
                                            value={params.rsi_length}
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, rsi_length: '' }));
                                                else {
                                                    const num = parseInt(v, 10);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, rsi_length: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="14"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <span className="text-primary text-xs">OS</span>
                                        <input
                                            type="number"
                                            value={params.oversold}
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, oversold: '' }));
                                                else {
                                                    const num = parseInt(v, 10);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, oversold: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="30"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <span className="text-danger text-xs">OB</span>
                                        <input
                                            type="number"
                                            value={params.overbought}
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, overbought: '' }));
                                                else {
                                                    const num = parseInt(v, 10);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, overbought: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="70"
                                        />
                                    </div>
                                </>
                            )}
                            {params.strategy_id === 'macd' && (
                                <>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <Activity size={13} className="text-cyan-400 opacity-70" />
                                        <span className="text-muted text-xs">FAST</span>
                                        <input
                                            type="number"
                                            value={params.macd_fast}
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, macd_fast: '' }));
                                                else {
                                                    const num = parseInt(v, 10);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, macd_fast: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="12"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <Activity size={13} className="text-orange-400 opacity-70" />
                                        <span className="text-muted text-xs">SLOW</span>
                                        <input
                                            type="number"
                                            value={params.macd_slow}
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, macd_slow: '' }));
                                                else {
                                                    const num = parseInt(v, 10);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, macd_slow: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="26"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <Zap size={13} className="text-cyan-400 opacity-70" />
                                        <span className="text-muted text-xs">SIG</span>
                                        <input
                                            type="number"
                                            value={params.macd_signal}
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, macd_signal: '' }));
                                                else {
                                                    const num = parseInt(v, 10);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, macd_signal: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="9"
                                        />
                                    </div>
                                </>
                            )}
                            {params.strategy_id === 'bollinger' && (
                                <>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <Activity size={13} className="text-blue-400 opacity-70" />
                                        <span className="text-muted text-xs">LEN</span>
                                        <input
                                            type="number"
                                            value={params.bb_length}
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, bb_length: '' }));
                                                else {
                                                    const num = parseInt(v, 10);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, bb_length: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="20"
                                        />
                                    </div>
                                    <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                        <Zap size={13} className="text-blue-400 opacity-70" />
                                        <span className="text-muted text-xs">MULT</span>
                                        <input
                                            type="number"
                                            value={params.bb_mult}
                                            step="0.5"
                                            onChange={(e) => {
                                                const v = e.target.value;
                                                if (v === '') setParams(p => ({ ...p, bb_mult: '' }));
                                                else {
                                                    const num = parseFloat(v);
                                                    if (!isNaN(num)) setParams(p => ({ ...p, bb_mult: num }));
                                                }
                                            }}
                                            className="bg-transparent text-text text-xs font-mono font-semibold w-10 focus:outline-none text-center"
                                            placeholder="2"
                                        />
                                    </div>
                                </>
                            )}
                        </div>

                        {/* Date Range & Presets */}
                        <div className="flex items-center gap-2">
                            <div className="flex items-center gap-1 p-1 bg-background/60 border border-border rounded-lg">
                                <button onClick={() => setDatePreset(1)} className="px-2 py-1 text-[10px] font-bold text-muted hover:text-text rounded transition-colors hover:bg-white/5">1Y</button>
                                <button onClick={() => setDatePreset(3)} className="px-2 py-1 text-[10px] font-bold text-muted hover:text-text rounded transition-colors hover:bg-white/5">3Y</button>
                                <button onClick={() => setDatePreset(5)} className="px-2 py-1 text-[10px] font-bold text-muted hover:text-text rounded transition-colors hover:bg-white/5">5Y</button>
                                <button onClick={() => setDatePreset(10)} className="px-2 py-1 text-[10px] font-bold text-muted hover:text-text rounded transition-colors hover:bg-white/5">10Y</button>
                                <button onClick={setAllData} className="px-2 py-1 text-[10px] font-bold text-muted hover:text-text rounded transition-colors hover:bg-white/5">ALL</button>
                            </div>

                            <div className="flex items-center gap-1.5 bg-background/60 border border-border rounded-lg px-3 py-1.5">
                                <Calendar size={13} className="text-muted" />
                                <input
                                    type="date"
                                    value={params.from}
                                    onChange={(e) => setParams(p => ({ ...p, from: e.target.value }))}
                                    className="bg-transparent text-text text-xs font-mono focus:outline-none min-w-[110px]"
                                />
                                <span className="text-muted">→</span>
                                <input
                                    type="date"
                                    value={params.to}
                                    onChange={(e) => setParams(p => ({ ...p, to: e.target.value }))}
                                    className="bg-transparent text-text text-xs font-mono focus:outline-none min-w-[110px]"
                                />
                            </div>
                        </div>

                        {/* Run Button */}
                        <button
                            onClick={runBacktest}
                            disabled={loading}
                            className={`flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-bold transition-all ${loading
                                ? 'bg-primary/30 text-primary/50 cursor-not-allowed'
                                : 'bg-primary text-background hover:shadow-[0_0_20px_rgba(5,224,125,0.4)] hover:scale-[1.02]'
                                }`}
                        >
                            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                            {loading ? 'Running...' : 'Run Backtest'}
                        </button>
                    </div>
                </div>
            </div>

            {/* ── Marquee (Data Availability Notice) ── */}
            <div className="w-full bg-primary/5 border-b border-primary/20 overflow-hidden h-9 flex items-center relative z-20">
                <div className="flex w-full overflow-hidden">
                    {[1, 2].map((id) => (
                        <div key={id} className="flex min-w-max animate-marquee items-center">
                            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary flex items-center opacity-80 whitespace-nowrap">
                                <span className="px-20">⚠️ Backtest Notice: Currently only 10 years of historical data is available for analysis in this environment</span>
                                <span className="px-20">⚠️ Backtest Notice: Currently only 10 years of historical data is available for analysis in this environment</span>
                            </p>
                        </div>
                    ))}
                </div>
            </div>

            <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6 space-y-6">

                {/* ── Range Warning ── */}
                {rangeWarning && (
                    <div className="glass-panel p-4 border-warning/30 bg-warning/5 text-warning text-sm flex items-center justify-between">
                        <span>{rangeWarning}</span>
                        <button onClick={() => setRangeWarning(null)} className="text-warning/60 hover:text-warning ml-4 text-lg font-bold">×</button>
                    </div>
                )}

                {/* ── Error ── */}
                {error && (
                    <div className="glass-panel p-4 border-danger/30 bg-danger/5 text-danger text-sm">
                        ⚠️ {error}
                    </div>
                )}

                {/* ── Empty State ── */}
                {!result && !loading && !error && (
                    <div className="glass-panel p-16 text-center">
                        <BarChart2 size={48} className="mx-auto mb-4 text-muted/40" />
                        <h2 className="text-xl font-bold text-text mb-2">Ready to Backtest</h2>
                        <p className="text-muted text-sm max-w-md mx-auto">
                            Configure parameters above and click <span className="text-primary font-semibold">Run Backtest</span> to start the EMA crossover strategy analysis on RELIANCE.
                        </p>
                    </div>
                )}

                {/* ── Loading State ── */}
                {loading && (
                    <div className="glass-panel p-16 text-center">
                        <div className="flex items-center justify-center gap-3 text-primary">
                            <RefreshCw size={24} className="animate-spin" />
                            <span className="text-lg font-semibold">Running backtest...</span>
                        </div>
                        <p className="text-muted text-sm mt-3">
                            Fetching {params.symbol} data and computing{' '}
                            {params.strategy_id === 'ema_trend'
                                ? `EMA(${params.ema || 20})`
                                : params.strategy_id === 'ema_crossover'
                                    ? `EMA Crossover (Fast ${params.fast_ema || 20}, Slow ${params.slow_ema || 50})`
                                    : params.strategy_id === 'supertrend'
                                        ? `Supertrend (ATR ${params.atr_period || 10}, Factor ${params.factor || 3})`
                                        : params.strategy_id === 'rsi'
                                            ? `RSI (Length ${params.rsi_length || 14}, OS ${params.oversold || 30}, OB ${params.overbought || 70})`
                                            : params.strategy_id === 'macd'
                                                ? `MACD (Fast ${params.macd_fast || 12}, Slow ${params.macd_slow || 26}, Signal ${params.macd_signal || 9})`
                                                : params.strategy_id === 'bollinger'
                                                    ? `Bollinger Band (Length ${params.bb_length || 20}, Mult ${params.bb_mult || 2})`
                                                    : params.strategy_id.replace('_', ' ')
                            } signals
                        </p>
                    </div>
                )}

                {result && !loading && (
                    <>
                        {/* ── Strategy Info Banner ── */}
                        <div className="glass-panel p-4 flex flex-wrap items-center gap-4 border-primary/20">
                            <div>
                                <span className="text-muted text-xs">Symbol</span>
                                <p className="text-primary font-bold text-sm">{result.symbol}</p>
                            </div>
                            <div className="w-px h-8 bg-border" />
                            <div>
                                <span className="text-muted text-xs">Strategy</span>
                                <p className="text-text font-bold text-sm">{result.strategy}</p>
                            </div>
                            <div className="w-px h-8 bg-border" />
                            <div>
                                <span className="text-muted text-xs">EMA Period</span>
                                <p className="text-text font-bold text-sm">{result.ema_period}</p>
                            </div>
                            <div className="w-px h-8 bg-border" />
                            <div>
                                <span className="text-muted text-xs">Timeframe</span>
                                <p className="text-text font-bold text-sm">{result.timeframe}</p>
                            </div>
                            <div className="w-px h-8 bg-border" />
                            <div>
                                <span className="text-muted text-xs">Period</span>
                                <p className="text-text font-bold text-sm">{result.from_date} → {result.to_date}</p>
                            </div>
                            <div className="w-px h-8 bg-border" />
                            <div>
                                <span className="text-muted text-xs">Data Points</span>
                                <p className="text-text font-bold text-sm">{result.data_points?.toLocaleString()}</p>
                            </div>
                        </div>

                        {/* ── Metrics Grid ── */}
                        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
                            {metrics.map((m, i) => (
                                <MetricCard key={i} {...m} />
                            ))}
                        </div>

                        {/* ── Distribution Panels ── */}
                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

                            {/* Win/Loss Distribution Left */}
                            <div className="glass-panel p-5">
                                <div className="flex justify-between items-center mb-6">
                                    <h3 className="text-sm font-bold uppercase tracking-wider text-muted">Win / Loss Distribution</h3>
                                    <span className="bg-white/10 text-muted px-2 py-0.5 rounded text-xs font-semibold">{result.total_trades} trades</span>
                                </div>

                                {/* Progress Bar */}
                                <div className="flex h-8 rounded overflow-hidden mb-3 text-xs font-bold font-mono text-center">
                                    <div style={{ width: `${result.win_rate}%` }} className="bg-primary text-black flex items-center justify-center">
                                        {result.win_rate}%
                                    </div>
                                    <div style={{ width: `${result.loss_rate}%` }} className="bg-danger text-white flex items-center justify-center">
                                        {result.loss_rate}%
                                    </div>
                                </div>
                                <div className="flex justify-between text-xs text-muted mb-8 font-mono">
                                    <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-primary" /> Winners: {result.winners_count}</div>
                                    <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-danger" /> Losers: {result.losers_count}</div>
                                </div>

                                <div className="space-y-1">
                                    {[
                                        { label: 'Max Win (single trade)', value: `+${fmtNum(result.max_win_pts)} pts`, color: 'text-primary' },
                                        { label: 'Max Loss (single trade)', value: `${fmtNum(result.max_loss_pts)} pts`, color: 'text-danger' },
                                        { label: 'Avg Win / Avg Loss Ratio', value: `${fmtNum(result.avg_win_loss_ratio)} : 1`, color: 'text-text' },
                                        { label: 'Total Win Points', value: `+${fmtNum(result.total_win_pts)}`, color: 'text-primary' },
                                        { label: 'Total Loss Points', value: `${fmtNum(result.total_loss_pts)}`, color: 'text-danger' },
                                        { label: 'Profit Factor', value: isFinite(result.profit_factor) ? fmtNum(result.profit_factor) : '∞', color: 'text-text' },
                                        { label: 'Long Trades', value: result.long_trades_count, color: 'text-primary' },
                                        { label: 'Short Trades', value: result.short_trades_count, color: 'text-danger' },
                                    ].map((row, i) => (
                                        <div key={i} className="flex justify-between items-center py-2.5 border-b border-border/50 text-sm">
                                            <span className="text-muted">{row.label}</span>
                                            <span className={`font-mono font-semibold ${row.color}`}>{row.value}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Top 10 Best & Worst Trades */}
                            <div className="glass-panel p-5">
                                <div className="flex justify-between items-center mb-5">
                                    <h3 className="text-sm font-bold uppercase tracking-wider text-muted">Best & Worst Trades</h3>
                                    <span className="bg-white/10 text-muted px-2 py-0.5 rounded text-xs font-semibold">Top 10 each</span>
                                </div>
                                <div className="grid grid-cols-2 gap-6">
                                    {/* Best 5 */}
                                    <div>
                                        <p className="text-xs font-bold uppercase tracking-widest text-primary mb-3">�� Best Trades</p>
                                        <div className="space-y-2">
                                            {[...(result.trades || [])].sort((a, b) => b.return_pts - a.return_pts).slice(0, 10).map((t, i) => {
                                                const maxPts = Math.max(...(result.trades || []).map(x => x.return_pts));
                                                const pct = Math.min(100, (t.return_pts / maxPts) * 100);
                                                return (
                                                    <div key={i}>
                                                        <div className="flex justify-between text-xs mb-1">
                                                            <span className="text-muted font-mono">{fmtDate(t.entry_time, true)}</span>
                                                            <span className="text-primary font-bold">+{fmtNum(t.return_pts)} pts</span>
                                                        </div>
                                                        <div className="w-full bg-white/5 rounded-full h-2">
                                                            <div className="bg-primary rounded-full h-2 transition-all" style={{ width: `${pct}%`, background: 'linear-gradient(90deg,#22c55e,#4ade80)' }} />
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                    {/* Worst 5 */}
                                    <div>
                                        <p className="text-xs font-bold uppercase tracking-widest text-danger mb-3">💀 Worst Trades</p>
                                        <div className="space-y-2">
                                            {[...(result.trades || [])].sort((a, b) => a.return_pts - b.return_pts).slice(0, 10).map((t, i) => {
                                                const minPts = Math.min(...(result.trades || []).map(x => x.return_pts));
                                                const pct = Math.min(100, (t.return_pts / minPts) * 100);
                                                return (
                                                    <div key={i}>
                                                        <div className="flex justify-between text-xs mb-1">
                                                            <span className="text-muted font-mono">{fmtDate(t.entry_time, true)}</span>
                                                            <span className="text-danger font-bold">{fmtNum(t.return_pts)} pts</span>
                                                        </div>
                                                        <div className="w-full bg-white/5 rounded-full h-2">
                                                            <div className="rounded-full h-2 transition-all" style={{ width: `${pct}%`, background: 'linear-gradient(90deg,#ef4444,#f87171)' }} />
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>


                        {/* ── Charts ── */}
                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

                            {/* Cumulative Equity (Points) */}
                            <div className="glass-panel p-5">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-sm font-bold uppercase tracking-wider text-muted flex items-center gap-2">
                                        <TrendingUp size={14} className="text-primary" />
                                        Cumulative Equity (Points)
                                    </h3>
                                    <span className="text-xs font-mono bg-white/5 border border-border rounded px-2 py-1 text-muted">
                                        peak <span className="text-primary font-bold">+{fmtNum(Math.max(...(result.equity_curve || []).map(d => d.cumulative_pts)))}</span>
                                        {' · '}
                                        valley <span className="text-danger font-bold">{fmtNum(Math.min(...(result.equity_curve || []).map(d => d.cumulative_pts)))}</span>
                                    </span>
                                </div>
                                <ResponsiveContainer width="100%" height={260}>
                                    <AreaChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                                        <defs>
                                            <linearGradient id="equityPosGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid stroke={C.border} strokeDasharray="3 3" />
                                        <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fontSize: 10, fill: C.muted }} tickLine={false} axisLine={false} />
                                        <YAxis tick={{ fontSize: 10, fill: C.muted }} tickLine={false} axisLine={false} domain={['auto', 'auto']} width={65}
                                            tickFormatter={v => (v >= 0 ? `+${v}` : `${v}`)} />
                                        <Tooltip content={<CustomTooltip />} />
                                        <ReferenceLine y={0} stroke={C.muted} strokeDasharray="4 2" />
                                        <Area type="monotone" dataKey="cumulative_pts" name="Cumul. PnL (pts)"
                                            stroke="#3b82f6" fill="url(#equityPosGrad)" dot={false} strokeWidth={1.5} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Drawdown (Points) */}
                            <div className="glass-panel p-5">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-sm font-bold uppercase tracking-wider text-muted flex items-center gap-2">
                                        <TrendingDown size={14} className="text-danger" />
                                        Drawdown Curve
                                    </h3>
                                    <span className="text-xs font-mono bg-white/5 border border-border rounded px-2 py-1 text-muted">
                                        max <span className="text-danger font-bold">{fmtNum(result.max_drawdown)} pts</span>
                                    </span>
                                </div>
                                <ResponsiveContainer width="100%" height={260}>
                                    <AreaChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                                        <defs>
                                            <linearGradient id="ddPtsGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.08} />
                                                <stop offset="95%" stopColor="#ef4444" stopOpacity={0.45} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid stroke={C.border} strokeDasharray="3 3" />
                                        <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fontSize: 10, fill: C.muted }} tickLine={false} axisLine={false} />
                                        <YAxis tick={{ fontSize: 10, fill: C.muted }} tickLine={false} axisLine={false} domain={['auto', 0]} width={65} />
                                        <Tooltip content={<CustomTooltip />} />
                                        <ReferenceLine y={0} stroke={C.muted} strokeDasharray="4 2" />
                                        <Area type="monotone" dataKey="drawdown_pts" name="Drawdown (pts)"
                                            stroke="#ef4444" fill="url(#ddPtsGrad)" dot={false} strokeWidth={1.5} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Trade Log Table */}
                        <div className="glass-panel p-5">
                            <div className="flex items-center gap-2 mb-4">
                                <h3 className="text-sm font-bold uppercase tracking-wider text-muted flex items-center gap-2">
                                    <BarChart2 size={14} className="text-primary" />
                                    Trade Log
                                    <span className="bg-white/10 text-muted px-2 py-0.5 rounded-full text-xs font-semibold ml-1">
                                        {result.trades?.length ?? 0}
                                    </span>
                                </h3>
                                <button
                                    className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary border border-primary/30 text-xs font-bold hover:bg-primary/20 transition-all cursor-pointer"
                                    onClick={() => {
                                        const trades = result.trades || [];
                                        if (!trades.length) return;
                                        const headers = ['#', 'Dir', 'Entry Time', 'Exit Time', 'Entry Price', 'Exit Price', 'Return Pts', 'Duration', 'Result'];
                                        const rows = trades.map((t, i) => [
                                            i + 1,
                                            t.direction,
                                            t.entry_time,
                                            t.exit_time,
                                            t.entry_price,
                                            t.exit_price,
                                            t.return_pts,
                                            t.duration_minutes >= 1440
                                                ? `${Math.round(t.duration_minutes / 1440)}d`
                                                : t.duration_minutes >= 60
                                                    ? `${Math.round(t.duration_minutes / 60)}h`
                                                    : `${t.duration_minutes}m`,
                                            t.is_win ? 'WIN' : 'LOSS'
                                        ]);
                                        const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
                                        const blob = new Blob([csv], { type: 'text/csv' });
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = `${result.symbol}_${result.strategy}_${result.timeframe}_trades.csv`;
                                        document.body.appendChild(a);
                                        a.click();
                                        document.body.removeChild(a);
                                        URL.revokeObjectURL(url);
                                    }}
                                >
                                    ⬇ Download CSV
                                </button>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs">
                                    <thead>
                                        <tr className="text-muted text-left border-b border-border">
                                            {['#', 'Dir', 'Entry Time', 'Exit Time', 'Entry Price', 'Exit Price', 'Return (Pts)', 'Duration', 'Result'].map(h => (
                                                <th key={h} className="py-2 px-3 font-semibold uppercase tracking-wide">{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(result.trades || []).map((t, i) => (
                                            <tr
                                                key={i}
                                                className={`border-b border-border/50 hover:bg-white/5 transition-colors ${t.is_win ? 'hover:border-primary/20' : 'hover:border-danger/20'}`}
                                            >
                                                <td className="py-2.5 px-3 text-muted font-mono">{i + 1}</td>
                                                <td className="py-2.5 px-3">
                                                    <span className={`inline-block px-2 py-0.5 rounded font-bold text-xs ${t.direction === 'LONG'
                                                        ? 'bg-primary/10 text-primary border border-primary/30'
                                                        : 'bg-danger/10 text-danger border border-danger/30'
                                                        }`}>
                                                        {t.direction === 'LONG' ? '▲ L' : '▼ S'}
                                                    </span>
                                                </td>
                                                <td className="py-2.5 px-3 font-mono">{fmtDate(t.entry_time, true)}</td>
                                                <td className="py-2.5 px-3 font-mono">{fmtDate(t.exit_time, true)}</td>
                                                <td className="py-2.5 px-3 font-mono text-text">₹{fmtNum(t.entry_price)}</td>
                                                <td className="py-2.5 px-3 font-mono text-text">₹{fmtNum(t.exit_price)}</td>
                                                <td className={`py-2.5 px-3 font-mono font-bold ${t.is_win ? 'text-primary' : 'text-danger'}`}>
                                                    {t.return_pts >= 0 ? '+' : ''}{fmtNum(t.return_pts)} pts
                                                </td>
                                                <td className="py-2.5 px-3 text-muted font-mono">
                                                    {t.duration_minutes >= 1440
                                                        ? `${Math.round(t.duration_minutes / 1440)}d`
                                                        : t.duration_minutes >= 60
                                                            ? `${Math.round(t.duration_minutes / 60)}h`
                                                            : `${t.duration_minutes}m`}
                                                </td>
                                                <td className="py-2.5 px-3">
                                                    <TradeTag win={t.is_win} />
                                                </td>
                                            </tr>
                                        ))}
                                        {(!result.trades || result.trades.length === 0) && (
                                            <tr>
                                                <td colSpan={9} className="py-8 text-center text-muted">No trades generated for this parameter set.</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
