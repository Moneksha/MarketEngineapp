import React, { useState, useEffect } from 'react';
import { ArrowLeft, BarChart3, Clock, Crosshair, Shield, Target } from 'lucide-react';
import api from '../services/api';
import LiveTrades from './LiveTrades';

const StrategyDetail = ({ strategyId, strategies, onBack }) => {
    const [strategy, setStrategy] = useState(null);
    const [tab, setTab] = useState('live');

    useEffect(() => {
        fetchStrategy();
    }, [strategyId]);

    const fetchStrategy = async () => {
        try {
            const { data } = await api.get(`/strategies/${strategyId}`);
            setStrategy(data);
        } catch (e) {
            console.error(e);
        }
    };

    if (!strategy) return <div className="glass-card h-64 animate-pulse" />;

    const tabs = [
        { id: 'live', label: 'Live Activity' },
        { id: 'info', label: 'Strategy Rules' },
    ];

    return (
        <div className="glass-card p-6">
            {/* Header */}
            <div className="flex items-center gap-4 mb-6">
                <button onClick={onBack} className="p-2 hover:bg-black/5 rounded-lg transition-colors">
                    <ArrowLeft size={20} className="text-muted" />
                </button>
                <div className="flex-1">
                    <h2 className="text-xl font-bold">{strategy.name}</h2>
                    <p className="text-sm text-muted mt-1">{strategy.description}</p>
                </div>
                <div className="flex gap-2">
                    {strategy.is_positional && (
                        <div className="px-3 py-1 bg-warning/20 border border-warning/50 rounded text-xs text-warning font-semibold tracking-wider uppercase">
                            Positional
                        </div>
                    )}
                    <div className="px-3 py-1 bg-surface/80 rounded text-xs text-muted font-mono tracking-wide">
                        {strategy.timeframe}
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 mb-6 bg-surface/50 p-1 rounded-lg w-fit">
                {tabs.map((t) => (
                    <button
                        key={t.id}
                        onClick={() => setTab(t.id)}
                        className={`px-4 py-2 text-sm font-medium rounded-md transition-all ${tab === t.id ? 'bg-primary/20 text-primary' : 'text-muted hover:text-text'
                            }`}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            {tab === 'info' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <InfoRow icon={<Clock size={16} />} label="Timeframe" value={strategy.timeframe} />
                    <InfoRow icon={<BarChart3 size={16} />} label="Indicators" value={strategy.indicators?.join(', ') || 'N/A'} />
                    <InfoRow icon={<Crosshair size={16} />} label="Entry Rules" value={strategy.entry_rules} />
                    <InfoRow icon={<Target size={16} />} label="Exit Rules" value={strategy.exit_rules} />
                    <InfoRow icon={<Shield size={16} />} label="Stop Loss" value={strategy.sl_logic} />
                    <InfoRow icon={<Target size={16} />} label="Target" value={strategy.target_logic} />
                </div>
            )}

            {tab === 'live' && <LiveTrades strategyId={strategyId} strategy={strategy} />}
        </div>
    );
};

const InfoRow = ({ icon, label, value }) => (
    <div className="flex items-start gap-3 p-3 bg-surface/30 rounded-lg">
        <div className="text-primary mt-0.5">{icon}</div>
        <div>
            <span className="text-xs text-muted block">{label}</span>
            <span className="text-sm">{value || 'N/A'}</span>
        </div>
    </div>
);

export default StrategyDetail;
