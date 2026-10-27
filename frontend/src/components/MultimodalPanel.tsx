"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { notifyDataUpdated, useLiveData } from "@/lib/liveData";
import { GlassCard } from "@/components/GlassCard";
import { StressGauge } from "@/components/StressGauge";
import { RagInterventionCard } from "@/components/RagInterventionCard";
import {
  Mic, Square, Loader2, AlertCircle, ClipboardList, ScanFace,
  Layers, CheckCircle2, XCircle, FlaskConical, Play, Flag, Ban,
  MessageCircleHeart,
} from "lucide-react";

const GAUGE_MAP: Record<string, number> = {
  Low: 18, Moderate: 48, High: 73, Severe: 92, Uncertain: 50,
};

const LEVEL_STYLE: Record<string, string> = {
  Low: "text-emerald-300 border-emerald-500/40 bg-emerald-500/10",
  Moderate: "text-amber-300 border-amber-500/40 bg-amber-500/10",
  High: "text-orange-300 border-orange-500/40 bg-orange-500/10",
  Severe: "text-rose-300 border-rose-500/40 bg-rose-500/10",
  Uncertain: "text-slate-300 border-slate-600 bg-slate-800",
};

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      const i = result.indexOf(",");
      resolve(i >= 0 ? result.slice(i + 1) : result);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

