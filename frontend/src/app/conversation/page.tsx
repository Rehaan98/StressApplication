"use client";

import React, { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { Sidebar } from "@/components/Sidebar";
import { GlassCard } from "@/components/GlassCard";
import { ConversationBot, CompanionStressContext } from "@/components/ConversationBot";
import { HeartHandshake, ShieldCheck, Mic, Volume2, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import Link from "next/link";

export default function ConversationPage() {
  const [stress, setStress] = useState<CompanionStressContext | null>(null);
  const [stressLabel, setStressLabel] = useState("");
  const [openingMessage, setOpeningMessage] = useState<string | null>(null);

  // Handoff from a unified assessment result ("Talk about this result"):
  // a one-time brief (user's own words + shared reading) becomes the
  // conversation's opening context. Never invented — only what was stored.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("stressai-result-brief");
      if (raw) {
        sessionStorage.removeItem("stressai-result-brief");
        const brief = JSON.parse(raw);
        const cat = String(brief?.category ?? "");
        const mods = Array.isArray(brief?.modalities) ? brief.modalities.join(", ") : "";
        if (cat) {
          setOpeningMessage(
            `I just got my combined assessment result: ${cat}` +
            (mods ? ` (based on ${mods})` : "") +
            `. ${String(brief?.note ?? "").slice(0, 200)} Can we talk about it?`
          );
          if (typeof brief?.score === "number") {
            setStress({
              stress_score: brief.score,
              stress_level: cat,
              confidence: 0.6,
              trend: "stable",
            });
            setStressLabel(`unified assessment · ${cat}`);
          }
          return; // brief wins over the face-scan default below
        }
      }
    } catch { /* fall through to face-scan default */ }
    // Best-effort: pull the latest face-scan reading so the companion can adapt
    // its tone. The user can toggle sharing off in the chat card. Failures are
    // silent — the bot works fully without detection.
    api.getFacialHistory(1)
      .then((res) => {
        const item = res?.items?.[0];
        if (item && typeof item.stress_score === "number") {
          setStress({
            stress_score: item.stress_score,
            stress_level: item.stress_level,
            confidence: item.confidence_score ?? undefined,
            trend: "stable",
          });
          setStressLabel(`face scan ${item.stress_score}/100 · ${item.stress_level}`);
        }
      })
      .catch(() => { /* companion works without detection */ });
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 max-w-6xl mx-auto w-full space-y-6">
          <div>
            <h1 className="text-3xl font-extrabold text-white flex items-center gap-3">
              <HeartHandshake className="w-8 h-8 text-teal-300" />
              Calm Companion
            </h1>
            <p className="text-slate-400 mt-2 text-sm max-w-2xl">
              A calm place to talk things through — by voice or by typing. The companion
              listens, asks one gentle question at a time, and can guide you through
              breathing, grounding, or sorting out what&apos;s on your mind. No pressure, ever.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            <div className="lg:col-span-2">
              <ConversationBot initialStressContext={stress} stressSourceLabel={stressLabel} openingMessage={openingMessage} />
            </div>

            <div className="space-y-4">
              <GlassCard className="border border-teal-500/20">
                <h3 className="font-bold text-white text-sm mb-2 flex items-center gap-2">
                  <Mic className="w-4 h-4 text-teal-300" /> How voice chat works
                </h3>
                <ol className="text-xs text-slate-300 space-y-1.5 list-decimal list-inside leading-relaxed">
                  <li>Tap the microphone and talk naturally.</li>
                  <li>Tap stop — your words are transcribed and sent to the companion.</li>
                  <li>The companion replies in text and speaks aloud.</li>
                  <li>Interrupt anytime: tap the mic or press Stop. ✕ discards a take.</li>
                </ol>
                <p className="text-[11px] text-slate-500 mt-2 flex items-center gap-1">
                  <Volume2 className="w-3 h-3" /> Use the speaker icon to mute or unmute spoken replies.
                </p>
              </GlassCard>

              <GlassCard className="border border-cyan-500/20">
                <h3 className="font-bold text-white text-sm mb-2 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-cyan-300" /> Want step-by-step exercises?
                </h3>
                <p className="text-xs text-slate-300 leading-relaxed">
                  The companion can guide you right here, or you can browse the full
                  library of coping exercises matched to how you feel.
                </p>
                <Link
                  href="/rag-coping"
                  className="mt-3 inline-block px-4 py-2 rounded-xl text-xs font-bold bg-cyan-500/20 text-cyan-200 border border-cyan-500/40 hover:bg-cyan-500/30 transition-all"
                >
                  Open Coping Help →
                </Link>
              </GlassCard>

              <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-700 flex items-start gap-3">
                <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <div className="text-xs text-slate-300 leading-relaxed">
                  <strong className="text-emerald-300">Private by design:</strong> this chat
                  stays in your current session and is never stored as a medical record.
                  The companion is supportive, not a diagnosis — if you&apos;re ever in crisis,
                  please contact someone you trust or your local emergency support.
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
