"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { api } from './api';

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  avatar_url?: string | null;
  created_at?: string | null;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  logout: () => {},
  refreshUser: async () => {},
});

const PUBLIC_PATHS = ['/', '/login', '/register'];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const logout = useCallback(() => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
    }
    setUser(null);
    router.push('/login');
  }, [router]);

  const refreshUser = useCallback(async () => {
    try {
      const me = await api.getMe();
      setUser(me);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let fetching = false;

    const initAuth = async () => {
      // Returns true if a fetch was actually needed/performed.
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

      if (!token) {
        if (user !== null) {
          // Token was cleared (e.g. expired) — reset session state.
          setUser(null);
        }
        setLoading(false);
        if (!PUBLIC_PATHS.includes(pathname)) {
          router.push('/login');
        }
        return;
      }

      // Once we have a user, only re-validate on explicit navigation changes
      // where an earlier fetch failed (avoids a /auth/me round-trip per page).
      if (user && !PUBLIC_PATHS.includes(pathname)) return;

      if (fetching || cancelled) return;
      fetching = true;
      try {
        const me = await api.getMe();
        if (!cancelled) setUser(me);
      } catch {
        localStorage.removeItem('token');
        if (!cancelled) setUser(null);
        if (!PUBLIC_PATHS.includes(pathname)) {
          router.push('/login');
        }
      } finally {
        fetching = false;
        if (!cancelled) setLoading(false);
      }
    };

    initAuth();

    return () => {
      cancelled = true;
    };
  }, [pathname, router, user]);

  return (
    <AuthContext.Provider value={{ user, loading, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