export const MultimodalPanel: React.FC = () => {
  // Session lifecycle: idle → collecting → finalizing → completed/cancelled
  const [sessionId, setSessionId] = useState("");
  const [consentMic, setConsentMic] = useState(false);
  const [consentCam, setConsentCam] = useState(false);
  const [assessments, setAssessments] = useState<any[]>([]);
  const [assessmentId, setAssessmentId] = useState("");
  const [voiceText, setVoiceText] = useState("");
  const [recording, setRecording] = useState(false);
  const [camOn, setCamOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const camStreamRef = useRef<MediaStream | null>(null);

  const loadAssessments = useCallback(async () => {
    try {
      const items: any = await api.listAssessments();
      const list = Array.isArray(items) ? items : [];
      setAssessments(list);
      setAssessmentId((current) => current || (list[0]?.id ?? ""));
    } catch {
      // Keep the current options if a background refresh fails.
    }
  }, []);

  useEffect(() => {
    loadAssessments();
    return () => {
      streamRef.current?.getTracks().forEach((t) => { try { t.stop(); } catch {} });
      camStreamRef.current?.getTracks().forEach((t) => { try { t.stop(); } catch {} });
    };
  }, [loadAssessments]);
  useLiveData(loadAssessments);

  const refreshLive = useCallback(async (sid: string) => {
    try {
      setLive(await api.mmSessionLive(sid));
    } catch { /* provisional is best-effort */ }
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const s = await api.mmSessionStart();
      setSessionId(s.session_id);
      setLive(null);
      setResult(null);
    } catch {
      setError("Could not start an assessment session. Is the backend running?");
    }
  }, []);

  const cancel = useCallback(async () => {
    if (!sessionId) return;
    try { await api.mmSessionCancel(sessionId); } catch { /* local close anyway */ }
    streamRef.current?.getTracks().forEach((t) => { try { t.stop(); } catch {} });
    camStreamRef.current?.getTracks().forEach((t) => { try { t.stop(); } catch {} });
    streamRef.current = null;
    camStreamRef.current = null;
    setSessionId("");
    setLive(null);
    setRecording(false);
    setCamOn(false);
  }, [sessionId]);

  const attachQuestionnaire = useCallback(async () => {
    if (!sessionId || !assessmentId || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.mmSessionQuestionnaire(sessionId, assessmentId);
      await refreshLive(sessionId);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Questionnaire could not be attached.");
    } finally {
      setBusy(false);
    }
  }, [sessionId, assessmentId, busy, refreshLive]);

  const toggleRecord = useCallback(async () => {
    if (recording) {
      const rec = recRef.current;
      if (rec && rec.state !== "inactive") { try { rec.stop(); } catch {} }
      return;
    }
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const rec = new MediaRecorder(stream);
      recRef.current = rec;
      chunksRef.current = [];
      rec.ondataavailable = (e: BlobEvent) => { if (e.data?.size) chunksRef.current.push(e.data); };
      rec.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        setRecording(false);
        streamRef.current?.getTracks().forEach((t) => { try { t.stop(); } catch {} });
        streamRef.current = null;
        recRef.current = null;
        if (blob.size < 800) {
          setError("Nothing was recorded — try again, or type your words and press Send voice words.");
          return;
        }
        let words = voiceText.trim();
        try {
          const base64 = await blobToBase64(blob);
          setBusy(true);
          await api.mmSessionVoice(sessionId, { audio_base64: base64, ...(words ? { transcript: words } : {}) });
          await refreshLive(sessionId);
        } catch (e: any) {
          setError(e?.response?.data?.detail || "Voice analysis failed for that clip.");
        } finally {
          setBusy(false);
        }
      };
      rec.start(250);
      setRecording(true);
    } catch (e: any) {
      setError(e?.name === "NotAllowedError"
        ? "Microphone permission denied — allow it, or continue with questionnaire and face scan."
        : "Could not access the microphone.");
    }
  }, [recording, sessionId, voiceText, refreshLive]);

  const sendVoiceWords = useCallback(async () => {
    const words = voiceText.trim();
    if (!sessionId || !words || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.mmSessionVoice(sessionId, { transcript: words });
      await refreshLive(sessionId);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Voice words could not be added.");
    } finally {
      setBusy(false);
    }
  }, [sessionId, voiceText, busy, refreshLive]);

  const toggleCam = useCallback(async () => {
    if (camOn) {
      camStreamRef.current?.getTracks().forEach((t) => { try { t.stop(); } catch {} });
      camStreamRef.current = null;
      setCamOn(false);
      return;
    }
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      camStreamRef.current = s;
      setCamOn(true);
      setTimeout(() => { if (videoRef.current) videoRef.current.srcObject = s; }, 50);
    } catch {
      setError("Could not access the camera. The session continues with voice and questionnaire.");
    }
  }, [camOn]);

  const snapFace = useCallback(async () => {
    const v = videoRef.current;
    if (!v || !v.videoWidth || !sessionId || busy) return;
    const c = document.createElement("canvas");
    const scale = Math.min(1, 640 / v.videoWidth);
    c.width = Math.round(v.videoWidth * scale);
    c.height = Math.round(v.videoHeight * scale);
    c.getContext("2d")?.drawImage(v, 0, 0, c.width, c.height);
    const image = c.toDataURL("image/jpeg", 0.85).split(",")[1];
    setBusy(true);
    setError(null);
    try {
      await api.mmSessionFace(sessionId, { image_base64: image });
      await refreshLive(sessionId);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "That frame couldn't be analyzed (no face / poor light?). Try again.");
    } finally {
      setBusy(false);
    }
  }, [sessionId, busy, refreshLive]);

  const finish = useCallback(async () => {
    if (!sessionId || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.mmSessionFinalize(sessionId);
      setResult(res);
      setLive(null);
      notifyDataUpdated(true);
      streamRef.current?.getTracks().forEach((t) => { try { t.stop(); } catch {} });
      camStreamRef.current?.getTracks().forEach((t) => { try { t.stop(); } catch {} });
      setRecording(false);
      setCamOn(false);
      setSessionId("");
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Finalize needs at least one valid input.");
    } finally {
      setBusy(false);
    }
  }, [sessionId, busy]);

  const talkAboutResult = useCallback(() => {
    if (!result) return;
    const brief = {
      category: result.overall_category,
      score: result.overall_estimate,
      modalities: result.available_modalities ?? [],
      note: result.overall_note ?? "",
    };
    try { sessionStorage.setItem("stressai-result-brief", JSON.stringify(brief)); } catch { /* ignore */ }
  }, [result]);

  const mods = (src: any) => [
    { key: "questionnaire", label: "Questionnaire", icon: ClipboardList, data: src?.questionnaire_result },
    { key: "voice", label: "Voice", icon: Mic, data: src?.voice_result },
    { key: "facial", label: "Face scan", icon: ScanFace, data: src?.face_result },
  ];

  const shown = result ?? live;
  const isFinal = !!result;

  return (
    <GlassCard gradient className="border border-violet-500/30">
      <div className="flex items-center gap-2 mb-1">
        <Layers className="w-5 h-5 text-violet-300" />
        <h3 className="font-bold text-white text-base">Unified Multimodal Assessment</h3>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-200 border border-violet-500/30 flex items-center gap-1">
          <FlaskConical className="w-3 h-3" /> experimental fusion
        </span>
        {live && !result && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-200 border border-amber-500/30">
            provisional — updates live
          </span>
        )}
      </div>
      <p className="text-xs text-slate-400 mb-4">
        One synchronized session: answer questions while voice and face analysis run in parallel.
        Missing inputs are left out, never zero-filled. An AI estimate, not a diagnosis.
      </p>

      {!sessionId && !result && (
        <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3 space-y-2">
          <label className="flex items-start gap-2 text-xs text-slate-300 cursor-pointer">
            <input type="checkbox" checked={consentMic} onChange={(e) => setConsentMic(e.target.checked)} className="mt-0.5 accent-violet-400" />
            <span>I agree to microphone use for voice stress analysis during this session. I can pause or stop anytime.</span>
          </label>
          <label className="flex items-start gap-2 text-xs text-slate-300 cursor-pointer">
            <input type="checkbox" checked={consentCam} onChange={(e) => setConsentCam(e.target.checked)} className="mt-0.5 accent-violet-400" />
            <span>I agree to camera use for facial analysis during this session. Frames are analyzed, never stored.</span>
          </label>
          <button onClick={start}
            className="w-full px-4 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-violet-600 to-cyan-500 text-white flex items-center justify-center gap-2">
            <Play className="w-4 h-4" /> Start synchronized assessment
          </button>
          <p className="text-[11px] text-slate-500">Tip: you can start with neither and add only the questionnaire.</p>
        </div>
      )}

      {sessionId && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
          <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
            <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-1.5">1 · Questionnaire (alongside)</div>
            {assessments.length === 0 ? (
              <p className="text-xs text-slate-500">No checks yet — <a href="/assessment" className="text-indigo-300 underline">take one</a>.</p>
            ) : (
              <div className="flex gap-1.5">
                <select value={assessmentId} onChange={(e) => setAssessmentId(e.target.value)}
                  className="flex-1 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-200 p-2">
                  {assessments.map((a: any) => (
                    <option key={a.id} value={a.id}>
                      PSS {a.total_pss ?? "?"} · {a.created_at ? new Date(a.created_at).toLocaleDateString() : ""}
                    </option>
                  ))}
                </select>
                <button onClick={attachQuestionnaire} disabled={busy || !assessmentId}
                  className="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-indigo-500/20 text-indigo-200 border border-indigo-500/40 disabled:opacity-50">
                  Add
                </button>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
            <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-1.5">
              2 · Voice {recording && <span className="text-rose-300">● recording</span>}
            </div>
            {!consentMic && <p className="text-[11px] text-slate-500 mb-1.5">Mic consent not given — type words below instead.</p>}
            <div className="flex gap-1.5">
              <button onClick={toggleRecord} disabled={!consentMic || busy}
                className={`flex-1 px-2 py-1.5 rounded-lg text-xs font-semibold border flex items-center justify-center gap-1 disabled:opacity-50 ${
                  recording ? "bg-rose-500/15 text-rose-200 border-rose-500/40 animate-pulse" : "bg-indigo-500/15 text-indigo-200 border-indigo-500/40"}`}>
                {recording ? <Square className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
                {recording ? "Stop" : "Record"}
              </button>
              <button onClick={sendVoiceWords} disabled={busy || !voiceText.trim()}
                className="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-teal-500/15 text-teal-200 border border-teal-500/40 disabled:opacity-50">
                Send words
              </button>
            </div>
            <textarea value={voiceText} onChange={(e) => setVoiceText(e.target.value)} rows={2}
              placeholder="Or type what you'd say…"
              className="mt-1.5 w-full rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-200 p-2 placeholder:text-slate-500" />
          </div>

          <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
            <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-1.5">
              3 · Face scan {camOn && <span className="text-violet-300">● camera on</span>}
            </div>
            {!consentCam && <p className="text-[11px] text-slate-500 mb-1.5">Camera consent not given — session runs without it.</p>}
            {!camOn ? (
              <button onClick={toggleCam} disabled={!consentCam || busy}
                className="w-full px-2 py-1.5 rounded-lg text-xs font-semibold bg-violet-500/15 text-violet-200 border border-violet-500/40 disabled:opacity-50 flex items-center justify-center gap-1">
                <ScanFace className="w-3.5 h-3.5" /> Open camera
              </button>
            ) : (
              <div className="space-y-1.5">
                <video ref={videoRef} autoPlay muted playsInline className="w-full h-20 rounded-lg border border-slate-700 object-cover" />
                <div className="flex gap-1.5">
                  <button onClick={snapFace} disabled={busy} className="flex-1 px-2 py-1 rounded-lg text-xs font-bold bg-violet-500/20 text-violet-200 border border-violet-500/40 disabled:opacity-50">Analyze frame</button>
                  <button onClick={toggleCam} className="px-2 py-1 rounded-lg text-xs text-slate-400 border border-slate-700">Close</button>
                </div>
              </div>
            )}
            {!camOn && <video ref={videoRef} className="hidden" />}
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-200 flex gap-2 mb-3">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" /><span>{error}</span>
        </div>
      )}

      {sessionId && (
        <div className="flex gap-2">
          <button onClick={finish} disabled={busy}
            className="flex-1 px-4 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-violet-600 to-cyan-500 text-white disabled:opacity-50 flex items-center justify-center gap-2">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Flag className="w-4 h-4" />}
            {busy ? "Working…" : "Finish & combine results"}
          </button>
          <button onClick={cancel}
            className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-300 border border-slate-600 hover:border-rose-400 flex items-center gap-1">
            <Ban className="w-3.5 h-3.5" /> Cancel
          </button>
        </div>
      )}

      {shown && (
        <div className="mt-4 pt-4 border-t border-slate-700/50 space-y-4">
          <div className={`p-4 rounded-2xl border text-center ${LEVEL_STYLE[shown.overall_category] ?? LEVEL_STYLE.Uncertain}`}>
            <p className="text-[11px] uppercase tracking-wider opacity-80">
              {isFinal ? "Unified estimate" : "Provisional estimate"} · {shown.overall_category}
            </p>
            <p className="text-3xl font-extrabold text-white mt-1">
              {shown.overall_estimate != null ? `${Math.round(shown.overall_estimate * 100)}/100` : "—"}
            </p>
            <p className="text-xs mt-1 opacity-80">{shown.overall_note}</p>
            <p className="text-[11px] mt-1 opacity-70">
              Reliability {(100 * (1 - (shown.uncertainty ?? 0))).toFixed(0)}% · {shown.fusion_method}
            </p>
          </div>

          <StressGauge level={shown.overall_category === "Uncertain" ? "Moderate" : shown.overall_category}
            score={shown.overall_estimate != null ? Math.round(shown.overall_estimate * 100) : GAUGE_MAP.Uncertain} />

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {mods(shown).map((m) => (
              <div key={m.key} className={`rounded-xl border p-2.5 ${m.data ? "border-slate-600 bg-slate-900/70" : "border-slate-800 bg-slate-900/40 opacity-60"}`}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-200">{m.label}</span>
                  {m.data
                    ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    : <span className="text-[10px] text-slate-500 flex items-center gap-1"><XCircle className="w-3 h-3" /> not included</span>}
                </div>
                {m.data ? (
                  <>
                    <p className="text-lg font-extrabold text-white mt-0.5">
                      {m.data.score != null ? `${Math.round(m.data.score * 100)}` : "—"}
                      <span className="text-[11px] font-semibold text-slate-400"> · {m.data.level}</span>
                    </p>
                    <p className="text-[11px] text-slate-400">
                      confidence {Math.round((m.data.confidence ?? 0) * 100)}%
                      {m.data.updated_at ? ` · ${new Date(m.data.updated_at * 1000).toLocaleTimeString()}` : ""}
                      {m.data.stale ? " · stale" : ""}
                    </p>
                    {m.key === "questionnaire" && m.data.detail?.interpretation && (
                      <p className="text-[11px] text-slate-300 mt-1">{m.data.detail.interpretation}</p>
                    )}
                    {m.key === "voice" && m.data.detail?.explanation && (
                      <p className="text-[11px] text-slate-300 mt-1 line-clamp-3">{m.data.detail.explanation}</p>
                    )}
                    {m.key === "facial" && m.data.detail?.emotion && (
                      <p className="text-[11px] text-slate-300 mt-1 capitalize">read as: {m.data.detail.emotion}</p>
                    )}
                  </>
                ) : (
                  <p className="text-[11px] text-slate-500 mt-1">Left out — never counted as zero.</p>
                )}
              </div>
            ))}
          </div>

          {(shown.contributing_factors?.length ?? 0) > 0 && (
            <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
              <p className="text-[11px] uppercase tracking-wider text-slate-400 mb-1.5">Why this result (actual evidence)</p>
              <ul className="text-xs text-slate-200 space-y-1 list-disc list-inside">
                {shown.contributing_factors.map((f: any, i: number) => (
                  <li key={i}><span className="text-slate-400">[{f.source}]</span> {f.text}</li>
                ))}
              </ul>
            </div>
          )}

          {(shown.limitations?.length ?? 0) > 0 && (
            <div className="rounded-xl border border-amber-500/25 bg-amber-950/10 p-3">
              <p className="text-[11px] uppercase tracking-wider text-amber-200 mb-1.5">Limitations</p>
              <ul className="text-[11px] text-slate-300 space-y-1 list-disc list-inside">
                {shown.limitations.map((l: string, i: number) => <li key={i}>{l}</li>)}
              </ul>
            </div>
          )}

          {(shown.recommendations?.length ?? 0) > 0 && isFinal && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {shown.recommendations.map((iv: any) => (
                <RagInterventionCard key={iv.id || iv.title} intervention={iv} />
              ))}
            </div>
          )}

          {isFinal && (
            <Link href="/conversation" onClick={talkAboutResult}
              className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-xl text-sm font-bold bg-teal-500/15 text-teal-200 border border-teal-500/40 hover:bg-teal-500/25 transition-all">
              <MessageCircleHeart className="w-4 h-4" /> Talk about this result with the companion
            </Link>
          )}
        </div>
      )}
    </GlassCard>
  );
};
