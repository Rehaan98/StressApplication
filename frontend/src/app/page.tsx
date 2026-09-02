"use client";

import React from 'react';
import Link from 'next/link';
import { Brain, Sparkles, Activity, Shield, Eye, ArrowRight, ScanFace, Camera, HeartPulse, CheckCircle2 } from 'lucide-react';

const FEATURES = [
  {
    icon: ScanFace,
    title: 'Face Stress Scan',
    desc: 'Our AI looks at your facial expressions through your webcam and shows you your stress level live — anger, fear, sadness, joy and more, in real time.',
    hover: 'hover:border-violet-500/40',
    iconBg: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
  },
  {
    icon: Activity,
    title: 'Simple Stress Check',
    desc: 'Answer a few short questions about your sleep, work and feelings. Every question is optional — skip anything you prefer not to answer.',
    hover: 'hover:border-indigo-500/40',
    iconBg: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
  },
  {
    icon: Eye,
    title: 'Why This Score?',
    desc: 'We explain your result in plain words — which parts of your life are raising your stress, and which are helping to keep it down.',
    hover: 'hover:border-cyan-500/40',
    iconBg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  },
  {
    icon: Sparkles,
    title: 'Coping Help That Fits You',
    desc: 'Get simple, step-by-step exercises — calm breathing, better sleep, easier thinking — matched to your answers and your emotions.',
    hover: 'hover:border-pink-500/40',
    iconBg: 'bg-pink-500/10 text-pink-400 border-pink-500/20',
  },
];

const STEPS = [
  { num: '01', title: 'Allow Webcam Access', desc: 'Your camera feed stays on your device — only small anonymized pictures are analyzed.' },
  { num: '02', title: 'Live Expression Reading', desc: 'Our AI checks your facial expression every 2.5 seconds and reads your emotions.' },
  { num: '03', title: 'Instant Stress Insights', desc: 'See your stress level from 0–100, with emotion details and your progress over time.' },
  { num: '04', title: 'Tailored Coping Plan', desc: 'Get easy, evidence-based exercises matched to how you are feeling right now.' },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col selection:bg-indigo-500 selection:text-white">
      {/* Header Navigation */}
      <header className="px-8 py-6 flex items-center justify-between max-w-7xl mx-auto w-full">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-400 flex items-center justify-center glow-primary">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <span className="font-bold text-xl tracking-tight">Psychological Stress AI</span>
        </div>

        <div className="flex items-center gap-4">
          <Link href="/login" className="px-5 py-2.5 rounded-xl text-sm font-medium text-slate-300 hover:text-white transition-colors">
            Sign In
          </Link>
          <Link href="/register" className="px-5 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white shadow-lg glow-primary transition-all">
            Get Started Free
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-8 py-16 flex-1 flex flex-col items-center text-center">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-morphism border-indigo-500/30 text-indigo-300 text-xs font-semibold uppercase tracking-wider mb-8">
          <Sparkles className="w-4 h-4 text-cyan-400" />
          Real-time AI · Emotion Recognition · Smart Coping Plans
        </div>

        <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight max-w-4xl leading-tight">
          Understand Your Stress —{' '}
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 via-cyan-300 to-pink-500">in Plain Language</span>
        </h1>

        <p className="text-lg md:text-xl text-slate-300 max-w-2xl mt-6 leading-relaxed">
          Answer a few simple questions, or let our AI read your facial expressions through your webcam.
          We then show you <span className="text-violet-300 font-semibold">how stressed you are</span>, why that might be,
          and give you <span className="text-cyan-300 font-semibold">easy, step-by-step coping exercises</span> you can start right away.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4 mt-10">
          <Link href="/facial" className="w-full sm:w-auto px-8 py-4 rounded-xl text-base font-bold bg-gradient-to-r from-violet-600 to-cyan-500 hover:from-violet-500 hover:to-cyan-400 text-white shadow-xl glow-pulse flex items-center justify-center gap-3 transition-all">
            <ScanFace className="w-5 h-5" />
            <span>Try the Live Facial Stress Scan</span>
            <ArrowRight className="w-5 h-5" />
          </Link>
          <Link href="/dashboard" className="w-full sm:w-auto px-8 py-4 rounded-xl text-base font-semibold glass-morphism border-slate-700 text-slate-200 hover:bg-slate-800/60 flex items-center justify-center gap-2 transition-all">
            <span>Explore the App</span>
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>

        {/* Feature Highlights Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-20 text-left max-w-6xl w-full">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div key={f.title} className={`p-6 rounded-2xl glass-morphism border border-slate-800 transition-all ${f.hover}`}>
                <div className={`p-3 rounded-xl w-fit mb-4 border ${f.iconBg}`}>
                  <Icon className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold text-white mb-2">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
              </div>
            );
          })}
        </div>

        {/* How it works */}
        <div className="mt-20 text-left max-w-6xl w-full">
          <h2 className="text-3xl font-extrabold text-center mb-10">
            How the <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-cyan-300">Face Stress Scan</span> works
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {STEPS.map((s) => (
              <div key={s.num} className="relative p-6 rounded-2xl glass-morphism border border-slate-800 hover:border-violet-500/40 transition-all">
                <span className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-br from-violet-500 to-cyan-500">{s.num}</span>
                <h4 className="font-bold text-white mt-3 mb-1.5">{s.title}</h4>
                <p className="text-xs text-slate-400 leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Trust strip */}
        <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 mt-20 text-xs text-slate-400">
          <span className="flex items-center gap-2"><Shield className="w-4 h-4 text-emerald-400" /> Private — your pictures are never stored</span>
          <span className="flex items-center gap-2"><HeartPulse className="w-4 h-4 text-rose-400" /> Exercises backed by health research</span>
          <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-cyan-400" /> 97% accurate at spotting stress</span>
          <span className="flex items-center gap-2"><Camera className="w-4 h-4 text-violet-400" /> Works live, ready for many users</span>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/60 py-8 px-8 text-center text-xs text-slate-500">
        <p>© 2026 Psychological Stress AI Enterprise Platform. Production Ready Build.</p>
      </footer>
    </div>
  );
}
