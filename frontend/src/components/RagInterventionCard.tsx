import React from 'react';
import { Sparkles, BookOpen, Clock, Award, CheckCircle } from 'lucide-react';
import { GlassCard } from './GlassCard';
import { friendlyCategory } from '@/lib/labels';

interface Intervention {
  id: string;
  category: string;
  title: string;
  summary: string;
  protocol: string[];
  evidence_base: string;
  difficulty: string;
  duration_min: number;
  relevance_score: number;
}

interface RagInterventionCardProps {
  intervention: Intervention;
}

export const RagInterventionCard: React.FC<RagInterventionCardProps> = ({ intervention }) => {
  return (
    <GlassCard className="border border-cyan-500/30 hover:border-cyan-500/50 transition-all">
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 uppercase tracking-wider">
            {friendlyCategory(intervention.category)}
          </span>
          <h3 className="text-lg font-bold text-white mt-2.5">{intervention.title}</h3>
        </div>
        <div className="flex items-center gap-1 text-xs font-bold text-cyan-400 bg-cyan-950/60 px-2.5 py-1 rounded-lg border border-cyan-800">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Best match</span>
        </div>
      </div>

      <p className="text-sm text-slate-300 mt-3 leading-relaxed">{intervention.summary}</p>

      <div className="mt-4 pt-3 border-t border-slate-700/50">
        <p className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Recommended Action Steps:</p>
        <ul className="space-y-1.5 text-xs text-slate-200">
          {intervention.protocol.map((step, idx) => (
            <li key={idx} className="flex items-start gap-2">
              <CheckCircle className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
              <span>{step}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-700/50 text-xs text-slate-400">
        <div className="flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span>{intervention.duration_min} min session</span>
        </div>
        <div className="flex items-center gap-1.5">
          <BookOpen className="w-3.5 h-3.5 text-slate-400" />
          <span className="truncate max-w-[200px]" title={intervention.evidence_base}>{intervention.evidence_base}</span>
        </div>
      </div>
    </GlassCard>
  );
};
