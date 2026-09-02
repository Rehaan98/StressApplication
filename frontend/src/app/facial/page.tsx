"use client";

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { GlassCard } from '@/components/GlassCard';
import { StressGauge } from '@/components/StressGauge';
import { RagInterventionCard } from '@/components/RagInterventionCard';
import {
  ScanFace, Camera, CameraOff, AlertTriangle, ShieldCheck, Activity, Timer, Sparkles, RefreshCw,
} from 'lucide-react';
import { api } from '@/lib/api';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';

const EMOTION_META: Record<string, { emoji: string; label: string; color: string; bar: string }> = {
  happiness: { emoji: '😊', label: 'Happy', color: 'text-emerald-300', bar: 'bg-emerald-500' },
  neutral:   { emoji: '😐', label: 'Neutral', color: 'text-slate-300', bar: 'bg-slate-400' },
  surprise:  { emoji: '😲', label: 'Surprised', color: 'text-cyan-300', bar: 'bg-cyan-500' },
  sadness:   { emoji: '😢', label: 'Sad', color: 'text-blue-300', bar: 'bg-blue-500' },
  anger:     { emoji: '😠', label: 'Angry', color: 'text-rose-300', bar: 'bg-rose-500' },
  disgust:   { emoji: '🤢', label: 'Disgusted', color: 'text-lime-300', bar: 'bg-lime-500' },
  fear:      { emoji: '😨', label: 'Afraid', color: 'text-purple-300', bar: 'bg-purple-500' },
  contempt:  { emoji: '😏', label: 'Contempt', color: 'text-amber-300', bar: 'bg-amber-500' },
};

const LEVEL_COLOR: Record<string, string> = {
  Low: 'text-emerald-400', Moderate: 'text-amber-400', High: 'text-orange-400', Severe: 'text-rose-400',
};
const LEVEL_BG: Record<string, string> = {
  Low: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300',
  Moderate: 'bg-amber-500/20 border-amber-500/40 text-amber-300',
  High: 'bg-orange-500/20 border-orange-500/40 text-orange-300',
  Severe: 'bg-rose-500/20 border-rose-500/40 text-rose-300',
};

interface FacialResult {
  id: string;
  face_detected: boolean;
  dominant_emotion: string;
  emotion_probabilities: Record<string, number>;
  stress_score: number;
  stress_level: string;
  confidence_score: number;
  model: string;
  processing_ms: number;
  interventions: any[];
}

interface HistoryItem {
  id: string;
  dominant_emotion: string;
  stress_score: number;
  stress_level: string;
  confidence_score: number;
  created_at: string;
}

const CAPTURE_INTERVAL_MS = 1500;

