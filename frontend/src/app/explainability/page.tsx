"use client";

import React, { useCallback, useEffect, useRef, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { GlassCard } from '@/components/GlassCard';
import { ShapBarChart } from '@/components/ShapBarChart';
import { LimeImpactList } from '@/components/LimeImpactList';
import { friendlyFeature } from '@/lib/labels';
import { Eye, GitBranch, Info, AlertCircle, TrendingUp, TrendingDown, Minus, RefreshCw, Layers } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { api } from '@/lib/api';
import { useLiveData } from '@/lib/liveData';
import Link from 'next/link';

const DEMO_SHAP = [
  { feature: 'total_pss', shap_value: 0.312, impact: 'increases_stress' },
  { feature: 'hrv_sdnn', shap_value: -0.218, impact: 'reduces_stress' },
  { feature: 'anxiety_score', shap_value: 0.187, impact: 'increases_stress' },
  { feature: 'composite_strain_index', shap_value: 0.165, impact: 'increases_stress' },
  { feature: 'sleep_hours', shap_value: -0.142, impact: 'reduces_stress' },
  { feature: 'work_stress_factor', shap_value: 0.121, impact: 'increases_stress' },
  { feature: 'sentiment_score', shap_value: -0.087, impact: 'reduces_stress' },
];

const DEMO_LIME = [
  { rule: 'total_pss > 22.0', weight: 0.289, effect: 'increases_stress' },
  { rule: 'hrv_sdnn <= 48.5', weight: 0.198, effect: 'increases_stress' },
  { rule: 'anxiety_score > 6.0', weight: 0.172, effect: 'increases_stress' },
  { rule: 'sleep_hours <= 6.5', weight: 0.155, effect: 'increases_stress' },
  { rule: 'sentiment_score <= 0.1', weight: 0.088, effect: 'increases_stress' },
];

const DEMO_GLOBAL_IMPORTANCE = [
  { feature: 'total_pss', importance: 0.28 },
  { feature: 'composite_strain_index', importance: 0.22 },
  { feature: 'hrv_sdnn', importance: 0.18 },
  { feature: 'anxiety_score', importance: 0.14 },
  { feature: 'sleep_deficiency_index', importance: 0.09 },
  { feature: 'work_stress_factor', importance: 0.05 },
  { feature: 'sentiment_score', importance: 0.04 },
];

interface TrendPoint {
  date: string;
  stress_level: string;
  total_pss: number;
  hrv_sdnn: number;
  sleep_hours: number;
  confidence_score: number;
}

interface UserAnalytics {
  total_assessments: number;
  latest_stress_level: string;
  timeline_trends: TrendPoint[];
  total_multimodal_assessments?: number;
  latest_multimodal_id?: string | null;
  latest_multimodal_modalities?: string[] | null;
  latest_multimodal_category?: string | null;
  latest_multimodal_score?: number | null;
  latest_multimodal_at?: string | null;
}

interface Explanation {
  drivers: any[];
  rules: any[];
  predictedClass: string;
  createdAt?: string | null;
  confidence?: number | null;
}

const average = (values: number[]) =>
  values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;

const parseServerDate = (value?: string | null): Date | null => {
  if (!value) return null;
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasZone ? value : `${value}Z`);
};

async function fetchExplanation(predictionId: string): Promise<Explanation> {
  const [xaiRes, detailRes] = await Promise.allSettled([
    api.getExplainability(predictionId),
    api.getPrediction(predictionId),
  ]);
  const xai: any = xaiRes.status === 'fulfilled' ? xaiRes.value : null;
  const detail: any = detailRes.status === 'fulfilled' ? detailRes.value : null;

  return {
    drivers: (xai?.top_drivers?.length ? xai.top_drivers : detail?.shap_explanation?.top_drivers) ?? [],
    rules: (xai?.lime_rules?.length ? xai.lime_rules : detail?.lime_explanation?.lime_rules) ?? [],
    predictedClass: xai?.predicted_class ?? detail?.stress_level ?? '',
    createdAt: detail?.created_at ?? null,
    confidence: detail?.confidence_score ?? null,
  };
}

