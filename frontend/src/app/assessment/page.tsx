"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { GlassCard } from '@/components/GlassCard';
import { api } from '@/lib/api';
import { ClipboardList, ChevronRight, ChevronLeft, Send, CheckCircle2 } from 'lucide-react';

const PSS_QUESTIONS = [
  "In the last month, how often have you been upset because of something that happened unexpectedly?",
  "In the last month, how often have you felt that you were unable to control the important things in your life?",
  "In the last month, how often have you felt nervous and stressed?",
  "In the last month, how often have you felt confident about your ability to handle your personal problems?",
  "In the last month, how often have you felt that things were going your way?",
  "In the last month, how often have you been able to control irritations in your life?",
  "In the last month, how often have you felt that you were on top of things?",
  "In the last month, how often have you been angered because of things that were outside of your control?",
  "In the last month, how often have you been unable to control the way you spend your time?",
  "In the last month, how often have you felt difficulties were piling up so high that you could not overcome them?",
];

const SCALE = [
  { label: "Never", value: 0 },
  { label: "Almost Never", value: 1 },
  { label: "Sometimes", value: 2 },
  { label: "Fairly Often", value: 3 },
  { label: "Very Often", value: 4 },
];

type PSSResponses = { [key: string]: number };

const PHYSIO_LABELS: Record<string, string> = {
  heart_rate: 'Heart rate',
  hrv_sdnn: 'Heart rhythm calmness',
  sleep_hours: 'Sleep duration',
  sleep_efficiency: 'Sleep quality',
  physical_activity_min: 'Daily activity',
};

const WORKLOAD_LABELS: Record<string, string> = {
  work_hours: 'Work hours',
  screen_time_hours: 'Screen time',
  breaks_per_day: 'Breaks per day',
  sentiment_score: 'Mood balance',
  anxiety_score: 'Anxiety level',
};

