import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import api from '@/services/api';
import type { AuthProviders, User } from '@/types';

interface SignupPayload {
  username: string;
  email: string;
  password: string;
  full_name: string;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  providers: AuthProviders;
  login: (username: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => void;
  can: (permission: string) => boolean;
}

const DEFAULT_PROVIDERS: AuthProviders = { google_enabled: false, google_client_id: null, signup_enabled: false };

const AuthContext = createContext<AuthState | null>(null);

function storeSession(data: { access_token: string; refresh_token: string }) {
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);
}

function clearSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [providers, setProviders] = useState<AuthProviders>(DEFAULT_PROVIDERS);

  useEffect(() => {
    api.get('/auth/providers').then((r) => setProviders(r.data)).catch(() => setProviders(DEFAULT_PROVIDERS));
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      api.get('/auth/me')
        .then((r) => setUser(r.data))
        .catch(clearSession)
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (username: string, password: string) => {
    const { data } = await api.post('/auth/login', { username, password });
    storeSession(data);
    setUser(data.user);
  };

  const loginWithGoogle = async (credential: string) => {
    const { data } = await api.post('/auth/google', { credential });
    storeSession(data);
    setUser(data.user);
  };

  const signup = async (payload: SignupPayload) => {
    const { data } = await api.post('/auth/signup', payload);
    storeSession(data);
    setUser(data.user);
  };

  const logout = () => {
    clearSession();
    setUser(null);
  };

  const can = useCallback(
    (permission: string) => !!user?.permissions?.includes(permission),
    [user],
  );

  return (
    <AuthContext.Provider value={{ user, loading, providers, login, loginWithGoogle, signup, logout, can }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
