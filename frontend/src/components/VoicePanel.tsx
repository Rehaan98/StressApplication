"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { notifyDataUpdated } from "@/lib/liveData";
import { GlassCard } from "@/components/GlassCard";
import { LEVEL_LABELS, LEVEL_EXPLANATIONS } from "@/lib/labels";
import { Mic, Square, Loader2, AlertCircle, TrendingUp, TrendingDown, Minus, Sparkles, Clock } from "lucide-react";
import { friendlyCategory } from "@/lib/labels";

type VoiceLevel = "Low" | "Moderate" | "High" | "Severe";

type VoiceIntervention = {
  id: string;
  category: string;
  title: string;
  summary: string;
  protocol: string[];
  evidence_base: string;
  difficulty: string;
  duration_min: number;
  relevance_score: number;
};

type VoiceHistoryItem = {
  id: string;
  score: number; // 0-100
  level: VoiceLevel;
  confidence: number; // 0-1
  duration: number; // seconds
  transcript: string;
  ts: number;
};

// ---- SpeechRecognition typings (browser API, no npm dep) ----
declare global {
  interface Window {
    SpeechRecognition?: any;
    webkitSpeechRecognition?: any;
  }
}
type RecognitionEvent = {
  resultIndex: number;
  results: ArrayLike<{
    isFinal: boolean;
    [index: number]: { transcript: string };
  }>;
};

// ---- Audio helpers ----

function pickSupportedMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  for (const t of candidates) {
    try {
      if (MediaRecorder.isTypeSupported(t)) return t;
    } catch {
      /* ignore */
    }
  }
  return undefined;
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      try {
        const result = reader.result as string;
        const comma = result.indexOf(",");
        resolve(comma >= 0 ? result.slice(comma + 1) : result);
      } catch (e) {
        reject(e);
      }
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/** Convert any recorded blob (webm/opus, mp4) to 16kHz mono WAV base64 for reliable backend decoding. */
async function blobToWav16kBase64(blob: Blob, targetRate = 16000): Promise<{ base64: string; duration: number }> {
  const arrayBuffer = await blob.arrayBuffer();
  const AC: typeof AudioContext | undefined =
    window.AudioContext || (window as any).webkitAudioContext;
  if (!AC) {
    const base64 = await blobToBase64(blob);
    return { base64, duration: 0 };
  }
  const ctx = new AC();
  try {
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0));
    const numCh = audioBuffer.numberOfChannels;
    const inRate = audioBuffer.sampleRate;
    const inLen = audioBuffer.length;
    // Mix to mono
    const mono = new Float32Array(inLen);
    for (let ch = 0; ch < numCh; ch++) {
      const data = audioBuffer.getChannelData(ch);
      for (let i = 0; i < inLen; i++) mono[i] += data[i] / numCh;
    }
    // Linear resample to targetRate
    const durationSec = inLen / inRate;
    const outLen = Math.max(1, Math.floor(durationSec * targetRate));
    const out = new Float32Array(outLen);
    if (inRate === targetRate) {
      out.set(mono.subarray(0, Math.min(outLen, mono.length)));
    } else {
      const ratio = inLen / outLen;
      for (let i = 0; i < outLen; i++) {
        const pos = i * ratio;
        const i0 = Math.floor(pos);
        const i1 = Math.min(i0 + 1, inLen - 1);
        const frac = pos - i0;
        out[i] = mono[i0] * (1 - frac) + mono[i1] * frac;
      }
    }
    // Encode 16-bit PCM WAV
    const buffer = new ArrayBuffer(44 + outLen * 2);
    const view = new DataView(buffer);
    const writeStr = (off: number, s: string) => {
      for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
    };
    writeStr(0, "RIFF");
    view.setUint32(4, 36 + outLen * 2, true);
    writeStr(8, "WAVE");
    writeStr(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, targetRate, true);
    view.setUint32(28, targetRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeStr(36, "data");
    view.setUint32(40, outLen * 2, true);
    for (let i = 0; i < outLen; i++) {
      const s = Math.max(-1, Math.min(1, out[i]));
      view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    const wavBlob = new Blob([buffer], { type: "audio/wav" });
    const base64 = await blobToBase64(wavBlob);
    return { base64, duration: durationSec };
  } finally {
    try {
      await ctx.close();
    } catch {
      /* ignore */
    }
  }
}

