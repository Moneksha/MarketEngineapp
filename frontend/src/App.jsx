import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import NiftyTicker from './components/NiftyTicker';
import NiftyCard from './components/NiftyCard';
import HeavyweightCards from './components/HeavyweightCards';
import PriceChart from './components/PriceChart';
import StrategySelector from './components/StrategySelector';
import StrategyDetail from './components/StrategyDetail';
import TradeTable from './components/TradeTable';
import AddStrategyModal from './components/AddStrategyModal';
import WhatsAppWidget from './components/WhatsAppWidget';
import ResearchDashboard from './pages/ResearchDashboard';
import { wsService } from './services/websocket';
import api from './services/api';
import { tradesApi, marketApi } from './services/api';

function App() {
  const [wsConnected, setWsConnected] = useState(false);
  const [nifty, setNifty] = useState(null);
  const [heavyweights, setHeavyweights] = useState([]);
  const [optionsData, setOptionsData] = useState(null);
  const [strategies, setStrategies] = useState([]);
  const [pnlMap, setPnlMap] = useState({});
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [trades, setTrades] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [currentView, setCurrentView] = useState('dashboard'); // 'dashboard' | 'research'

  // Fetch initial data
  useEffect(() => {
    fetchStrategies();
    fetchTrades();
    fetchInitialMarketData(); // Load NIFTY + heavyweights via REST immediately
  }, []);

  const fetchInitialMarketData = async () => {
    try {
      const [niftyRes, hwRes] = await Promise.allSettled([
        marketApi.getNifty(),
        marketApi.getHeavyweights(),
      ]);

      if (niftyRes.status === 'fulfilled') {
        const d = niftyRes.value.data;
        setNifty({
          symbol: d.symbol || 'NIFTY 50',
          ltp: d.ltp,
          change: d.change,
          change_pct: d.change_pct,
          open: d.open || 0, high: d.high || 0, low: d.low || 0,
          vix: d.vix || null,
        });
      }

      if (hwRes.status === 'fulfilled') {
        setHeavyweights(hwRes.value.data.stocks || []);
      }
    } catch (e) {
      console.warn('Initial market data fetch failed:', e);
    }
  };

  // WebSocket connection
  useEffect(() => {
    wsService.connect();
    const unsub = wsService.subscribe(handleWsMessage);
    return () => {
      unsub();
      wsService.disconnect();
    };
  }, []);

  // Connection Status (Optional: check backend auth status again if needed, but handled by Header)
  // We no longer read tokens from the URL.
  // The backend callback /auth/zerodha/callback handles this securely and redirects here.

  const handleWsMessage = useCallback((data) => {
    if (data.type === 'market_update') {
      setWsConnected(true);

      if (data.nifty) {
        setNifty((prev) => ({
          ...prev,
          symbol: 'NIFTY 50',
          ltp: data.nifty.ltp,
          change: data.nifty.change,
          change_pct: data.nifty.change_pct,
          open: 0, high: 0, low: 0,
          // Update VIX live from broadcaster when available
          vix: data.vix || prev?.vix || null,
        }));
      }

      if (data.options) {
        setOptionsData(data.options);
      }

      if (data.heavyweights) {
        setHeavyweights(data.heavyweights);
      }

      if (data.strategies) {
        const map = {};
        data.strategies.forEach((s) => {
          map[s.strategy_id] = s;
        });
        setPnlMap(map);

        // Update running state on local strategies
        setStrategies((prev) =>
          prev.map((s) => ({
            ...s,
            is_running: map[s.id]?.is_running ?? s.is_running,
          }))
        );
      }
    }
  }, []);

  const fetchStrategies = async () => {
    try {
      const { data } = await api.get('/strategies');
      setStrategies(data.strategies || data);
    } catch (e) {
      console.error('Failed to fetch strategies', e);
    }
  };

  const fetchTrades = async () => {
    try {
      const { data } = await tradesApi.getTodayTrades();
      setTrades(data.trades || []);
    } catch (e) {
      console.error('Failed to fetch trades', e);
    }
  };

  // Auto-refresh today's trades every 5 seconds
  useEffect(() => {
    const interval = setInterval(fetchTrades, 5000);
    return () => clearInterval(interval);
  }, []);

  const toggleStrategy = async (id) => {
    const strat = strategies.find((s) => s.id === id);
    if (!strat) return;
    try {
      if (strat.is_running) {
        await api.post(`/strategies/${id}/stop`);
      } else {
        await api.post(`/strategies/${id}/start`);
      }
      fetchStrategies();
    } catch (e) {
      console.error(e);
    }
  };

  // If we're in research view, render the full-page dashboard
  if (currentView === 'research') {
    return (
      <div className="min-h-screen bg-background text-text font-sans selection:bg-primary/30">
        <ResearchDashboard onBack={() => setCurrentView('dashboard')} />
        <WhatsAppWidget />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-text font-sans selection:bg-primary/30">
      <Header isConnected={wsConnected} />

      {/* Research Dashboard Navigation Tab */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-4 flex gap-3">
        <button
          onClick={() => setCurrentView('dashboard')}
          className={`px-4 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${currentView === 'dashboard'
              ? 'bg-primary text-background shadow-[0_0_12px_rgba(5,224,125,0.3)]'
              : 'text-muted hover:text-text border border-border'
            }`}
        >
          Live Dashboard
        </button>
        <button
          onClick={() => setCurrentView('research')}
          className={`px-4 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${currentView === 'research'
              ? 'bg-primary text-background shadow-[0_0_12px_rgba(5,224,125,0.3)]'
              : 'text-muted hover:text-text border border-border'
            }`}
        >
          ⚗️ Equity Research
        </button>
      </div>

      {/* Top 10 NIFTY Ticker always below header */}
      <NiftyTicker heavyweights={heavyweights} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">

        {/* Row 1: NIFTY Context */}
        <div className="glass-panel p-6">
          <NiftyCard data={nifty} />
        </div>

        {/* Row 2: Heavyweights */}
        <div>
          <h2 className="text-sm font-semibold text-muted uppercase tracking-wider mb-4 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary/70"></span>
            Key Market Drivers
          </h2>
          <HeavyweightCards stocks={heavyweights} />
        </div>

        {/* Row 3: Main Chart */}
        <div className="glass-panel p-1">
          <PriceChart />
        </div>

        {/* Row 4: Strategies */}
        <div className="glass-panel p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold flex items-center gap-3">
              <span className="animate-pulse w-2 h-2 bg-primary rounded-full shadow-[0_0_8px_rgba(5,224,125,0.8)]" />
              STRATEGY ENGINE
            </h2>
            <button
              onClick={() => setShowModal(true)}
              className="group relative flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all overflow-hidden bg-surface border border-primary/30 text-primary hover:border-primary/60 hover:shadow-[0_0_20px_rgba(5,224,125,0.2)]"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700"></div>
              <span className="text-lg leading-none">+</span>
              Add Strategy
            </button>
          </div>

          {selectedStrategy ? (
            <StrategyDetail
              strategyId={selectedStrategy}
              strategies={strategies}
              onBack={() => setSelectedStrategy(null)}
            />
          ) : (
            <StrategySelector
              strategies={strategies}
              activeId={selectedStrategy}
              onSelect={(id) => setSelectedStrategy(id)}
              onToggle={toggleStrategy}
              pnlMap={pnlMap}
            />
          )}
        </div>

        {/* Row 5: Today's Trades */}
        <div className="glass-panel p-6">
          <div className="flex items-center gap-4 mb-6">
            <h2 className="text-xl font-bold flex items-center gap-3">
              <span className="w-2 h-2 bg-warning rounded-full shadow-[0_0_8px_rgba(255,176,32,0.8)]" />
              TODAY'S TRADES
            </h2>
            <span className="bg-white/10 text-muted px-2.5 py-0.5 rounded-full text-xs font-semibold">
              {trades.length} {trades.length === 1 ? 'Trade' : 'Trades'}
            </span>
          </div>
          <TradeTable trades={trades} />
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center py-8 text-xs text-muted border-t border-border mt-12 bg-surface/50 backdrop-blur">
        <p className="font-mono opacity-60">MARKET ENGINE v2.0</p>
        <p className="mt-1">Institutional-Grade Paper Trading Platform · Powered by Zerodha Kite Connect</p>
      </footer>

      {/* Add Strategy Modal */}
      {showModal && <AddStrategyModal onClose={() => setShowModal(false)} />}

      {/* Floating Global Widgets */}
      <WhatsAppWidget />
    </div>
  );
}

export default App;
