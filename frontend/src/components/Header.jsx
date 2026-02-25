import React, { useState, useEffect } from 'react';
import { Wifi, WifiOff } from 'lucide-react';
import { marketApi } from '../services/api';
import logo from '../assets/logo.svg';

const Header = ({ isConnected }) => {
    const [authStatus, setAuthStatus] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        checkAuth();
    }, []);

    const checkAuth = async () => {
        try {
            const { data } = await marketApi.authStatus();
            setAuthStatus(data.connected);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleLogin = async () => {
        try {
            const { data } = await marketApi.getLoginUrl();
            if (data.login_url) {
                window.location.href = data.login_url;
            }
        } catch (e) {
            console.error("Login failed", e);
        }
    };

    return (
        <header className="glass sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
                <img src={logo} alt="Market Engine" className="h-12 w-auto object-contain" />
            </div>

            <div className="flex items-center gap-6">
                {/* WS Status */}
                <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-surface/50 border border-black/5">
                    {isConnected ? (
                        <Wifi className="w-4 h-4 text-green-400" />
                    ) : (
                        <WifiOff className="w-4 h-4 text-red-400" />
                    )}
                    <span className="text-xs font-medium text-muted">
                        {isConnected ? 'LIVE FEED' : 'OFFLINE'}
                    </span>
                </div>

                {/* Zerodha Auth */}
                <div className="flex items-center gap-2">
                    {loading ? (
                        <div className="w-24 h-8 bg-surface/50 rounded animate-pulse" />
                    ) : authStatus ? (
                        <div className="flex items-center gap-2 text-green-400 text-sm font-medium">
                            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                            ZERODHA ACTIVE
                        </div>
                    ) : (
                        <button
                            onClick={handleLogin}
                            className="px-4 py-2 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/50 rounded-lg text-sm font-semibold transition-all"
                        >
                            CONNECT KITE
                        </button>
                    )}
                </div>
            </div>
        </header>
    );
};

export default Header;
