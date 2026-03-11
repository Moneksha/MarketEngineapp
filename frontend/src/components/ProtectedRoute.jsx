import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const ProtectedRoute = () => {
    const { user, loading } = useAuth();

    // Wait for AuthContext to finish reading localStorage
    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
            </div>
        );
    }

    // Primary guard: user state is set
    if (user) {
        return <Outlet />;
    }

    // Safety net: if a token exists in localStorage but React state hasn't
    // caught up yet (edge case), show spinner rather than wrongly redirecting
    const token = localStorage.getItem('token');
    if (token) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
            </div>
        );
    }

    // No user, no token — truly unauthenticated
    return <Navigate to="/login" replace />;
};

export default ProtectedRoute;
