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

            // ONLY wipe token for real JWT authentication failures.
            // Zerodha-specific 401s ("Not authenticated with Zerodha") must NOT
            // log out the user — they just mean Kite is disconnected, not that
            // the user's app session is invalid.
            // A true JWT failure has the 'Bearer' WWW-Authenticate header set by FastAPI's
            // OAuth2PasswordBearer dependency, or an explicit credential validation error.
            const isZerodhaSideError = detail.toLowerCase().includes('zerodha') ||
                detail.toLowerCase().includes('not authenticated with') ||
                detail.toLowerCase().includes('kite') ||
                detail.toLowerCase().includes('not authenticated');

            const isJwtFailure = !isZerodhaSideError && (
                detail === 'Could not validate credentials' ||
                detail === 'Token has expired' ||
                (wwwAuth.toLowerCase().includes('bearer') && detail !== 'Not authenticated with Zerodha')
            );

            if (isJwtFailure) {
                console.warn('[API] JWT token invalid/expired, clearing session.');
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
