"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { api } from "@/lib/api";
import { GlassCard } from "@/components/GlassCard";
import { transcribeLocally, isLocalTranscribeError, logTranscribeError } from "@/lib/localTranscription";
import {
  Mic, Square, Send, Loader2, AlertCircle, Volume2, VolumeX,
  Wind, Anchor, ListChecks, Armchair, Sun, Footprints, MessagesSquare,
  PhoneOff, RotateCcw, HeartHandshake,
} from "lucide-react";

declare global {
  interface Window {
    SpeechRecognition?: any;
    webkitSpeechRecognition?: any;
  }
}

export interface CompanionStressContext {
  stress_score?: number; // 0-1 or 0-100
  stress_level?: string;
  confidence?: number;
  trend?: string;
}

interface ChatMsg {
  from: "you" | "assistant";
  text: string;
  activityTitle?: string;
  activitySteps?: string[];
  checkIn?: string;
  safety?: boolean;
}

const ACTIVITY_SHORTCUTS = [
  { id: "breathing", label: "Breathe", icon: Wind, prompt: "Can we do a breathing exercise together?" },
  { id: "grounding", label: "Ground", icon: Anchor, prompt: "Can you guide me through a grounding exercise?" },
  { id: "thought_organizing", label: "Organize", icon: ListChecks, prompt: "I have too many things on my mind. Can you help me sort them?" },
  { id: "relaxation", label: "Relax", icon: Armchair, prompt: "I feel tense. Can you help me relax a little?" },
  { id: "positive_reflection", label: "Small win", icon: Sun, prompt: "Can you help me notice something good about today?" },
  { id: "healthy_routine", label: "Routine", icon: Footprints, prompt: "What small healthy step could I take right now?" },
  { id: "supportive_conversation", label: "Just talk", icon: MessagesSquare, prompt: "I don't want advice; I just want to talk." },
];

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

