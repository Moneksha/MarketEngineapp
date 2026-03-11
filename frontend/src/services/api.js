import axios from 'axios';

const api = axios.create({
    baseURL: '/api',
    headers: {
        'Content-Type': 'application/json',
    },
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            const detail = error.response?.data?.detail || '';
            const wwwAuth = error.response?.headers?.['www-authenticate'] || '';

            // Only clear session for JWT token failures.
            // FastAPI's OAuth2PasswordBearer adds 'WWW-Authenticate: Bearer'
            // on JWT auth failures. Zerodha 401s ("Not authenticated with Zerodha")
            // do NOT have this header — so we leave the session intact for those.
            const isJwtFailure = wwwAuth.toLowerCase().includes('bearer') ||
                detail === 'Could not validate credentials' ||
                detail === 'Token has expired';

            if (isJwtFailure) {
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                if (window.location.pathname !== '/login') {
                    window.location.href = '/login';
                }
            }
        }
        return Promise.reject(error);
    }
);

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
