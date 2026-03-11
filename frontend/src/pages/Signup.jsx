import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import PhoneInput from 'react-phone-input-2';
import 'react-phone-input-2/lib/style.css';
import logo from '../assets/logo.svg';

const Signup = () => {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [phoneNumber, setPhoneNumber] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const { signup, user } = useAuth();
    const navigate = useNavigate();

    // Navigate once user state is confirmed after signup (auto-login)
    useEffect(() => {
        if (user) navigate('/dashboard', { replace: true });
    }, [user, navigate]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (password !== confirmPassword) return setError('Passwords do not match');
        if (password.length < 6) return setError('Password must be at least 6 characters');

        // Set phoneNumber as just digits for basic length validation, or pass directly to regex
        // react-phone-input-2 returns the number with the country code but NOT the '+'
        // e.g., '919876543210' for India.
        const formattedPhone = phoneNumber ? `+${phoneNumber}` : '';

        // Basic phone validation if provided
        if (formattedPhone && !/^\+\d{10,15}$/.test(formattedPhone)) {
            return setError('Phone must be in international format (e.g. India +91)');
        }

        setLoading(true);
        try {
            // signup returns JWT now — AuthContext stores it and sets user
            await signup(name, email, formattedPhone, password, confirmPassword);
            // Navigation is handled by the useEffect above
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to create account');
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
                <h2 className="text-2xl font-bold mb-6 text-center">Create Account</h2>

                {error && (
                    <div className="bg-red-500/10 border border-red-500/50 text-red-500 text-sm p-3 rounded mb-6 text-center">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-muted mb-1">Name</label>
                        <input
                            type="text"
                            required
                            className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-text focus:outline-none focus:border-primary transition-colors"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-muted mb-1">Email</label>
                        <input
                            type="email"
                            required
                            className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-text focus:outline-none focus:border-primary transition-colors"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-muted mb-1">
                            Phone Number{' '}
                            <span className="text-muted text-xs font-normal">(optional)</span>
                        </label>
                        <div className="phone-input-wrapper mt-1">
                            <style>{`
                                /* Main input box styling */
                                .react-tel-input .form-control {
                                    width: 100%;
                                    height: 46px;
                                    background-color: #0f172a;
                                    border: 1px solid #334155;
                                    border-radius: 8px;
                                    color: white;
                                    padding-left: 58px; /* Room for the flag dropdown */
                                }
                                .react-tel-input .form-control:focus {
                                    border-color: #22c55e;
                                    box-shadow: none;
                                }

                                /* Left flag dropdown button */
                                .react-tel-input .flag-dropdown {
                                    background-color: #0f172a;
                                    border: 1px solid #334155;
                                    border-right: none;
                                    border-radius: 8px 0 0 8px;
                                    transition: background-color 0.2s ease;
                                }
                                .react-tel-input .flag-dropdown.open,
                                .react-tel-input .selected-flag:hover, 
                                .react-tel-input .selected-flag:focus {
                                    background-color: #020617;
                                }

                                /* Dropdown menu list styling */
                                .react-tel-input .country-list {
                                    background-color: #020617;
                                    color: white;
                                    border: 1px solid #334155;
                                    border-radius: 8px;
                                    border-top-left-radius: 0;
                                    border-top-right-radius: 0;
                                    z-index: 9999;
                                    margin-top: 2px;
                                    scrollbar-width: thin;
                                    scrollbar-color: #334155 #020617;
                                }
                                .react-tel-input .country-list .country {
                                    padding: 10px 12px;
                                }
                                .react-tel-input .country-list .country:hover,
                                .react-tel-input .country-list .country.highlight {
                                    background-color: #334155;
                                }
                                .react-tel-input .country-list .divider {
                                    border-bottom-color: #334155;
                                }
                                .react-tel-input .country-list .search {
                                    background-color: #0f172a;
                                    padding: 10px;
                                }
                                .react-tel-input .country-list .search-box {
                                    background-color: #020617;
                                    border: 1px solid #334155;
                                    color: white;
                                    padding: 6px 12px;
                                }
                                .react-tel-input .country-list .search-box::placeholder {
                                    color: #94a3b8;
                                }
                            `}</style>
                            <PhoneInput
                                country={'in'}
                                value={phoneNumber}
                                onChange={phone => setPhoneNumber(phone)}
                                inputProps={{
                                    name: 'phone',
                                    required: false,
                                }}
                            />
                        </div>
                        <p className="text-xs text-muted mt-1">Use this to log in securely using your phone</p>
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
                    <div>
                        <label className="block text-sm font-medium text-muted mb-1">Confirm Password</label>
                        <input
                            type="password"
                            required
                            className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-text focus:outline-none focus:border-primary transition-colors"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-primary/10 hover:bg-primary/20 text-primary border border-primary/50 font-semibold rounded-lg px-4 py-3 transition-all disabled:opacity-50 mt-4"
                    >
                        {loading ? 'Creating Account...' : 'SIGN UP'}
                    </button>
                    <div className="text-center text-sm text-muted mt-6">
                        Already have an account?{' '}
                        <Link to="/login" className="text-primary hover:underline">Log in</Link>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default Signup;