function ExplainabilityContent() {
  const searchParams = useSearchParams();
  const predId = searchParams.get('id');
  const [activeTab, setActiveTab] = useState<'shap' | 'lime' | 'global'>('shap');
  const [shapDrivers, setShapDrivers] = useState<any[]>([]);
  const [limeRules, setLimeRules] = useState<any[]>([]);
  const [predictedClass, setPredictedClass] = useState<string>('');
  const [explainedAt, setExplainedAt] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<UserAnalytics | null>(null);
  const [combinedDetail, setCombinedDetail] = useState<any>(null);
  const [isDemo, setIsDemo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [lastSynced, setLastSynced] = useState<Date | null>(null);
  const inFlight = useRef(false);
  const analyticsRef = useRef<UserAnalytics | null>(null);

  const load = useCallback(async (showSpinner = false) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (showSpinner) setLoading(true);

    try {
      const [predsRes, analyticsRes] = await Promise.allSettled([
        api.listPredictions(10),
        api.getUserAnalytics(),
      ]);

      if (analyticsRes.status === 'fulfilled') {
        analyticsRef.current = analyticsRes.value;
        setAnalytics(analyticsRes.value);
      }

      const predictions: any[] = predsRes.status === 'fulfilled' && Array.isArray(predsRes.value)
        ? predsRes.value
        : [];
      const requestedId = predId && predId !== 'demo' ? predId : null;
      const latestId = predictions[0]?.id ?? null;
      const candidateIds = requestedId
        ? [requestedId, ...predictions.map((p) => p.id).filter((id) => id !== requestedId)]
        : predictions.map((p) => p.id);

      let explanation: Explanation | null = null;
      for (const id of candidateIds) {
        try {
          const candidate = await fetchExplanation(id);
          const hasExplanation = candidate.drivers.length > 0 || candidate.rules.length > 0;
          if (hasExplanation) {
            explanation = candidate;
            break;
          }
          if (!explanation) explanation = candidate;
        } catch {
          // Stale/removed prediction id — try the next most recent one.
        }
      }

      if (explanation && (explanation.predictedClass || explanation.drivers.length || explanation.rules.length)) {
        setShapDrivers(explanation.drivers);
        setLimeRules(explanation.rules);
        setPredictedClass(explanation.predictedClass);
        setExplainedAt(explanation.createdAt ?? null);
        setIsDemo(false);
      } else if (!latestId) {
        setShapDrivers(DEMO_SHAP);
        setLimeRules(DEMO_LIME);
        setPredictedClass('Moderate');
        setExplainedAt(null);
        setIsDemo(true);
      } else {
        setShapDrivers([]);
        setLimeRules([]);
        setPredictedClass('');
        setExplainedAt(null);
        setIsDemo(false);
      }

      setLastSynced(new Date());
    } catch {
      if (!analyticsRef.current) {
        setShapDrivers(DEMO_SHAP);
        setLimeRules(DEMO_LIME);
        setPredictedClass('Moderate');
        setIsDemo(true);
      }
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }, [predId]);

  useEffect(() => { load(); }, [load]);
  useLiveData(() => load(false), { intervalMs: 30000 });

  useEffect(() => {
    const id = analytics?.latest_multimodal_id;
    if (!id) {
      setCombinedDetail(null);
      return;
    }
    let cancelled = false;
    api.multimodalGet(id)
      .then((detail: any) => { if (!cancelled) setCombinedDetail(detail); })
      .catch(() => { if (!cancelled) setCombinedDetail(null); });
    return () => { cancelled = true; };
  }, [analytics?.latest_multimodal_id]);

  const maxAbs = Math.max(...shapDrivers.map(d => Math.abs(d.shap_value ?? 0)), 0.001);
  const globalImportance = shapDrivers.length > 0
    ? [...shapDrivers]
        .map(d => ({ feature: d.feature, importance: Math.abs(d.shap_value ?? 0) / maxAbs }))
        .sort((a, b) => b.importance - a.importance)
        .slice(0, 7)
    : DEMO_GLOBAL_IMPORTANCE;

  const topAmplifier = shapDrivers.find(d => (d.shap_value ?? 0) > 0);
  const topProtector = shapDrivers.find(d => (d.shap_value ?? 0) < 0);
  const latestCheckDate = parseServerDate(analytics?.latest_multimodal_at);
  const explanationDate = parseServerDate(explainedAt);
  const latestCheckIsNewer = Boolean(
    latestCheckDate && explanationDate && latestCheckDate.getTime() > explanationDate.getTime()
  );
  const latestCheckModalities: string[] = combinedDetail?.available_modalities?.length
    ? combinedDetail.available_modalities
    : analytics?.latest_multimodal_modalities ?? [];

  // Recent trend: the page follows the newest AI result and shows how it fits
  // the last checks, so "why this score" is always backed by recent results.
  const trendPoints = (analytics?.timeline_trends ?? []).slice(-10);
  const latestPoint = trendPoints[trendPoints.length - 1];
  const split = Math.floor(trendPoints.length / 2);
  const earlierAvg = average(trendPoints.slice(0, split).map((point) => point.total_pss));
  const laterAvg = average(trendPoints.slice(split).map((point) => point.total_pss));
  const trendChange = trendPoints.length > 1 ? laterAvg - earlierAvg : 0;
  const trendDirection = trendChange < -0.75 ? 'down' : trendChange > 0.75 ? 'up' : 'flat';
  const trendLabel = trendDirection === 'down'
    ? 'Stress easing'
    : trendDirection === 'up'
      ? 'Stress rising'
      : 'Holding steady';
  const trendIcon = trendDirection === 'down'
    ? TrendingDown
    : trendDirection === 'up'
      ? TrendingUp
      : Minus;
  const trendTone = trendDirection === 'down'
    ? 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10'
    : trendDirection === 'up'
      ? 'text-rose-300 border-rose-500/40 bg-rose-500/10'
      : 'text-slate-300 border-slate-600 bg-slate-800';
  const TrendIcon = trendIcon;
  const explainedDate = explainedAt
    ? new Date(explainedAt).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
    : null;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 max-w-6xl mx-auto w-full space-y-8">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h1 className="text-3xl font-extrabold text-white flex items-center gap-3">
              <Eye className="w-8 h-8 text-cyan-400" />
              Why This Score
            </h1>
            <div className="flex items-center gap-2 flex-wrap">
              {loading ? (
                <span className="text-xs px-3 py-1 rounded-full bg-slate-700 text-slate-400 border border-slate-600">Loading…</span>
              ) : isDemo ? (
                <span className="text-xs px-3 py-1 rounded-full bg-slate-700 text-slate-400 border border-slate-600">Demo Data</span>
              ) : (
                <span className="px-4 py-1.5 rounded-full text-sm font-bold border uppercase tracking-wider bg-cyan-500/10 border-cyan-500/40 text-cyan-300">
                  {predictedClass || 'Latest'} Prediction · {explainedDate ? `Saved ${explainedDate}` : 'No Saved Result'}
                </span>
              )}
              <button
                onClick={() => load(true)}
                disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold glass-morphism border border-slate-700 text-slate-300 hover:bg-slate-800/60 transition-all disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
          </div>
          <p className="text-slate-400 mt-2 text-sm -mt-5">
            We believe your stress result should never be a mystery. This page explains, in plain words,
            what is affecting your newest saved prediction and how it fits your recent questionnaire trend.
          </p>
          {lastSynced && (
            <p className="text-[11px] text-slate-500 -mt-6">
              Synced with your latest results at {lastSynced.toLocaleTimeString()}
            </p>
          )}

          {isDemo && !loading && (
            <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
              <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <p className="text-xs text-amber-200">
                No results found yet. Take a quick{' '}
                <Link href="/assessment" className="underline font-bold hover:text-amber-100">stress check</Link>{' '}
                and we will explain your score in plain words.
              </p>
            </div>
          )}

          {/* Plain-language banner */}
          <GlassCard className="border border-indigo-500/30">
            <div className="flex items-start gap-4">
              <Info className="w-6 h-6 text-indigo-400 shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-white text-sm mb-1">How we explain your score</h3>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Your stress result is calculated from your answers, your body signals and, if you used it,
                  your facial expressions. We then look at <strong className="text-indigo-300">what is pushing your score up</strong>{' '}
                  (like long work hours, poor sleep or high anxiety) and{' '}
                  <strong className="text-cyan-300">what is pulling it down</strong> (like good sleep or a calm heart rhythm).
                  The reasons below are taken from your most recent saved AI result, and the trend panel keeps
                  them anchored to your latest checks.
                </p>
              </div>
            </div>
          </GlassCard>

          {/* Recent trend context */}
          {trendPoints.length > 1 && (
            <GlassCard gradient className="border border-indigo-500/20">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    <TrendIcon className="w-5 h-5 text-indigo-400" /> Your Questionnaire Trend
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Based on your last {trendPoints.length} questionnaire checks · newest {latestPoint?.date ?? '—'}
                  </p>
                </div>
                <span className={`text-xs px-3 py-1 rounded-full font-bold border ${trendTone}`}>
                  {trendLabel}
                </span>
              </div>

              <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-700">
                  <p className="text-[11px] uppercase tracking-wider text-slate-400">Latest check</p>
                  <p className="text-xl font-extrabold text-white mt-0.5">
                    {latestPoint?.total_pss ?? '—'}<span className="text-xs text-slate-400 font-semibold"> / 40</span>
                  </p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    {latestPoint?.stress_level ?? '—'} · {latestPoint?.date ?? '—'}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-700">
                  <p className="text-[11px] uppercase tracking-wider text-slate-400">Recent change</p>
                  <p className={`text-xl font-extrabold mt-0.5 ${trendDirection === 'down' ? 'text-emerald-300' : trendDirection === 'up' ? 'text-rose-300' : 'text-slate-200'}`}>
                    {trendChange > 0 ? '+' : ''}{trendChange.toFixed(1)}
                    <span className="text-xs text-slate-400 font-semibold"> pts</span>
                  </p>
                  <p className="text-[11px] text-slate-400 mt-0.5">First half vs second half</p>
                </div>
                <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-700">
                  <p className="text-[11px] uppercase tracking-wider text-slate-400">AI result used</p>
                  <p className="text-sm font-bold text-white mt-1">{explainedDate ?? 'Checking…'}</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    {topAmplifier ? `Main booster: ${friendlyFeature(topAmplifier.feature)}` : 'No booster detected'}
                  </p>
                </div>
              </div>

              <div className="h-28 mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trendPoints} margin={{ top: 5, right: 10, left: -24, bottom: 0 }}>
                    <defs>
                      <linearGradient id="explainTrendGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#6366f1" stopOpacity={0.45} />
                        <stop offset="100%" stopColor="#6366f1" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#33415555" />
                    <XAxis dataKey="date" stroke="#64748b" fontSize={10} />
                    <YAxis domain={[0, 40]} stroke="#64748b" fontSize={10} />
                    <Tooltip
                      contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, fontSize: 12 }}
                      labelStyle={{ color: '#94a3b8' }}
                      formatter={(value: any) => [`${value} / 40`, 'Stress score']}
                    />
                    <Area type="monotone" dataKey="total_pss" stroke="#818cf8" strokeWidth={2.5} fill="url(#explainTrendGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <p className="text-[11px] text-slate-500 mt-2">
                The SHAP and LIME reasons below come from your newest available saved questionnaire prediction,
                so this page stays in sync with the same recent results shown on your dashboard and My Trends.
              </p>
            </GlassCard>
          )}

          {/* Latest synchronized voice + face + questionnaire result */}
          {analytics?.latest_multimodal_category && (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl glass-morphism border border-cyan-500/30">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-sm font-bold text-white">
                    Newest saved check: {analytics.latest_multimodal_category} · {analytics.latest_multimodal_score ?? '—'}/100
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Based on {latestCheckModalities.length > 0 ? latestCheckModalities.join(', ') : 'saved inputs'}
                    {latestCheckDate ? ` · ${latestCheckDate.toLocaleString()}` : ''}
                  </p>
                  {(combinedDetail?.contributing_factors?.length ?? 0) > 0 && (
                    <ul className="mt-2 text-[11px] text-slate-300 list-disc list-inside space-y-0.5">
                      {combinedDetail.contributing_factors.slice(0, 4).map((factor: any, i: number) => (
                        <li key={i}>
                          <span className="text-slate-500">[{factor.source}]</span> {factor.text}
                        </li>
                      ))}
                    </ul>
                  )}
                  {latestCheckIsNewer && (
                    <p className="text-[11px] text-amber-300/90 mt-1.5">
                      This saved check is newer than the prediction explained below.
                      {latestCheckModalities.length === 1
                        ? ` It used only your ${latestCheckModalities[0]} data, so its score is not directly comparable.`
                        : ''}
                    </p>
                  )}
                </div>
              </div>
              <Link href="/analytics" className="text-xs font-bold px-4 py-2 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30 transition-all text-center">
                See Check Trend →
              </Link>
            </div>
          )}

          {/* Tab Navigation */}
          <div className="flex gap-2 border-b border-slate-700/50 pb-0">
            {[
              { key: 'shap', label: 'What Affects My Score', icon: GitBranch },
              { key: 'lime', label: 'Simple Reasons', icon: Eye },
              { key: 'global', label: 'What Matters Most', icon: GitBranch },
            ].map(tab => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key as any)}
                  className={`px-4 py-2.5 text-xs font-bold flex items-center gap-2 border-b-2 transition-all -mb-px ${
                    activeTab === tab.key
                      ? 'border-indigo-500 text-indigo-300'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* SHAP Tab */}
          {activeTab === 'shap' && (
            <GlassCard gradient>
              <h3 className="font-bold text-white text-base mb-1">
                What Affects My Score — {explainedDate ? `Result from ${explainedDate}` : 'Latest Result'}
              </h3>
              <p className="text-xs text-slate-400 mb-6">
                Each bar shows how much one part of your life affects your stress.
                Bars pointing <span className="text-rose-300 font-semibold">right (red) push stress up</span> —
                bars pointing <span className="text-emerald-300 font-semibold">left (green) keep stress down</span>.
                Bigger bars matter more.
              </p>
              {loading ? (
                <div className="flex items-center justify-center py-16">
                  <div className="w-10 h-10 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                </div>
              ) : shapDrivers.length > 0 ? (
                <ShapBarChart drivers={shapDrivers} />
              ) : (
                <p className="text-slate-500 text-sm text-center py-8">No explanation data available yet.</p>
              )}
              <div className="mt-6 grid grid-cols-2 gap-4 text-xs text-slate-300">
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30">
                  <p className="font-bold text-rose-300 mb-1">Biggest Stress Booster</p>
                  {topAmplifier ? (
                    <p><strong>{friendlyFeature(topAmplifier.feature)}</strong> — the thing pushing your stress up the most.</p>
                  ) : (
                    <p>Nothing is pushing your stress up right now. Nice!</p>
                  )}
                </div>
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                  <p className="font-bold text-emerald-300 mb-1">Biggest Stress Soother</p>
                  {topProtector ? (
                    <p><strong>{friendlyFeature(topProtector.feature)}</strong> — the thing helping your stress stay down.</p>
                  ) : (
                    <p>No stress-reducing factors detected in this result.</p>
                  )}
                </div>
              </div>
            </GlassCard>
          )}

          {/* LIME Tab */}
          {activeTab === 'lime' && (
            <GlassCard gradient>
              <h3 className="font-bold text-white text-base mb-1">Simple Reasons for Your Score</h3>
              <p className="text-xs text-slate-400 mb-6">
                These are the biggest reasons behind your newest result, written in plain words.
              </p>
              {loading ? (
                <div className="flex items-center justify-center py-16">
                  <div className="w-10 h-10 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                </div>
              ) : limeRules.length > 0 ? (
                <LimeImpactList rules={limeRules} />
              ) : (
                <p className="text-slate-500 text-sm text-center py-8">No explanation data available yet.</p>
              )}
            </GlassCard>
          )}

          {/* Global Feature Importance Tab */}
          {activeTab === 'global' && (
            <GlassCard gradient>
              <h3 className="font-bold text-white text-base mb-1">What Matters Most for Stress Overall</h3>
              <p className="text-xs text-slate-400 mb-6">
                These are the factors that influenced your stress the most across your latest result.
              </p>
              <div className="space-y-4">
                {globalImportance.map((item, idx) => (
                  <div key={item.feature}>
                    <div className="flex justify-between text-xs font-semibold text-slate-200 mb-1.5">
                      <span className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded bg-indigo-500/20 text-indigo-300 text-center leading-5 text-xs font-bold border border-indigo-500/30">
                          {idx + 1}
                        </span>
                        {friendlyFeature(item.feature)}
                      </span>
                      <span>{(item.importance * 100).toFixed(1)}%</span>
                    </div>
                    <div className="h-3 rounded-full bg-slate-800 p-0.5">
                      <div
                        className="h-2 rounded-full bg-gradient-to-r from-indigo-500 to-cyan-400 transition-all duration-700"
                        style={{ width: `${Math.min(item.importance * 100, 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          )}
        </main>
      </div>
    </div>
  );
}

export default function ExplainabilityPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950 flex flex-col" />}>
      <ExplainabilityContent />
    </Suspense>
  );
}
