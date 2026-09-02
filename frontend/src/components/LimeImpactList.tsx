import React from 'react';
import { ArrowUpRight, ArrowDownRight, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { friendlyRule } from '@/lib/labels';

interface LimeRule {
  rule: string;
  weight: number;
  effect: string;
}

interface LimeImpactListProps {
  rules: LimeRule[];
}

export const LimeImpactList: React.FC<LimeImpactListProps> = ({ rules }) => {
  return (
    <div className="space-y-3">
      {rules.map((item, idx) => {
        const isNegative = item.weight > 0;
        return (
          <div
            key={idx}
            className={`flex items-center justify-between gap-3 p-3 rounded-xl border text-sm transition-all ${
              isNegative
                ? 'bg-rose-500/10 border-rose-500/30 text-rose-200'
                : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
            }`}
          >
            <div className="flex items-center gap-3 min-w-0">
              {isNegative ? (
                <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0" />
              ) : (
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              )}
              <span className="text-xs text-slate-200">{friendlyRule(item.rule)}</span>
            </div>
            <div className="flex items-center gap-1.5 font-bold shrink-0">
              {isNegative ? (
                <ArrowUpRight className="w-4 h-4 text-rose-400" />
              ) : (
                <ArrowDownRight className="w-4 h-4 text-emerald-400" />
              )}
              <span className="text-xs">{Math.abs(item.weight).toFixed(2)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
