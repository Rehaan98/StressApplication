"use client";

import React, { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { GlassCard } from '@/components/GlassCard';
import { ShapBarChart } from '@/components/ShapBarChart';
import { LimeImpactList } from '@/components/LimeImpactList';
import { friendlyFeature } from '@/lib/labels';
import { Eye, GitBranch, Info, AlertCircle } from 'lucide-react';
import { api } from '@/lib/api';
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

function ExplainabilityContent() {
  const searchParams = useSearchParams();
  const predId = searchParams.get('id');
  const [activeTab, setActiveTab] = useState<'shap' | 'lime' | 'global'>('shap');
  const [shapDrivers, setShapDrivers] = useState<any[]>([]);
  const [limeRules, setLimeRules] = useState<any[]>([]);
  const [predictedClass, setPredictedClass] = useState<string>('');
  const [isDemo, setIsDemo] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        let targetPredId = predId && predId !== 'demo' ? predId : null;
        if (!targetPredId) {
          const preds = await api.listPredictions(1);
          targetPredId = preds?.length ? preds[0].id : null;
        }

        if (targetPredId) {
          const xai = await api.getExplainability(targetPredId);
          setShapDrivers(xai.top_drivers ?? []);
          setLimeRules(xai.lime_rules ?? []);
          setPredictedClass(xai.predicted_class ?? '');
          setIsDemo(false);
        } else {
          setShapDrivers(DEMO_SHAP);
          setLimeRules(DEMO_LIME);
          setPredictedClass('Moderate');
          setIsDemo(true);
        }
      } catch {
        setShapDrivers(DEMO_SHAP);
        setLimeRules(DEMO_LIME);
        setPredictedClass('Moderate');
        setIsDemo(true);
      }
      setLoading(false);
    };

    load();
  }, [predId]);

  const maxAbs = Math.max(...shapDrivers.map(d => Math.abs(d.shap_value ?? 0)), 0.001);
  const globalImportance = shapDrivers.length > 0
    ? [...shapDrivers]
        .map(d => ({ feature: d.feature, importance: Math.abs(d.shap_value ?? 0) / maxAbs }))
        .sort((a, b) => b.importance - a.importance)
        .slice(0, 7)
    : DEMO_GLOBAL_IMPORTANCE;

  const topAmplifier = shapDrivers.find(d => (d.shap_value ?? 0) > 0);
  const topProtector = shapDrivers.find(d => (d.shap_value ?? 0) < 0);

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
            {loading ? (
              <span className="text-xs px-3 py-1 rounded-full bg-slate-700 text-slate-400 border border-slate-600">Loading…</span>
            ) : isDemo ? (
              <span className="text-xs px-3 py-1 rounded-full bg-slate-700 text-slate-400 border border-slate-600">Demo Data</span>
            ) : (
              <span className="px-4 py-1.5 rounded-full text-sm font-bold border uppercase tracking-wider bg-cyan-500/10 border-cyan-500/40 text-cyan-300">
                {predictedClass} Prediction · Live Data
              </span>
            )}
          </div>
          <p className="text-slate-400 mt-2 text-sm -mt-5">
            We believe your stress result should never be a mystery. This page explains, in plain words,
            what is affecting your score and why.
          </p>

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
                  Everything below is written for people — no jargon.
                </p>
              </div>
            </div>
          </GlassCard>

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
              <h3 className="font-bold text-white text-base mb-1">What Affects My Score — Latest Result</h3>
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
                <p className="text-slate-500 text-sm text-center py-8">No data available yet.</p>
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
                These are the biggest reasons behind your result, written in plain words.
              </p>
              {loading ? (
                <div className="flex items-center justify-center py-16">
                  <div className="w-10 h-10 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                </div>
              ) : limeRules.length > 0 ? (
                <LimeImpactList rules={limeRules} />
              ) : (
                <p className="text-slate-500 text-sm text-center py-8">No data available yet.</p>
              )}
            </GlassCard>
          )}

          {/* Global Feature Importance Tab */}
          {activeTab === 'global' && (
            <GlassCard gradient>
              <h3 className="font-bold text-white text-base mb-1">What Matters Most for Stress Overall</h3>
              <p className="text-xs text-slate-400 mb-6">
                Across all users, these are the things that influence stress levels the most.
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