function levelColor(level: string): string {
  switch (level) {
    case "Low":
      return "text-emerald-300 border-emerald-500/40 bg-emerald-500/10";
    case "Moderate":
      return "text-amber-300 border-amber-500/40 bg-amber-500/10";
    case "High":
      return "text-orange-300 border-orange-500/40 bg-orange-500/10";
    case "Severe":
      return "text-rose-300 border-rose-500/40 bg-rose-500/10";
    default:
      return "text-slate-300 border-slate-600 bg-slate-800";
  }
}

export const VoicePanel: React.FC = () => {
  const { user } = useAuth();
  const [isListening, setIsListening] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [voiceScore, setVoiceScore] = useState(0);
  const [voiceLevel, setVoiceLevel] = useState<VoiceLevel>("Low");
  const [confidence, setConfidence] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const [showResults, setShowResults] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [micLevel, setMicLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [sttSupported, setSttSupported] = useState(true);
  const [history, setHistory] = useState<VoiceHistoryItem[]>([]);
  const [voiceToneScore, setVoiceToneScore] = useState<number | null>(null);
  const [wordsScore, setWordsScore] = useState<number | null>(null);
  const [voiceToneConf, setVoiceToneConf] = useState<number | null>(null);
  const [wordsConf, setWordsConf] = useState<number | null>(null);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [emotionHint, setEmotionHint] = useState<string>("");
  const [explanation, setExplanation] = useState<string>("");
  const [interventions, setInterventions] = useState<VoiceIntervention[]>([]);
  const [insufficient, setInsufficient] = useState(false);
  const [quietWarning, setQuietWarning] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState<string | null>(null);
  const [micDevices, setMicDevices] = useState<MediaDeviceInfo[]>([]);
  const [micDeviceId, setMicDeviceId] = useState<string>("");
  const [showMicPicker, setShowMicPicker] = useState(false);
  const [loadingExercises, setLoadingExercises] = useState(false);
  const [manualText, setManualText] = useState("");
  const [showManual, setShowManual] = useState(false);
  const lastAudioBase64Ref = useRef<string>("");
  const lastDurationRef = useRef(0);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recognitionRef = useRef<any>(null);
  const timerRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const finalTranscriptRef = useRef("");
  const startTsRef = useRef(0);
  const stoppingRef = useRef(false);
  const sessionIdRef = useRef<string>("");
  if (!sessionIdRef.current && typeof crypto !== "undefined" && "randomUUID" in crypto) {
    try {
      sessionIdRef.current = crypto.randomUUID();
    } catch {
      sessionIdRef.current = `voice-${Date.now()}`;
    }
  }
  if (!sessionIdRef.current) sessionIdRef.current = `voice-${Date.now()}`;

  const cleanupAudioGraph = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    analyserRef.current = null;
  }, []);

  const stopTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => {
      try {
        t.stop();
      } catch {
        /* ignore */
      }
    });
    streamRef.current = null;
  }, []);

  const applyResult = useCallback((data: any, duration: number, spokenText: string) => {
    const score = Math.round(Number(data.stress_score) * 100);
    const level = String(data.stress_level || "Low") as VoiceLevel;
    const conf = Number(data.confidence ?? 0);

    setVoiceScore(score);
    setVoiceLevel(level);
    setConfidence(conf);
    setAudioDuration(duration);
    setVoiceToneScore(
      data.voice_score !== undefined && data.voice_score !== null
        ? Math.round(Number(data.voice_score) * 100)
        : null
    );
    setWordsScore(
      data.text_score !== undefined && data.text_score !== null
        ? Math.round(Number(data.text_score) * 100)
        : null
    );
    setVoiceToneConf(
      data.voice_confidence !== undefined && data.voice_confidence !== null
        ? Number(data.voice_confidence)
        : null
    );
    setWordsConf(
      data.text_confidence !== undefined && data.text_confidence !== null
        ? Number(data.text_confidence)
        : null
    );
    setKeywords(Array.isArray(data.text_keywords) ? data.text_keywords.map(String).slice(0, 8) : []);
    setEmotionHint(typeof data.emotion_hint === "string" ? data.emotion_hint : "");
    setExplanation(typeof data.explanation === "string" ? data.explanation : "");
    setInterventions(Array.isArray(data.interventions) ? data.interventions.slice(0, 3) : []);
    setInsufficient(!!data.insufficient_evidence);
    setQuietWarning(typeof data.quiet_warning === "string" ? data.quiet_warning : null);
    setAudioLevel(typeof data.audio_level === "string" ? data.audio_level : null);
    setShowResults(true);
    setHistory((prev) =>
      [
        ...prev,
        {
          id: `${Date.now()}-${prev.length}`,
          score,
          level,
          confidence: conf,
          duration,
          transcript: spokenText,
          ts: Date.now(),
        },
      ].slice(-8)
    );
    notifyDataUpdated();
  }, []);

  const reanalyzeWithText = useCallback(async () => {
    const typed = manualText.trim();
    if (!typed || !lastAudioBase64Ref.current || isAnalyzing) return;
    setIsAnalyzing(true);
    setError(null);
    try {
      const data = await api.analyzeVoice(
        lastAudioBase64Ref.current,
        16000,
        lastDurationRef.current || undefined,
        typed,
        sessionIdRef.current
      );
      setTranscript(typed);
      finalTranscriptRef.current = typed;
      applyResult(data, lastDurationRef.current, typed);
      setShowManual(false);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || "Re-analysis failed. Please try again.";
      setError(typeof msg === "string" ? msg : "Re-analysis failed.");
    } finally {
      setIsAnalyzing(false);
    }
  }, [manualText, isAnalyzing, applyResult]);

  const processRecording = useCallback(
    async (recordedChunks: Blob[], spokenText: string, elapsed: number) => {
      setIsAnalyzing(true);
      setError(null);
      try {
        const blobType = recordedChunks[0]?.type || "audio/webm";
        const blob = new Blob(recordedChunks, { type: blobType });
        if (blob.size < 800) {
          throw new Error("No audio was captured. Please speak closer to the mic and try again.");
        }
        // Prefer WAV-16k for backend; fall back to raw if conversion fails.
        let base64 = "";
        let duration = elapsed;
        try {
          const wav = await blobToWav16kBase64(blob, 16000);
          base64 = wav.base64;
          if (wav.duration > 0.2) duration = wav.duration;
        } catch {
          base64 = await blobToBase64(blob);
        }
        if (!base64) throw new Error("Could not encode your recording. Please try again.");
        lastAudioBase64Ref.current = base64;
        lastDurationRef.current = duration;
        setManualText(spokenText);

        const data = await api.analyzeVoice(base64, 16000, duration, spokenText, sessionIdRef.current);
        applyResult(data, duration, spokenText);
      } catch (e: any) {
        const msg =
          e?.response?.data?.detail ||
          e?.message ||
          "Voice analysis failed. Please check your mic and try again.";
        setError(typeof msg === "string" ? msg : "Voice analysis failed.");
        setShowResults(false);
      } finally {
        setIsAnalyzing(false);
        stoppingRef.current = false;
      }
    },
    [applyResult]
  );

  const stopRecording = useCallback(() => {
    if (!isListening || stoppingRef.current) return;
    stoppingRef.current = true;
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    try {
      recognitionRef.current?.stop?.();
    } catch {
      /* ignore */
    }
    recognitionRef.current = null;
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    const rec = recorderRef.current;
    const elapsed = (Date.now() - startTsRef.current) / 1000;
    const spoken = finalTranscriptRef.current.trim();
    if (rec && rec.state !== "inactive") {
      // onstop handler (registered at start) will call processRecording
      (rec as any)._elapsed = elapsed;
      (rec as any)._spoken = spoken;
      try {
        rec.stop();
      } catch {
        // If stop throws, process from chunks directly
        const chunks = [...chunksRef.current];
        setIsListening(false);
        cleanupAudioGraph();
        stopTracks();
        recorderRef.current = null;
        processRecording(chunks, spoken, elapsed);
      }
    } else {
      const chunks = [...chunksRef.current];
      setIsListening(false);
      cleanupAudioGraph();
      stopTracks();
      recorderRef.current = null;
      if (chunks.length > 0) processRecording(chunks, spoken, elapsed);
      else {
        stoppingRef.current = false;
        setError("Nothing was recorded. Please press Talk and speak for a few seconds.");
      }
    }
  }, [isListening, cleanupAudioGraph, stopTracks, processRecording]);

  const fetchMoreExercises = useCallback(async () => {
    const q = (finalTranscriptRef.current || transcript).trim();
    if (!q || loadingExercises) return;
    setLoadingExercises(true);
    try {
      const res = await api.queryRAG(undefined, q, 3, emotionHint || undefined);
      if (Array.isArray(res?.interventions) && res.interventions.length > 0) {
        setInterventions(res.interventions.slice(0, 3));
      }
    } catch {
      /* keep existing suggestions */
    } finally {
      setLoadingExercises(false);
    }
  }, [transcript, emotionHint, loadingExercises]);

  const loadMicDevices = useCallback(async () => {
    try {
      if (!navigator.mediaDevices?.enumerateDevices) return;
      const devices = await navigator.mediaDevices.enumerateDevices();
      setMicDevices(devices.filter((d) => d.kind === "audioinput"));
    } catch {
      /* picker is optional */
    }
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    setShowResults(false);
    setTranscript("");
    setInterim("");
    setVoiceScore(0);
    setConfidence(0);
    setAudioDuration(0);
    setRecordingTime(0);
    setMicLevel(0);
    setVoiceToneScore(null);
    setWordsScore(null);
    setVoiceToneConf(null);
    setWordsConf(null);
    setKeywords([]);
    setEmotionHint("");
    setExplanation("");
    setInterventions([]);
    setInsufficient(false);
    setQuietWarning(null);
    setAudioLevel(null);
    finalTranscriptRef.current = "";
    chunksRef.current = [];
    stoppingRef.current = false;

    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("Microphone is not available in this browser. Please use Chrome or Edge over localhost/https.");
      return;
    }

    try {
      const constraints: MediaStreamConstraints = micDeviceId
        ? { audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, deviceId: { exact: micDeviceId } } }
        : { audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;
      setIsListening(true);
      startTsRef.current = Date.now();

      // Mic level meter
      try {
        const AC = window.AudioContext || (window as any).webkitAudioContext;
        if (AC) {
          const ctx = new AC();
          audioCtxRef.current = ctx;
          const src = ctx.createMediaStreamSource(stream);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 512;
          src.connect(analyser);
          analyserRef.current = analyser;
          const buf = new Uint8Array(analyser.frequencyBinCount);
          const tick = () => {
            if (!analyserRef.current) return;
            analyserRef.current.getByteTimeDomainData(buf as any);
            let sum = 0;
            for (let i = 0; i < buf.length; i++) {
              const v = (buf[i] - 128) / 128;
              sum += v * v;
            }
            setMicLevel(Math.min(1, Math.sqrt(sum / buf.length) * 3));
            rafRef.current = requestAnimationFrame(tick);
          };
          tick();
        }
      } catch {
        /* meter is optional */
      }

      // Speech-to-text (live words)
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) {
        setSttSupported(false);
      } else {
        setSttSupported(true);
        try {
          const recog = new SR();
          recognitionRef.current = recog;
          recog.continuous = true;
          recog.interimResults = true;
          recog.lang = "en-US";
          recog.onresult = (event: RecognitionEvent) => {
            let interimText = "";
            let finalText = finalTranscriptRef.current;
            for (let i = event.resultIndex; i < event.results.length; i++) {
              const res = event.results[i];
              const text = res[0]?.transcript ?? "";
              if (res.isFinal) finalText += text + " ";
              else interimText += text;
            }
            finalTranscriptRef.current = finalText;
            setTranscript(finalText.trim());
            setInterim(interimText.trim());
          };
          recog.onerror = (ev: any) => {
            const err = ev?.error;
            if (err === "not-allowed" || err === "service-not-allowed") {
              setSttSupported(false);
              setError("Speech transcription was blocked. Audio stress scoring will still work — please allow mic access.");
            } else if (err === "network") {
              // Brave etc: API exists but the transcription service is blocked.
              setSttSupported(false);
              setError("Live transcription is blocked in this browser (Brave Shields does this). Audio scoring still works — or type your words below.");
            }
            // Other errors (no-speech, aborted) are transient; keep recording.
          };
          recog.onend = () => {
            // Auto-restart while still recording
            if (recognitionRef.current && !stoppingRef.current) {
              try {
                recognitionRef.current.start();
              } catch {
                /* ignore restart race */
              }
            }
          };
          recog.start();
        } catch {
          setSttSupported(false);
        }
      }

      // Audio recorder
      const mimeType = pickSupportedMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (e: BlobEvent) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const chunks = [...chunksRef.current];
        const elapsed = (Date.now() - startTsRef.current) / 1000;
        const spoken = finalTranscriptRef.current.trim();
        setIsListening(false);
        cleanupAudioGraph();
        stopTracks();
        recorderRef.current = null;
        processRecording(chunks, spoken, elapsed);
      };
      recorder.onerror = () => {
        setError("Recording failed. Please try again.");
      };
      recorder.start(250);

      timerRef.current = window.setInterval(() => {
        setRecordingTime((Date.now() - startTsRef.current) / 1000);
      }, 200);
    } catch (e: any) {
      setIsListening(false);
      cleanupAudioGraph();
      stopTracks();
      setError(
        e?.name === "NotAllowedError"
          ? "Microphone permission was denied. Click the lock icon in the address bar to allow the mic, then try again."
          : "Could not access the microphone. Please check your device and try again."
      );
    }
  }, [cleanupAudioGraph, stopTracks, processRecording]);

  // Stop everything on unmount
  useEffect(() => {
    return () => {
      try {
        recognitionRef.current?.abort?.();
      } catch {
        /* ignore */
      }
      try {
        if (recorderRef.current && recorderRef.current.state !== "inactive") recorderRef.current.stop();
      } catch {
        /* ignore */
      }
      if (timerRef.current) window.clearInterval(timerRef.current);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      audioCtxRef.current?.close().catch(() => {});
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const avg = history.length ? Math.round(history.reduce((a, h) => a + h.score, 0) / history.length) : 0;
  const trend =
    history.length >= 2
      ? history[history.length - 1].score - history[history.length - 2].score
      : 0;
  const TrendIcon = trend > 3 ? TrendingUp : trend < -3 ? TrendingDown : Minus;

  return (
    <GlassCard className="p-4 max-w-md w-full">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Mic className="w-4 h-4 text-indigo-300" />
            <h3 className="text-sm font-bold text-white">Voice Stress Check</h3>
          </div>
          <span
            className={`text-[11px] px-2 py-0.5 rounded-full border ${
              isAnalyzing
                ? "text-amber-300 border-amber-500/40 bg-amber-500/10"
                : isListening
                ? "text-rose-300 border-rose-500/40 bg-rose-500/10"
                : "text-slate-400 border-slate-700 bg-slate-800/60"
            }`}
          >
            {isAnalyzing ? "Analyzing…" : isListening ? "● Recording" : "Idle"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {!isListening && !isAnalyzing && (
            <button
              onClick={startRecording}
              className="flex-1 px-3 py-2 rounded-xl font-medium bg-indigo-600/20 text-indigo-200 border border-indigo-500/30 hover:border-indigo-400/60 text-sm transition-all flex items-center justify-center gap-2"
            >
              <Mic className="w-4 h-4" />
              Talk — start voice check
            </button>
          )}
          {!isListening && !isAnalyzing && (
            <button
              onClick={() => { setShowMicPicker((v) => !v); loadMicDevices(); }}
              aria-label="Choose microphone"
              title="Choose microphone"
              className="px-3 py-2 rounded-xl text-xs text-slate-300 border border-slate-700 hover:border-indigo-400"
            >
              🎙️
            </button>
          )}
          {isListening && (
            <button
              onClick={stopRecording}
              className="flex-1 px-3 py-2 rounded-xl font-medium bg-red-600/20 text-red-200 border border-red-500/40 hover:border-red-400/70 text-sm transition-all flex items-center justify-center gap-2"
            >
              <Square className="w-4 h-4" />
              Stop & analyze ({Math.round(recordingTime)}s)
            </button>
          )}
          {isAnalyzing && (
            <div className="flex-1 px-3 py-2 rounded-xl bg-slate-800/60 border border-slate-700 text-sm text-slate-300 flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Analyzing your voice…
            </div>
          )}
        </div>

        {showMicPicker && !isListening && !isAnalyzing && (
          <div className="rounded-xl border border-slate-700/80 bg-slate-900/60 p-2.5">
            <label className="text-[11px] uppercase tracking-wider text-slate-400 block mb-1">
              Microphone {micDevices.length > 0 && `(${micDevices.length} found)`}
            </label>
            {micDevices.length === 0 ? (
              <p className="text-xs text-slate-500">Allow mic access once, then reopen this picker to see device names.</p>
            ) : (
              <select
                value={micDeviceId}
                onChange={(e) => setMicDeviceId(e.target.value)}
                className="w-full rounded-lg bg-slate-800 border border-slate-700 text-sm text-slate-200 p-2"
              >
                <option value="">Default microphone</option>
                {micDevices.map((d, i) => (
                  <option key={d.deviceId || i} value={d.deviceId}>
                    {d.label || `Microphone ${i + 1}`}
                  </option>
                ))}
              </select>
            )}
          </div>
        )}

        {/* Live mic level */}
        {isListening && (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-amber-400 to-rose-400 transition-all"
                style={{ width: `${Math.round(micLevel * 100)}%` }}
              />
            </div>
            <span className="text-[11px] text-slate-400 w-10 text-right">{Math.round(recordingTime)}s</span>
          </div>
        )}

        {/* Live transcript — the words being captured */}
        <div className="rounded-xl border border-slate-700/80 bg-slate-900/60 p-3 min-h-[76px]">
          <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-1">
            What we hear {isListening ? "· live" : transcript || history.length ? "" : "· press Talk and speak"}
          </div>
          {isListening || transcript || interim ? (
            <p className="text-sm text-slate-200 leading-relaxed">
              {transcript}
              {interim && <span className="text-indigo-300/80"> {interim}</span>}
              {!transcript && !interim && (
                <span className="text-slate-500">Listening… speak now — your words will appear here.</span>
              )}
              {isListening && <span className="inline-block w-2 h-4 bg-indigo-400 ml-1 animate-pulse align-middle" />}
            </p>
          ) : (
            <p className="text-sm text-slate-500">Press “Talk”, allow the mic, and speak for 5–20 seconds.</p>
          )}
          {!sttSupported && (
            <p className="text-[11px] text-amber-300/90 mt-1">
              Live transcription isn’t supported in this browser — audio stress scoring still works.
            </p>
          )}
        </div>

        {/* Typed-words fallback: some browsers (e.g. Brave) block live
            transcription, so you can type what you said and re-check —
            the words score + treatments update without re-recording. */}
        {!isListening && !isAnalyzing && lastAudioBase64Ref.current && (
          <div className="rounded-xl border border-slate-700/80 bg-slate-900/60 p-2.5">
            {!showManual ? (
              <button
                onClick={() => {
                  setShowManual(true);
                  setManualText(transcript);
                }}
                className="text-[11px] text-indigo-300 hover:text-indigo-200"
              >
                Words look wrong or empty? Type what you said →
              </button>
            ) : (
              <div className="space-y-2">
                <textarea
                  value={manualText}
                  onChange={(e) => setManualText(e.target.value)}
                  rows={2}
                  placeholder="Type what you said, e.g. I feel sad and tired…"
                  className="w-full rounded-lg bg-slate-800 border border-slate-700 text-sm text-slate-200 p-2 placeholder:text-slate-500"
                />
                <div className="flex gap-2">
                  <button
                    onClick={reanalyzeWithText}
                    disabled={!manualText.trim()}
                    className="px-3 py-1.5 rounded-xl text-xs font-bold bg-indigo-500/20 text-indigo-200 border border-indigo-500/40 hover:bg-indigo-500/30 disabled:opacity-50"
                  >
                    Re-check with these words
                  </button>
                  <button
                    onClick={() => setShowManual(false)}
                    className="px-3 py-1.5 rounded-xl text-xs text-slate-400 border border-slate-700 hover:text-white"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-200 flex gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Honest signal notices: never a confident verdict on weak evidence */}
        {showResults && !isAnalyzing && insufficient && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-200">
            Not enough clear signal to estimate stress — this score is a neutral placeholder, not a reading.
            Please speak for a few seconds near the mic and try again.
          </div>
        )}
        {showResults && !isAnalyzing && !insufficient && quietWarning && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-200">
            {quietWarning}
          </div>
        )}

        {/* Latest result */}
        {showResults && !isAnalyzing && (
          <div className={`p-3 rounded-xl border text-center ${levelColor(voiceLevel)}`}>
            <div className="text-lg font-bold text-white mb-0.5">
              {LEVEL_LABELS[voiceLevel as keyof typeof LEVEL_LABELS] ?? voiceLevel} · {Math.round(voiceScore)}%
            </div>
            <div className="text-xs opacity-80 mb-1">
              {LEVEL_EXPLANATIONS[voiceLevel as keyof typeof LEVEL_EXPLANATIONS] ?? "Voice analysis complete."}
            </div>
            <div className="text-[11px] opacity-70">
              Confidence {Math.round(confidence * 100)}% · {audioDuration.toFixed(1)}s of speech
              {audioLevel && audioLevel !== "normal" ? ` · mic: ${audioLevel.replace("_", " ")}` : ""}
            </div>
            <button
              onClick={() => setShowResults(false)}
              className="mt-2 px-3 py-1.5 rounded-xl text-xs bg-slate-800/80 text-slate-200 border border-slate-600 hover:border-indigo-400 hover:text-white transition-all"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Why this score: voice tone + spoken words */}
        {showResults && !isAnalyzing && (voiceToneScore !== null || wordsScore !== null || explanation) && (
          <div className="rounded-xl border border-slate-700/80 bg-slate-900/60 p-3 text-left">
            <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-2">Why this score</div>
            {voiceToneScore !== null && (
              <div className="mb-1.5">
                <div className="flex justify-between text-[11px] text-slate-300 mb-0.5">
                  <span>Voice tone (pitch, energy, pace){voiceToneConf !== null ? ` · conf ${Math.round(voiceToneConf * 100)}%` : ""}</span>
                  <span className="font-bold">{voiceToneScore}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full rounded-full bg-cyan-400/80" style={{ width: `${Math.min(100, voiceToneScore)}%` }} />
                </div>
              </div>
            )}
            {wordsScore !== null && (
              <div className="mb-1.5">
                <div className="flex justify-between text-[11px] text-slate-300 mb-0.5">
                  <span>Spoken words (what you said){wordsConf !== null ? ` · conf ${Math.round(wordsConf * 100)}%` : ""}</span>
                  <span className="font-bold">{wordsScore}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full rounded-full bg-violet-400/80" style={{ width: `${Math.min(100, wordsScore)}%` }} />
                </div>
              </div>
            )}
            {explanation && <p className="text-xs text-slate-300 leading-relaxed mt-1.5">{explanation}</p>}
            {keywords.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {keywords.map((k) => (
                  <span key={k} className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-200 border border-indigo-500/30">
                    {k}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Suggested treatment based on voice + words */}
        {showResults && !isAnalyzing && (
          <div className="rounded-xl border border-cyan-500/25 bg-cyan-950/20 p-3 text-left">
            <div className="flex items-center gap-1.5 mb-1">
              <Sparkles className="w-3.5 h-3.5 text-cyan-300" />
              <span className="text-[11px] uppercase tracking-wider text-cyan-200 font-semibold">
                Suggested treatment for this voice check
              </span>
            </div>
            {interventions.length === 0 ? (
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-slate-300">No tailored exercise yet — fetch ones matched to your words.</p>
                <button
                  onClick={fetchMoreExercises}
                  disabled={loadingExercises}
                  className="shrink-0 px-3 py-1.5 rounded-xl text-xs font-bold bg-cyan-500/20 text-cyan-200 border border-cyan-500/40 hover:bg-cyan-500/30 disabled:opacity-50"
                >
                  {loadingExercises ? "Finding…" : "Find exercises"}
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {interventions.map((iv, i) => (
                  <div key={iv.id || i} className="rounded-lg border border-slate-700/60 bg-slate-900/70 p-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-200 border border-cyan-500/30 uppercase tracking-wider">
                        {friendlyCategory(iv.category) || iv.category || "Coping"}
                      </span>
                      {iv.duration_min > 0 && (
                        <span className="flex items-center gap-1 text-[11px] text-slate-400">
                          <Clock className="w-3 h-3" /> {iv.duration_min} min
                        </span>
                      )}
                    </div>
                    <div className="text-sm font-bold text-white mt-1">{iv.title}</div>
                    {iv.summary && <p className="text-xs text-slate-300 mt-0.5 leading-relaxed">{iv.summary}</p>}
                    {iv.protocol && iv.protocol.length > 0 && (
                      <ol className="text-xs text-slate-200 mt-1.5 space-y-0.5 list-decimal list-inside">
                        {iv.protocol.slice(0, 3).map((step, si) => (
                          <li key={si}>{step}</li>
                        ))}
                      </ol>
                    )}
                  </div>
                ))}
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={fetchMoreExercises}
                    disabled={loadingExercises}
                    className="px-3 py-1.5 rounded-xl text-xs font-bold bg-cyan-500/20 text-cyan-200 border border-cyan-500/40 hover:bg-cyan-500/30 disabled:opacity-50"
                  >
                    {loadingExercises ? "Finding…" : "More like this"}
                  </button>
                  <a
                    href="/rag-coping"
                    className="px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-300 border border-slate-600 hover:border-cyan-400 hover:text-white transition-all"
                  >
                    Open Coping Help
                  </a>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Voice trend across recordings — always visible */}
        <div className="pt-1 border-t border-slate-700/50">
          <div className="flex items-center justify-between mb-2 mt-2">
            <h4 className="text-xs font-semibold text-slate-300">
              Voice trend {history.length > 0 && <span className="text-slate-500">({history.length} check{history.length > 1 ? "s" : ""} · avg {avg}%)</span>}
            </h4>
            {history.length >= 2 && (
              <span
                className={`flex items-center gap-1 text-[11px] ${
                  trend > 3 ? "text-rose-300" : trend < -3 ? "text-emerald-300" : "text-slate-400"
                }`}
              >
                <TrendIcon className="w-3.5 h-3.5" />
                {trend > 3 ? `+${Math.round(trend)} rising` : trend < -3 ? `${Math.round(trend)} falling` : "steady"}
              </span>
            )}
          </div>
          {history.length === 0 ? (
            <p className="text-slate-500 text-xs">No voice checks yet. Each Talk → Stop adds a point here so you can see stress go up or down.</p>
          ) : (
            <>
              <div className="flex items-end gap-1 h-14 mb-2">
                {history.map((h) => (
                  <div key={h.id} className="flex-1 flex flex-col items-center gap-1" title={`${h.score}% · ${h.level}`}>
                    <div
                      className={`w-full rounded-t ${
                        h.level === "Low"
                          ? "bg-emerald-400/70"
                          : h.level === "Moderate"
                          ? "bg-amber-400/70"
                          : "bg-rose-400/70"
                      }`}
                      style={{ height: `${Math.max(6, h.score)}%` }}
                    />
                    <span className="text-[10px] text-slate-500">{h.score}</span>
                  </div>
                ))}
              </div>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {[...history].reverse().map((h) => (
                  <div key={h.id} className="p-2 rounded-lg bg-slate-800/70 border border-slate-700/60 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className={`font-bold ${h.level === "Low" ? "text-emerald-300" : h.level === "Moderate" ? "text-amber-300" : "text-rose-300"}`}>
                        {h.level} · {h.score}%
                      </span>
                      <span className="text-slate-500">
                        {new Date(h.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · {h.duration.toFixed(0)}s
                      </span>
                    </div>
                    {h.transcript && <div className="text-slate-300 mt-1 line-clamp-2">“{h.transcript}”</div>}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {!isListening && !isAnalyzing && history.length === 0 && (
          <p className="text-[11px] text-slate-500">Tip: allow mic access, speak naturally for 5–20s, then Stop. Your words + stress score appear above.</p>
        )}
      </div>
    </GlassCard>
  );
};
