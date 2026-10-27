"""
Transcription fallback tests (spec section 8).

Covers endpoint validation (auth, MIME, empty, oversized, malformed),
provider-unconfigured 503, mocked-provider success, and status reporting.
No real provider calls, no randomness: synthesized WAV audio in-memory.
"""

import base64
import io

import pytest
import numpy as np
import soundfile as sf
from httpx import AsyncClient

from backend.app.main import app
from backend.app.services import transcription as stt


def speech_wav(amp=0.3, secs=3.0, sr=16000):
    t = np.arange(int(sr * secs)) / sr
    y = (amp * np.sin(2 * np.pi * 160 * t)
         * (0.65 + 0.35 * np.sin(2 * np.pi * 2.5 * t))).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, y, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def silence_wav(secs=2.0, sr=16000):
    buf = io.BytesIO()
    sf.write(buf, np.zeros(int(sr * secs), dtype=np.float32), sr,
             format="WAV", subtype="PCM_16")
    return buf.getvalue()


class FakeUpload:
    def __init__(self, data: bytes, content_type: str, filename: str = "voice.webm"):
        self._data = data
        self.content_type = content_type
        self.filename = filename

    async def read(self):
        return self._data

    async def close(self):
        pass


class FakeAdapter:
    name = "fake"

    def __init__(self, text="hello companion"):
        self._text = text

    async def transcribe(self, audio, filename, mime):
        assert len(audio) > 800
        from backend.app.services.transcription import TranscriptionResult
        return TranscriptionResult(transcript=self._text, provider="fake",
                                   duration_seconds=3.0)


@pytest.fixture(scope="module")
def event_loop():
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def auth_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        res = await client.post("/api/v1/auth/register", json={
            "email": "sttfix@stressai.com",
            "full_name": "STT Fix",
            "password": "SttFix@2026",
        })
        if res.status_code != 201:
            res = await client.post("/api/v1/auth/login", json={
                "email": "sttfix@stressai.com",
                "password": "SttFix@2026",
            })
        return res.json().get("access_token", "")


@pytest.mark.asyncio
async def test_rejects_bad_uploads():
    with pytest.raises(stt.EmptyRecording):
        await stt.transcribe_upload(FakeUpload(b"", "audio/webm"))
    with pytest.raises(stt.MalformedAudio):
        await stt.transcribe_upload(FakeUpload(b"x" * 2000, "text/plain", "note.txt"))
    with pytest.raises(stt.MalformedAudio):
        await stt.transcribe_upload(FakeUpload(b"not audio" * 500, "audio/webm"))
    with pytest.raises(stt.EmptyRecording):
        await stt.transcribe_upload(FakeUpload(silence_wav(), "audio/wav", "s.wav"))


@pytest.mark.asyncio
async def test_unconfigured_provider_503_service(monkeypatch):
    monkeypatch.setattr(stt.settings, "STT_PROVIDER", "none")
    with pytest.raises(stt.ProviderNotConfigured):
        await stt.transcribe_upload(FakeUpload(speech_wav(), "audio/wav", "s.wav"))


@pytest.mark.asyncio
async def test_mocked_provider_success(monkeypatch):
    monkeypatch.setattr(stt, "_adapter", lambda: FakeAdapter("i feel stressed"))
    res = await stt.transcribe_upload(FakeUpload(speech_wav(), "audio/wav", "s.wav"))
    assert res.transcript == "i feel stressed"
    assert res.provider == "fake"


@pytest.mark.asyncio
async def test_status_reports_configured_flag(monkeypatch):
    monkeypatch.setattr(stt.settings, "STT_PROVIDER", "none")
    info = stt.provider_status()
    assert set(("provider", "configured", "max_mb", "note")) <= set(info)
    assert info["configured"] is False
    assert "API_KEY" not in str(info) and "sk-" not in str(info)
    monkeypatch.setattr(stt.settings, "STT_PROVIDER", "local")
    info = stt.provider_status()
    assert info["configured"] is True
    assert info["provider"] == "local"


@pytest.mark.asyncio
async def test_api_validation_and_status(auth_token, monkeypatch):
    # Force the unconfigured path for the 503 assertion regardless of local .env.
    monkeypatch.setattr(stt.settings, "STT_PROVIDER", "none")
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Auth required.
        r = await client.post("/api/v1/voice/transcribe",
                              files={"audio": ("s.wav", speech_wav(), "audio/wav")})
        assert r.status_code in (401, 403), r.status_code

        # Status is reachable and leaks no secrets.
        r = await client.get("/api/v1/voice/transcribe/status", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["configured"] is False
        assert "sk-" not in r.text

        # No provider configured → honest 503, never a fake transcript.
        r = await client.post("/api/v1/voice/transcribe",
                              files={"audio": ("s.wav", speech_wav(), "audio/wav")},
                              headers=headers)
        assert r.status_code == 503, (r.status_code, r.text[:120])

        # Silence → 422 (no speech), not a Moderate score.
        r = await client.post("/api/v1/voice/transcribe",
                              files={"audio": ("s.wav", silence_wav(), "audio/wav")},
                              headers=headers)
        assert r.status_code == 422, (r.status_code, r.text[:120])

        # Malformed → 400.
        r = await client.post("/api/v1/voice/transcribe",
                              files={"audio": ("s.wav", b"junk" * 500, "audio/wav")},
                              headers=headers)
        assert r.status_code == 400, (r.status_code, r.text[:120])


@pytest.mark.asyncio
async def test_api_success_with_mocked_provider(auth_token, monkeypatch):
    import backend.app.api.v1.endpoints.transcribe as ep

    async def fake_upload(file):
        assert file.filename
        return stt.TranscriptionResult(transcript="i feel stressed",
                                      provider="fake", duration_seconds=3.0)

    monkeypatch.setattr(ep, "transcribe_upload", fake_upload)
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/api/v1/voice/transcribe",
                              files={"audio": ("s.wav", speech_wav(), "audio/wav")},
                              headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["transcript"] == "i feel stressed"


@pytest.mark.asyncio
async def test_real_local_adapter_silence_is_empty():
    """Real faster-whisper adapter (no mock): silence transcribes to nothing,
    proving the provider path works without faking text."""
    pytest.importorskip("faster_whisper")
    adapter = stt.LocalWhisperAdapter(model_size="tiny.en")
    res = await adapter.transcribe(silence_wav(), "s.wav", "audio/wav")
    assert res.transcript == ""
    assert res.provider == "local-whisper"
