import axios from 'axios';

const api = axios.create({
    baseURL: '/api',
    headers: {
        'Content-Type': 'application/json',
    },
});

export const marketApi = {
    getNifty: () => api.get('/market/nifty'),
    getHeavyweights: () => api.get('/market/heavyweights'),
    getBias: () => api.get('/market/bias'),
    getOHLC: (symbol, interval = '5minute', days = 5) =>
        api.get(`/market/ohlc/${symbol}`, { params: { interval, days } }),
    authStatus: () => api.get('/market/auth/zerodha/status'),
    autoLogin: () => api.post('/market/auth/zerodha/auto-login'),
    getLoginUrl: () => api.post('/market/auth/zerodha/login'),
};

export const tradesApi = {
    getTrades: (limit = 50, strategyId = null) => api.get('/trades', { params: { limit, strategy_id: strategyId } }),
    getTodayTrades: () => api.get('/trades/today'),
    getPnl: (strategyId) => api.get(`/pnl/${strategyId}`),
    getAllPnl: () => api.get('/pnl/all'),
};

export default api;