function pickCalmVoice(): SpeechSynthesisVoice | null {  try {
    if (!("speechSynthesis" in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    if (!voices.length) return null;
    const en = voices.filter((v) => v.lang?.toLowerCase().startsWith("en"));
    const pool = en.length ? en : voices;
    return (
      pool.find((v) => /samantha|zira|google us english|female/i.test(v.name)) ??
      pool[0] ??
      null
    );
  } catch {
    return null;
  }
}

export const ConversationBot: React.FC<{
  initialStressContext?: CompanionStressContext | null;
  stressSourceLabel?: string;
  /** Optional first user message (e.g. arriving from an assessment result). Sent once on start. */
  openingMessage?: string | null;
}> = ({ initialStressContext = null, stressSourceLabel, openingMessage = null }) => {
  const [sessionId, setSessionId] = useState("");
  const [chat, setChat] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [listening, setListening] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [voiceOn, setVoiceOn] = useState(true);
  const [shareStress, setShareStress] = useState(!!initialStressContext);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [liveInterim, setLiveInterim] = useState("");
  const [sttSupported, setSttSupported] = useState(true);
  const [ttsSupported, setTtsSupported] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(true);
  const [ended, setEnded] = useState(false);
  const [micDevices, setMicDevices] = useState<MediaDeviceInfo[]>([]);
  const [micDeviceId, setMicDeviceId] = useState("");
  const [showMicPicker, setShowMicPicker] = useState(false);
  const [micLevel, setMicLevel] = useState(0);
  const [handsFree, setHandsFree] = useState(false);
  // Layered STT state machine: idle → requesting → recording → transcribing → responding.
  const [requestingMic, setRequestingMic] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [transcribeDetail, setTranscribeDetail] = useState("");
  const [fallbackReady, setFallbackReady] = useState<boolean | null>(null);
  const [localModelReady, setLocalModelReady] = useState(false);
  const [voiceRetryable, setVoiceRetryable] = useState(false);
  // Dev-only diagnostics (capabilities + last attempt timeline). Never holds
  // transcripts or audio — counts and stage names only.
  const [diag, setDiag] = useState<Record<string, unknown> | null>(null);
  const diagRef = useRef<Record<string, unknown>>({});
  const markDiag = useCallback((patch: Record<string, unknown>) => {
    diagRef.current = { ...diagRef.current, ...patch };
    setDiag({ ...diagRef.current });
  }, []);

  const recogRef = useRef<any>(null);
  const finalRef = useRef("");
  const stoppingRef = useRef(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const sessionRef = useRef("");
  const shareRef = useRef(shareStress);
  const stressRef = useRef(initialStressContext);
  // Mic-liveness tracking: distinguishes "heard sound, transcription failed"
  // (e.g. Brave blocks the speech service) from genuine silence.
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const maxLevelRef = useRef(0);
  const speechDetectedRef = useRef(false);
  const silenceMsRef = useRef(0);
  const listenStartRef = useRef(0);
  const handsFreeRef = useRef(false);
  const autoArmedRef = useRef(false);
  const stopRef = useRef<(() => void) | null>(null);
  // Server-transcription fallback capture (runs alongside browser STT).
  const chunksRef = useRef<Blob[]>([]);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recorderMimeRef = useRef("");
  const recordingIdRef = useRef(0);
  const finalizedForRef = useRef(0); // idempotent finalize: one recording → one outcome
  const srDeadRef = useRef(false); // browser STT terminally failed; don't restart it
  const cancelledRef = useRef(false);
  sessionRef.current = sessionId;
  shareRef.current = shareStress;
  stressRef.current = initialStressContext;
  handsFreeRef.current = handsFree;

  const stopAudioGraph = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    analyserRef.current = null;
    streamRef.current?.getTracks().forEach((t) => { try { t.stop(); } catch {} });
    streamRef.current = null;
    setMicLevel(0);
  }, []);

  const speakQueueRef = useRef<string[]>([]);
  const speakIdxRef = useRef(0);

  const stopSpeaking = useCallback(() => {
    speakQueueRef.current = [];
    speakIdxRef.current = 0;
    try {
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    } catch { /* ignore */ }
    setSpeaking(false);
  }, []);

  const speakNext = useCallback(() => {
    if (speakIdxRef.current >= speakQueueRef.current.length) {
      setSpeaking(false);
      return;
    }
    const chunk = speakQueueRef.current[speakIdxRef.current++];
    try {
      const utter = new SpeechSynthesisUtterance(chunk);
      utter.rate = 0.95;
      utter.pitch = 1;
      utter.lang = "en-US";
      const voice = pickCalmVoice();
      if (voice) utter.voice = voice;
      utter.onstart = () => setSpeaking(true);
      utter.onend = () => {
        // Chain to the next sentence so long replies start fast and
        // interruption always lands cleanly between sentences.
        if (speakIdxRef.current < speakQueueRef.current.length) speakNext();
        else setSpeaking(false);
      };
      utter.onerror = () => setSpeaking(false);
      window.speechSynthesis.speak(utter);
    } catch {
      setSpeaking(false);
    }
  }, []);

  const speak = useCallback((text: string) => {
    if (!voiceOn) return;
    if (!("speechSynthesis" in window)) {
      setTtsSupported(false);
      return;
    }
    // Sentence-chunked playback: first sentence starts immediately
    // (lower perceived latency), transcript stays synchronized in chat.
    const chunks = text
      .match(/[^.!?]+[.!?]+["']?\s*|[^.!?]+$/g)
      ?.map((s) => s.trim())
      .filter(Boolean) ?? [text];
    speakQueueRef.current = chunks;
    speakIdxRef.current = 0;
    try {
      window.speechSynthesis.cancel();
    } catch { /* ignore */ }
    speakNext();
  }, [voiceOn, speakNext]);

  useEffect(() => {
    try {
      if (!("speechSynthesis" in window)) setTtsSupported(false);
      else if (window.speechSynthesis.getVoices().length === 0) {
        window.speechSynthesis.onvoiceschanged = () => {};
      }
    } catch {
      setTtsSupported(false);
    }
    if (!(window.SpeechRecognition || window.webkitSpeechRecognition)) {
      setSttSupported(false);
    }
    // Capability probe (feeds the dev diagnostics panel; no audio touched).
    markDiag({
      caps: {
        getUserMedia: !!(navigator.mediaDevices?.getUserMedia),
        mediaRecorder: typeof MediaRecorder !== "undefined",
        webSpeech: !!(window.SpeechRecognition || window.webkitSpeechRecognition),
        speechSynthesis: "speechSynthesis" in window,
        secureContext: typeof window !== "undefined" ? !!window.isSecureContext : null,
      },
    });
    // Probe server transcription once: decides messaging only, never blocks.
    api.transcribeStatus()
      .then((s) => {
        setFallbackReady(!!s?.configured);
        markDiag({ serverStt: !!s?.configured, serverProvider: s?.provider ?? "none" });
      })
      .catch(() => setFallbackReady(null));
  }, [markDiag]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, liveTranscript, processing, transcribing]);

  useEffect(() => () => {
    try { recogRef.current?.abort?.(); } catch {}
    try { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); } catch {}
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    try { audioCtxRef.current?.close().catch(() => {}); } catch {}
    streamRef.current?.getTracks().forEach((t) => { try { t.stop(); } catch {} });
  }, []);

  const sendMessageRef = useRef<(text: string) => void>(() => {});
  const openingSentRef = useRef(false);

  const startSession = useCallback(async () => {
    setStarting(true);
    setError(null);
    setEnded(false);
    openingSentRef.current = false;
    try {
      const res = await api.conversationStart();
      setSessionId(res.session_id);
      setChat([{ from: "assistant", text: res.reply }]);
      speak(res.reply);
    } catch (e: any) {
      setError(
        e?.response?.data?.detail ||
        "Could not reach the companion. Is the backend running? You can retry."
      );
    } finally {
      setStarting(false);
    }
  }, [speak]);

  useEffect(() => {
    startSession();
  }, [startSession]);

  // Handoff from an assessment result: send the user's opening message once
  // the session exists. The companion then responds with full context.
  useEffect(() => {
    if (
      openingMessage && !openingSentRef.current &&
      sessionId && !starting && !ended
    ) {
      openingSentRef.current = true;
      const t = setTimeout(() => sendMessageRef.current(openingMessage), 600);
      return () => clearTimeout(t);
    }
  }, [openingMessage, sessionId, starting, ended]);

  const sendMessage = useCallback(async (rawText: string) => {
    const text = rawText.trim();
    if (!text || processing || transcribing || !sessionRef.current || ended) return;
    stopSpeaking(); // never talk over the user
    setError(null);
    setChat((prev) => [...prev, { from: "you", text }]);
    setInput("");
    setLiveTranscript("");
    setLiveInterim("");
    setProcessing(true);
    try {
      const stress = shareRef.current ? stressRef.current : null;
      const res = await api.conversationMessage({
        session_id: sessionRef.current,
        message: text,
        ...(stress ? {
          stress_context: {
            ...(stress.stress_score !== undefined ? { stress_score: stress.stress_score } : {}),
            ...(stress.stress_level ? { stress_level: stress.stress_level } : {}),
            ...(stress.confidence !== undefined ? { confidence: stress.confidence } : {}),
            ...(stress.trend ? { trend: stress.trend } : {}),
          },
        } : {}),
      });
      setChat((prev) => [...prev, {
        from: "assistant",
        text: res.reply,
        activityTitle: res.activity_title || undefined,
        activitySteps: Array.isArray(res.activity_steps) ? res.activity_steps.slice(0, 6) : undefined,
        checkIn: res.activity_check_in || undefined,
        safety: !!res.is_safety,
      }]);
      speak(res.reply);
      // Hands-free companion flow: after the bot finishes, the mic reopens
      // by itself so the conversation keeps flowing.
      if (handsFreeRef.current) autoArmedRef.current = true;
    } catch (e: any) {
      const status = e?.response?.status;
      setError(
        status === 404
          ? "This conversation expired. Please start a new one."
          : (e?.response?.data?.detail || "The reply didn't come through. Please check your connection and try again.")
      );
    } finally {
      setProcessing(false);
    }
  }, [processing, transcribing, ended, stopSpeaking, speak]);

  sendMessageRef.current = sendMessage;

  const transcribeErrorMessage = useCallback((e: any): string => {
    const status = e?.status ?? e?.response?.status;
    if (status === 503) {
      return "Voice transcription is temporarily unavailable. You can still type your message.";
    }
    if (status === 422) {
      return "I couldn't recognize those words. Please try again or type your message.";
    }
    if (status === 400) {
      return "That recording couldn't be read. Please try again or type your message.";
    }
    return e?.message || "Transcription didn't go through. Please try again or type your message.";
  }, []);

  /** Finalize one recording: browser words → on-device Whisper → server STT. */
  const finalizeRecording = useCallback(async (rid: number) => {
    if (rid !== recordingIdRef.current) return; // stale callback from an older take
    if (finalizedForRef.current === rid) return; // already finalized: never duplicate
    finalizedForRef.current = rid;
    const stopTs = Date.now();
    const srText = finalRef.current.trim();
    const chunks = [...chunksRef.current];
    const mime = recorderMimeRef.current;
    const heardSound = maxLevelRef.current > 0.06 || speechDetectedRef.current;
    stopAudioGraph();
    setListening(false);
    recogRef.current = null;
    stoppingRef.current = false;
    recorderRef.current = null;
    if (cancelledRef.current) {
      cancelledRef.current = false;
      markDiag({ outcome: "cancelled" });
      return; // user discarded this take
    }
    if (srText) {
      markDiag({ outcome: "browser-stt", chars: srText.length });
      sendMessage(srText); // instant path: browser transcription worked
      return;
    }
    const blob = new Blob(chunks, { type: mime || "audio/webm" });
    markDiag({
      mime: blob.type || "unknown",
      kb: Math.round(blob.size / 1024),
      heardSound,
      recordMs: stopTs - listenStartRef.current,
    });
    if (!blob.size || blob.size < 800) {
      const msg = heardSound
        ? "I couldn't recognize those words. Please try again or type your message."
        : "I didn't hear anything. Please check your mic, speak, and try again — or type your message.";
      markDiag({ outcome: heardSound ? "empty-unrecognized" : "empty-silent" });
      setError(msg);
      return;
    }
    if (typeof MediaRecorder === "undefined") {
      markDiag({ outcome: "unsupported" });
      setError("Voice recording isn't supported in this browser. Please type your message.");
      return;
    }
    // Layer 2: on-device transcription — free, private, no key needed.
    // This is what makes voice work in Brave.
    const t0 = Date.now();
    setTranscribing(true);
    setTranscribeDetail("Preparing voice recognition…");
    try {
      const text = await transcribeLocally(blob, (_pct, label) => {
        if (rid === recordingIdRef.current) setTranscribeDetail(label);
      });
      if (rid !== recordingIdRef.current || cancelledRef.current) return;
      markDiag({ transcribeMs: Date.now() - t0, localModel: "ready" });
      setLocalModelReady(true);
      if (text) {
        markDiag({ outcome: "local-stt", chars: text.length });
        sendMessage(text);
        return;
      }
      markDiag({ outcome: "local-empty" });
      setError("I couldn't recognize those words. Please try again or type your message.");
      return;
    } catch (localErr: any) {
      if (rid !== recordingIdRef.current) return;
      if (String(localErr?.message || "").includes("empty audio")) {
        markDiag({ outcome: "local-empty" });
        setError("I couldn't recognize those words. Please try again or type your message.");
        return;
      }
      // Stage-accurate message — never blame the download for everything.
      const stage = isLocalTranscribeError(localErr) ? localErr.stage : "unknown";
      const logged = logTranscribeError(localErr);
      markDiag({ outcome: `local-failed:${stage}`, lastError: logged });
      setVoiceRetryable(stage === "lib-load" || stage === "model-load");
      // Layer 3: server provider, if one is configured.
      if (fallbackReady) {
        try {
          setTranscribeDetail("Voice transcription is unavailable. Trying an alternative…");
          const res = await api.transcribeVoice(blob);
          if (rid !== recordingIdRef.current || cancelledRef.current) return;
          const text = (res.transcript || "").trim();
          markDiag({ transcribeMs: Date.now() - t0, serverProvider: res.provider });
          if (text) {
            markDiag({ outcome: "server-stt", chars: text.length });
            sendMessage(text);
            return;
          }
          markDiag({ outcome: "server-empty" });
          setError(
            res.warning ||
            "I couldn't recognize those words. Please try again or type your message."
          );
          return;
        } catch (e: any) {
          if (rid !== recordingIdRef.current) return;
          markDiag({ outcome: `server-failed:${e?.status ?? "network"}` });
          setError(transcribeErrorMessage(e));
          setVoiceRetryable(e?.status === 502 || e?.status === 503);
          return;
        } finally {
          if (rid === recordingIdRef.current) setTranscribing(false);
        }
      }
      // Neither on-device nor server worked — say exactly which stage failed.
      setError(
        isLocalTranscribeError(localErr)
          ? localErr.message
          : "Voice transcription couldn't start. You can still type your message."
      );
    } finally {
      if (rid === recordingIdRef.current) {
        setTranscribing(false);
        setTranscribeDetail("");
      }
    }
  }, [sendMessage, stopAudioGraph, transcribeErrorMessage, fallbackReady, markDiag]);

  const stopListening = useCallback(() => {
    if (!listening || stoppingRef.current) return;
    stoppingRef.current = true;
    autoArmedRef.current = false; // user took manual control
    try { recogRef.current?.stop?.(); } catch {}
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    const rid = recordingIdRef.current;
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") {
      try { rec.stop(); } catch { finalizeRecording(rid); }
      // Safety net: if onstop never fires, finalize from buffered chunks.
      setTimeout(() => {
        if (stoppingRef.current && rid === recordingIdRef.current) finalizeRecording(rid);
      }, 2500);
    } else {
      finalizeRecording(rid);
    }
  }, [listening, finalizeRecording]);

  const cancelListening = useCallback(() => {
    if (!listening) return;
    recordingIdRef.current += 1; // invalidate any in-flight callbacks
    cancelledRef.current = false;
    stoppingRef.current = false;
    autoArmedRef.current = false;
    try { recogRef.current?.abort?.(); } catch {}
    try {
      const rec = recorderRef.current;
      if (rec && rec.state !== "inactive") rec.stop();
    } catch { /* discarded */ }
    recorderRef.current = null;
    recogRef.current = null;
    chunksRef.current = [];
    finalRef.current = "";
    setLiveTranscript("");
    setLiveInterim("");
    stopAudioGraph();
    setListening(false);
    setTranscribing(false);
    setTranscribeDetail("");
  }, [listening, stopAudioGraph]);

  const loadMicDevices = useCallback(async () => {
    try {
      if (!navigator.mediaDevices?.enumerateDevices) return;
      const devices = await navigator.mediaDevices.enumerateDevices();
      setMicDevices(devices.filter((d) => d.kind === "audioinput"));
    } catch {
      /* picker is optional */
    }
  }, []);

  const startListening = useCallback(async () => {
    setError(null);
    setVoiceRetryable(false);
    stopSpeaking(); // allow interrupting the bot
    autoArmedRef.current = false; // consumed
    // State machine guard: never open duplicate sessions.
    if (listening || processing || transcribing || requestingMic || !sessionId || ended) return;
    setRequestingMic(true);
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const canRecord = typeof MediaRecorder !== "undefined";
    if (!SR && !canRecord) {
      setSttSupported(false);
      setRequestingMic(false);
      setError("Voice input isn't supported in this browser. Please type your message instead.");
      return;
    }
    if (!SR) setSttSupported(false); // recorder-only path still works
    // Keep the mic stream OPEN while listening so a live level meter can
    // prove the mic hears you — even if transcription later fails.
    let stream: MediaStream | null = null;
    if (typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia) {
      try {
        const constraints: MediaStreamConstraints = micDeviceId
          ? { audio: { deviceId: { exact: micDeviceId } } }
          : { audio: true };
        // 10s cap so a hung permission prompt can't stick us in "requesting".
        const request: Promise<MediaStream> = navigator.mediaDevices.getUserMedia(constraints);
        const timeout = new Promise<MediaStream>((_, reject) =>
          window.setTimeout(() => reject({ name: "TimeoutError" }), 10000)
        );
        stream = await Promise.race([request, timeout]);
        streamRef.current = stream;
      } catch (e: any) {
        setRequestingMic(false);
        const name = e?.name || "";
        if (name === "NotAllowedError") {
          setError("Microphone permission is required to use voice chat. Allow the mic or type instead.");
        } else if (name === "NotFoundError" || name === "OverconstrainedError" || name === "DevicesNotFoundError") {
          setError("No microphone was found. Check that one is connected and enabled, or type instead.");
        } else if (name === "TimeoutError") {
          setError("The microphone request timed out. Please try again or type instead.");
          setVoiceRetryable(true);
        } else {
          setError("Could not access the microphone. Please type your message instead.");
        }
        return;
      }
    } else {
      setRequestingMic(false);
      setError("Microphone is not available in this browser. Please type your message instead.");
      return;
    }
    const rid = ++recordingIdRef.current;
    cancelledRef.current = false;
    srDeadRef.current = false;
    finalRef.current = "";
    maxLevelRef.current = 0;
    speechDetectedRef.current = false;
    silenceMsRef.current = 0;
    listenStartRef.current = Date.now();
    setLiveTranscript("");
    setLiveInterim("");
    setMicLevel(0);
    stoppingRef.current = false;
    setRequestingMic(false);

    // Live level meter + hands-free silence detection (~150ms ticks).
    try {
      if (stream) {
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
            const raw = Math.sqrt(sum / buf.length);
            maxLevelRef.current = Math.max(maxLevelRef.current, raw);
            setMicLevel(Math.min(1, raw * 3));
            if (raw > 0.04) {
              speechDetectedRef.current = true;
              silenceMsRef.current = 0;
            } else {
              silenceMsRef.current += 150;
            }
            // Hands-free: user finished their turn (speech, then ~2.5s hush).
            if (
              handsFreeRef.current &&
              speechDetectedRef.current &&
              silenceMsRef.current > 2500 &&
              Date.now() - listenStartRef.current > 2500
            ) {
              stopRef.current?.();
              return;
            }
          };
          // Paced ~150ms loop (cheaper than rAF for a meter).
          const loop = () => {
            if (!analyserRef.current) return;
            tick();
            setTimeout(() => { if (analyserRef.current) loop(); }, 150);
          };
          loop();
        }
      }
    } catch {
      /* meter is optional; listening continues */
    }

    // Layer 1: browser speech recognition (instant when it works).
    if (SR) {
      try {
        const recog = new SR();
        recogRef.current = recog;
        recog.continuous = true;
        recog.interimResults = true;
        recog.lang = "en-US";
        recog.onresult = (ev: any) => {
          let interim = "";
          let fin = finalRef.current;
          for (let i = ev.resultIndex; i < ev.results.length; i++) {
            const t = ev.results[i][0]?.transcript ?? "";
            if (ev.results[i].isFinal) fin += t + " ";
            else interim += t;
          }
          finalRef.current = fin;
          setLiveTranscript(fin.trim());
          setLiveInterim(interim.trim());
        };
        recog.onerror = (ev: any) => {
          const err = ev?.error;
          if (err === "not-allowed" || err === "service-not-allowed") {
            // Terminal for this take: fall back to the parallel recording.
            srDeadRef.current = true;
          } else if (err === "network") {
            // The API object exists but its service is unreachable (e.g.
            // Brave). Stay silent here — the recorder path below covers it
            // and only a real failure will surface a message.
            srDeadRef.current = true;
          }
        };
        recog.onend = () => {
          if (srDeadRef.current) return; // never hammer a failing service
          if (recogRef.current && !stoppingRef.current) {
            try { recogRef.current.start(); } catch {}
            return;
          }
        };
        recog.start();
      } catch {
        srDeadRef.current = true;
      }
    }

    // Layer 2: parallel MediaRecorder capture → server transcription fallback.
    if (stream) {
      try {
        const mime = pickSupportedMimeType();
        const rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
        recorderRef.current = rec;
        recorderMimeRef.current = mime || "";
        chunksRef.current = [];
        rec.ondataavailable = (e: BlobEvent) => {
          if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
        };
        rec.onstop = () => { finalizeRecording(rid); };
        rec.onerror = () => { /* finalize uses buffered chunks + SR text */ };
        rec.start(250);
      } catch {
        recorderRef.current = null;
      }
    }

    if (!recogRef.current && !recorderRef.current) {
      stopAudioGraph();
      setError("Could not start voice input. Please type your message instead.");
      return;
    }
    setListening(true);
  }, [stopSpeaking, micDeviceId, stopAudioGraph, listening, processing, transcribing, requestingMic, sessionId, ended, finalizeRecording]);

  const endSession = useCallback(async () => {
    stopSpeaking();
    autoArmedRef.current = false;
    try { recogRef.current?.abort?.(); } catch {}
    stopAudioGraph();
    setListening(false);
    if (sessionRef.current) {
      try { await api.conversationEnd(sessionRef.current); } catch { /* local goodbye anyway */ }
    }
    setChat((prev) => [...prev, {
      from: "assistant",
      text: "Take care. Be gentle with yourself today. I'm here whenever you want to talk.",
    }]);
    setSessionId("");
    setEnded(true);
  }, [stopSpeaking]);

  const toggleVoice = useCallback(() => {
    if (voiceOn) stopSpeaking();
    setVoiceOn((v) => !v);
  }, [voiceOn, stopSpeaking]);

  const toggleHandsFree = useCallback(() => {
    setHandsFree((v) => {
      const next = !v;
      if (!next) autoArmedRef.current = false;
      return next;
    });
  }, []);

  // Hands-free companion loop: when the bot finishes a turn, reopen the mic
  // automatically so the user can just keep talking.
  useEffect(() => {
    if (
      handsFree && autoArmedRef.current &&
      !processing && !speaking && !listening && !ended && !starting &&
      sessionId
    ) {
      autoArmedRef.current = false;
      startListening();
    }
  }, [handsFree, processing, speaking, listening, ended, starting, sessionId, startListening]);

  // Meter loop (defined inside startListening) calls stop via ref to avoid
  // a stale closure over stopListening.
  stopRef.current = stopListening;

  return (
    <GlassCard className="p-4 w-full max-w-2xl flex flex-col" >
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/50">
        <div className="flex items-center gap-2">
          <HeartHandshake className="w-5 h-5 text-teal-300" />
          <div>
            <h3 className="text-sm font-bold text-white">Calm Companion</h3>
            <p className="text-[11px] text-slate-400">
              {starting ? "Connecting…" : ended ? "Conversation ended"
                : requestingMic ? "Requesting microphone…"
                : transcribing ? (transcribeDetail || "Transcribing your message…")
                : processing ? "Thinking…" : speaking ? "Speaking…"
                : listening ? (handsFree ? "Recording your voice… (pause to send)" : "Recording your voice…") : "Here with you"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={toggleHandsFree}
            aria-label={handsFree ? "Turn off hands-free conversation" : "Turn on hands-free conversation"}
            title={handsFree ? "Hands-free ON: mic reopens after each reply" : "Hands-free OFF: tap the mic each turn"}
            className={`px-2.5 py-2 rounded-lg text-[11px] font-semibold border transition-all ${
              handsFree
                ? "bg-teal-500/20 text-teal-200 border-teal-500/50"
                : "bg-slate-800/60 text-slate-400 border-slate-700/50 hover:text-slate-200"
            }`}
          >
            Hands-free {handsFree ? "on" : "off"}
          </button>
          <button
            onClick={toggleVoice}
            aria-label={voiceOn ? "Mute spoken replies" : "Unmute spoken replies"}
            title={voiceOn ? "Mute spoken replies" : "Unmute spoken replies"}
            className="p-2 rounded-lg bg-slate-800/60 text-slate-300 hover:text-white border border-slate-700/50"
          >
            {voiceOn ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          </button>
          {!ended && (
            <button
              onClick={endSession}
              aria-label="End conversation"
              title="End conversation"
              className="p-2 rounded-lg bg-slate-800/60 text-slate-300 hover:text-rose-300 border border-slate-700/50"
            >
              <PhoneOff className="w-4 h-4" />
            </button>
          )}
          {ended && (
            <button
              onClick={startSession}
              aria-label="Start new conversation"
              title="Start new conversation"
              className="p-2 rounded-lg bg-teal-500/15 text-teal-200 border border-teal-500/40 flex items-center gap-1 text-xs font-semibold px-3"
            >
              <RotateCcw className="w-4 h-4" /> New chat
            </button>
          )}
        </div>
      </div>

      {/* Stress sharing toggle */}
      {initialStressContext && (
        <label className="flex items-center gap-2 pt-3 text-[11px] text-slate-400 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={shareStress}
            onChange={(e) => setShareStress(e.target.checked)}
            className="accent-teal-400"
          />
          Share my latest stress reading{stressSourceLabel ? ` (${stressSourceLabel})` : ""} so the companion can adapt its tone
        </label>
      )}

      {/* Chat area */}
      <div className="flex-1 min-h-[280px] max-h-[420px] overflow-y-auto py-3 space-y-2" role="log" aria-live="polite">
        {starting && (
          <div className="flex items-center justify-center gap-2 text-sm text-slate-400 py-8">
            <Loader2 className="w-4 h-4 animate-spin" /> Connecting to your companion…
          </div>
        )}
        {chat.map((m, i) => (
          <div key={i} className={`flex ${m.from === "you" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] text-sm p-2.5 rounded-2xl leading-relaxed ${
              m.from === "you"
                ? "bg-teal-500/15 border border-teal-500/30 text-teal-50 rounded-br-md"
                : m.safety
                ? "bg-amber-500/10 border border-amber-500/40 text-slate-100 rounded-bl-md"
                : "bg-slate-800/70 border border-slate-700/60 text-slate-100 rounded-bl-md"
            }`}>
              {m.text}
              {m.activitySteps && m.activitySteps.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-700/60">
                  {m.activityTitle && <p className="text-xs font-bold text-teal-200 mb-1">{m.activityTitle}</p>}
                  <ol className="text-xs text-slate-200 space-y-0.5 list-decimal list-inside">
                    {m.activitySteps.map((s, si) => <li key={si}>{s}</li>)}
                  </ol>
                  {m.checkIn && <p className="text-xs text-slate-300 mt-1.5 italic">{m.checkIn}</p>}
                </div>
              )}
            </div>
          </div>
        ))}

        {listening && (
          <div className="flex justify-end">
            <div className="max-w-[85%] text-sm p-2.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-100 rounded-br-md">
              <span className="text-[11px] uppercase tracking-wider text-rose-300">Recording your voice… </span>
              {liveTranscript || liveInterim
                ? <span>{liveTranscript}{liveInterim && <span className="opacity-70"> {liveInterim}</span>}</span>
                : <span className="text-rose-200/70">speak now</span>}
              <span className="inline-block w-2 h-4 bg-rose-400 ml-1 animate-pulse align-middle" />
              {/* Live mic proof: moves as you speak, even if transcription fails */}
              <div className="flex items-center gap-2 mt-2">
                <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-amber-400 to-rose-400 transition-all"
                    style={{ width: `${Math.round(micLevel * 100)}%` }}
                  />
                </div>
                <span className="text-[10px] text-slate-400">mic live</span>
              </div>
            </div>
          </div>
        )}

        {transcribing && (
          <div className="flex justify-start">
            <div className="text-sm p-2.5 rounded-2xl bg-slate-800/70 border border-slate-700/60 text-slate-300 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> {transcribeDetail || "Transcribing your message…"}
            </div>
          </div>
        )}

        {processing && (
          <div className="flex justify-start">
            <div className="text-sm p-2.5 rounded-2xl bg-slate-800/70 border border-slate-700/60 text-slate-300 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Thinking…
            </div>
          </div>
        )}

        {speaking && !processing && (
          <div className="flex items-center gap-2 text-[11px] text-teal-300">
            <span className="flex items-end gap-0.5 h-3">
              {[0, 1, 2, 3].map((b) => (
                <span key={b} className="w-1 bg-teal-400/80 rounded animate-pulse" style={{ height: `${6 + ((b * 5) % 8)}px`, animationDelay: `${b * 120}ms` }} />
              ))}
            </span>
            Speaking… you can interrupt anytime
            <button onClick={stopSpeaking} className="px-2 py-0.5 rounded-lg text-[11px] font-semibold bg-slate-800 border border-slate-600 hover:border-teal-400">
              Stop
            </button>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-200 flex gap-2 mb-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span className="flex-1">{error}</span>
          {voiceRetryable && !listening && !transcribing && (
            <button
              onClick={startListening}
              className="shrink-0 px-2.5 py-1 rounded-lg text-[11px] font-bold bg-rose-500/20 text-rose-100 border border-rose-500/40 hover:bg-rose-500/30"
            >
              Try again
            </button>
          )}
        </div>
      )}

      {!sttSupported && fallbackReady === false && (
        <p className="text-[11px] text-amber-300/90 mb-2">Voice transcription is temporarily unavailable — typing works exactly the same.</p>
      )}
      {!sttSupported && fallbackReady !== false && (
        <p className="text-[11px] text-amber-300/90 mb-2">Using on-device transcription for your voice — private, no account needed. Typing works too.</p>
      )}
      {!ttsSupported && (
        <p className="text-[11px] text-amber-300/90 mb-2">Spoken replies aren&apos;t available in this browser — you&apos;ll see text replies.</p>
      )}

      {/* Activity shortcuts */}
      {!ended && (
        <div className="flex flex-wrap gap-1.5 pb-2">
          {ACTIVITY_SHORTCUTS.map((a) => {
            const Icon = a.icon;
            return (
              <button
                key={a.id}
                onClick={() => sendMessage(a.prompt)}
                disabled={processing || transcribing || !sessionId}
                title={a.prompt}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-slate-800/60 text-slate-300 border border-slate-700 hover:border-teal-500/60 hover:text-teal-200 disabled:opacity-50 transition-all"
              >
                <Icon className="w-3 h-3" /> {a.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Input row */}
      <div className="flex items-center gap-2 pt-2 border-t border-slate-700/50">
        {!listening ? (
          <button
            onClick={startListening}
            disabled={processing || transcribing || requestingMic || !sessionId || ended}
            aria-label="Talk with your voice"
            title="Talk with your voice"
            className="p-2.5 rounded-xl bg-teal-500/15 text-teal-200 border border-teal-500/40 hover:bg-teal-500/25 disabled:opacity-50 transition-all"
          >
            {requestingMic ? <Loader2 className="w-5 h-5 animate-spin" /> : <Mic className="w-5 h-5" />}
          </button>
        ) : (
          <>
            <button
              onClick={stopListening}
              aria-label="Stop and send"
              title="Stop and send"
              className="p-2.5 rounded-xl bg-rose-500/15 text-rose-200 border border-rose-500/40 hover:bg-rose-500/25 transition-all animate-pulse"
            >
              <Square className="w-5 h-5" />
            </button>
            <button
              onClick={cancelListening}
              aria-label="Cancel recording"
              title="Cancel — discard this recording"
              className="p-2.5 rounded-xl text-xs text-slate-400 border border-slate-700 hover:border-rose-400 hover:text-rose-300 transition-all"
            >
              ✕
            </button>
          </>
        )}
        <button
          onClick={() => { setShowMicPicker((v) => !v); loadMicDevices(); }}
          disabled={listening || processing || transcribing}
          aria-label="Choose microphone"
          title="Choose microphone"
          className="p-2.5 rounded-xl text-xs text-slate-300 border border-slate-700 hover:border-teal-500/60 disabled:opacity-50"
        >
          🎙️
        </button>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") sendMessage(input); }}
          placeholder={transcribing ? "Transcribing…" : listening ? "Recording… tap ■ to send, ✕ to cancel" : ended ? "Conversation ended" : "Type how you're feeling…"}
          disabled={processing || transcribing || ended || listening}
          aria-label="Type your message"
          className="flex-1 rounded-xl bg-slate-800 border border-slate-700 text-sm text-slate-100 p-2.5 placeholder:text-slate-500 disabled:opacity-50"
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={!input.trim() || processing || transcribing || ended || listening}
          aria-label="Send message"
          title="Send"
          className="p-2.5 rounded-xl bg-gradient-to-r from-teal-600 to-cyan-500 text-white disabled:opacity-50 transition-all"
        >
          {(processing || transcribing) ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
        </button>
      </div>

      {!voiceOn && ttsSupported && (
        <p className="text-[11px] text-slate-500 pt-1.5">Spoken replies are muted — tap the speaker icon to hear the companion.</p>
      )}

      {showMicPicker && !listening && (
        <div className="rounded-xl border border-slate-700/80 bg-slate-900/60 p-2.5 mt-2">
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

      {/* Dev-only voice diagnostics: capabilities + last-attempt timeline.
          Counts and stage names only — never transcripts or audio. */}
      {process.env.NODE_ENV === "development" && diag && (
        <details className="mt-2 rounded-xl border border-slate-700/60 bg-slate-900/60 p-2.5">
          <summary className="text-[11px] font-semibold text-slate-400 cursor-pointer select-none">
            Voice diagnostics (dev only)
          </summary>
          <pre className="mt-1.5 text-[11px] font-mono text-slate-300 whitespace-pre-wrap break-words">
            {JSON.stringify(
              {
                phase: requestingMic
                  ? "requesting_permission"
                  : listening
                  ? "recording"
                  : transcribing
                  ? (localModelReady ? "transcribing" : "initializing")
                  : processing
                  ? "responding"
                  : "idle",
                localModelReady,
                ...diag,
              },
              null,
              1
            )}
          </pre>
        </details>
      )}
    </GlassCard>
  );
};
