"""
Session conversation context — what the bot remembers within one conversation.

Keeps: turn history, user-stated facts (topic, energy drain, small win),
preferences (e.g. "just wants to talk, no advice"), recent bot phrasings
(to avoid repetition), and the latest optional stress context passed in by
the caller. Everything lives in-memory per session; ending a session drops it.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class StressContext:
    """Optional stress estimate from EXISTING pipelines. All fields optional.

    Accepted score scales: 0-1 or 0-100 (auto-normalized). The bot never
    invents these values — when absent, the conversation simply relies on
    what the user says.
    """

    stress_score: Optional[float] = None  # normalized 0-1
    stress_level: Optional[str] = None  # Low | Moderate | High | Severe | Very High
    confidence: Optional[float] = None  # 0-1
    trend: Optional[str] = None  # increasing | decreasing | stable
    voice_indicators: Dict[str, Any] = field(default_factory=dict)
    webcam_indicators: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Optional[Dict[str, Any]]) -> "StressContext":
        if not payload:
            return cls()
        raw_score = payload.get("stress_score")
        score = None
        if raw_score is not None:
            try:
                score = float(raw_score)
                if score > 1.0:  # allow 0-100 scale
                    score = score / 100.0
                score = max(0.0, min(1.0, score))
            except (TypeError, ValueError):
                score = None
        level = payload.get("stress_level")
        level = str(level).strip().title() if isinstance(level, str) and level.strip() else None
        if level == "Very high":
            level = "Very High"
        if level not in ("Low", "Moderate", "High", "Severe", "Very High"):
            level = None
        conf = payload.get("confidence")
        try:
            conf = max(0.0, min(1.0, float(conf))) if conf is not None else None
        except (TypeError, ValueError):
            conf = None
        trend = payload.get("trend")
        trend = str(trend).strip().lower() if isinstance(trend, str) else None
        if trend not in ("increasing", "decreasing", "stable"):
            trend = None
        vi = payload.get("voice_indicators") or {}
        wi = payload.get("webcam_indicators") or {}
        return cls(
            stress_score=score,
            stress_level=level,
            confidence=conf,
            trend=trend,
            voice_indicators=dict(vi) if isinstance(vi, dict) else {},
            webcam_indicators=dict(wi) if isinstance(wi, dict) else {},
        )

    def band(self) -> str:
        """Coarse band used only to adapt tone — never stated as diagnosis."""
        if self.stress_level in ("Severe", "Very High", "High"):
            return "high"
        if self.stress_level == "Moderate":
            return "moderate"
        if self.stress_level == "Low":
            return "low"
        if self.stress_score is None:
            return "unknown"
        if self.stress_score >= 0.60:
            return "high"
        if self.stress_score >= 0.33:
            return "moderate"
        return "low"

    def is_uncertain(self) -> bool:
        return self.confidence is not None and self.confidence < 0.35


@dataclass
class ConversationSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    turns: List[Dict[str, Any]] = field(default_factory=list)
    # Remembered details within this conversation only.
    facts: Dict[str, Any] = field(default_factory=dict)
    wants_advice: Optional[bool] = None  # False when user says "just want to talk"
    tone: str = "gentle"  # gentle | calm | encouraging | practical
    recent_phrasings: List[str] = field(default_factory=list)
    asked_questions: List[str] = field(default_factory=list)
    lang_scores: List[float] = field(default_factory=list)
    trajectory_flagged: bool = False
    exercise: Dict[str, Any] = field(
        default_factory=lambda: {"status": "idle", "activity": None}
    )
    last_activity: Optional[str] = None
    last_stress: StressContext = field(default_factory=StressContext)
    user_name: Optional[str] = None

    def add_turn(self, role: str, text: str, **meta: Any) -> None:
        self.turns.append({"role": role, "text": text, "ts": time.time(), **meta})
        self.last_active = time.time()

    def user_turns(self) -> List[str]:
        return [t["text"] for t in self.turns if t.get("role") == "user"]

    def track_phrasing(self, key: str, keep: int = 6) -> None:
        self.recent_phrasings.append(key)
        del self.recent_phrasings[: max(0, len(self.recent_phrasings) - keep)]

    def used_recently(self, key: str) -> bool:
        return key in self.recent_phrasings

    def ask_question(self, question: str, keep: int = 4) -> None:
        """Remember a follow-up question so we don't repeat it next turn."""
        norm = " ".join(question.strip().lower().split())
        if norm:
            self.asked_questions.append(norm)
            del self.asked_questions[: max(0, len(self.asked_questions) - keep)]

    def asked_recently(self, question: str) -> bool:
        norm = " ".join(question.strip().lower().split())
        return norm in self.asked_questions

    def remember_fact(self, key: str, value: Any) -> None:
        if value:
            self.facts[str(key)] = value

    def to_history(self) -> List[Dict[str, Any]]:
        return [
            {"role": t.get("role", "user"), "text": t.get("text", "")}
            for t in self.turns
        ]


_sessions: Dict[str, ConversationSession] = {}

#: Idle sessions older than this are dropped (privacy: conversations are
#: in-memory only and never written to disk). Configurable via env.
SESSION_TTL_SECONDS = 30 * 60


def _ttl_seconds() -> float:
    import os

    try:
        return max(60.0, float(os.getenv("CONVERSATION_SESSION_TTL_MIN", "30")) * 60.0)
    except (TypeError, ValueError):
        return float(SESSION_TTL_SECONDS)


def prune_expired(max_age_s: Optional[float] = None) -> int:
    """Drop idle sessions. Returns the number removed. Never raises."""
    try:
        import time as _time

        limit = max_age_s if max_age_s is not None else _ttl_seconds()
        now = _time.time()
        expired = [sid for sid, s in _sessions.items() if now - s.last_active > limit]
        for sid in expired:
            _sessions.pop(sid, None)
        return len(expired)
    except Exception:
        return 0


def create_session(user_name: Optional[str] = None) -> ConversationSession:
    prune_expired()
    sess = ConversationSession(user_name=(user_name or "").strip() or None)
    _sessions[sess.session_id] = sess
    return sess


def fetch_session(session_id: str) -> Optional[ConversationSession]:
    import time as _time

    sess = _sessions.get(session_id)
    if sess is None:
        return None
    # Lazily expire on access (privacy: no lingering conversations).
    if _time.time() - sess.last_active > _ttl_seconds():
        _sessions.pop(session_id, None)
        return None
    return sess


def drop_session(session_id: str) -> bool:
    return _sessions.pop(session_id, None) is not None
