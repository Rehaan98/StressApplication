"use client";

import React, { useState } from 'react';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { GlassCard } from '@/components/GlassCard';
import { RagInterventionCard } from '@/components/RagInterventionCard';
import { Sparkles, Search, Loader2, BookOpen } from 'lucide-react';
import { api } from '@/lib/api';

const DEMO_INTERVENTIONS = [
  {
    id: 'KB-ANS-02', category: 'Calm Breathing',
    title: 'Calm Breathing Exercise',
    summary: 'A simple 4-4-4-4 breathing pattern that calms your body and mind quickly.',
    protocol: ['Inhale through nose for 4 seconds', 'Hold breath gently for 4 seconds', 'Exhale fully through mouth for 4 seconds', 'Hold empty for 4 seconds — repeat 5 cycles'],
    evidence_base: 'Recommended by health researchers for quick calm',
    difficulty: 'Immediate', duration_min: 5, relevance_score: 0.91
  },
  {
    id: 'KB-CBT-01', category: 'Reframe Your Thoughts',
    title: 'Reframe Your Thoughts',
    summary: 'Catch stressful thoughts and replace them with more balanced, helpful ones.',
    protocol: ['Catch automatic negative thoughts', 'Ask: What is the real evidence for this thought?', 'Write a more balanced view', 'Break the stressor into a 5-minute first step'],
    evidence_base: 'A well-studied technique for anxiety and stress',
    difficulty: 'Beginner', duration_min: 10, relevance_score: 0.83
  },
  {
    id: 'KB-SLP-03', category: 'Better Sleep',
    title: 'Better Sleep Routine',
    summary: 'Simple daily habits that help you fall asleep faster and sleep deeper.',
    protocol: ['Get 10–15 min of daylight within 1 hour of waking', 'No caffeine at least 8 hours before bed', 'Keep your bedroom cool and dark', 'If awake in bed, do a 10-min body-relaxation scan'],
    evidence_base: 'Well-known advice from sleep researchers',
    difficulty: 'Easy', duration_min: 15, relevance_score: 0.76
  },
];

export default function RagCopingPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(DEMO_INTERVENTIONS);
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searched, setSearched] = useState(false);

  // Category pills are derived from the currently visible results so filtering
  // always works with real backend categories, not just the demo list.
  const categoryOptions = ['All', ...Array.from(new Set(
    results.map(r => r.category).filter(Boolean) as string[]
  ))];
  const filteredResults =
    selectedCategory === 'All'
      ? results
      : results.filter(r => r.category === selectedCategory || r.title === selectedCategory);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    setSelectedCategory('All');
    try {
      const res = await api.queryRAG(undefined, query);
      if (res?.interventions?.length > 0) {
        setResults(res.interventions);
      } else {
        setResults(DEMO_INTERVENTIONS);
      }
    } catch {
      setResults(DEMO_INTERVENTIONS);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 max-w-6xl mx-auto w-full space-y-8">
          {/* Header */}
          <div>
            <h1 className="text-3xl font-extrabold text-white flex items-center gap-3">
              <Sparkles className="w-8 h-8 text-cyan-400" />
              Coping Help Center
            </h1>
            <p className="text-slate-400 mt-2 text-sm">
              Simple, step-by-step exercises to help you feel calmer, sleep better and think more clearly.
              Tell us how you feel and we will find the right exercises for you.
            </p>
          </div>

          {/* Search Bar */}
          <GlassCard gradient className="border border-cyan-500/30">
            <div className="flex items-center gap-3">
              <div className="flex-1 relative">
                <Search className="w-5 h-5 text-slate-400 absolute left-4 top-3.5" />
                <input
                  type="text"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                  placeholder="e.g. 'I can't sleep because of work', 'I feel angry', 'help me relax'…"
                  className="w-full glass-input rounded-xl pl-12 pr-4 py-3 text-sm"
                />
              </div>
              <button
                onClick={handleSearch}
                disabled={loading || !query.trim()}
                className="px-6 py-3 rounded-xl font-bold text-sm bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white shadow-lg flex items-center gap-2 disabled:opacity-50 transition-all whitespace-nowrap"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                {loading ? 'Finding exercises…' : 'Find Exercises'}
              </button>
            </div>

            {/* Category Pills */}
            <div className="flex flex-wrap gap-2 mt-4">
              {categoryOptions.map(cat => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    selectedCategory === cat
                      ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300'
                      : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </GlassCard>

          {/* How it works note */}
          <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-700 flex items-start gap-3">
            <BookOpen className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
            <div className="text-xs text-slate-300 leading-relaxed">
              <strong className="text-cyan-300">How matching works:</strong> We compare what you tell us — your feelings, your answers,
              and even the emotions our face scanner detects — with a library of expert-written coping exercises.
              Then we show you the ones that fit you best. No jargon, just helpful steps.
            </div>
          </div>

          {/* Results */}
          <div>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-white">
                {searched ? `${filteredResults.length} Exercises Found for You` : 'Popular Exercises'}
              </h2>
              <span className="text-xs text-slate-400">{filteredResults.length} exercises · Best matches first</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
              {filteredResults.map(intervention => (
                <RagInterventionCard key={intervention.id} intervention={intervention} />
              ))}
            </div>
            {filteredResults.length === 0 && (
              <p className="text-slate-500 text-sm text-center py-8">
                No exercises match this category. Try another category or search again.
              </p>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
