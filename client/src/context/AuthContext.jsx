import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import axios from 'axios';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [sessionExpired, setSessionExpired] = useState(false);
    const userRef = useRef(null);

    useEffect(() => { userRef.current = user; }, [user]);

    useEffect(() => {
        const checkAuth = async () => {
            try {
                const { data } = await axios.get('/api/auth/me');
                setUser(data.user);
            } catch (error) {
                // 401 = not logged in (expected on first load); anything else is a real problem
                if (error.response?.status !== 401) {
                    console.warn('Auth check failed:', error);
                }
            } finally {
                setLoading(false);
            }
        };
        checkAuth();
    }, []);

    // Global 401 interceptor — gracefully logs out if the token expires mid-session
    useEffect(() => {
        const id = axios.interceptors.response.use(
            res => res,
            err => {
                if (err.response?.status === 401 && userRef.current !== null) {
                    setSessionExpired(true);
                    setUser(null);
                }
                return Promise.reject(err);
            }
        );
        return () => axios.interceptors.response.eject(id);
    }, []);

    const login = async (username, password, rememberMe) => {
        setSessionExpired(false);
        try {
            const { data } = await axios.post('/api/auth/login', { username, password, rememberMe });
            setUser(data.user);
            return { success: true };
        } catch (error) {
            const msg = error.response?.data?.detail || error.response?.data?.message || 'Login failed';
            return { success: false, message: msg };
        }
    };

    const logout = async () => {
        try {
            await axios.post('/api/auth/logout');
            setUser(null);
        } catch (error) {
            console.error('Logout failed', error);
        }
    };

    const logoutWithExpiry = async () => {
        setSessionExpired(true);
        await logout();
    };

    const value = {
        user,
        login,
        logout,
        logoutWithExpiry,
        sessionExpired,
        loading
    };

    return (
        <AuthContext.Provider value={value}>
            {!loading && children}
        </AuthContext.Provider>
    );
};
