import React from 'react';

interface StressGaugeProps {
  level: string; // Low, Moderate, High, Severe
  score?: number;
}

export const StressGauge: React.FC<StressGaugeProps> = ({ level, score = 65 }) => {
  const getBadgeStyle = (lvl: string) => {
    switch (lvl.toLowerCase()) {
      case 'low':
        return { text: 'Low Stress', color: 'text-emerald-400', bg: 'bg-emerald-500/20 border-emerald-500/40', bar: 'bg-emerald-500' };
      case 'moderate':
        return { text: 'Moderate Stress', color: 'text-amber-400', bg: 'bg-amber-500/20 border-amber-500/40', bar: 'bg-amber-500' };
      case 'high':
        return { text: 'High Stress', color: 'text-orange-400', bg: 'bg-orange-500/20 border-orange-500/40', bar: 'bg-orange-500' };
      case 'severe':
        return { text: 'Severe Stress', color: 'text-rose-400', bg: 'bg-rose-500/20 border-rose-500/40', bar: 'bg-rose-500' };
      default:
        return { text: 'Moderate Stress', color: 'text-amber-400', bg: 'bg-amber-500/20 border-amber-500/40', bar: 'bg-amber-500' };
    }
  };

  const config = getBadgeStyle(level);

  return (
    <div className="flex flex-col items-center justify-center p-4">
      <div className={`px-4 py-1.5 rounded-full text-sm font-bold border ${config.bg} ${config.color} uppercase tracking-wider mb-4`}>
        {config.text}
      </div>
      
      <div className="w-full bg-slate-800 rounded-full h-3.5 p-0.5 border border-slate-700">
        <div className={`h-2.5 rounded-full ${config.bar} transition-all duration-1000`} style={{ width: `${score}%` }}></div>
      </div>
      
      <div className="flex justify-between w-full text-xs text-slate-400 mt-2 px-1">
        <span>Low</span>
        <span>Moderate</span>
        <span>High</span>
        <span>Severe</span>
      </div>
    </div>
  );
};
