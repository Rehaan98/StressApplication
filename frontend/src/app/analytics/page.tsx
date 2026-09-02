"use client";

import React, { useEffect, useState } from 'react';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { GlassCard } from '@/components/GlassCard';
import { StatCard } from '@/components/StatCard';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { BarChart2, TrendingUp, Download, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';

const PIE_COLORS: Record<string, string> = {
  Low: '#10b981',
  Moderate: '#f59e0b',
  High: '#f97316',
  Severe: '#ef4444',
};

const TOOLTIP_STYLE = {
  backgroundColor: '#1e293b',
  borderColor: '#475569',
  borderRadius: '8px',
  color: '#fff',
  fontSize: '12px',
};

// Static fallback demo data (used when no assessments exist yet)
const DEMO_TIMELINE = [
  { date: 'Jun 25', pss: 18, hrv: 62, sleep: 7.5 },
  { date: 'Jun 28', pss: 22, hrv: 55, sleep: 7.0 },
  { date: 'Jul 01', pss: 26, hrv: 48, sleep: 6.5 },
  { date: 'Jul 04', pss: 30, hrv: 40, sleep: 5.5 },
  { date: 'Jul 08', pss: 28, hrv: 44, sleep: 6.0 },
  { date: 'Jul 12', pss: 24, hrv: 50, sleep: 6.8 },
  { date: 'Jul 16', pss: 20, hrv: 58, sleep: 7.2 },
  { date: 'Jul 20', pss: 22, hrv: 54, sleep: 7.0 },
];

interface Analytics {
  total_assessments: number;
  latest_stress_level: string;
  average_pss_score: number;
  average_hrv_sdnn: number;
  average_sleep_hours: number;
  stress_distribution: Record<string, number>;
  timeline_trends: any[];
}

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [isDemo, setIsDemo] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await api.getUserAnalytics();
      setAnalytics(data);
      setIsDemo(data.total_assessments === 0);
    } catch {
      setIsDemo(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleDownload = async () => {
    try {
      const blob = await api.downloadCSVReport();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'stress_report.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('Could not download report. Please ensure you are logged in.');
    }
  };

  // Build chart data from real timeline or fall back to demo
  const timelineData = (analytics?.timeline_trends?.length ?? 0) > 0
    ? analytics!.timeline_trends.map(t => ({
        date: t.date,
        pss: t.total_pss,
        hrv: t.hrv_sdnn,
        sleep: t.sleep_hours,
      }))
    : DEMO_TIMELINE;

  const pieData = analytics
    ? Object.entries(analytics.stress_distribution)
        .filter(([, v]) => v > 0)
        .map(([name, value]) => ({ name, value, color: PIE_COLORS[name] ?? '#6366f1' }))
    : [
        { name: 'Low', value: 2, color: '#10b981' },
        { name: 'Moderate', value: 6, color: '#f59e0b' },
        { name: 'High', value: 2, color: '#f97316' },
      ];

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 max-w-7xl mx-auto w-full space-y-8">

          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-3xl font-extrabold text-white flex items-center gap-3">
                <BarChart2 className="w-8 h-8 text-indigo-400" />
                My Stress Trends
                {isDemo && <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-slate-700 text-slate-400 border border-slate-600 ml-2">Sample Data</span>}
              </h1>
              <p className="text-slate-400 mt-2 text-sm">How your stress, sleep and heart rhythm are changing over time.</p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={loadData}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold glass-morphism border border-slate-700 text-slate-300 hover:bg-slate-800/60 transition-all disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 text-slate-400 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
              <button
                onClick={handleDownload}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold glass-morphism border border-slate-700 text-slate-200 hover:bg-slate-800/60 transition-all"
              >
                <Download className="w-4 h-4 text-indigo-400" />
                Export CSV
              </button>
            </div>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
            <StatCard
              title="Total Stress Checks"
              value={analytics?.total_assessments ?? '—'}
              subtitle="All time"
              icon={BarChart2}
              color="indigo"
            />
            <StatCard
              title="Average Stress Score"
              value={analytics ? `${analytics.average_pss_score}` : '—'}
              subtitle={analytics?.average_pss_score >= 27 ? 'High Range' : analytics?.average_pss_score >= 14 ? 'Moderate Range' : 'Low Range'}
              icon={TrendingUp}
              color="amber"
            />
            <StatCard
              title="Heart Rhythm Calmness"
              value={analytics ? `${analytics.average_hrv_sdnn} ms` : '—'}
              subtitle="Calmer above 60 ms"
              icon={TrendingUp}
              color="cyan"
            />
            <StatCard
              title="Average Sleep"
              value={analytics ? `${analytics.average_sleep_hours} hrs` : '—'}
              subtitle="Recommended: 7–9 hrs"
              icon={TrendingUp}
              color="rose"
            />
          </div>

          {/* PSS Score Timeline */}
          <GlassCard gradient>
            <h3 className="font-bold text-white mb-5 text-base">My Stress Score Over Time</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={timelineData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} domain={[0, 40]} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Line type="monotone" dataKey="pss" stroke="#6366f1" strokeWidth={2.5} dot={{ fill: '#6366f1', r: 4 }} name="Stress Score (0–40)" />
              </LineChart>
            </ResponsiveContainer>
          </GlassCard>

          {/* HRV & Stress Distribution */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GlassCard gradient>
              <h3 className="font-bold text-white mb-5 text-base">Heart Rhythm Trend</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={timelineData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Bar dataKey="hrv" fill="#06b6d4" radius={[4, 4, 0, 0]} name="Calmness (ms)" />
                </BarChart>
              </ResponsiveContainer>
            </GlassCard>

            <GlassCard gradient>
              <h3 className="font-bold text-white mb-5 text-base">My Stress Level Mix</h3>
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      nameKey="name"
                      label={({ name, value }) => `${name}: ${value}`}
                      labelLine={false}
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Legend
                      iconType="circle"
                      iconSize={10}
                      formatter={(v) => <span style={{ color: '#cbd5e1', fontSize: '12px' }}>{v}</span>}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-slate-500 text-sm text-center py-8">No prediction data yet.</p>
              )}
            </GlassCard>
          </div>

          {/* Sleep Quality Timeline */}
          <GlassCard gradient>
            <h3 className="font-bold text-white mb-5 text-base">My Sleep Over Time</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={timelineData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} domain={[4, 10]} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Line type="monotone" dataKey="sleep" stroke="#a78bfa" strokeWidth={2.5} dot={{ fill: '#a78bfa', r: 4 }} name="Sleep (hrs)" />
              </LineChart>
            </ResponsiveContainer>
          </GlassCard>

        </main>
      </div>
    </div>
  );
}
