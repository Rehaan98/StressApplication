"""
Server-side speech-to-text fallback for browsers whose built-in Web Speech
API is unavailable or blocked (e.g. Brave exposes the API object but its
transcription service fails).

Architecture: frontend records with MediaRecorder → multipart upload here →
provider adapter → transcript back. Keys live only in backend env vars.
Nothing is stored: audio is transcribed in memory and dropped.

Supported providers (STT_PROVIDER):
  * "none"   — no provider configured; endpoint answers 503 (never fakes text)
  * "local"  — on-server faster-whisper model (no key, audio never leaves host)
  * "openai" — Whisper via the OpenAI audio API (needs STT_OPENAI_API_KEY)

To add a provider, implement ``ProviderAdapter`` and register it in
``_PROVIDERS`` — no endpoint changes needed.
"""

import asyncio
import base64
import io
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Protocol

from fastapi import UploadFile

from backend.app.core.config import settings

logger = logging.getLogger("stress_ai")

# MediaRecorder outputs across Chrome/Edge/Brave/Safari/Firefox.
ALLOWED_MIME_TYPES = {
    "audio/webm",
    "audio/webm;codecs=opus",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/ogg;codecs=opus",
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/aiff",
    "audio/x-aiff",
    "audio/x-caf",
    "video/webm",  # some browsers label mic recordings this way
    "application/octet-stream",  # unnamed blobs; content is still validated
}

EXT_BY_MIME = {
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "video/webm": "webm",
}


@dataclass
class TranscriptionResult:
    transcript: str
    provider: str
    duration_seconds: float
    language: Optional[str] = None
    warning: Optional[str] = None


class TranscriptionError(Exception):
    """Base error (message is safe to show the user)."""


class ProviderNotConfigured(TranscriptionError):
    pass


class EmptyRecording(TranscriptionError):
    pass


class MalformedAudio(TranscriptionError):
    pass


class ProviderFailed(TranscriptionError):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class ProviderAdapter(Protocol):
    name: str

    async def transcribe(self, audio: bytes, filename: str, mime: str) -> TranscriptionResult:
        ...


class OpenAIWhisperAdapter:
    """Whisper transcription via the OpenAI audio API (server-side key)."""
    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str, timeout_s: float):
        self._key = api_key
        self._model = model or "whisper-1"
        self._base = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._timeout = timeout_s or 30.0

    async def transcribe(self, audio: bytes, filename: str, mime: str) -> TranscriptionResult:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._key}"},
                    files={"file": (filename, audio, mime or "audio/webm")},
                    data={"model": self._model, "response_format": "verbose_json"},
                )
        except (TimeoutError, asyncio.TimeoutError):
            raise ProviderFailed("The transcription service timed out. Please try again.", retryable=True)
        except Exception as e:
            logger.warning("STT provider network error: %s", type(e).__name__)
            raise ProviderFailed("Could not reach the transcription service. Please try again.", retryable=True)

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                raise ProviderFailed("The transcription service returned an unreadable response.", retryable=True)
            text = str(data.get("text", "") or "").strip()
            dur = data.get("duration")
            try:
                dur_f = float(dur) if dur is not None else 0.0
            except (TypeError, ValueError):
                dur_f = 0.0
            if not text:
                return TranscriptionResult(transcript="", provider=self.name,
                                           duration_seconds=dur_f,
                                           warning="No speech was recognized in that recording.")
            return TranscriptionResult(transcript=text, provider=self.name,
                                       duration_seconds=dur_f,
                                       language=data.get("language"))
        if resp.status_code == 401:
            logger.warning("STT provider rejected credentials (401).")
            raise ProviderFailed("Transcription is misconfigured. Please try typing instead.", retryable=False)
        if resp.status_code == 429:
            raise ProviderFailed("Transcription is busy right now. Please wait a moment and try again.", retryable=True)
        logger.warning("STT provider error: HTTP %s", resp.status_code)
        raise ProviderFailed("The transcription service had trouble with that recording.", retryable=True)


class LocalWhisperAdapter:
    """On-server faster-whisper transcription (no key, audio never leaves host).

    The model loads lazily on first use (one-time download into the HF cache
    or STT_MODEL_DIR, then offline). VAD filtering stays OFF so soft starts,
    pauses, and hesitant speech are preserved rather than clipped.
    """

    name = "local-whisper"
    _model = None
    _model_key: Optional[str] = None

    def __init__(self, model_size: str = "tiny.en", device: str = "cpu",
                 compute_type: str = "int8", download_root: Optional[str] = None):
        self._size = model_size
        self._device = device
        self._compute = compute_type
        self._root = download_root

    @classmethod
    def _load(cls, size: str, device: str, compute: str, root: Optional[str]):
        key = f"{size}|{device}|{compute}|{root or ''}"
        if cls._model is None or cls._model_key != key:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise ProviderNotConfigured(
                    "Local transcription isn't installed (pip install faster-whisper). "
                    "You can still type your message."
                )
            import os as _os

            if root:
                _os.makedirs(root, exist_ok=True)
            try:
                cls._model = WhisperModel(size, device=device,
                                          compute_type=compute,
                                          download_root=root)
            except Exception as e:
                logger.warning("Local Whisper load failed: %s", type(e).__name__)
                raise ProviderFailed(
                    "Local transcription couldn't start. Please try again or type your message.",
                    retryable=True,
                )
            cls._model_key = key
        return cls._model

    async def transcribe(self, audio: bytes, filename: str, mime: str) -> TranscriptionResult:
        import asyncio as _asyncio
        import tempfile as _tf
        import os as _os

        model = self._load(self._size, self._device, self._compute, self._root)
        suffix = ".webm"
        low = (mime or "").lower()
        if "mp4" in low or "m4a" in low:
            suffix = ".m4a"
        elif "wav" in low:
            suffix = ".wav"
        elif "ogg" in low or "opus" in low:
            suffix = ".ogg"
        path = None
        try:
            with _tf.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(audio)
                path = f.name
            # CPU-bound: run off the event loop. beam_size=1 keeps latency low;
            # vad_filter stays off to preserve quiet/paused speech.
            loop = _asyncio.get_running_loop()
            segments, info = await loop.run_in_executor(
                None,
                lambda: model.transcribe(path, language="en", beam_size=1,
                                         vad_filter=False),
            )
            text = " ".join((s.text or "").strip() for s in segments).strip()
            if not text:
                return TranscriptionResult(transcript="", provider=self.name,
                                           duration_seconds=float(info.duration or 0.0),
                                           language=getattr(info, "language", None),
                                           warning="No speech was recognized in that recording.")
            return TranscriptionResult(transcript=text, provider=self.name,
                                       duration_seconds=float(info.duration or 0.0),
                                       language=getattr(info, "language", None))
        except ProviderFailed:
            raise
        except Exception as e:
            logger.warning("Local Whisper transcribe failed: %s", type(e).__name__)
            raise ProviderFailed(
                "Local transcription had trouble with that recording.", retryable=True
            )
        finally:
            try:
                if path and _os.path.exists(path):
                    _os.remove(path)
            except Exception:
                pass


