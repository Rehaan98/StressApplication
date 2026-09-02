"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, ClipboardList, Activity, Eye, Sparkles, BarChart2, ShieldCheck, Settings, LogOut, ScanFace } from 'lucide-react';
import { useAuth } from '@/lib/auth';

const NAV_ITEMS = [
  { label: 'Home', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Face Stress Scan', href: '/facial', icon: ScanFace },
  { label: 'Stress Check', href: '/assessment', icon: ClipboardList },
  { label: 'My Results', href: '/predictions', icon: Activity },
  { label: 'Why This Score', href: '/explainability', icon: Eye },
  { label: 'Coping Help', href: '/rag-coping', icon: Sparkles },
  { label: 'My Trends', href: '/analytics', icon: BarChart2 },
  { label: 'Admin Panel', href: '/admin', icon: ShieldCheck },
  { label: 'Settings', href: '/settings', icon: Settings },
];

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const { logout, user } = useAuth();

  // Admin panel is restricted to the admin role (backend enforces it too)
  const visibleItems = NAV_ITEMS.filter(
    item => item.href !== '/admin' || user?.role === 'admin'
  );

  return (
    <aside className="w-64 glass-morphism border-r border-slate-700/50 min-h-[calc(100vh-65px)] p-4 flex flex-col justify-between">
      <div className="space-y-1">
        {visibleItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive
                  ? 'bg-gradient-to-r from-indigo-600/80 to-cyan-600/80 text-white shadow-lg border border-indigo-400/30 font-semibold'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/50'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'text-white' : 'text-slate-400'}`} />
              {item.label}
            </Link>
          );
        })}
      </div>

      <div className="pt-4 border-t border-slate-700/50">
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium text-rose-400 hover:bg-rose-500/10 transition-colors"
        >
          <LogOut className="w-5 h-5 text-rose-400" />
          Sign Out
        </button>
      </div>
    </aside>
  );
};
