import { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import logo from '../assets/logo.svg';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

const Login = () => {
    const [identifier, setIdentifier] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [googleLoading, setGoogleLoading] = useState(false);
    const { login, googleLogin, user } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    // Check for error from Google OAuth redirect loop
    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const urlError = params.get('error');
        if (urlError) {
            setError(urlError);
            window.history.replaceState({}, document.title, location.pathname);
        }
    }, [location]);

    // Navigate once user state is confirmed (prevents race condition)
    useEffect(() => {
        if (user) navigate('/dashboard', { replace: true });
    }, [user, navigate]);

    const handleGoogleClick = () => {
        if (!GOOGLE_CLIENT_ID) {
            setError('Google Sign-In is not configured. Add VITE_GOOGLE_CLIENT_ID to .env');
            return;
        }
        window.location.href = `http://localhost:8000/api/auth/google/login`;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await login(identifier, password);
            // Navigation handled by useEffect above
        } catch (err) {
            setError(err.response?.data?.detail || 'Invalid credentials');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-background text-text flex items-center justify-center p-4">
            <div className="glass-panel w-full max-w-md p-8 relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary to-transparent" />
                <div className="flex justify-center mb-8">
                    <img src={logo} alt="Market Engine" className="h-12 w-auto object-contain" />
                </div>
                <h2 className="text-2xl font-bold mb-6 text-center">Sign In</h2>

                {error && (
                    <div className="bg-red-500/10 border border-red-500/50 text-red-500 text-sm p-3 rounded mb-6 text-center">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-muted mb-1">
                            Email or Phone Number
                        </label>
                        <input
                            type="text"
                            required
                            placeholder="you@email.com or +91XXXXXXXXXX"
                            className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-text focus:outline-none focus:border-primary transition-colors"
                            value={identifier}
                            onChange={(e) => setIdentifier(e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-muted mb-1">Password</label>
                        <input
                            type="password"
                            required
                            className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-text focus:outline-none focus:border-primary transition-colors"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={loading || googleLoading}
                        className="w-full bg-primary/10 hover:bg-primary/20 text-primary border border-primary/50 font-semibold rounded-lg px-4 py-3 transition-all disabled:opacity-50 mt-4"
                    >
                        {loading ? 'Authenticating...' : 'LOGIN'}
                    </button>
                    <div className="text-right text-sm mt-2">
                        <Link to="/forgot-password" className="text-primary hover:underline">Forgot Password?</Link>
                    </div>
                </form>

                {/* Divider */}
                <div className="flex items-center my-5">
                    <div className="flex-1 h-px bg-border" />
                    <span className="mx-3 text-xs text-muted">OR</span>
                    <div className="flex-1 h-px bg-border" />
                </div>

                {/* Google Sign-In */}
                <button
                    type="button"
                    onClick={handleGoogleClick}
                    disabled={loading || googleLoading}
                    className="w-full flex items-center justify-center gap-3 bg-surface hover:bg-surface/80 border border-border rounded-lg px-4 py-3 transition-all disabled:opacity-50 font-medium text-sm"
                >
                    {/* Google SVG icon */}
                    <svg width="18" height="18" viewBox="0 0 48 48">
                        <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
                        <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
                        <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
                        <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
                    </svg>
                    {googleLoading ? 'Signing in...' : 'Continue with Google'}
                </button>

                <div className="text-center text-sm text-muted mt-6">
                    Don't have an account?{' '}
                    <Link to="/signup" className="text-primary hover:underline">Create Account</Link>
                </div>
            </div>
        </div>
    );
};

export default Login;
