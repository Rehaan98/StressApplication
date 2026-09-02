"use client";

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { GlassCard } from '@/components/GlassCard';
import { StatCard } from '@/components/StatCard';
import { StressGauge } from '@/components/StressGauge';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { Activity, Heart, Moon, Sun, ClipboardList, Sparkles, Eye, ScanFace } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';

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
}

interface FacialHistoryItem {
  id: string;
  dominant_emotion: string;
  stress_score: number;
  stress_level: string;
  confidence_score: number;
  created_at: string;
}

const STRESS_GAUGE_MAP: Record<string, number> = {
  Low: 18, Moderate: 48, High: 73, Severe: 92,
};

const FACIAL_EMOJI: Record<string, string> = {
  happiness: '😊', neutral: '😐', surprise: '😲', sadness: '😢',
  anger: '😠', disgust: '🤢', fear: '😨', contempt: '😏',
};

export default function DashboardPage() {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [facialHistory, setFacialHistory] = useState<FacialHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      api.getUserAnalytics(),
      api.getFacialHistory(30),
    ]).then(([a, f]) => {
      if (a.status === 'fulfilled') setAnalytics(a.value);
      if (f.status === 'fulfilled') setFacialHistory(f.value.items ?? []);
    }).finally(() => setLoading(false));
  }, []);

  const stressLevel =
    analytics?.latest_stress_level && analytics.latest_stress_level !== 'Normal'
      ? analytics.latest_stress_level
      : 'No Data';
  const gaugeScore = STRESS_GAUGE_MAP[stressLevel] ?? 0;

  const facialChart = [...facialHistory].reverse().map((h, i) => ({
    name: i === 0 ? 'Earliest' : i === facialHistory.length - 1 ? 'Latest' : '',
    score: h.stress_score,
    emotion: h.dominant_emotion,
  }));

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />

      <div className="flex flex-1">
        <Sidebar />

        <main className="flex-1 p-8 max-w-7xl mx-auto space-y-8">
          {/* Welcome Banner */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-3xl bg-gradient-to-r from-indigo-900/40 via-slate-900 to-cyan-900/30 border border-indigo-500/30">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-white">
                Welcome back, {user?.full_name?.split(' ')[0] ?? 'there'}
              </h1>
              <p className="text-sm text-slate-300 mt-1">Here is how your stress levels are looking right now</p>
            </div>
            <div className="flex items-center gap-3">
              <Link href="/facial" className="px-5 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-violet-600 to-cyan-500 hover:from-violet-500 hover:to-cyan-400 text-white shadow-lg glow-primary flex items-center gap-2 transition-all">
                <ScanFace className="w-4 h-4" />
                Face Stress Scan
              </Link>
              <Link href="/assessment" className="px-5 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white shadow-lg glow-primary flex items-center gap-2 transition-all">
                <ClipboardList className="w-4 h-4" />
                Take a Stress Check
              </Link>
            </div>
          </div>

          {/* Top Metric Cards Grid */}
          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-28 rounded-2xl glass-morphism animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              <StatCard
                title="Current Stress Level"
                value={stressLevel}
                subtitle={`${analytics?.total_assessments ?? 0} checks so far`}
                icon={Activity}
                color="amber"
              />
              <StatCard
                title="Heart Rhythm Calmness"
                value={`${analytics?.average_hrv_sdnn ?? 0} ms`}
                subtitle="Higher = calmer"
                icon={Heart}
                color="rose"
              />
              <StatCard
                title="Sleep Duration"
                value={`${analytics?.average_sleep_hours ?? 0} hrs`}
                subtitle="Aim for 7–8 hrs"
                icon={Moon}
                color="cyan"
              />
              <StatCard
                title="Stress Score (0–40)"
                value={`${analytics?.average_pss_score ?? 0}`}
                subtitle={analytics?.average_pss_score >= 27 ? 'High strain' : analytics?.average_pss_score >= 14 ? 'Moderate strain' : 'Low strain'}
                icon={Sun}
                color="indigo"
              />
            </div>
          )}

          {/* Facial scan strip */}
          {analytics && (analytics.total_facial_analyses ?? 0) > 0 && (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl glass-morphism border border-violet-500/30">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-violet-500/15 text-violet-300 border border-violet-500/30">
                  <ScanFace className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-sm font-bold text-white">
                    Latest Face Scan: <span className={`
                      ${analytics.latest_facial_stress_level === 'Low' ? 'text-emerald-400'
                        : analytics.latest_facial_stress_level === 'Moderate' ? 'text-amber-400'
                        : analytics.latest_facial_stress_level === 'High' ? 'text-orange-400'
                        : 'text-rose-400'}`}>
                      {analytics.latest_facial_stress_level} · {analytics.latest_facial_stress_score}/100
                    </span>
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    How you looked: <span className="text-violet-300 font-semibold capitalize">{analytics.latest_facial_emotion}</span> · {analytics.total_facial_analyses} readings so far
                  </p>
                </div>
              </div>
              <Link href="/facial" className="text-xs font-bold px-4 py-2 rounded-xl bg-violet-500/20 text-violet-300 border border-violet-500/40 hover:bg-violet-500/30 transition-all text-center">
                Scan Again →
              </Link>
            </div>
          )}

          {/* Facial scan trend widget */}
          {facialHistory.length > 0 && (
            <GlassCard gradient className="border border-violet-500/20">
              <div className="flex items-center justify-between border-b border-slate-700/50 pb-3 mb-4">
                <div className="flex items-center gap-2">
                  <ScanFace className="w-5 h-5 text-violet-400" />
                  <h3 className="font-bold text-white text-base">My Face Scan Trend</h3>
                </div>
                <span className="text-xs text-slate-400">{facialHistory.length} recent scans</span>
              </div>
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={facialChart} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="facialGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.5} />
                        <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#33415555" />
                    <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                    <YAxis domain={[0, 100]} stroke="#64748b" fontSize={11} />
                    <Tooltip
                      contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, fontSize: 12 }}
                      labelStyle={{ color: '#94a3b8' }}
                      formatter={(v: any, name: any) => [`${v} / 100`, 'Face Scan Stress']}
                    />
                    <Area type="monotone" dataKey="score" stroke="#8b5cf6" strokeWidth={2.5} fill="url(#facialGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-3 pt-3 border-t border-slate-700/50 flex flex-wrap gap-2 text-xs">
                {facialHistory.slice(0, 10).map((h, i) => (
                  <span key={i} className="px-2 py-1 rounded-lg bg-slate-900 border border-slate-700 text-slate-300">
                    {FACIAL_EMOJI[h.dominant_emotion] ?? '😶'} {h.stress_score}
                  </span>
                ))}
              </div>
            </GlassCard>
          )}

          {/* Main Dashboard Widgets Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Stress Risk Gauge Widget */}
            <GlassCard className="lg:col-span-1 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-slate-700/50 pb-3 mb-4">
                  <h3 className="font-bold text-white text-base">Real-Time Risk Gauge</h3>
                  {stressLevel !== 'No Data' && (
                    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold border
                      ${stressLevel === 'Low' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                        : stressLevel === 'Moderate' ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                        : stressLevel === 'High' ? 'bg-orange-500/20 text-orange-300 border-orange-500/30'
                        : 'bg-rose-500/20 text-rose-300 border-rose-500/30'}`}>
                      {stressLevel}
                    </span>
                  )}
                </div>

                {analytics && analytics.total_assessments > 0 ? (
                  <StressGauge level={stressLevel} score={gaugeScore} />
                ) : (
                  <div className="flex flex-col items-center justify-center py-8 text-slate-400 text-sm text-center">
                    <ClipboardList className="w-10 h-10 text-slate-600 mb-3" />
                    <p>No assessments yet.</p>
                    <Link href="/assessment" className="mt-2 text-indigo-400 font-semibold hover:underline text-xs">
                      Take your first assessment →
                    </Link>
                  </div>
                )}
              </div>

              <div className="mt-6 pt-4 border-t border-slate-700/50 space-y-2">
                <Link href="/explainability" className="flex items-center justify-between text-xs font-semibold text-indigo-300 hover:text-white p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 transition-all">
                  <span className="flex items-center gap-1.5"><Eye className="w-4 h-4 text-indigo-400" /> See why your score is what it is</span>
                  <span>→</span>
                </Link>
              </div>
            </GlassCard>

            {/* Stress Distribution + RAG Spotlight */}
            <GlassCard className="lg:col-span-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-slate-700/50 pb-3 mb-4">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-cyan-400" />
                    <h3 className="font-bold text-white text-base">Stress Breakdown & Coping Help</h3>
                  </div>
                  <Link href="/rag-coping" className="text-xs font-semibold text-cyan-400 hover:underline">See all exercises →</Link>
                </div>

                {/* Stress distribution breakdown */}
                {analytics && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
                    {Object.entries(analytics.stress_distribution).map(([level, count]) => {
                      const colors: Record<string, string> = {
                        Low: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30',
                        Moderate: 'text-amber-300 bg-amber-500/10 border-amber-500/30',
                        High: 'text-orange-300 bg-orange-500/10 border-orange-500/30',
                        Severe: 'text-rose-300 bg-rose-500/10 border-rose-500/30',
                      };
                      return (
                        <div key={level} className={`rounded-xl p-3 border text-center ${colors[level] ?? 'text-slate-300 bg-slate-800 border-slate-700'}`}>
                          <p className="text-xl font-extrabold">{count}</p>
                          <p className="text-xs font-semibold mt-0.5">{level}</p>
                        </div>
                      );
                    })}
                  </div>
                )}

                <div className="space-y-3">
                  <div className="p-4 rounded-xl bg-slate-900/80 border border-cyan-500/30">
                    <span className="text-xs font-semibold px-2.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">Breathing & calm</span>
                    <h4 className="font-bold text-white text-sm mt-2">Box Breathing to Calm Your Nerves</h4>
                    <p className="text-xs text-slate-300 mt-1">A simple 4-4-4-4 breathing pattern that helps your body relax and steadies your heart rhythm.</p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-700">
                    <span className="text-xs font-semibold px-2.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">Thinking & mindset</span>
                    <h4 className="font-bold text-white text-sm mt-2">Easier Thinking When Overwhelmed</h4>
                    <p className="text-xs text-slate-300 mt-1">A simple way to catch stressful thoughts and break big problems into small 5-minute steps.</p>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-700/50 flex justify-end">
                <Link href="/rag-coping" className="text-xs font-bold px-4 py-2 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30 transition-all">
                  Open Coping Help
                </Link>
              </div>
            </GlassCard>
          </div>

          {/* Recent Timeline */}
          {analytics && analytics.timeline_trends.length > 0 && (
            <GlassCard gradient>
              <h3 className="font-bold text-white text-base mb-4">Your Recent Checks</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-700 text-slate-400 uppercase tracking-wider">
                      <th className="text-left pb-3 font-semibold">Date</th>
                      <th className="text-left pb-3 font-semibold">Stress Level</th>
                      <th className="text-left pb-3 font-semibold">Stress Score</th>
                      <th className="text-left pb-3 font-semibold">Heart Rate</th>
                      <th className="text-left pb-3 font-semibold">Heart Rhythm</th>
                      <th className="text-left pb-3 font-semibold">Sleep (hrs)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {analytics.timeline_trends.slice(-8).reverse().map((row, i) => {
                      const levelColors: Record<string, string> = {
                        Low: 'text-emerald-400', Moderate: 'text-amber-400',
                        High: 'text-orange-400', Severe: 'text-rose-400',
                      };
                      return (
                        <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                          <td className="py-2.5 text-slate-300">{row.date}</td>
                          <td className={`py-2.5 font-bold ${levelColors[row.stress_level] ?? 'text-slate-300'}`}>{row.stress_level}</td>
                          <td className="py-2.5 text-slate-300">{row.total_pss}</td>
                          <td className="py-2.5 text-slate-300">{row.heart_rate}</td>
                          <td className="py-2.5 text-slate-300">{row.hrv_sdnn}</td>
                          <td className="py-2.5 text-slate-300">{row.sleep_hours}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </GlassCard>
          )}
        </main>
      </div>
    </div>
  );
}
