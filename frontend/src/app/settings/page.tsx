"use client";

import React, { useState, useEffect } from 'react';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { GlassCard } from '@/components/GlassCard';
import { Settings, User, Lock, Bell, Shield, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';

const NOTIFICATION_KEY = 'stressai.notification_prefs';

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [notifications, setNotifications] = useState({ email: true, push: false, weekly: true });
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');

  useEffect(() => {
    setFullName(user?.full_name ?? '');
  }, [user?.full_name]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(NOTIFICATION_KEY);
      if (stored) setNotifications(JSON.parse(stored));
    } catch {
      // ignore corrupt stored prefs
    }
  }, []);

  const toggleNotification = (key: keyof typeof notifications) => {
    setNotifications(prev => {
      const next = { ...prev, [key]: !prev[key] };
      try {
        localStorage.setItem(NOTIFICATION_KEY, JSON.stringify(next));
      } catch {
        // storage unavailable — keep in-memory state only
      }
      return next;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSaved(false);

    const tasks: Promise<unknown>[] = [];
    if (fullName.trim() && fullName.trim() !== user?.full_name) {
      tasks.push(api.updateProfile({ full_name: fullName.trim() }));
    }
    if (newPassword) {
      tasks.push(
        api.changePassword(currentPassword, newPassword).catch((err: any) => {
          throw new Error(err?.response?.data?.detail ?? 'Password change failed.');
        })
      );
    }

    if (tasks.length === 0) {
      setSaving(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      return;
    }

    try {
      await Promise.all(tasks);
      await refreshUser();
      setCurrentPassword('');
      setNewPassword('');
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to save settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : '—';

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 max-w-4xl mx-auto w-full space-y-8">
          <div>
            <h1 className="text-3xl font-extrabold text-white flex items-center gap-3">
              <Settings className="w-8 h-8 text-slate-400" />
              Settings & Profile
            </h1>
            <p className="text-slate-400 mt-2 text-sm">Manage your account, notification preferences, and security configuration.</p>
          </div>

          {saved && (
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/40 text-emerald-300 text-sm flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" /> Settings saved successfully.
            </div>
          )}
          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/40 text-rose-300 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4" /> {error}
            </div>
          )}

          {/* Profile Settings */}
          <GlassCard gradient>
            <h3 className="font-bold text-white mb-5 flex items-center gap-2">
              <User className="w-5 h-5 text-indigo-400" /> Profile Information
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  className="w-full glass-input rounded-xl px-4 py-2.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Email Address</label>
                <input
                  type="email"
                  value={user?.email ?? ''}
                  readOnly
                  className="w-full glass-input rounded-xl px-4 py-2.5 text-sm opacity-60 cursor-not-allowed"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Role</label>
                <input
                  type="text"
                  value={user?.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : '—'}
                  readOnly
                  className="w-full glass-input rounded-xl px-4 py-2.5 text-sm opacity-60 cursor-not-allowed"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Account Status</label>
                <input
                  type="text"
                  value={user?.is_active ? 'Active & Verified' : 'Inactive'}
                  readOnly
                  className="w-full glass-input rounded-xl px-4 py-2.5 text-sm opacity-60 cursor-not-allowed"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Member Since</label>
                <input
                  type="text"
                  value={memberSince}
                  readOnly
                  className="w-full glass-input rounded-xl px-4 py-2.5 text-sm opacity-60 cursor-not-allowed"
                />
              </div>
            </div>
          </GlassCard>

          {/* Notification Preferences */}
          <GlassCard gradient>
            <h3 className="font-bold text-white mb-5 flex items-center gap-2">
              <Bell className="w-5 h-5 text-cyan-400" /> Notification Preferences
            </h3>
            <div className="space-y-4">
              {[
                { key: 'email', label: 'Email Notifications', sub: 'Assessment results and prediction summaries via email' },
                { key: 'push', label: 'Push Notifications', sub: 'Real-time browser notifications for critical stress alerts' },
                { key: 'weekly', label: 'Weekly Stress Report', sub: 'Automated weekly summary of your stress trend and insights' },
              ].map(item => (
                <div key={item.key} className="flex items-center justify-between p-4 rounded-xl bg-slate-900 border border-slate-700">
                  <div>
                    <p className="text-sm font-semibold text-slate-200">{item.label}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{item.sub}</p>
                  </div>
                  <button
                    onClick={() => toggleNotification(item.key as keyof typeof notifications)}
                    className={`relative w-12 h-6 rounded-full transition-colors ${notifications[item.key as keyof typeof notifications] ? 'bg-indigo-500' : 'bg-slate-700'}`}
                  >
                    <span className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-all ${notifications[item.key as keyof typeof notifications] ? 'left-7' : 'left-1'}`} />
                  </button>
                </div>
              ))}
            </div>
          </GlassCard>

          {/* Security Settings */}
          <GlassCard gradient>
            <h3 className="font-bold text-white mb-5 flex items-center gap-2">
              <Lock className="w-5 h-5 text-rose-400" /> Security & Password
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Current Password</label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={e => setCurrentPassword(e.target.value)}
                  placeholder="Required to change password"
                  className="w-full glass-input rounded-xl px-4 py-2.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  placeholder="Min. 6 characters (leave empty to keep)"
                  className="w-full glass-input rounded-xl px-4 py-2.5 text-sm"
                />
              </div>
            </div>
            <div className="mt-4 p-3 rounded-xl bg-slate-900 border border-slate-700 flex items-center gap-3">
              <Shield className="w-5 h-5 text-emerald-400 shrink-0" />
              <p className="text-xs text-slate-300">
                <strong className="text-emerald-300">Security:</strong> Passwords are bcrypt-hashed with a random salt. JWT tokens expire after 7 days. All API calls are HTTPS-ready.
              </p>
            </div>
          </GlassCard>

          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-8 py-3 rounded-xl font-bold text-sm bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white shadow-lg glow-primary transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {saving ? 'Saving…' : 'Save All Settings'}
            </button>
          </div>
        </main>
      </div>
    </div>
  );
}