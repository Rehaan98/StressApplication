"use client";

import React, { useEffect, useState } from 'react';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { GlassCard } from '@/components/GlassCard';
import { StatCard } from '@/components/StatCard';
import { ShieldCheck, Users, Activity, BarChart2, CheckCircle2, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';

const ROLE_BADGE: Record<string, string> = {
  admin: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
  clinician: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40',
  user: 'bg-slate-700 text-slate-300 border-slate-600',
};

interface AdminAnalytics {
  total_users: number;
  total_assessments: number;
  total_predictions: number;
  system_stress_breakdown: Record<string, number>;
  active_users_7d: number;
  model_performance_summary: Record<string, any>;
}

export default function AdminPage() {
  const { user } = useAuth();
  const [adminData, setAdminData] = useState<AdminAnalytics | null>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [analyticsRes, usersRes] = await Promise.allSettled([
        api.getAdminAnalytics(),
        api.adminListUsers(0, 50),
      ]);
      if (analyticsRes.status === 'fulfilled') setAdminData(analyticsRes.value);
      if (usersRes.status === 'fulfilled') setUsers(usersRes.value);
    } catch {
      // non-admin users will get 403 — silently degrade
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const perf = adminData?.model_performance_summary ?? {};

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 max-w-7xl mx-auto w-full space-y-8">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-3xl font-extrabold text-white flex items-center gap-3">
                <ShieldCheck className="w-8 h-8 text-rose-400" />
                Admin Control Panel
              </h1>
              <p className="text-slate-400 mt-2 text-sm">
                System-wide management: user administration, model performance monitoring, and audit oversight.
              </p>
            </div>
            <button
              onClick={loadData}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold glass-morphism border border-slate-700 text-slate-300 hover:bg-slate-800/60 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
            <StatCard
              title="Total Users"
              value={adminData?.total_users ?? '—'}
              subtitle="Registered accounts"
              icon={Users}
              color="indigo"
            />
            <StatCard
              title="Total Assessments"
              value={adminData?.total_assessments ?? '—'}
              subtitle="System-wide all time"
              icon={Activity}
              color="cyan"
            />
            <StatCard
              title="Total Predictions"
              value={adminData?.total_predictions ?? '—'}
              subtitle="ML predictions run"
              icon={BarChart2}
              color="emerald"
            />
            <StatCard
              title="Model F1-Score"
              value={perf.f1_score ? `${(perf.f1_score * 100).toFixed(1)}%` : '—'}
              subtitle={perf.model_type ?? 'ML Classifier'}
              icon={ShieldCheck}
              color="pink"
            />
          </div>

          {/* Model Performance Card */}
          <GlassCard gradient className="border border-indigo-500/30">
            <h3 className="font-bold text-white text-base mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-indigo-400" />
              Active ML Model Performance
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Accuracy', value: perf.accuracy ? `${(perf.accuracy * 100).toFixed(1)}%` : '—', color: 'text-emerald-400' },
                { label: 'F1-Score (Macro)', value: perf.f1_score ? `${(perf.f1_score * 100).toFixed(1)}%` : '—', color: 'text-indigo-400' },
                { label: 'Precision', value: perf.precision ? `${(perf.precision * 100).toFixed(1)}%` : '—', color: 'text-cyan-400' },
                { label: 'Recall', value: perf.recall ? `${(perf.recall * 100).toFixed(1)}%` : '—', color: 'text-amber-400' },
                { label: 'Model Type', value: perf.model_type ?? '—', color: 'text-slate-300' },
                { label: 'XAI Status', value: perf.xai_status ?? '—', color: 'text-emerald-400' },
                { label: 'Active Users (7d)', value: adminData?.active_users_7d ?? '—', color: 'text-cyan-400' },
                { label: 'Stress Breakdown', value: Object.keys(adminData?.system_stress_breakdown ?? {}).length > 0 ? 'Live' : 'No data', color: 'text-pink-400' },
              ].map(m => (
                <div key={m.label} className="p-3 rounded-xl bg-slate-900 border border-slate-700 text-center">
                  <p className="text-xs text-slate-400 mb-1">{m.label}</p>
                  <p className={`font-bold text-sm ${m.color}`}>{String(m.value)}</p>
                </div>
              ))}
            </div>
          </GlassCard>

          {/* Stress Level Breakdown */}
          {adminData && Object.keys(adminData.system_stress_breakdown).length > 0 && (
            <GlassCard gradient>
              <h3 className="font-bold text-white text-base mb-4">System-Wide Stress Distribution</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {['Low', 'Moderate', 'High', 'Severe'].map(level => {
                  const colors: Record<string, string> = {
                    Low: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30',
                    Moderate: 'text-amber-300 bg-amber-500/10 border-amber-500/30',
                    High: 'text-orange-300 bg-orange-500/10 border-orange-500/30',
                    Severe: 'text-rose-300 bg-rose-500/10 border-rose-500/30',
                  };
                  return (
                    <div key={level} className={`rounded-xl p-4 border text-center ${colors[level]}`}>
                      <p className="text-2xl font-extrabold">{adminData.system_stress_breakdown[level] ?? 0}</p>
                      <p className="text-xs font-semibold mt-1">{level}</p>
                    </div>
                  );
                })}
              </div>
            </GlassCard>
          )}

          {/* User Management Table */}
          <GlassCard gradient>
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-bold text-white text-base flex items-center gap-2">
                <Users className="w-5 h-5 text-indigo-400" />
                User Management
              </h3>
              <span className="text-xs text-slate-400">{users.length} registered users</span>
            </div>

            {users.length === 0 ? (
              <p className="text-slate-500 text-sm text-center py-8">
                {loading ? 'Loading users…' : 'No users found or insufficient permissions.'}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 text-xs text-slate-400 uppercase tracking-wider">
                      <th className="text-left pb-3 font-semibold">Name</th>
                      <th className="text-left pb-3 font-semibold">Email</th>
                      <th className="text-left pb-3 font-semibold">Role</th>
                      <th className="text-left pb-3 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {users.map((u: any) => (
                      <tr key={u.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-3.5 font-semibold text-white">{u.full_name}</td>
                        <td className="py-3.5 text-slate-400">{u.email}</td>
                        <td className="py-3.5">
                          <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border capitalize ${ROLE_BADGE[u.role] ?? ROLE_BADGE.user}`}>
                            {u.role}
                          </span>
                        </td>
                        <td className="py-3.5">
                          <span className={`flex items-center gap-1.5 text-xs font-semibold ${u.is_active ? 'text-emerald-400' : 'text-slate-500'}`}>
                            <CheckCircle2 className="w-4 h-4" />
                            {u.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </GlassCard>
        </main>
      </div>
    </div>
  );
}
