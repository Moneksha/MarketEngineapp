import React, { useState, useEffect } from 'react';
import { Wifi, WifiOff, LogOut } from 'lucide-react';
import { marketApi } from '../services/api';
import { useAuth } from '../context/AuthContext';
import logo from '../assets/logo.svg';

const Header = ({ isConnected }) => {
    const { user, logout } = useAuth();
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
            setLoading(true);
            await marketApi.autoLogin();

            // Start polling for auth status until it connects
            const pollInterval = setInterval(async () => {
                const { data } = await marketApi.authStatus();
                if (data.connected) {
                    setAuthStatus(true);
                    setLoading(false);
                    clearInterval(pollInterval);
                    // Reload the page to refresh WS and feeds
                    window.location.reload();
                }
            }, 3000);

            // Stop polling after 60 seconds (script timeout limit)
            setTimeout(() => {
                clearInterval(pollInterval);
                setLoading(false);
            }, 60000);

        } catch (e) {
            console.error("Auto login failed", e);
            setLoading(false);
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

                {/* User Session Info */}
                {user && (
                    <div className="flex items-center gap-4 border-l border-border pl-6">
                        <div className="flex flex-col items-end">
                            <span className="text-sm font-semibold text-text">{user.name}</span>
                            <span className="text-xs text-muted">{user.email}</span>
                        </div>
                        <button
                            onClick={logout}
                            className="p-2 hover:bg-red-500/10 text-muted hover:text-red-500 rounded-lg transition-colors"
                            title="Logout"
                        >
                            <LogOut className="w-5 h-5" />
                        </button>
                    </div>
                )}
            </div>
        </header>
    );
};

export default Header;
