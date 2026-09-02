"use client";

import React from 'react';
import Link from 'next/link';
import { Brain, Bell, Sparkles } from 'lucide-react';
import { useAuth } from '@/lib/auth';

export const Navbar: React.FC = () => {
  const { user } = useAuth();

  const initials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : 'U';

  return (
    <header className="sticky top-0 z-50 glass-morphism border-b border-slate-700/50 px-6 py-3.5 flex items-center justify-between">
      <Link href="/dashboard" className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-400 flex items-center justify-center glow-primary">
          <Brain className="w-6 h-6 text-white" />
        </div>
        <div>
          <span className="font-bold text-lg text-white tracking-wide">StressAI</span>
          <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Your calm companion</span>
        </div>
      </Link>

      <div className="flex items-center gap-4">
        <Link href="/rag-coping" className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-500/20 transition-all">
          <Sparkles className="w-4 h-4 text-cyan-400" />
          Coping Help
        </Link>
        <button className="p-2 rounded-lg bg-slate-800/60 text-slate-300 hover:text-white border border-slate-700/50 transition-colors relative">
          <Bell className="w-5 h-5" />
        </button>
        <Link href="/settings" className="flex items-center gap-2 p-1.5 rounded-lg bg-slate-800/60 border border-slate-700/50 hover:bg-slate-700/50 text-slate-200 transition-colors">
          <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white">
            {initials}
          </div>
          <span className="text-sm font-medium pr-1 max-w-[120px] truncate">
            {user?.full_name?.split(' ')[0] ?? 'Account'}
          </span>
        </Link>
      </div>
    </header>
  );
};
