"use client";

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { GlassCard } from '@/components/GlassCard';
import { StatCard } from '@/components/StatCard';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { BarChart2, TrendingUp, Download, RefreshCw, ScanFace, Layers } from 'lucide-react';
import { api } from '@/lib/api';
import { useLiveData } from '@/lib/liveData';

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
  total_facial_analyses?: number;
  latest_facial_emotion?: string | null;
  latest_facial_stress_level?: string | null;
  latest_facial_stress_score?: number | null;
  total_multimodal_assessments?: number;
  latest_multimodal_modalities?: string[] | null;
  latest_multimodal_category?: string | null;
  latest_multimodal_score?: number | null;
  latest_multimodal_at?: string | null;
  multimodal_trends?: { date: string; category: string; score: number; modalities: string[] }[];
}

interface FacialHistoryItem {
  id: string;
  dominant_emotion: string;
  stress_score: number;
  stress_level: string;
  created_at: string;
}

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [facialHistory, setFacialHistory] = useState<FacialHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isDemo, setIsDemo] = useState(false);
  const [lastSynced, setLastSynced] = useState<Date | null>(null);
  const inFlight = useRef(false);
  const analyticsRef = useRef<Analytics | null>(null);

  const loadData = useCallback(async (showSpinner = false) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (showSpinner) setLoading(true);
    try {
      const [analyticsRes, facialRes] = await Promise.allSettled([
        api.getUserAnalytics(),
        api.getFacialHistory(60),
      ]);

      if (analyticsRes.status === 'fulfilled') {
        const data = analyticsRes.value;
        analyticsRef.current = data;
        setAnalytics(data);
        setIsDemo(data.total_assessments === 0 && (data.total_facial_analyses ?? 0) === 0);
      } else if (!analyticsRef.current) {
        setIsDemo(true);
      }

      if (facialRes.status === 'fulfilled') {
        setFacialHistory(facialRes.value.items ?? []);
      }

      setLastSynced(new Date());
    } catch {
      if (!analyticsRef.current) setIsDemo(true);
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  useLiveData(() => loadData(false), { intervalMs: 30000 });

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

  // Build chart data from real recent results; use sample data only for a
  // completely new account so real facial-only users never see fake trends.
  const timelineData = (analytics?.timeline_trends?.length ?? 0) > 0
    ? analytics!.timeline_trends.map(t => ({
        date: t.date,
        pss: t.total_pss,
        hrv: t.hrv_sdnn,
        sleep: t.sleep_hours,
      }))
    : isDemo ? DEMO_TIMELINE : [];

  const pieData = analytics
    ? Object.entries(analytics.stress_distribution)
        .filter(([, v]) => v > 0)
        .map(([name, value]) => ({ name, value, color: PIE_COLORS[name] ?? '#6366f1' }))
    : isDemo
      ? [
          { name: 'Low', value: 2, color: '#10b981' },
          { name: 'Moderate', value: 6, color: '#f59e0b' },
          { name: 'High', value: 2, color: '#f97316' },
        ]
      : [];

  const facialTrend = [...facialHistory].reverse().map((item) => ({
    name: new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    when: new Date(item.created_at).toLocaleString(),
    score: item.stress_score,
    level: item.stress_level,
    emotion: item.dominant_emotion,
  }));
  const hasFacialTrend = facialTrend.length > 0;
  const multimodalTrend = analytics?.multimodal_trends ?? [];
  const hasMultimodalTrend = multimodalTrend.length > 0;

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
              {lastSynced && (
                <p className="text-slate-500 mt-1 text-[11px]">
                  Synced with your latest results at {lastSynced.toLocaleTimeString()}
                </p>
              )}
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => loadData(true)}
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
              title="Questionnaire Checks"
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
            {timelineData.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={timelineData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} domain={[0, 40]} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Line type="monotone" dataKey="pss" stroke="#6366f1" strokeWidth={2.5} dot={{ fill: '#6366f1', r: 4 }} name="Stress Score (0–40)" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-slate-500 text-sm text-center py-12">
                No questionnaire checks yet. Take a stress check to start this trend.
              </p>
            )}
            <p className="text-[11px] text-slate-500 mt-2">
              A check is placed at the time of its latest saved result, so questionnaires reused in a newer combined check still appear as recent.
            </p>
          </GlassCard>

          {/* HRV & Stress Distribution */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GlassCard gradient>
              <h3 className="font-bold text-white mb-5 text-base">Heart Rhythm Trend</h3>
              {timelineData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={timelineData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
                    <YAxis stroke="#64748b" fontSize={11} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Bar dataKey="hrv" fill="#06b6d4" radius={[4, 4, 0, 0]} name="Calmness (ms)" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-slate-500 text-sm text-center py-12">No heart rhythm checks yet.</p>
              )}
            </GlassCard>

            <GlassCard gradient>
              <h3 className="font-bold text-white text-base">My Stress Level Mix</h3>
              <p className="text-[11px] text-slate-500 mb-4">Latest result for each questionnaire check, using the combined result when available.</p>
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
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Legend
                      iconType="circle"
                      iconSize={10}
                      formatter={(v: any, entry: any) => (
                        <span style={{ color: '#cbd5e1', fontSize: '12px' }}>
                          {v}: {entry?.payload?.value ?? 0}
                        </span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-slate-500 text-sm text-center py-8">No prediction data yet.</p>
              )}
            </GlassCard>
          </div>

          {/* Facial Stress Timeline */}
          <GlassCard gradient className="border border-violet-500/20">
            <div className="flex items-center justify-between flex-wrap gap-2 mb-5">
              <h3 className="font-bold text-white text-base flex items-center gap-2">
                <ScanFace className="w-5 h-5 text-violet-400" /> My Face Scan Trend
              </h3>
              {hasFacialTrend && (
                <span className="text-xs text-slate-400">
                  {facialHistory.length} recent scans · latest {facialTrend[facialTrend.length - 1]?.score}/100
                </span>
              )}
            </div>
            {hasFacialTrend ? (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={facialTrend} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <defs>
                    <linearGradient id="analyticsFacialGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.45} />
                      <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    labelFormatter={(_label, payload) => payload?.[0]?.payload?.when ?? _label}
                    formatter={(value: any) => [`${value} / 100`, 'Face scan stress']}
                  />
                  <Area type="monotone" dataKey="score" stroke="#8b5cf6" strokeWidth={2.5} fill="url(#analyticsFacialGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-slate-500 text-sm text-center py-12">
                No face scans yet. Run a live face scan to add recent readings here.
              </p>
            )}
          </GlassCard>

          {/* Synchronized multimodal trend */}
          {hasMultimodalTrend && (
            <GlassCard gradient className="border border-cyan-500/20">
              <div className="flex items-center justify-between flex-wrap gap-2 mb-5">
                <h3 className="font-bold text-white text-base flex items-center gap-2">
                  <Layers className="w-5 h-5 text-cyan-400" /> My Check Trend
                </h3>
                <span className="text-xs text-slate-400">
                  {analytics?.total_multimodal_assessments ?? multimodalTrend.length} saved check{(analytics?.total_multimodal_assessments ?? multimodalTrend.length) === 1 ? '' : 's'}
                  {analytics?.latest_multimodal_category
                    ? ` · latest ${analytics.latest_multimodal_category} ${analytics.latest_multimodal_score ?? '—'}/100${(analytics.latest_multimodal_modalities?.length ?? 0) > 0 ? ` (${analytics.latest_multimodal_modalities!.join(', ')})` : ''}`
                    : ''}
                </span>
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={multimodalTrend} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <defs>
                    <linearGradient id="analyticsMultiGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.45} />
                      <stop offset="100%" stopColor="#06b6d4" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={(value: any, _name, item: any) => [
                      `${value} / 100 · ${item?.payload?.category ?? ''}`,
                      `Combined (${(item?.payload?.modalities ?? []).join(', ') || 'no modalities'})`,
                    ]}
                  />
                  <Area type="monotone" dataKey="score" stroke="#06b6d4" strokeWidth={2.5} fill="url(#analyticsMultiGrad)" />
                </AreaChart>
              </ResponsiveContainer>
              <p className="text-[11px] text-slate-500 mt-2">
                Showing your latest {multimodalTrend.length} saved checks. They can combine questionnaire, voice, and face readings; single-sensor checks are labeled by their modalities.
              </p>
            </GlassCard>
          )}

          {/* Sleep Quality Timeline */}
          <GlassCard gradient>
            <h3 className="font-bold text-white mb-5 text-base">My Sleep Over Time</h3>
            {timelineData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={timelineData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} domain={[4, 10]} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Line type="monotone" dataKey="sleep" stroke="#a78bfa" strokeWidth={2.5} dot={{ fill: '#a78bfa', r: 4 }} name="Sleep (hrs)" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-slate-500 text-sm text-center py-12">No sleep data yet.</p>
            )}
          </GlassCard>

        </main>
      </div>
    </div>
  );
}
