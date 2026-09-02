import React from 'react';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  gradient?: boolean;
}

export const GlassCard: React.FC<GlassCardProps> = ({ children, className = '', gradient = false }) => {
  return (
    <div className={`rounded-2xl p-6 glass-morphism transition-all duration-300 ${gradient ? 'bg-gradient-to-br from-slate-800/80 via-slate-900/80 to-slate-800/80 border-indigo-500/20' : ''} ${className}`}>
      {children}
    </div>
  );
};
