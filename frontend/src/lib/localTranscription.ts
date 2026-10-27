/**
 * On-device speech transcription (Whisper, runs fully in the browser).
 *
 * Fully local: the library is bundled from npm (never a CDN script tag),
 * the ONNX Runtime WASM binaries are served from /vendor/ort/, and the
 * Whisper model files from /models/ (see scripts/fetch-stt-assets.sh).
 * With `allowRemoteModels: false` nothing at runtime can reach an external
 * host, so Brave Shields / ad-blockers cannot break initialization.
 * Audio never leaves the device.
 *
 * Failures are typed (LocalTranscribeError with a `stage`) so callers can
 * show accurate messages instead of blaming the download for everything.
 */

export type TranscriptionProgress = (percent: number, label: string) => void;

export type TranscribeStage = "lib-load" | "model-load" | "decode" | "transcribe";

export class LocalTranscribeError extends Error {
  stage: TranscribeStage;
  /** Failing URL when known (model file, wasm) — safe to show/log. */
  url?: string;

  constructor(stage: TranscribeStage, message: string, url?: string) {
    super(message);
    this.name = "LocalTranscribeError";
    this.stage = stage;
    this.url = url;
  }
}

export function isLocalTranscribeError(e: unknown): e is LocalTranscribeError {
  return (
    typeof e === "object" &&
    e !== null &&
    (e as LocalTranscribeError).name === "LocalTranscribeError" &&
    typeof (e as LocalTranscribeError).stage === "string"
  );
}

/** Real error detail for console + dev diagnostics (never transcripts/audio). */
export function logTranscribeError(e: unknown): { stage: string; name: string; message: string; url?: string } {
  const info = {
    stage: isLocalTranscribeError(e) ? e.stage : "unknown",
    name: e instanceof Error ? e.name : typeof e,
    message: e instanceof Error ? e.message : String(e),
    url: isLocalTranscribeError(e) ? e.url : undefined,
  };
  if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
    // eslint-disable-next-line no-console
    console.error("[STT]", info);
    if (e instanceof Error && e.stack) {
      // eslint-disable-next-line no-console
      console.error("[STT] stack:", e.stack);
    }
  }
  return info;
}

type WhisperPipeline = (audio: Float32Array, options?: Record<string, unknown>) => Promise<{ text?: string }>;

const MODEL_ID = "Xenova/whisper-tiny.en";
// Prebuilt browser bundle served from /public (see scripts/fetch-stt-assets.sh).
// webpackIgnore keeps Next.js out of it: the browser imports it natively,
// so bundler quirks (ignored Node-only modules evaluating at chunk load)
// cannot break initialization.
const VENDOR_URL = "/vendor/transformers.bundle.mjs";
// Local model parsing (150MB from disk); generous but finite so the UI can
// never stick in "initializing" forever. Failures reset for retry.
const MODEL_TIMEOUT_MS = 90000;

let pipePromise: Promise<WhisperPipeline> | null = null;

async function blobToMono16k(blob: Blob): Promise<Float32Array> {
  let buf: ArrayBuffer;
  try {
    buf = await blob.arrayBuffer();
  } catch {
    throw new LocalTranscribeError("decode", "That recording could not be read. Please try again or type your message.");
  }
  const AC: typeof AudioContext | undefined =
    window.AudioContext || (window as any).webkitAudioContext;
  if (!AC) throw new LocalTranscribeError("decode", "Audio decoding is not supported in this browser. Please type your message.");
  const ctx = new AC();
  try {
    let decoded;
    try {
      decoded = await ctx.decodeAudioData(buf.slice(0));
    } catch {
      throw new LocalTranscribeError("decode", "That recording could not be decoded. Please record again or type your message.");
    }
    const channels = decoded.numberOfChannels;
    const inRate = decoded.sampleRate;
    const inLen = decoded.length;
    const mono = new Float32Array(inLen);
    for (let ch = 0; ch < channels; ch++) {
      const data = decoded.getChannelData(ch);
      for (let i = 0; i < inLen; i++) mono[i] += data[i] / channels;
    }
    if (inRate === 16000) return mono;
    const outLen = Math.max(1, Math.floor((inLen / inRate) * 16000));
    const out = new Float32Array(outLen);
    const ratio = inLen / outLen;
    for (let i = 0; i < outLen; i++) {
      const pos = i * ratio;
      const i0 = Math.floor(pos);
      const i1 = Math.min(i0 + 1, inLen - 1);
      const frac = pos - i0;
      out[i] = mono[i0] * (1 - frac) + mono[i1] * frac;
    }
    return out;
  } finally {
    try {
      await ctx.close();
    } catch {
      /* ignore */
    }
  }
}

