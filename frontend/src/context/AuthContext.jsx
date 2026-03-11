import { useState, useEffect, createContext, useContext } from 'react';
import api from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const initAuth = async () => {
            const urlParams = new URLSearchParams(window.location.search);
            const urlToken = urlParams.get('token');

            if (urlToken) {
                // Clear the token from URL
                window.history.replaceState({}, document.title, window.location.pathname);
                try {
                    await loginWithToken(urlToken);
                } catch (e) {
                    console.error('OAuth token login failed', e);
                }
                setLoading(false);
                return;
            }

            const storedUser = localStorage.getItem('user');
            const token = localStorage.getItem('token');

            if (storedUser && token) {
                try {
                    setUser(JSON.parse(storedUser));
                } catch (e) {
                    localStorage.removeItem('user');
                    localStorage.removeItem('token');
                }
            } else {
                localStorage.removeItem('user');
                localStorage.removeItem('token');
            }
            setLoading(false);
        };

        initAuth();
    }, []);

    const _storeAuth = (data) => {
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        setUser(data.user);
    };

    // Login with email OR phone number
    const login = async (identifier, password) => {
        const { data } = await api.post('/auth/login', { identifier, password });
        _storeAuth(data);
        return data;
    };

    // Signup — backend now returns a token so the user is logged in immediately
    const signup = async (name, email, phone_number, password, confirm_password) => {
        const { data } = await api.post('/auth/signup', {
            name, email, phone_number: phone_number || null, password, confirm_password
        });
        _storeAuth(data);
        return data;
    };

    // Google OAuth login directly via token (called from frontend redirect loop)
    const loginWithToken = async (googleToken) => {
        // Set token temporarily so API requests work
        localStorage.setItem('token', googleToken);
        api.defaults.headers.common['Authorization'] = `Bearer ${googleToken}`;
        try {
            const { data } = await api.get('/auth/me');
            _storeAuth({ access_token: googleToken, user: data.user });
            return data;
        } catch (e) {
            localStorage.removeItem('token');
            delete api.defaults.headers.common['Authorization'];
            throw e;
        }
    };

    const logout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, signup, loginWithToken, logout }}>
            {!loading && children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
