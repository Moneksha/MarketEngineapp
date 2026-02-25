import React, { useState } from 'react';
import { X, User, Phone, Mail, FileText, Send, CheckCircle, Loader } from 'lucide-react';
import api from '../services/api';

const AddStrategyModal = ({ onClose }) => {
    const [form, setForm] = useState({ name: '', phone: '', email: '', description: '' });
    const [status, setStatus] = useState('idle'); // idle | loading | success | error
    const [message, setMessage] = useState('');

    const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.name || !form.phone || !form.email || !form.description) return;

        setStatus('loading');
        try {
            const { data } = await api.post('/strategies/request', form);
            setStatus('success');
            setMessage(data.message);
        } catch (err) {
            setStatus('error');
            setMessage('Something went wrong. Please try again.');
        }
    };

    return (
        /* ── Backdrop ── */
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)' }}
            onClick={(e) => e.target === e.currentTarget && onClose()}
        >
            {/* ── Modal Card ── */}
            <div
                className="relative w-full max-w-lg rounded-2xl overflow-hidden"
                style={{
                    background: 'linear-gradient(135deg, rgba(17,24,39,0.95) 0%, rgba(10,14,26,0.98) 100%)',
                    border: '1px solid rgba(0,212,255,0.2)',
                    boxShadow: '0 0 60px rgba(0,212,255,0.08), 0 25px 50px rgba(0,0,0,0.5)',
                }}
            >
                {/* Glowing accent line */}
                <div style={{ height: '2px', background: 'linear-gradient(90deg, #00d4ff, #00ff88, #00d4ff)' }} />

                {/* Close button */}
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 p-2 rounded-lg hover:bg-black/10 transition-colors text-muted hover:text-black"
                >
                    <X size={18} />
                </button>

                <div className="p-8">
                    {/* Header */}
                    <div className="mb-7">
                        <h2 className="text-2xl font-bold text-black mb-1">Request a Strategy</h2>
                        <p className="text-sm text-muted">Tell us your idea — we'll build and test it for you.</p>
                    </div>

                    {/* ── Success State ── */}
                    {status === 'success' ? (
                        <div className="flex flex-col items-center py-8 gap-4 text-center">
                            <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center">
                                <CheckCircle size={36} className="text-green-400" />
                            </div>
                            <h3 className="text-lg font-semibold text-green-400">Request Received!</h3>
                            <p className="text-sm text-muted max-w-xs">{message}</p>
                            <button
                                onClick={onClose}
                                className="mt-4 px-6 py-2 rounded-lg bg-primary/10 border border-primary/30 text-primary text-sm font-medium hover:bg-primary/20 transition-all"
                            >
                                Close
                            </button>
                        </div>
                    ) : (
                        /* ── Form ── */
                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* Name */}
                            <Field icon={<User size={15} />} label="Full Name">
                                <input
                                    name="name" type="text" value={form.name} onChange={handleChange}
                                    placeholder="Moneksha Dangat"
                                    required
                                />
                            </Field>

                            {/* Phone */}
                            <Field icon={<Phone size={15} />} label="Phone Number">
                                <input
                                    name="phone" type="tel" value={form.phone} onChange={handleChange}
                                    placeholder="+91 98765 43210"
                                    required
                                />
                            </Field>

                            {/* Email */}
                            <Field icon={<Mail size={15} />} label="Email Address">
                                <input
                                    name="email" type="email" value={form.email} onChange={handleChange}
                                    placeholder="you@example.com"
                                    required
                                />
                            </Field>

                            {/* Description */}
                            <Field icon={<FileText size={15} />} label="Strategy Description">
                                <textarea
                                    name="description" value={form.description} onChange={handleChange}
                                    placeholder="Describe your strategy idea — entry rules, exit conditions, timeframe, indicators..."
                                    rows={4}
                                    required
                                    style={{ resize: 'none' }}
                                />
                            </Field>

                            {/* Error message */}
                            {status === 'error' && (
                                <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                                    {message}
                                </p>
                            )}

                            {/* Submit */}
                            <button
                                type="submit"
                                disabled={status === 'loading'}
                                className="w-full mt-2 flex items-center justify-center gap-2 py-3 px-6 rounded-xl font-semibold text-sm transition-all"
                                style={{
                                    background: status === 'loading'
                                        ? 'rgba(0,212,255,0.1)'
                                        : 'linear-gradient(135deg, rgba(0,212,255,0.2), rgba(0,255,136,0.15))',
                                    border: '1px solid rgba(0,212,255,0.4)',
                                    color: '#00d4ff',
                                    boxShadow: status !== 'loading' ? '0 0 20px rgba(0,212,255,0.1)' : 'none',
                                }}
                            >
                                {status === 'loading' ? (
                                    <><Loader size={16} className="animate-spin" /> Sending…</>
                                ) : (
                                    <><Send size={16} /> Submit Request</>
                                )}
                            </button>
                        </form>
                    )}
                </div>
            </div>
        </div>
    );
};

/* ── Reusable input field wrapper ── */
const Field = ({ icon, label, children }) => (
    <div>
        <label className="flex items-center gap-1.5 text-xs font-medium text-muted mb-1.5">
            <span className="text-primary">{icon}</span>
            {label}
        </label>
        <div
            style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '10px',
                transition: 'border-color 0.2s',
            }}
            className="focus-within:border-primary/40"
        >
            {React.cloneElement(children, {
                className: 'w-full bg-transparent px-4 py-2.5 text-sm text-black placeholder:text-muted/50 outline-none rounded-[10px]',
            })}
        </div>
    </div>
);

export default AddStrategyModal;
