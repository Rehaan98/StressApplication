"use client";

import React, { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { GlassCard } from '@/components/GlassCard';
import { StressGauge } from '@/components/StressGauge';
import { ShapBarChart } from '@/components/ShapBarChart';
import { LimeImpactList } from '@/components/LimeImpactList';
import { RagInterventionCard } from '@/components/RagInterventionCard';
import { Activity, Sparkles, Eye, TrendingUp, AlertCircle, ClipboardList } from 'lucide-react';
import { api } from '@/lib/api';
import Link from 'next/link';

const STRESS_GAUGE_MAP: Record<string, number> = {
  Low: 18, Moderate: 48, High: 73, Severe: 92,
};

const LEVEL_COLORS: Record<string, string> = {
  Low: 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10',
  Moderate: 'text-amber-400 border-amber-500/40 bg-amber-500/10',
  High: 'text-orange-400 border-orange-500/40 bg-orange-500/10',
  Severe: 'text-rose-400 border-rose-500/40 bg-rose-500/10',
};

// Demo fallback data
const DEMO_RESULT = {
  id: 'demo',
  stress_level: 'Moderate',
  confidence_score: 0.942,
  class_probabilities: { Low: 0.04, Moderate: 0.94, High: 0.02, Severe: 0.00 },
  shap_explanation: {
    top_drivers: [
      { feature: 'total_pss', shap_value: 0.312, impact: 'increases_stress' },
      { feature: 'hrv_sdnn', shap_value: -0.218, impact: 'reduces_stress' },
      { feature: 'anxiety_score', shap_value: 0.187, impact: 'increases_stress' },
      { feature: 'sleep_hours', shap_value: -0.142, impact: 'reduces_stress' },
      { feature: 'work_stress_factor', shap_value: 0.121, impact: 'increases_stress' },
    ],
  },
  lime_explanation: {
    lime_rules: [
      { rule: 'total_pss > 22.0', weight: 0.289, effect: 'increases_stress' },
      { rule: 'hrv_sdnn <= 48.5', weight: 0.198, effect: 'increases_stress' },
      { rule: 'anxiety_score > 6.0', weight: 0.172, effect: 'increases_stress' },
      { rule: 'sleep_hours <= 6.5', weight: 0.155, effect: 'increases_stress' },
      { rule: 'sentiment_score <= 0.1', weight: 0.088, effect: 'increases_stress' },
    ],
  },
  rag_interventions: [
    {
      id: 'KB-ANS-02',
      category: 'Autonomic Nervous System Regulation',
      title: 'Calm Breathing Exercise',
      summary: 'A simple 4-4-4-4 breathing pattern that calms your body and mind quickly.',
      protocol: ['Inhale through nose 4s', 'Hold 4s', 'Exhale through mouth 4s', 'Hold empty 4s — repeat 5 cycles'],
      evidence_base: 'Recommended by health researchers for quick calm',
      difficulty: 'Immediate',
      duration_min: 5,
      relevance_score: 0.89,
    },
    {
      id: 'KB-CBT-01',
      category: 'Cognitive Behavioral Therapy (CBT)',
      title: 'Reframe Your Thoughts',
      summary: 'Catch stressful thoughts and replace them with more balanced, helpful ones.',
      protocol: [
        'Catch automatic negative thoughts',
        'Examine the evidence',
        'Write a balanced alternative',
        'Break the stressor into a 5-min first step',
      ],
      evidence_base: 'A well-studied technique for anxiety and stress',
      difficulty: 'Beginner',
      duration_min: 10,
      relevance_score: 0.77,
    },
  ],
};

function PredictionContent() {
  const searchParams = useSearchParams();
  const predId = searchParams.get('id');
  const [result, setResult] = useState<any>(null);
  const [xai, setXai] = useState<any>(null);
  const [rag, setRag] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isDemo, setIsDemo] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);

      // Use the requested prediction, or load the user's latest prediction
      // when arriving from the sidebar without a query parameter.
      let targetPredId = predId && predId !== 'demo' ? predId : null;
      if (!targetPredId) {
        try {
          const latest = await api.listPredictions(1);
          targetPredId = latest?.[0]?.id ?? null;
        } catch {
          targetPredId = null;
        }
      }

      if (targetPredId) {
        try {
          // Primary: full prediction detail endpoint (real confidence + probabilities)
          const [detailRes, ragRes] = await Promise.allSettled([
            api.getPrediction(targetPredId),
            api.queryRAG(targetPredId),
          ]);

          const detail: any = detailRes.status === 'fulfilled' ? detailRes.value : null;
          const ragResult: any = ragRes.status === 'fulfilled' ? ragRes.value : null;

          if (detail) {
            setResult({
              id: detail.id,
              stress_level: detail.stress_level ?? 'Moderate',
              confidence_score: detail.confidence_score ?? 0,
              class_probabilities: detail.class_probabilities ?? {},
            });
            setXai({
              top_drivers: detail.shap_explanation?.top_drivers ?? [],
              lime_rules: detail.lime_explanation?.lime_rules ?? [],
            });
          } else {
            setResult(DEMO_RESULT);
            setIsDemo(true);
          }

          setRag(ragResult?.interventions ?? detail?.rag_interventions ?? []);
        } catch {
          // Fallback: compose from the explainability endpoint
          try {
            const xaiData: any = await api.getExplainability(targetPredId);
            setResult({
              id: targetPredId,
              stress_level: xaiData.predicted_class ?? 'Moderate',
              confidence_score: 0,
              class_probabilities: {},
            });
            setXai({
              top_drivers: xaiData.top_drivers ?? [],
              lime_rules: xaiData.lime_rules ?? [],
            });
          } catch {
            setResult(DEMO_RESULT);
            setIsDemo(true);
          }
        }
      } else {
        // No real id — show demo data
        setTimeout(() => {
          setResult(DEMO_RESULT);
          setIsDemo(true);
        }, 600);
      }

      setLoading(false);
    };

    load();
  }, [predId]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-12">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-300 font-semibold">Working out your stress level…</p>
          <p className="text-slate-500 text-xs mt-1">Checking your answers, understanding what matters, and preparing your coping plan</p>
        </div>
      </div>
    );
  }

  const level = result?.stress_level ?? 'Moderate';
  const badge = LEVEL_COLORS[level] ?? LEVEL_COLORS.Moderate;

  const shapDrivers = xai?.top_drivers ?? result?.shap_explanation?.top_drivers ?? [];
  const limeRules = xai?.lime_rules ?? result?.lime_explanation?.lime_rules ?? [];
  const ragInterventions = rag ?? result?.rag_interventions ?? [];

  return (
    <main className="flex-1 p-8 max-w-7xl mx-auto w-full space-y-8">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-3xl font-extrabold text-white flex items-center gap-3">
          <Activity className="w-8 h-8 text-indigo-400" />
          My Stress Results
        </h1>
        <div className="flex items-center gap-3">
          {isDemo && (
            <span className="text-xs px-3 py-1 rounded-full bg-slate-700 text-slate-400 border border-slate-600">Demo Data</span>
          )}
          <span className={`px-4 py-1.5 rounded-full text-sm font-bold border uppercase tracking-wider ${badge}`}>
            {level} Risk
          </span>
          <Link href="/assessment" className="px-4 py-2 rounded-xl text-xs font-bold bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 hover:bg-indigo-600/50 flex items-center gap-1.5 transition-all">
            <ClipboardList className="w-4 h-4" /> Take Another Check
          </Link>
        </div>
      </div>

      {/* Confidence + Class Probabilities */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <GlassCard gradient>
          <h3 className="font-bold text-white mb-4 text-base flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-indigo-400" /> Your Stress Level
          </h3>
          <StressGauge level={level} score={STRESS_GAUGE_MAP[level] ?? 50} />
          <div className="mt-4 pt-4 border-t border-slate-700/50 grid grid-cols-2 gap-3">
            <div className="text-center p-3 rounded-xl bg-slate-900">
              <p className="text-xs text-slate-400 uppercase tracking-wider">How sure are we?</p>
              <p className="text-2xl font-extrabold text-white mt-1">
                {((result?.confidence_score ?? 0) * 100).toFixed(1)}%
              </p>
            </div>
            <div className="text-center p-3 rounded-xl bg-slate-900">
              <p className="text-xs text-slate-400 uppercase tracking-wider">Method</p>
              <p className="text-sm font-bold text-indigo-300 mt-1">AI Analysis</p>
            </div>
          </div>
        </GlassCard>

        <GlassCard gradient>
          <h3 className="font-bold text-white mb-4 text-base">Chances of Each Stress Level</h3>
          <p className="text-xs text-slate-400 mb-4">The likelihood, based on your answers, that your stress is at each level.</p>
          <div className="space-y-3 mt-2">
            {Object.entries(result?.class_probabilities ?? {}).map(([cls, prob]: [string, any]) => (
              <div key={cls}>
                <div className="flex justify-between text-xs text-slate-300 mb-1 font-semibold">
                  <span>{cls}</span><span>{(prob * 100).toFixed(1)}%</span>
                </div>
                <div className="h-2.5 rounded-full bg-slate-800 p-0.5">
                  <div
                    className={`h-1.5 rounded-full transition-all duration-700 ${
                      cls === 'Low' ? 'bg-emerald-500'
                        : cls === 'Moderate' ? 'bg-amber-500'
                        : cls === 'High' ? 'bg-orange-500'
                        : 'bg-rose-500'
                    }`}
                    style={{ width: `${prob * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {/* What affects the score */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GlassCard gradient>
          <h3 className="font-bold text-white mb-2 text-base flex items-center gap-2">
            <Eye className="w-5 h-5 text-cyan-400" /> What Raises Your Stress
          </h3>
          <p className="text-xs text-slate-400 mb-4">Red bars increase stress · Green bars reduce stress</p>
          {shapDrivers.length > 0 ? (
            <ShapBarChart drivers={shapDrivers} />
          ) : (
            <p className="text-slate-500 text-sm text-center py-8">No data available yet.</p>
          )}
        </GlassCard>

        <GlassCard gradient>
          <h3 className="font-bold text-white mb-2 text-base flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-pink-400" /> Simple Reasons for This Result
          </h3>
          <p className="text-xs text-slate-400 mb-4">Which parts of your answers mattered most</p>
          {limeRules.length > 0 ? (
            <LimeImpactList rules={limeRules} />
          ) : (
            <p className="text-slate-500 text-sm text-center py-8">No data available yet.</p>
          )}
        </GlassCard>
      </div>

      {/* Coping interventions */}
      {ragInterventions.length > 0 && (
        <div>
          <h2 className="text-xl font-bold text-white mb-5 flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-cyan-400" />
            Your Coping Plan
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {ragInterventions.map((intervention: any) => (
              <RagInterventionCard key={intervention.id} intervention={intervention} />
            ))}
          </div>
        </div>
      )}
    </main>
  );
}

export default function PredictionsPage() {
  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-slate-400">Loading…</div>}>
          <PredictionContent />
        </Suspense>
      </div>
    </div>
  );
}