export default function AssessmentPage() {
  const router = useRouter();
  const [step, setStep] = useState(0); // 0 = PSS-10, 1 = Physiological, 2 = Workload, 3 = Review
  const [pss, setPss] = useState<PSSResponses>({});
  const [physio, setPhysio] = useState({
    heart_rate: 72,
    hrv_sdnn: 55,
    sleep_hours: 7.0,
    sleep_efficiency: 85,
    physical_activity_min: 30,
  });
  const [workload, setWorkload] = useState({
    work_hours: 8.0,
    screen_time_hours: 6.0,
    breaks_per_day: 4,
    sentiment_score: 0.2,
    anxiety_score: 4.0,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const answeredCount = Object.keys(pss).length;
  const answered = (q: string) => pss[q] !== undefined;

  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    try {
      // Send only answered questions — the backend fills neutral defaults for skipped ones
      const pssData = Object.fromEntries(
        PSS_QUESTIONS.map((_, i) => [`pss_q${i + 1}`, pss[`q${i + 1}`]])
          .filter(([, v]) => v !== undefined)
      );
      const assessment = await api.createAssessment({
        ...pssData,
        ...physio,
        ...workload,
      } as any);

      const prediction = await api.runPrediction(assessment.id);
      router.push(`/predictions?id=${prediction.id}`);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to submit assessment. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 max-w-4xl mx-auto w-full">
          <div className="mb-8">
            <h1 className="text-3xl font-extrabold text-white flex items-center gap-3">
              <ClipboardList className="w-8 h-8 text-indigo-400" />
              Stress Check
            </h1>
            <p className="text-slate-400 mt-2 text-sm">Answer as many questions as you like — every question is optional. Skipped items are scored as neutral.</p>
          </div>

          {/* Step Progress Bar */}
          <div className="flex items-center gap-2 mb-8">
            {["1. Your Feelings", "2. Your Body & Sleep", "3. Work & Screen Time", "4. Review & Submit"].map((label, idx) => (
              <React.Fragment key={idx}>
                <div className={`flex items-center gap-2 text-xs font-semibold ${step === idx ? 'text-indigo-300' : step > idx ? 'text-emerald-400' : 'text-slate-500'}`}>
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center border text-xs font-bold
                    ${step === idx ? 'border-indigo-400 bg-indigo-500/20 text-indigo-300' : step > idx ? 'border-emerald-500 bg-emerald-500/20 text-emerald-400' : 'border-slate-600 text-slate-500'}`}>
                    {step > idx ? <CheckCircle2 className="w-4 h-4" /> : idx + 1}
                  </div>
                  <span className="hidden md:block">{label}</span>
                </div>
                {idx < 3 && <div className={`flex-1 h-px ${step > idx ? 'bg-emerald-500/50' : 'bg-slate-700'}`} />}
              </React.Fragment>
            ))}
          </div>

          {/* STEP 0 — Feelings questionnaire */}
          {step === 0 && (
            <GlassCard gradient>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold text-white">How have you felt this month?</h2>
                <span className={`text-xs font-bold px-3 py-1.5 rounded-full border ${
                  answeredCount === 10
                    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                    : 'bg-amber-500/15 text-amber-300 border-amber-500/40'
                }`}>
                  {answeredCount} / 10 answered {answeredCount < 10 && '· optional'}
                </span>
              </div>
              <div className="space-y-6">
                {PSS_QUESTIONS.map((q, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-xl transition-colors ${
                      answered(`q${i + 1}`) ? '' : 'bg-amber-500/5 border border-amber-500/20'
                    }`}
                  >
                    <p className="text-sm text-slate-200 font-medium mb-3">
                      <span className="text-indigo-400 font-bold">Q{i + 1}.</span> {q}
                      {!answered(`q${i + 1}`) && (
                        <span className="ml-2 text-[10px] font-bold uppercase tracking-wider text-amber-400/80">· skipped</span>
                      )}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {SCALE.map((s) => (
                        <button
                          key={s.value}
                          onClick={() => setPss(prev => ({ ...prev, [`q${i + 1}`]: s.value }))}
                          className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all
                            ${pss[`q${i + 1}`] === s.value
                              ? 'bg-indigo-600 border-indigo-400 text-white'
                              : 'bg-slate-800/60 border-slate-600 text-slate-300 hover:border-indigo-500 hover:text-white'}`}
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-8 flex justify-between items-center">
                <span className="text-xs text-slate-500">
                  {answeredCount === 0
                    ? 'Tip: you can skip this section entirely and continue.'
                    : answeredCount < 10
                      ? `${10 - answeredCount} question${10 - answeredCount > 1 ? 's' : ''} skipped — will be scored as "Sometimes" (neutral).`
                      : 'All questions answered. Great job!'}
                </span>
                <button
                  onClick={() => setStep(1)}
                  className="px-6 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-indigo-600 to-cyan-500 text-white flex items-center gap-2 transition-all"
                >
                  Next: Your Body & Sleep <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </GlassCard>
          )}

          {/* STEP 1 — Body & Sleep */}
          {step === 1 && (
            <GlassCard gradient>
              <h2 className="text-lg font-bold text-white mb-6">Your Body & Sleep</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {[
                  { label: "Heart Rate (beats per minute)", key: "heart_rate", min: 40, max: 160, step: 0.5, hint: "How fast your heart beats at rest" },
                  { label: "Heart Rhythm Calmness", key: "hrv_sdnn", min: 10, max: 150, step: 0.5, hint: "Higher = calmer and more relaxed" },
                  { label: "Sleep Duration (hours)", key: "sleep_hours", min: 1, max: 14, step: 0.5, hint: "Average sleep per night" },
                  { label: "Sleep Quality (%)", key: "sleep_efficiency", min: 20, max: 100, step: 1, hint: "How well you sleep" },
                  { label: "Physical Activity (min/day)", key: "physical_activity_min", min: 0, max: 300, step: 5, hint: "Walking, exercise, movement" },
                ].map(field => (
                  <div key={field.key}>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                      {field.label}: <span className="text-white">{physio[field.key as keyof typeof physio]}</span>
                    </label>
                    <p className="text-[11px] text-slate-500 mb-2">{field.hint}</p>
                    <input
                      type="range"
                      min={field.min}
                      max={field.max}
                      step={field.step}
                      value={physio[field.key as keyof typeof physio]}
                      onChange={e => setPhysio(prev => ({ ...prev, [field.key]: parseFloat(e.target.value) }))}
                      className="w-full accent-indigo-500"
                    />
                    <div className="flex justify-between text-xs text-slate-500 mt-1">
                      <span>{field.min}</span><span>{field.max}</span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-8 flex justify-between">
                <button onClick={() => setStep(0)} className="px-5 py-2.5 rounded-xl font-bold text-sm glass-morphism border-slate-700 text-slate-300 flex items-center gap-2">
                  <ChevronLeft className="w-4 h-4" /> Back
                </button>
                <button onClick={() => setStep(2)} className="px-6 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-indigo-600 to-cyan-500 text-white flex items-center gap-2 transition-all">
                  Next: Work & Screen Time <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </GlassCard>
          )}

          {/* STEP 2 — Work & Screen Time */}
          {step === 2 && (
            <GlassCard gradient>
              <h2 className="text-lg font-bold text-white mb-6">Work & Screen Time</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {[
                  { label: "Work Hours (per day)", key: "work_hours", min: 0, max: 20, step: 0.5, hint: "Hours spent working each day" },
                  { label: "Screen Time (hours/day)", key: "screen_time_hours", min: 0, max: 20, step: 0.5, hint: "Phones, computers, TV" },
                  { label: "Breaks Per Day", key: "breaks_per_day", min: 0, max: 20, step: 1, hint: "Short rests during the day" },
                  { label: "Mood Balance (-1 to 1)", key: "sentiment_score", min: -1.0, max: 1.0, step: 0.05, hint: "Negative = low mood · Positive = good mood" },
                  { label: "Anxiety Level (1–10)", key: "anxiety_score", min: 1, max: 10, step: 0.5, hint: "How anxious or worried you feel" },
                ].map(field => (
                  <div key={field.key}>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                      {field.label}: <span className="text-white">{workload[field.key as keyof typeof workload]}</span>
                    </label>
                    <p className="text-[11px] text-slate-500 mb-2">{field.hint}</p>
                    <input
                      type="range"
                      min={field.min}
                      max={field.max}
                      step={field.step}
                      value={workload[field.key as keyof typeof workload]}
                      onChange={e => setWorkload(prev => ({ ...prev, [field.key]: parseFloat(e.target.value) }))}
                      className="w-full accent-indigo-500"
                    />
                    <div className="flex justify-between text-xs text-slate-500 mt-1">
                      <span>{field.min}</span><span>{field.max}</span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-8 flex justify-between">
                <button onClick={() => setStep(1)} className="px-5 py-2.5 rounded-xl font-bold text-sm glass-morphism border-slate-700 text-slate-300 flex items-center gap-2">
                  <ChevronLeft className="w-4 h-4" /> Back
                </button>
                <button onClick={() => setStep(3)} className="px-6 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-indigo-600 to-cyan-500 text-white flex items-center gap-2 transition-all">
                  Review & Submit <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </GlassCard>
          )}

          {/* STEP 3 — Review & Submit */}
          {step === 3 && (
            <GlassCard gradient>
              <h2 className="text-lg font-bold text-white mb-6">Review & Submit</h2>
              {error && (
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm mb-4">{error}</div>
              )}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-sm">
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-700">
                  <p className="text-xs text-slate-400 uppercase font-semibold mb-3">Your Feelings</p>
                  <div className="grid grid-cols-2 gap-1.5">
                    {PSS_QUESTIONS.map((_, i) => (
                      <div key={i} className="flex justify-between text-slate-300 text-xs py-1 border-b border-slate-800">
                        <span>Q{i + 1}</span>
                        {answered(`q${i + 1}`) ? (
                          <span className="font-bold text-indigo-300">{pss[`q${i + 1}`]}</span>
                        ) : (
                          <span className="font-semibold text-amber-400/90">Skipped → neutral</span>
                        )}
                      </div>
                    ))}
                  </div>
                  {answeredCount < 10 && (
                    <p className="text-[11px] text-amber-300/80 mt-2">
                      {10 - answeredCount} skipped item{10 - answeredCount > 1 ? 's' : ''} scored as &quot;Sometimes&quot; (2) — neutral value.
                    </p>
                  )}
                </div>
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-700">
                  <p className="text-xs text-slate-400 uppercase font-semibold mb-3">Body & Sleep</p>
                  {Object.entries(physio).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs text-slate-300 py-1 border-b border-slate-800">
                      <span>{PHYSIO_LABELS[k] ?? k.replace(/_/g, ' ')}</span><span className="font-bold text-cyan-300">{v}</span>
                    </div>
                  ))}
                </div>
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-700">
                  <p className="text-xs text-slate-400 uppercase font-semibold mb-3">Work & Screen Time</p>
                  {Object.entries(workload).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs text-slate-300 py-1 border-b border-slate-800">
                      <span>{WORKLOAD_LABELS[k] ?? k.replace(/_/g, ' ')}</span><span className="font-bold text-pink-300">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="mt-8 flex justify-between">
                <button onClick={() => setStep(2)} className="px-5 py-2.5 rounded-xl font-bold text-sm glass-morphism border-slate-700 text-slate-300 flex items-center gap-2">
                  <ChevronLeft className="w-4 h-4" /> Back
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="px-8 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-indigo-600 to-cyan-500 text-white shadow-lg glow-primary flex items-center gap-2 disabled:opacity-50 transition-all"
                >
                  <Send className="w-4 h-4" />
                  {loading ? 'Calculating your results…' : 'Submit & See My Results'}
                </button>
              </div>
            </GlassCard>
          )}
        </main>
      </div>
    </div>
  );
}
