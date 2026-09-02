"use client";

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Brain, Lock, Mail, ArrowRight } from 'lucide-react';
import { GlassCard } from '@/components/GlassCard';
import { api } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('user@stressai.com');
  const [password, setPassword] = useState('User@2026');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await api.login(email, password);
      if (res.access_token) {
        localStorage.setItem('token', res.access_token);
        router.push('/dashboard');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Authentication failed. Please verify email and password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-cyan-400 flex items-center justify-center glow-primary mb-3">
            <Brain className="w-7 h-7 text-white" />
          </div>
          <h2 className="text-2xl font-bold text-white">Sign In to StressAI</h2>
          <p className="text-sm text-slate-400 mt-1">Enterprise Psychological Stress Intelligence</p>
        </div>

        <GlassCard gradient>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-medium">
                {error}
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Email Address</label>
              <div className="relative">
                <Mail className="w-5 h-5 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full glass-input rounded-xl pl-11 pr-4 py-2.5 text-sm"
                  placeholder="name@company.com"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Password</label>
              <div className="relative">
                <Lock className="w-5 h-5 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full glass-input rounded-xl pl-11 pr-4 py-2.5 text-sm"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl font-bold bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white shadow-lg glow-primary flex items-center justify-center gap-2 transition-all mt-2"
            >
              <span>{loading ? 'Authenticating...' : 'Sign In'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <div className="mt-4 p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/30">
            <p className="text-xs font-semibold text-indigo-300 mb-2">Demo Accounts:</p>
            <div className="space-y-1 text-xs text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-400">User:</span>
                <span className="font-mono">user@stressai.com / User@2026</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Admin:</span>
                <span className="font-mono">admin@stressai.com / Admin@StressAI2026</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Clinician:</span>
                <span className="font-mono">dr.sarah@clinic.com / Clinician@2026</span>
              </div>
            </div>
          </div>

          <div className="mt-6 text-center text-xs text-slate-400">
            Don&apos;t have an account?{' '}
            <Link href="/register" className="text-cyan-400 font-semibold hover:underline">
              Create account
            </Link>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