def _adapter() -> ProviderAdapter:
    provider = (settings.STT_PROVIDER or "none").strip().lower()
    if provider == "local":
        return LocalWhisperAdapter(
            model_size=(settings.STT_MODEL or "tiny.en").strip() or "tiny.en",
            device=(settings.STT_DEVICE or "cpu").strip() or "cpu",
            compute_type=(settings.STT_COMPUTE or "int8").strip() or "int8",
            download_root=(settings.STT_MODEL_DIR or "").strip() or None,
        )
    if provider == "openai":
        key = (settings.STT_OPENAI_API_KEY or "").strip()
        if not key:
            raise ProviderNotConfigured(
                "Voice transcription is temporarily unavailable. You can still type your message."
            )
        return OpenAIWhisperAdapter(key, settings.STT_OPENAI_MODEL,
                                    settings.STT_OPENAI_BASE_URL, settings.STT_TIMEOUT_S)
    raise ProviderNotConfigured(
        "Voice transcription is temporarily unavailable. You can still type your message."
    )


def provider_status() -> Dict[str, object]:
    provider = (settings.STT_PROVIDER or "none").strip().lower()
    if provider == "local":
        try:
            import faster_whisper  # noqa: F401
            configured: bool = True
            note = "Local on-server transcription ready (no key needed)."
        except ImportError:
            configured = False
            note = "Local provider selected but faster-whisper isn't installed."
    elif provider == "openai":
        configured = bool((settings.STT_OPENAI_API_KEY or "").strip())
        note = ("Server transcription ready." if configured
                else "OpenAI provider selected but no API key is set.")
    else:
        configured = False
        note = "No transcription provider configured — voice typing needs one."
    return {
        "provider": provider,
        "configured": configured,
        "max_mb": float(settings.STT_MAX_MB),
        "note": note,
    }


async def transcribe_upload(file: UploadFile) -> TranscriptionResult:
    """Validate an uploaded recording and transcribe it. Never stores audio."""
    if file is None or not getattr(file, "filename", None):
        raise MalformedAudio("No audio was uploaded. Please record again.")

    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME_TYPES:
        raise MalformedAudio(
            f"That audio format isn't supported ({mime or 'unknown'}). Please try again."
        )

    max_bytes = int(float(settings.STT_MAX_MB) * 1024 * 1024)
    try:
        audio = await file.read()
    except Exception:
        raise MalformedAudio("Could not read the uploaded audio. Please try again.")
    finally:
        try:
            await file.close()
        except Exception:
            pass

    if not audio or len(audio) < 800:
        raise EmptyRecording("That recording was empty. Please speak and try again.")
    if len(audio) > max_bytes:
        raise MalformedAudio(
            f"That recording is too large (over {settings.STT_MAX_MB:g} MB). Please record a shorter message."
        )

    # Content validation + speech-presence check on the REAL bytes (never faked).
    from backend.app.services import voice_service as vs

    try:
        raw_b64 = base64.b64encode(audio).decode()
        y, _sr = vs._decode_audio(raw_b64)
    except ValueError:
        raise MalformedAudio("That recording couldn't be read. Please record again.")
    level = vs.assess_audio_level(y)
    duration = round(float(len(y)) / 16000.0, 2)
    if not level.get("usable"):
        raise EmptyRecording(
            "No speech was detected in that recording. Please move closer to the mic and try again."
        )

    adapter = _adapter()
    ext = EXT_BY_MIME.get(mime, "webm")
    try:
        result = await asyncio.wait_for(
            adapter.transcribe(audio, f"voice.{ext}", mime or "audio/webm"),
            timeout=float(settings.STT_TIMEOUT_S) + 5.0,
        )
    except (TimeoutError, asyncio.TimeoutError):
        raise ProviderFailed("The transcription service timed out. Please try again.", retryable=True)
    if not result.duration_seconds:
        result.duration_seconds = duration
    # Never log transcripts or audio — only sizes and outcomes.
    logger.info("STT transcribed %d bytes via %s (%.1fs audio).",
                len(audio), result.provider, result.duration_seconds)
    return result