function loadPipeline(onProgress?: TranscriptionProgress): Promise<WhisperPipeline> {
  if (!pipePromise) {
    pipePromise = (async () => {
      // Native browser import of the vendored bundle (NOT the npm package
      // entry: that pulls Node-only modules into bundler graphs, which is
      // what broke initialization before).
      let lib: {
        pipeline: (task: string, model: string, options?: Record<string, unknown>) => Promise<unknown>;
        env: {
          allowLocalModels: boolean;
          allowRemoteModels: boolean;
          localModelPath: string;
          backends: { onnx: { wasm: { wasmPaths: string; numThreads: number } } };
        };
      };
      try {
        const mod = await import(/* webpackIgnore: true */ VENDOR_URL) as Record<string, unknown>;
        if (typeof mod.pipeline !== "function" || !mod.env) {
          throw new Error("bundle missing pipeline/env exports");
        }
        lib = mod as unknown as typeof lib;
      } catch (e) {
        throw new LocalTranscribeError(
          "lib-load",
          "The on-device speech engine failed to start. Please try again — or type your message.",
          VENDOR_URL
        );
      }
      // Pin every runtime path to localhost: WASM binaries, model files, and
      // no remote fallback, so blockers and offline-after-setup can't break it.
      lib.env.allowLocalModels = true;
      lib.env.allowRemoteModels = false;
      lib.env.localModelPath = "/models/";
      try {
        lib.env.backends.onnx.wasm.wasmPaths = "/vendor/ort/";
        // No COOP/COEP headers are set (and none are needed): stay single-threaded.
        lib.env.backends.onnx.wasm.numThreads = 1;
      } catch {
        /* older backend shape — defaults still work */
      }
      onProgress?.(10, "Preparing voice recognition…");
      type LoadWin = { ok: true; pipe: WhisperPipeline } | { ok: false };
      const loadP: Promise<LoadWin> = lib
        .pipeline("automatic-speech-recognition", MODEL_ID)
        .then((pipe): LoadWin => ({ ok: true, pipe: pipe as unknown as WhisperPipeline }));
      const timeoutP: Promise<LoadWin> = new Promise<LoadWin>((resolve) => {
        window.setTimeout(() => resolve({ ok: false }), MODEL_TIMEOUT_MS);
      });
      const winner: LoadWin = await Promise.race([loadP, timeoutP]);
      if (!winner.ok) {
        throw new LocalTranscribeError(
          "model-load",
          "Voice recognition took too long to start. Please try again — or type your message.",
          "/models/Xenova/whisper-tiny.en/"
        );
      }
      onProgress?.(100, "Speech model ready…");
      return winner.pipe;
    })().catch((e) => {
      pipePromise = null; // allow retry; never cache failure
      if (isLocalTranscribeError(e)) throw e;
      const url = e instanceof Error ? /https?:\/\/\S+/.exec(e.message)?.[0] : undefined;
      throw new LocalTranscribeError(
        "model-load",
        "Voice recognition couldn't start (missing or unreadable local model file). " +
        "Run scripts/fetch-stt-assets.sh, restart the frontend, and try again — or type your message.",
        url
      );
    });
  } else if (onProgress) {
    onProgress(100, "Speech model ready…");
  }
  return pipePromise;
}

/**
 * Transcribe recorded audio fully on-device. Throws LocalTranscribeError
 * with a stage (lib-load | model-load | decode | transcribe) or a plain
 * Error("empty audio") for sub-second/empty input.
 */
export async function transcribeLocally(
  blob: Blob,
  onProgress?: TranscriptionProgress
): Promise<string> {
  if (!blob || blob.size < 800) throw new Error("empty audio");
  const [pipe, samples] = await Promise.all([
    loadPipeline(onProgress),
    blobToMono16k(blob),
  ]);
  if (samples.length < 1600) throw new Error("empty audio"); // <0.1s
  onProgress?.(100, "Transcribing your message…");
  let out;
  try {
    out = await pipe(samples, {
      chunk_length_s: 30,
      stride_length_s: 5,
      return_timestamps: false,
    });
  } catch {
    throw new LocalTranscribeError(
      "transcribe",
      "On-device transcription failed on that recording. Please try again or type your message."
    );
  }
  return String(out?.text || "").trim();
}

/** True once the model pipeline has loaded (no init wait on next use). */
export function isLocalModelReady(): boolean {
  return pipePromise !== null;
}