export default function FacialAnalysisPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const armTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const analyzingRef = useRef(false);

  const [live, setLive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [noFaceWarn, setNoFaceWarn] = useState(false);
  const [result, setResult] = useState<FacialResult | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [sessionReadings, setSessionReadings] = useState<HistoryItem[]>([]);
  const [readings, setReadings] = useState(0);
  const [sessionAvg, setSessionAvg] = useState<number | null>(null);

  // Load existing history on mount
  useEffect(() => {
    api.getFacialHistory(50)
      .then((res) => setHistory(res.items ?? []))
      .catch(() => {});
  }, []);

  const stopCamera = useCallback(() => {
    // Cancel any pending warm-up arm timer first, so an interval can never
    // be registered after the user already stopped the camera.
    if (armTimerRef.current) {
      clearTimeout(armTimerRef.current);
      armTimerRef.current = null;
    }
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setLive(false);
    setAnalyzing(false);
    setNoFaceWarn(false);
    setReadings(0);
    setSessionAvg(null);
    setSessionReadings([]);
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  const captureFrame = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || analyzingRef.current) return;
    if (video.readyState < 2 || video.videoWidth === 0) return;

    analyzingRef.current = true;
    setAnalyzing(true);
    try {
      const maxW = 640;
      const scale = maxW / video.videoWidth;
      canvas.width = maxW;
      canvas.height = Math.round(video.videoHeight * scale);
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.85).split(',')[1];

      const res: FacialResult = await api.analyzeFacial(dataUrl);
      setResult(res);
      setNoFaceWarn(false);
      const item: HistoryItem = {
        id: res.id,
        dominant_emotion: res.dominant_emotion,
        stress_score: res.stress_score,
        stress_level: res.stress_level,
        confidence_score: res.confidence_score,
        created_at: new Date().toISOString(),
      };
      // Session average is computed from the current session readings only,
      // not the user's entire history.
      setSessionReadings((prev) => {
        const next = [item, ...prev].slice(0, 200);
        setSessionAvg(Math.round(next.reduce((a, b) => a + b.stress_score, 0) / next.length));
        return next;
      });
      setHistory((prev) => [item, ...prev].slice(0, 50));
      setReadings((r) => r + 1);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail === 'No face detected in the frame.') {
        setNoFaceWarn(true);
      } else {
        setCameraError(typeof detail === 'string' ? detail : 'Analysis failed. Please try again.');
      }
    } finally {
      analyzingRef.current = false;
      setAnalyzing(false);
    }
  }, []);

  const startCamera = async () => {
    setCameraError('');
    setStarting(true);
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Webcam not supported in this browser. Try Chrome or Edge.');
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setLive(true);
      // Warm-up delay, then begin periodic analysis. The timer is tracked so
      // stopping the camera during warm-up cannot leave an orphaned interval.
      armTimerRef.current = setTimeout(() => {
        armTimerRef.current = null;
        if (!streamRef.current) return; // stopped during warm-up
        captureFrame();
        intervalRef.current = setInterval(captureFrame, CAPTURE_INTERVAL_MS);
      }, 1200);
    } catch (err: any) {
      setCameraError(err?.message ?? 'Could not access the webcam. Please allow camera permission.');
    } finally {
      setStarting(false);
    }
  };

  const sortedEmotions = result
    ? Object.entries(result.emotion_probabilities).sort((a, b) => b[1] - a[1])
    : [];
  const meta = result ? EMOTION_META[result.dominant_emotion] ?? EMOTION_META.neutral : null;

  const sessionLevel =
    sessionAvg === null ? null
      : sessionAvg >= 80 ? 'Severe'
      : sessionAvg >= 60 ? 'High'
      : sessionAvg >= 35 ? 'Moderate'
      : 'Low';

  const chartData = [...sessionReadings].reverse().map((h, i) => ({
    name: `#${i + 1}`,
    score: h.stress_score,
    level: h.stress_level,
  }));

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 max-w-7xl mx-auto space-y-6">
          {/* Hero Banner */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-3xl bg-gradient-to-r from-violet-900/40 via-slate-900 to-indigo-900/30 border border-violet-500/30">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-violet-600 to-cyan-400 flex items-center justify-center glow-primary">
                <ScanFace className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-2xl md:text-3xl font-extrabold text-white">Face Stress Scanner</h1>
                <p className="text-sm text-slate-300 mt-1">
                  Our AI reads your facial expressions through your webcam to spot stress in real time
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-300 bg-slate-900/70 border border-slate-700 rounded-xl px-3 py-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Frames are analyzed securely & never stored as images</span>
            </div>
          </div>

          {cameraError && (
            <div className="flex items-center gap-3 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/40 text-rose-300 text-sm">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <div>
                <p className="font-semibold">{cameraError}</p>
                <p className="text-xs text-rose-300/70 mt-0.5">
                  On macOS: System Settings → Privacy & Security → Camera → allow your browser.
                </p>
              </div>
              <button onClick={() => setCameraError('')} className="ml-auto text-xs font-bold px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 transition-colors">
                Dismiss
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Camera Card */}
            <GlassCard className="lg:col-span-2 flex flex-col">
              <div className="flex items-center justify-between border-b border-slate-700/50 pb-3 mb-4">
                <div className="flex items-center gap-2">
                  {live ? <Camera className="w-5 h-5 text-emerald-400" /> : <CameraOff className="w-5 h-5 text-slate-400" />}
                  <h3 className="font-bold text-white text-base">{live ? 'Live Scan in Progress' : 'Camera Off'}</h3>
                </div>
                {live && (
                  <span className="flex items-center gap-2 text-xs font-bold text-emerald-300 bg-emerald-500/15 border border-emerald-500/40 rounded-full px-3 py-1">
                    <span className="relative flex h-2.5 w-2.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                    </span>
                    LIVE
                  </span>
                )}
              </div>

              <div className="relative rounded-2xl overflow-hidden bg-slate-900 border border-slate-700/60 aspect-video">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className={`w-full h-full object-cover transition-all duration-500 ${live ? 'opacity-100' : 'opacity-0'}`}
                />
                {!live && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-slate-500">
                    <ScanFace className="w-16 h-16" />
                    <p className="text-sm font-medium">Camera preview appears here</p>
                    <p className="text-xs text-slate-600">Position your face in good lighting, facing the camera</p>
                  </div>
                )}
                {live && (
                  <>
                    <div className="absolute inset-0 pointer-events-none scanlines" />
                    <div className="absolute inset-0 rounded-2xl border-2 border-transparent pointer-events-none"
                      style={{ boxShadow: 'inset 0 0 40px rgba(139,92,246,0.15)' }} />
                    {analyzing && (
                      <div className="absolute top-3 right-3 flex items-center gap-1.5 text-[11px] font-bold text-violet-300 bg-slate-950/80 border border-violet-500/40 rounded-full px-2.5 py-1">
                        <RefreshCw className="w-3 h-3 animate-spin" /> Analyzing…
                      </div>
                    )}
                  </>
                )}
                <canvas ref={canvasRef} className="hidden" />
              </div>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  {noFaceWarn && live && (
                    <p className="text-xs font-semibold text-amber-300 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" /> No face detected — look toward the camera
                    </p>
                  )}
                  {!noFaceWarn && live && (
                    <p className="text-xs text-slate-400 flex items-center gap-1.5">
                      <Timer className="w-3.5 h-3.5" /> Analyzing every {CAPTURE_INTERVAL_MS / 1000}s · {readings} readings taken
                    </p>
                  )}
                  {!live && !cameraError && (
                    <p className="text-xs text-slate-400">Your video stays on this device — only a small anonymized frame is sent for analysis.</p>
                  )}
                </div>
                {!live ? (
                  <button
                    onClick={startCamera}
                    disabled={starting}
                    className="px-6 py-3 rounded-xl font-bold text-sm bg-gradient-to-r from-violet-600 to-cyan-500 hover:from-violet-500 hover:to-cyan-400 text-white shadow-lg glow-primary flex items-center gap-2 transition-all disabled:opacity-60"
                  >
                    {starting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
                    {starting ? 'Starting Camera…' : 'Start Live Scan'}
                  </button>
                ) : (
                  <button
                    onClick={stopCamera}
                    className="px-6 py-3 rounded-xl font-bold text-sm bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/40 flex items-center gap-2 transition-all"
                  >
                    <CameraOff className="w-4 h-4" /> Stop Scan
                  </button>
                )}
              </div>
            </GlassCard>

            {/* Live Emotion & Stress Card */}
            <GlassCard className="flex flex-col">
              <div className="flex items-center justify-between border-b border-slate-700/50 pb-3 mb-4">
                <div className="flex items-center gap-2">
                  <Activity className="w-5 h-5 text-violet-400" />
                  <h3 className="font-bold text-white text-base">Your Emotions Right Now</h3>
                </div>
                {result && (
                  <span className={`text-xs px-2.5 py-0.5 rounded-full font-bold border ${LEVEL_BG[result.stress_level] ?? ''}`}>
                    {result.stress_level}
                  </span>
                )}
              </div>

              {!result ? (
                <div className="flex flex-col items-center justify-center flex-1 py-10 text-center text-slate-500">
                  <ScanFace className="w-14 h-14 text-slate-600 mb-3" />
                  <p className="text-sm font-medium">Waiting for analysis</p>
                  <p className="text-xs mt-1 max-w-[220px]">Start the live scan to read your facial expressions in real time</p>
                </div>
              ) : (
                <>
                  <div className="flex flex-col items-center py-2">
                    <div className="text-6xl mb-2 drop-shadow-lg">{meta?.emoji}</div>
                    <div className={`text-xl font-extrabold ${meta?.color ?? 'text-slate-200'}`}>
                      {meta?.label ?? result.dominant_emotion}
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1">
                      How sure: {(result.confidence_score * 100).toFixed(0)}% · Analysed in {result.processing_ms}ms
                    </p>
                  </div>

                  <StressGauge level={result.stress_level} score={result.stress_score} />

                  <div className="mt-4 space-y-2">
                    {sortedEmotions.map(([emotion, prob]) => {
                      const m = EMOTION_META[emotion] ?? { label: emotion, bar: 'bg-slate-500' };
                      return (
                        <div key={emotion} className="flex items-center gap-2 text-xs">
                          <span className="w-20 shrink-0 text-slate-400">{m.label}</span>
                          <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                            <div className={`h-full ${m.bar} rounded-full transition-all duration-700`} style={{ width: `${prob * 100}%` }} />
                          </div>
                          <span className="w-9 text-right text-slate-300 font-semibold">{(prob * 100).toFixed(0)}%</span>
                        </div>
                      );
                    })}
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-700/50 flex items-center justify-between text-xs">
                    <span className="text-slate-400">Session average</span>
                    <span className={`font-extrabold text-base ${sessionAvg === null ? 'text-slate-500' : LEVEL_COLOR[sessionLevel ?? ''] ?? 'text-slate-200'}`}>
                      {sessionAvg === null ? '—' : sessionAvg}
                    </span>
                  </div>
                </>
              )}
            </GlassCard>
          </div>

          {/* RAG Coping Interventions */}
          {result && result.interventions.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="w-5 h-5 text-cyan-400" />
                <h3 className="font-bold text-white text-base">Coping Exercises for You (Coping Help)</h3>
                <span className="text-xs text-slate-400">matched to how you are feeling right now</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                {result.interventions.map((iv) => (
                  <RagInterventionCard key={iv.id} intervention={iv} />
                ))}
              </div>
            </div>
          )}

          {/* History & Trend */}
          <GlassCard gradient>
            <div className="flex items-center justify-between border-b border-slate-700/50 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-indigo-400" />
                <h3 className="font-bold text-white text-base">Session Stress Trend</h3>
              </div>
              {sessionReadings.length > 0 && (
                <div className="flex items-center gap-2">
                  {Object.entries(EMOTION_META).filter(([e]) => sessionReadings.some((h) => h.dominant_emotion === e)).map(([e, m]) => (
                    <span key={e} className="text-lg" title={m.label}>{m.emoji}</span>
                  ))}
                </div>
              )}
            </div>

            {sessionReadings.length === 0 ? (
              <div className="text-center py-10 text-slate-500 text-sm">
                No scans in this session yet — start the live scan above.
                {history.length > 0 && (
                  <p className="text-xs text-slate-600 mt-2">You have {history.length} past scan{history.length > 1 ? 's' : ''} on record.</p>
                )}
              </div>
            ) : (
              <>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="stressGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.5} />
                          <stop offset="100%" stopColor="#a78bfa" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#33415555" />
                      <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                      <YAxis domain={[0, 100]} stroke="#64748b" fontSize={11} />
                      <Tooltip
                        contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, fontSize: 12 }}
                        labelStyle={{ color: '#94a3b8' }}
                        formatter={(v: any) => [`${v} / 100`, 'Stress Score']}
                      />
                      <Area type="monotone" dataKey="score" stroke="#a78bfa" strokeWidth={2.5} fill="url(#stressGrad)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-700/50 flex flex-wrap gap-2 text-xs">
                  {sessionReadings.slice(0, 12).map((h, i) => (
                    <span key={h.id} className={`px-2 py-1 rounded-lg border ${LEVEL_BG[h.stress_level] ?? 'bg-slate-800 border-slate-700 text-slate-300'}`}>
                      {EMOTION_META[h.dominant_emotion]?.emoji ?? '😶'} {h.stress_score}
                    </span>
                  ))}
                </div>
              </>
            )}

            {history.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-700/50">
                <p className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider mb-2">
                  Past scans on record · {history.length}
                </p>
                <div className="flex flex-wrap gap-2 text-xs">
                  {history.slice(0, 15).map((h, i) => (
                    <span key={i} className={`px-2 py-1 rounded-lg border ${LEVEL_BG[h.stress_level] ?? 'bg-slate-800 border-slate-700 text-slate-300'}`}>
                      {EMOTION_META[h.dominant_emotion]?.emoji ?? '😶'} {h.stress_score}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </GlassCard>
        </main>
      </div>
    </div>
  );
}
