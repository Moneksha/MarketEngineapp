import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api from '../services/api';
import logo from '../assets/logo.svg';

const ForgotPassword = () => {
    const [step, setStep] = useState(1);
    const [identifier, setIdentifier] = useState('');
    const [otp, setOtp] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [resetToken, setResetToken] = useState('');
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const navigate = useNavigate();

    const handleSendOTP = async (e) => {
        e.preventDefault();
        setError('');
        setSuccessMessage('');
        setLoading(true);
        try {
            const res = await api.post('/auth/forgot-password', { identifier });
            setSuccessMessage(res.data.detail || 'OTP sent to your email.');
            setStep(2);
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to send OTP. User may not exist.');
        } finally {
            setLoading(false);
        }
    };

    const handleVerifyOTP = async (e) => {
        e.preventDefault();
        setError('');
        setSuccessMessage('');
        setLoading(true);
        try {
            const res = await api.post('/auth/verify-reset-otp', { identifier, otp });
            setResetToken(res.data.reset_token);
            setSuccessMessage('OTP Verified successfully.');
            setStep(3);
        } catch (err) {
            setError(err.response?.data?.detail || 'Invalid or expired OTP.');
        } finally {
            setLoading(false);
        }
    };

    const handleResetPassword = async (e) => {
        e.preventDefault();
        setError('');
        setSuccessMessage('');

        if (newPassword !== confirmPassword) {
            return setError('Passwords do not match');
        }
        if (newPassword.length < 6) {
            return setError('Password must be at least 6 characters');
        }

        setLoading(true);
        try {
            await api.post('/auth/reset-password', {
                reset_token: resetToken,
                new_password: newPassword,
                confirm_password: confirmPassword
            });
            setSuccessMessage('Password successfully reset! Redirecting to login...');
            setTimeout(() => {
                navigate('/login');
            }, 2000);
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to reset password. Token may have expired.');
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
                
                <h2 className="text-2xl font-bold mb-2 text-center">Reset Password</h2>
                <div className="text-sm text-center text-muted mb-6 flex justify-center space-x-2">
                    <span className={step >= 1 ? 'text-primary' : ''}>1. Identifying</span>
                    <span>→</span>
                    <span className={step >= 2 ? 'text-primary' : ''}>2. OTP</span>
                    <span>→</span>
                    <span className={step >= 3 ? 'text-primary' : ''}>3. New Password</span>
                </div>

                {error && (
                    <div className="bg-red-500/10 border border-red-500/50 text-red-500 text-sm p-3 rounded mb-6 text-center">
                        {error}
                    </div>
                )}
                {successMessage && (
                    <div className="bg-primary/10 border border-primary/50 text-primary text-sm p-3 rounded mb-6 text-center">
                        {successMessage}
                    </div>
                )}

                {step === 1 && (
                    <form onSubmit={handleSendOTP} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-muted mb-1">Email OR 10-digit Phone Number</label>
                            <input
                                type="text"
                                required
                                placeholder="you@example.com or 9876543210"
                                className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-text focus:outline-none focus:border-primary transition-colors"
                                value={identifier}
                                onChange={(e) => setIdentifier(e.target.value)}
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={loading || !identifier}
                            className="w-full bg-primary/10 hover:bg-primary/20 text-primary border border-primary/50 font-semibold rounded-lg px-4 py-3 transition-all disabled:opacity-50 mt-4"
                        >
                            {loading ? 'Sending OTP...' : 'Send OTP'}
                        </button>
                    </form>
                )}

                {step === 2 && (
                    <form onSubmit={handleVerifyOTP} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-muted mb-1">Enter 6-digit OTP</label>
                            <input
                                type="text"
                                required
                                maxLength="6"
                                placeholder="123456"
                                className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-text focus:outline-none focus:border-primary transition-colors text-center text-2xl tracking-[0.5em]"
                                value={otp}
                                onChange={(e) => setOtp(e.target.value.replace(/[^0-9]/g, ''))}
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={loading || otp.length !== 6}
                            className="w-full bg-primary/10 hover:bg-primary/20 text-primary border border-primary/50 font-semibold rounded-lg px-4 py-3 transition-all disabled:opacity-50 mt-4"
                        >
                            {loading ? 'Verifying...' : 'Verify OTP'}
                        </button>
                        <div className="text-center mt-4">
                            <button 
                                type="button"
                                onClick={handleSendOTP}
                                disabled={loading}
                                className="text-sm text-muted hover:text-primary transition-colors"
                            >
                                Resend OTP
                            </button>
                        </div>
                    </form>
                )}

                {step === 3 && (
                    <form onSubmit={handleResetPassword} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-muted mb-1">New Password</label>
                            <input
                                type="password"
                                required
                                className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-text focus:outline-none focus:border-primary transition-colors"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
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
                            disabled={loading || !newPassword || !confirmPassword}
                            className="w-full bg-primary/10 hover:bg-primary/20 text-primary border border-primary/50 font-semibold rounded-lg px-4 py-3 transition-all disabled:opacity-50 mt-4"
                        >
                            {loading ? 'Updating...' : 'Reset Password'}
                        </button>
                    </form>
                )}

                <div className="text-center text-sm text-muted mt-6">
                    <Link to="/login" className="text-primary hover:underline">Back to Login</Link>
                </div>
            </div>
        </div>
    );
};

export default ForgotPassword;
