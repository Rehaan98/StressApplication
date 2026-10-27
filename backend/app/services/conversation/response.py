"""
Natural response generation for the conversation bot.

Two paths, same contract:
  1. Optional LLM (OpenAI-compatible, configured via env vars). Used when
     CONVERSATION_LLM_API_KEY is set; any failure falls back to (2).
  2. Offline compositional generator — deterministic, varied phrasing,
     context-aware, and fully testable without network or keys.

Both paths receive the same understanding (voice_language analysis),
conversation memory, and optional stress context. Stress detection and
response generation stay separate modules: stress context only adapts tone
and suggestions, never dictates the reply, and uncertain predictions are
treated as unknown.
"""

import hashlib
import re
from typing import Dict, Any, List, Optional

from backend.app.services.conversation.activities import (
    select_activity,
    detect_requested_activity,
    activity_payload,
)
from backend.app.services.conversation.context import (
    ConversationSession,
    StressContext,
)
from backend.app.services.conversation.safety import safety_check, safety_response


# ---------------------------------------------------------------------------
# Intent helpers (lightweight; deep understanding comes from voice_language)
# ---------------------------------------------------------------------------

_GREETING_RE = re.compile(r"^\s*(hi+|hey+|hello|yo|good\s?(morning|afternoon|evening)|howdy)\b", re.I)
_HOW_ARE_YOU_RE = re.compile(r"how are you", re.I)
_THANKS_RE = re.compile(r"\b(thank|thanks|thx|appreciated)\b", re.I)
_BYE_RE = re.compile(r"\b(bye|goodbye|good night|see you|gotta go|i have to go)\b", re.I)
_JUST_TALK_RE = re.compile(
    r"(just (want|wanna) (to )?talk|don'?t want advice|no advice|just listen|"
    r"someone to listen|need someone to listen|need .* to listen|just need to|"
    r"don'?t (try to )?fix|not looking for advice|i just need to (talk|vent)|"
    r"hear me out|let me vent|need to vent|listen to me)",
    re.I,
)
_MISUNDERSTOOD_RE = re.compile(
    r"(nobody understands|no one understands|misunderstood|tired of explaining|"
    r"explain(ing)? (myself|everything)|don'?t get me|doesn'?t understand me|"
    r"no one gets me|nobody gets me)",
    re.I,
)
_NO_START_RE = re.compile(
    r"(don'?t (even )?know where to start|dont know where|no idea where to (start|begin)|"
    r"don'?t know what to say|where do i (start|begin))",
    re.I,
)
_TONE_RE = re.compile(
    r"\bbe\s+(more\s+)?(practical|direct|straightforward|gentle|soft|calm|encouraging|"
    r"supportive|cheerful|positive)\b",
    re.I,
)
_TONE_WORDS = {
    "practical": "practical", "direct": "practical", "straightforward": "practical",
    "gentle": "gentle", "soft": "gentle",
    "calm": "calm",
    "encouraging": "encouraging", "supportive": "encouraging",
    "cheerful": "encouraging", "positive": "encouraging",
}
_EXERCISE_YES_RE = re.compile(
    r"^\s*(yes|yeah|yep|yup|ok|okay|sure|please|go ahead|let'?s (try|do) (it|that)|"
    r"sounds good|why not|alright|fine,? (let'?s|we can))\s*[.!]?\s*$",
    re.I,
)
_EXERCISE_NO_RE = re.compile(
    r"^\s*(no,?\s+)?(no|nope|not now|later|maybe later|no thanks|i'?d rather (just )?talk|"
    r"just (want to )?talk|let'?s (just )?talk|talk instead)\s*[.!]?\s*$",
    re.I,
)
_EXERCISE_STOP_RE = re.compile(r"\b(stop|pause|enough|too much|uncomfortable|don'?t like this)\b", re.I)
_WORSE_RE = re.compile(
    r"(worse|not helping|didn'?t help|doesn'?t help|still (bad|stressed|anxious|awful)|"
    r"no better|not better|same as before)",
    re.I,
)

#: Activities that involve spoken step-by-step guidance (need permission first).
GUIDABLE_ACTIVITIES = ("breathing", "grounding", "relaxation", "thought_organizing")
_BETTER_RE = re.compile(
    r"(feeling better|feel better|a (little|lot|bit) better|bit better|"
    r"slightly better|somewhat better|much better|"
    r"calmer now|more relaxed|that helped|i'?m (okay|ok|fine) now)",
    re.I,
)
_FINE_RE = re.compile(
    r"^\s*(i'?m\s+)?(fine|okay|ok|alright|good|not bad|so[-\s]?so)\s*[.!]?\s*$",
    re.I,
)
_CALM_DOWN_RE = re.compile(r"(calm( me)? down|help me (relax|calm)|breathing exercise|panic|freaking out)", re.I)
_OVERWHELM_RE = re.compile(r"(too many|too much|everything( piles| at once| all at once)|overwhelm|all at once|juggling .*things|swamped)", re.I)
_OVERTHINK_RE = re.compile(r"(overthink|can'?t stop thinking|racing thoughts|thoughts? (won'?t|wont) stop|my mind (won'?t|keeps))", re.I)
_LONELY_RE = re.compile(r"(lonel|alone|isolated|no one (cares|understands)|nobody (cares|understands))", re.I)
_EXHAUSTED_RE = re.compile(r"(exhausted|tired|drained|no energy|wiped out|burne?d out|weary|fatigue)", re.I)
_POSITIVE_RE = re.compile(r"\b(happy|great|good day|wonderful|excited|grateful|joy|awesome|fantastic|amazing)\b", re.I)
_STRESSED_RE = re.compile(r"(stress|overwhelm|too much|pressure|anxiet|worried|worry|tense|on my mind)", re.I)


def _pick(variants: List[str], salt: str) -> str:
    """Deterministic variant choice (stable across runs, varies by turn)."""
    digest = hashlib.md5(salt.encode()).hexdigest()
    return variants[int(digest, 16) % len(variants)]


def _question_of(reply: str) -> str:
    """Extract the trailing question (used for anti-repeat tracking)."""
    parts = [p.strip() for p in re.split(r"(?<=[.?!])\s+", reply.strip()) if p.strip()]
    for p in reversed(parts):
        if "?" in p:
            return p
    return ""


def _pick_fresh(variants: List[str], session: "ConversationSession", salt: str) -> str:
    """Pick a variant whose question wasn't asked in recent turns."""
    ordered = sorted(variants, key=lambda v: int(hashlib.md5((salt + v).encode()).hexdigest(), 16))
    for v in ordered:
        q = _question_of(v)
        if not q or not session.asked_recently(q):
            return v
    return ordered[0]


def _trajectory_prefix(
    session: "ConversationSession", current_score: float, tagset: set
) -> str:
    """One-time acknowledgment when distress clearly rises or eases."""
    if session.trajectory_flagged or len(session.lang_scores) < 2:
        return ""
    start = session.lang_scores[0]
    delta = current_score - start
    if delta > 0.15 and "distress" in tagset:
        session.trajectory_flagged = True
        return "Things seem to be getting heavier as we talk. "
    if delta < -0.15 and ("positive" in tagset or "negated" in tagset):
        session.trajectory_flagged = True
        return "Things seem to be easing a little. "
    return ""


def _tone_closer(session: "ConversationSession", default_question: str) -> str:
    """Adapt the follow-up question to the user's preferred tone."""
    if session.tone == "practical":
        return "What's the smallest first step you could take in the next ten minutes?"
    return default_question


_EXERCISE_ALTERNATIVES = {
    "breathing": "grounding",
    "grounding": "breathing",
    "relaxation": "breathing",
    "thought_organizing": "relaxation",
}


def _guide_now(session: "ConversationSession", activity_id: str) -> Dict[str, Any]:
    """Begin spoken step-by-step guidance (permission already granted)."""
    from backend.app.services.conversation.activities import ACTIVITIES

    session.exercise = {"status": "guiding", "activity": activity_id}
    payload = activity_payload(activity_id)
    steps = payload["activity_steps"]
    lead = " ".join(steps[:2])
    spec = ACTIVITIES.get(activity_id, {})
    reply = (
        f"Let's do it together — {spec.get('title', 'this exercise').lower()}. "
        f"{lead} Take your time with those. "
        "Tell me how it feels when you're ready — or say stop anytime."
    )
    return {
        "reply": reply,
        **payload,
        "suggested_action": f"Guide {activity_id} step by step; user can stop anytime.",
        "safety_notice": None,
        "is_safety": False,
    }


def _offer_exercise(session: "ConversationSession", activity_id: str, salt: str) -> Dict[str, Any]:
    """Ask permission before guiding (spec: never start uninvited)."""
    session.exercise = {"status": "offered", "activity": activity_id}
    payload = activity_payload(activity_id)
    question = _pick_fresh(
        [
            "Would you like to try something small with me for a minute, or would you rather talk about what's bothering you first?",
            "We could try a short calming exercise together, or keep talking — what sounds better to you?",
        ],
        session,
        salt,
    )
    return {
        "reply": question,
        **payload,
        "suggested_action": f"Ask permission before guiding {activity_id}.",
        "safety_notice": None,
        "is_safety": False,
    }


def _handle_exercise_turn(
    session: "ConversationSession",
    text: str,
    lowered: str,
    lang: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Continue an in-progress exercise flow. None = no active flow / new topic."""
    status = session.exercise.get("status", "idle")
    if status == "idle":
        return None
    activity_id = session.exercise.get("activity") or "breathing"
    tags = set(lang.get("tags", []) or [])
    has_fresh_signal = bool(tags & {"distress", "withdrawal", "help-seeking", "safety"})
    short = len(text.split()) <= 6

    if _EXERCISE_STOP_RE.search(lowered):
        session.exercise = {"status": "idle", "activity": None}
        return {
            "reply": "Of course — we stopped. There's no pressure to continue. Would you like to talk instead?",
            **activity_payload("supportive_conversation"),
            "suggested_action": "Exercise stopped on request; return to listening.",
            "safety_notice": None,
            "is_safety": False,
        }

    if status == "offered":
        if short and _EXERCISE_YES_RE.match(text):
            return _guide_now(session, activity_id)
        if short and _EXERCISE_NO_RE.match(text):
            session.exercise = {"status": "idle", "activity": None}
            session.wants_advice = False
            return {
                "reply": "That's completely fine. I'm here to listen — tell me whatever feels right.",
                **activity_payload("supportive_conversation"),
                "suggested_action": "Offer declined; listen without pushing.",
                "safety_notice": None,
                "is_safety": False,
            }
        # Substantive new message → user moved on; drop the pending offer.
        if len(text.split()) > 6 or has_fresh_signal:
            session.exercise = {"status": "idle", "activity": None}
            return None
        return {
            "reply": "No rush at all. Would you like to try it, or shall we keep talking?",
            **activity_payload(session.exercise.get("activity") or "supportive_conversation"),
            "suggested_action": "Re-ask once, gently.",
            "safety_notice": None,
            "is_safety": False,
        }

    if status == "guiding":
        if _BETTER_RE.search(lowered) or ("positive" in tags and "distress" not in tags):
            session.exercise = {"status": "idle", "activity": None}
            return {
                "reply": "I'm really glad that helped, even a little. You can come back to it anytime. What would feel good next?",
                **activity_payload("positive_reflection"),
                "suggested_action": "Celebrate the small win; close the exercise.",
                "safety_notice": None,
                "is_safety": False,
            }
        if _WORSE_RE.search(lowered):
            alt = _EXERCISE_ALTERNATIVES.get(activity_id, "grounding")
            session.exercise = {"status": "offered", "activity": alt}
            payload = activity_payload(alt)
            return {
                "reply": (
                    "That one's not for everyone, and that's completely okay. "
                    f"Would you like to try {payload['activity_title'].lower()} instead, "
                    "or would you rather just talk?"
                ),
                **payload,
                "suggested_action": f"Offer alternative {alt} after poor feedback.",
                "safety_notice": None,
                "is_safety": False,
            }
        if has_fresh_signal and len(text.split()) > 4:
            session.exercise = {"status": "idle", "activity": None}
            return None  # new concern takes priority
        session.exercise = {"status": "idle", "activity": None}
        return {
            "reply": "Thanks for trying that with me. How are you feeling now — has anything shifted, even a little?",
            **activity_payload(activity_id),
            "suggested_action": "Check in after the exercise; adapt to feedback.",
            "safety_notice": None,
            "is_safety": False,
        }

    session.exercise = {"status": "idle", "activity": None}
    return None


def _short_ack_detail(key_phrases: List[str]) -> str:
    """Turn analyzer key phrases into a brief, natural acknowledgment fragment."""
    cleaned = []
    for p in (key_phrases or [])[:2]:
        p = str(p).strip().lower()
        if not p or p in ("fine", "okay", "good"):
            continue
        # "i'm exhausted" → "feeling exhausted" reads naturally in acknowledgments.
        for prefix in ("i'm ", "i am ", "im ", "feel ", "feeling "):
            if p.startswith(prefix):
                core = p[len(prefix):].strip()
                if core:
                    p = f"feeling {core}"
                break
        cleaned.append(p)
    if not cleaned:
        return ""
    # Single-word distress nouns read badly after "dealing with"
    # ("dealing with stressed") — use "feeling <word>" instead.
    SinglesAsFeeling = {
        "stressed", "sad", "lonely", "alone", "tired", "exhausted",
        "anxious", "overwhelmed", "unhappy", "worried", "empty", "drained",
    }
    pretty = []
    for p in cleaned:
        if p in SinglesAsFeeling:
            pretty.append(f"feeling {p}")
        else:
            pretty.append(p)
    if len(pretty) == 1:
        single = cleaned[0]
        if single in SinglesAsFeeling:
            return f"feeling {single}"
        return f"dealing with {pretty[0]}"
    return f"dealing with {pretty[0]} and {pretty[1]}"


# ---------------------------------------------------------------------------
# Offline compositional generator
# ---------------------------------------------------------------------------

def _tone_prefix(band: str, trend: Optional[str]) -> str:
    if band == "high":
        return "Let's take this slowly. "
    if trend == "increasing":
        return "Let's slow down a little. "
    return ""


def generate_local(
    session: ConversationSession,
    user_text: str,
    lang: Dict[str, Any],
    stress: StressContext,
) -> Dict[str, Any]:
    text = (user_text or "").strip()
    lowered = text.lower()
    tags: List[str] = list(lang.get("tags", []) or [])
    tagset = set(tags)
    subject = str(lang.get("subject", "self"))
    tense = next((t.split(":")[1] for t in tags if t.startswith("tense:")), "present")
    key_phrases: List[str] = list(lang.get("key_phrases", []) or [])
    turn_idx = len(session.user_turns())
    salt = f"{session.session_id}:{turn_idx}:{text[:40]}"
    band = stress.band()
    uncertain = stress.is_uncertain()
    _has_signal = bool(tagset & {"distress", "withdrawal", "help-seeking"})

    # Emotion trajectory across turns (rising distress / easing), flagged once.
    _trajectory_note = _trajectory_prefix(session, float(lang.get("language_score", 0.5)), tagset)

    # --- 0. Empty input ----------------------------------------------------
    if not text:
        return {
            "reply": "I didn't quite catch that. Could you say it again in your own words?",
            **activity_payload("supportive_conversation"),
            "suggested_action": "Invite the user to repeat or type their message.",
            "safety_notice": None,
            "is_safety": False,
        }

    # --- 0b. In-progress exercise flow takes priority -------------------------
    _ex_turn = _handle_exercise_turn(session, text, lowered, lang)
    if _ex_turn is not None:
        return _ex_turn

    # --- 1. Thanks / goodbye (warm, brief) ----------------------------------
    if _THANKS_RE.search(lowered) and "distress" not in tagset:
        reply = _pick(
            [
                "You're welcome. I'm glad that helped a little. I'm here if you need me.",
                "Of course. You did the hard part by talking about it. I'm here anytime.",
            ],
            salt,
        )
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Warm close; no exercise pushed.",
                "safety_notice": None, "is_safety": False}

    if _BYE_RE.search(lowered):
        reply = _pick(
            [
                "Take care. Be gentle with yourself today. I'm here whenever you want to talk.",
                "Goodbye for now. I hope the rest of your day feels a little lighter.",
            ],
            salt,
        )
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Close the session warmly.",
                "safety_notice": None, "is_safety": False}

    # --- 1b. Tone preference ("be more practical / gentle / calm") --------------
    _tone_match = _TONE_RE.search(text)
    if _tone_match and "distress" not in tagset and "safety" not in tagset:
        _tone_word = _tone_match.group(2).lower()
        session.tone = _TONE_WORDS.get(_tone_word, "gentle")
        session.remember_fact("tone_ack_done", False)
        reply = _pick_fresh(
            [
                f"Got it — I'll keep things {session.tone} from here. What's on your mind?",
                f"Thanks for telling me. I'll be more {session.tone} with you. What would you like to talk about?",
            ],
            session,
            salt,
        )
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": f"Tone set to {session.tone}.",
                "safety_notice": None, "is_safety": False}

    # --- 2. Greeting ("Hi, how are you?") -----------------------------------
    if _GREETING_RE.search(lowered) and "distress" not in tagset and not _HOW_ARE_YOU_RE.search(lowered):
        name = f" {session.user_name}" if session.user_name else ""
        reply = _pick(
            [
                f"Hey{name}! I'm here with you. How are you feeling today?",
                f"Hi{name}! Good to see you. How are you doing right now?",
                f"Hello{name}! I'm here to listen. What's on your mind today?",
            ],
            salt,
        )
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Greet warmly and ask how the user feels.",
                "safety_notice": None, "is_safety": False}

    if _HOW_ARE_YOU_RE.search(lowered) and len(lowered.split()) <= 8 and "distress" not in tagset:
        reply = _pick(
            [
                "Thanks for asking. I'm here and ready to listen. More importantly — how are you feeling today?",
                "I'm doing well, thank you. I'm an AI companion, so I don't have feelings of my own. How are you doing?",
            ],
            salt,
        )
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Answer briefly without pretending to be human; return focus to the user.",
                "safety_notice": None, "is_safety": False}

    # --- 3. Someone else's pain ("My friend feels lonely") -------------------
    # Note: the analyzer still tags distress words for other-subject sentences
    # (score is dampened), so subject must win over the distress tag here —
    # unless the sentence is ALSO strongly about the user (mixed) or unsafe.
    if subject == "other" and "safety" not in tagset:
        reply = (
            "It sounds like your friend is going through a hard time, and it says a lot "
            "that you care about them. "
            "How does it feel for you, supporting them through this?"
        )
        session.remember_fact("other_person", text[:120])
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Support the user as a caring friend; don't assume they are distressed.",
                "safety_notice": None, "is_safety": False}
    if subject == "mixed" and "safety" not in tagset and not _STRESSED_RE.search(lowered):
        reply = (
            "It makes sense you feel for them — caring about someone who's hurting can weigh on you too. "
            "How are you holding up with all of this?"
        )
        session.remember_fact("other_person", text[:120])
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Acknowledge both the friend's pain and the user's load.",
                "safety_notice": None, "is_safety": False}

    # Remember topic details for later turns — only on genuine self-subject
    # distress signals, never from single generic words ("tired", "pain") or
    # someone else's story. This keeps memory specific instead of bogus.
    if subject == "self" and _has_signal:
        for topic, keys in (
            ("work", ("workload", "deadline", "overtime", "my boss", "my job", "meeting")),
            ("study", ("exam", "studying", "assignment", "my class", "school pressure")),
            ("sleep", ("insomnia", "can't sleep", "cannot sleep", "sleepless", "awake all night")),
            ("loneliness", ("i feel lonely", "feel alone", "feeling alone", "isolated", "left out")),
        ):
            if any(k in lowered for k in keys):
                session.remember_fact("topic", topic)
                session.remember_fact("topic_text", text[:120])
                break

    # --- 3b. Explicit exercise request → guide directly (request = permission)
    _explicit = detect_requested_activity(text)
    if _explicit in GUIDABLE_ACTIVITIES and "safety" not in tagset:
        session.wants_advice = True
        return _guide_now(session, _explicit)

    # --- 3c. Feeling misunderstood -------------------------------------------
    if _MISUNDERSTOOD_RE.search(lowered) and "safety" not in tagset:
        reply = (
            _trajectory_note
            + "That sounds exhausting. When you've tried to explain yourself and still "
            "feel misunderstood, it can be hard to keep trying. "
            "You don't have to explain everything perfectly here. "
            + _tone_closer(session, "What's been weighing on you the most?")
        )
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Validate being misunderstood; lower the bar for sharing.",
                "safety_notice": None, "is_safety": False}

    # --- 3d. "Don't know where to start" → offer three small doors -------------
    if _NO_START_RE.search(lowered) and "safety" not in tagset:
        reply = (
            "That's okay. We don't have to solve everything at once. Let's start small. "
            "Is it more about something that happened with someone, pressure from studies "
            "or work, or just a heavy feeling you can't quite explain?"
        )
        return {"reply": reply, **activity_payload("thought_organizing"),
                "suggested_action": "Offer three gentle starting points; let the user pick one.",
                "safety_notice": None, "is_safety": False}

    # --- 4. "Feeling better now" — acknowledge progress ------------------------
    # Checked before the general negated/past/positive block so recovery always
    # gets its dedicated reply (never a coin-flip between two branches).
    if _BETTER_RE.search(lowered) and "safety" not in tagset:
        reply = _pick(
            [
                "I'm glad to hear that, even a little better counts. What helped most just now?",
                "That's a good sign. I'm glad things feel lighter. What do you think made the difference?",
            ],
            salt,
        )
        return {"reply": reply, **activity_payload("positive_reflection"),
                "suggested_action": "Acknowledge progress without assuming everything is resolved.",
                "safety_notice": None, "is_safety": False}

    # --- 5. Negated / past / positive — do NOT treat as distress -------------
    # The analyzer marks `severe` only for present-tense, self-subject distress,
    # so it cleanly separates "I was stressed yesterday" from "I am stressed".
    _severe_now = bool(lang.get("severe", False))
    _negated_now = "negated" in tagset and "distress" not in tagset
    _past_now = "tense:past" in tagset and not _severe_now
    _positive_now = (
        ("positive" in tagset or bool(_POSITIVE_RE.search(lowered)))
        and "distress" not in tagset
    )
    if not _severe_now and "safety" not in tagset and (_negated_now or _past_now or _positive_now):
        if _negated_now:
            reply = _pick(
                [
                    "Glad to hear that. What's today been like for you?",
                    "That's good to know. How are things feeling today?",
                ],
                salt,
            )
        elif _positive_now:
            reply = _pick(
                [
                    "That's good to hear. Bad days pass, and it matters that today feels better. What's been helping?",
                    "I'm glad today feels lighter. What made the difference for you?",
                ],
                salt,
            )
        else:
            reply = _pick(
                [
                    "Thanks for telling me. It makes sense that was hard then. How are things feeling for you today?",
                    "I hear you — that was then, and today sounds steadier. What's today been like?",
                ],
                salt,
            )
        return {"reply": reply, **activity_payload("positive_reflection" if _positive_now else "supportive_conversation"),
                "suggested_action": "Acknowledge the change over time; no stress exercise pushed.",
                "safety_notice": None, "is_safety": False}

    # --- 6. "I'm fine" — no pressure -----------------------------------------
    if _FINE_RE.match(text) or ("masking" in tagset and not key_phrases):
        if band == "high" and not uncertain and stress.confidence and stress.confidence >= 0.5:
            reply = (
                "Okay, no pressure. We can talk about something else, or just take a quiet moment. "
                "I notice some signs of tension, but you know yourself best — what would feel best for you?"
            )
        else:
            reply = _pick(
                [
                    "Okay, no pressure. We can talk about something else, or we can just take a quiet moment. What would feel best for you?",
                    "Got it — no pressure at all. Is there something else on your mind, or shall we just sit with a calm moment?",
                ],
                salt,
            )
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Respect 'fine'; offer choice, don't interrogate.",
                "safety_notice": None, "is_safety": False}

    # --- 7. "Just want to talk" — listen, don't fix ----------------------------
    if _JUST_TALK_RE.search(lowered):
        session.wants_advice = False
        reply = _pick(
            [
                "Of course. I'm here to listen, no advice unless you want it. What's on your mind?",
                "Absolutely. I'm here to listen — you don't need to fix anything right now. Tell me whatever feels right.",
            ],
            salt,
        )
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Listen only; withhold suggestions until asked.",
                "safety_notice": None, "is_safety": False}

    # --- 8. Immediate calming request ------------------------------------------
    if _CALM_DOWN_RE.search(lowered) or detect_requested_activity(text) == "breathing":
        prefix = "Of course. "
        body = (
            "Let's take this slowly. If you're comfortable, breathe in gently for about "
            "four seconds, then breathe out slowly for about six seconds. "
            "There's no need to force your breathing. Let's try a few comfortable breaths together. "
            "You can stop anytime."
        )
        payload = activity_payload("breathing")
        reply = prefix + body
        return {"reply": reply, **payload,
                "suggested_action": "Guide gentle breathing; offer to stop anytime.",
                "safety_notice": None, "is_safety": False}

    # --- 9. Overthinking ---------------------------------------------------------
    if _OVERTHINK_RE.search(lowered):
        reply = (
            _tone_prefix(band, stress.trend)
            + "That can be exhausting. Let's try making things a little simpler. "
            "Is there one thought that's bothering you the most right now?"
        )
        return {"reply": reply, **activity_payload("thought_organizing"),
                "suggested_action": "Help isolate the single heaviest thought; separate what can wait.",
                "safety_notice": None, "is_safety": False}

    # --- 10. Loneliness / sadness --------------------------------------------------
    if _LONELY_RE.search(lowered):
        detail = _short_ack_detail(key_phrases)
        # Avoid echoing loneliness back redundantly ("feeling alone ... feeling lonely").
        if "lonel" in detail or "alone" in detail:
            detail = ""
        ack = f"Feeling alone can be really difficult{(' — ' + detail) if detail else ''}. "
        follow = _pick_fresh(
            [
                "Did something happen today that made you feel this way, or has it been building up for a while?",
                "Do you want to tell me what today has been like?",
            ],
            session,
            salt,
        )
        reply = (
            _trajectory_note
            + "I'm sorry you're feeling this way. " + ack
            + "I'm here to listen. " + follow
        )
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Listen; ask one gentle question about today vs building up.",
                "safety_notice": None, "is_safety": False}

    # --- 11. Exhaustion --------------------------------------------------------------
    if _EXHAUSTED_RE.search(lowered):
        detail = _short_ack_detail(key_phrases)
        # The acknowledgment already names exhaustion — don't echo it twice.
        if any(w in detail for w in ("exhaust", "tired", "drained", "weary", "energy")):
            detail = ""
        ack = f"It sounds like you've been carrying a lot lately{(' — ' + detail) if detail else ''}. "
        reply = (
            ack + "You don't have to explain everything at once. "
            "What's been taking the most energy out of you recently?"
        )
        return {"reply": reply, **activity_payload("relaxation"),
                "suggested_action": "Acknowledge depletion; suggest short break, water, shoulder release when fitting.",
                "safety_notice": None, "is_safety": False}

    # --- 12. Stressed / overwhelmed ----------------------------------------------------
    if _OVERWHELM_RE.search(lowered):
        reply = (
            "That sounds overwhelming. When everything piles up, it can be hard to know where to start. "
            "Would it help if we picked one small thing to focus on first?"
        )
        return {"reply": reply, **activity_payload("thought_organizing"),
                "suggested_action": "Break the pile into one small first step.",
                "safety_notice": None, "is_safety": False}

    if _STRESSED_RE.search(lowered) or "distress" in tagset or "help-seeking" in tagset:
        detail = _short_ack_detail(key_phrases)
        if detail.startswith("feeling "):
            ack = f"I hear you're {detail} right now. "
        elif detail:
            ack = f"I'm sorry things feel stressful right now — {detail}. "
        else:
            ack = "I'm sorry things feel stressful right now. "
        if band == "high":
            # One question, two doors: permission-style offer, never uninvited guiding.
            session.exercise = {"status": "offered", "activity": "grounding"}
            payload = activity_payload("grounding")
            reply = (
                _tone_prefix(band, stress.trend) + ack
                + "Would a short calming exercise help, or would you rather tell me what's on your mind first?"
            )
            return {"reply": reply, **payload,
                    "suggested_action": "High band: slow down + permission-style offer.",
                    "safety_notice": None, "is_safety": False}
        reply = _trajectory_note + ack + "Would you like to tell me what's been on your mind?"
        act = "supportive_conversation"
        # If user explicitly asked what to do, lean practical.
        if "help-seeking" in tagset and act == "supportive_conversation":
            act = "thought_organizing"
        return {"reply": reply, **activity_payload(act),
                "suggested_action": "Acknowledge, ask one follow-up; offer a small next step.",
                "safety_notice": None, "is_safety": False}

    # --- 13. Withdrawal ("leave me alone", "whatever") -------------------------------
    if "withdrawal" in tagset:
        reply = (
            "That's okay. There's no pressure here. "
            "We can pause, change topics, or just sit quietly for a moment. What feels best?"
        )
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Give space; offer pause or topic change.",
                "safety_notice": None, "is_safety": False}

    # --- 14. Follow-up on earlier topic --------------------------------------------------
    # Only when the current message has no strong signal of its own — never let
    # memory hijack a message about something new (stress, overwhelm, ...).
    _fresh_signal = bool(
        _OVERWHELM_RE.search(lowered)
        or _OVERTHINK_RE.search(lowered)
        or _LONELY_RE.search(lowered)
        or _EXHAUSTED_RE.search(lowered)
        or _CALM_DOWN_RE.search(lowered)
        or _STRESSED_RE.search(lowered)
        or "distress" in tagset
        or "help-seeking" in tagset
        or "withdrawal" in tagset
    )
    if session.facts.get("topic") and turn_idx >= 1 and not _fresh_signal:
        topic = session.facts.get("topic")
        reply = _pick_fresh(
            [
                f"Thanks for sharing that. Earlier you mentioned {topic} — is that still the heaviest part, or is it something else now?",
                f"I hear you. How does this connect with the {topic} situation you mentioned?",
            ],
            session,
            salt,
        )
        return {"reply": reply, **activity_payload("supportive_conversation"),
                "suggested_action": "Connect to remembered context with one gentle question.",
                "safety_notice": None, "is_safety": False}

    # --- 15. Default: acknowledge specifics, one gentle question --------------------------
    detail = _short_ack_detail(key_phrases)
    if detail:
        reply = (
            f"Thank you for telling me — {detail} sounds really hard. "
            "I'm here with you. " + _tone_closer(session, "Would you like to say a little more about it?")
        )
    else:
        reply = _pick_fresh(
            [
                "Thanks for sharing that with me. I'm here to listen. What's been weighing on you most?",
                "I hear you. Take your time — what feels hardest about this right now?",
                "That matters, and I'm glad you said it. What would feel most helpful — talking more, or trying something calming?",
            ],
            session,
            salt,
        )
    return {"reply": reply, **activity_payload("supportive_conversation"),
            "suggested_action": "Acknowledge and ask one open, gentle question.",
            "safety_notice": None, "is_safety": False}


# ---------------------------------------------------------------------------
# Optional LLM path (OpenAI-compatible). Best effort; never required.
# ---------------------------------------------------------------------------

_LLM_SYSTEM = """You are a calm, friendly stress-relief conversation companion inside a wellbeing app.
Rules you MUST follow:
- Use simple everyday English, short sentences, one gentle question at a time.
- Be warm, respectful, non-judgmental. Acknowledge the user's specific words.
- Sometimes just listen; do not give advice every turn, especially if the user only wants to talk.
- Never claim to be human, never claim feelings or experiences of your own.
- Never diagnose or treat any mental-health condition; never say "everything is fine" to someone struggling.
- Never pressure the user to share personal details. Respect stop / topic-change / declined suggestions.
- Understand negation, tense and subject: "I'm not stressed" is not stress; "my friend is lonely" is about someone else; past memories are not current crises; "I'm happy" needs no exercise.
- Stress-detection context (if given) only adapts tone; uncertain predictions must not drive the reply. Always trust what the user says over the numbers.
- For possible self-harm or suicidal intent: respond calmly, acknowledge distress, ask directly about immediate safety, encourage a trusted person / professional / local emergency or crisis line.
- Keep replies under 70 words. No bullet lists unless guiding an exercise. No medical jargon."""


async def generate_with_llm(
    *,
    history: List[Dict[str, str]],
    user_text: str,
    lang_summary: str,
    stress_summary: str,
    memory_summary: str,
) -> Optional[str]:
    """Call an OpenAI-compatible chat API if configured. Returns None on any issue."""
    import os

    api_key = os.getenv("CONVERSATION_LLM_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = os.getenv("CONVERSATION_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("CONVERSATION_LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

    messages: List[Dict[str, str]] = [{"role": "system", "content": _LLM_SYSTEM}]
    if memory_summary:
        messages.append({"role": "system", "content": f"Conversation memory: {memory_summary}"})
    if lang_summary:
        messages.append({"role": "system", "content": f"Language understanding: {lang_summary}"})
    if stress_summary:
        messages.append({"role": "system", "content": f"Stress context (adapt tone only): {stress_summary}"})
    for turn in history[-10:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        content = str(turn.get("text", ""))[:800]
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text[:1500]})

    try:
        import httpx

        timeout_s = float(os.getenv("CONVERSATION_LLM_TIMEOUT_S", "20"))
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 220},
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        content = str(content or "").strip()
        if len(content) < 5:
            return None
        # Keep spoken replies short (TTS-friendly): hard cap with graceful cut.
        if len(content) > 600:
            cut = content[:600]
            last_stop = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
            content = cut[: last_stop + 1] if last_stop > 200 else cut.rstrip() + "…"
        return content
    except Exception:
        return None


def _lang_summary(lang: Dict[str, Any]) -> str:
    parts = [
        f"score={lang.get('language_score')}",
        f"tags={','.join(lang.get('tags', []))}",
        f"subject={lang.get('subject', 'self')}",
    ]
    if lang.get("key_phrases"):
        parts.append(f"phrases={'; '.join(lang['key_phrases'][:4])}")
    return "; ".join(parts)


def _stress_summary(stress: StressContext) -> str:
    if stress.stress_score is None and not stress.stress_level:
        return "no stress detection available — rely on the user's words"
    return (
        f"band={stress.band()}, level={stress.stress_level}, "
        f"score={stress.stress_score}, confidence={stress.confidence}, "
        f"trend={stress.trend}, uncertain={stress.is_uncertain()}"
    )


def _memory_summary(session: ConversationSession) -> str:
    bits = []
    if session.user_name:
        bits.append(f"user name: {session.user_name}")
    if session.facts:
        bits.append("remembered: " + ", ".join(f"{k}={v}" for k, v in session.facts.items()))
    if session.wants_advice is False:
        bits.append("user prefers listening over advice")
    if session.last_activity:
        bits.append(f"last activity offered: {session.last_activity}")
    return "; ".join(bits)


# ---------------------------------------------------------------------------
# Main entry: understand → (safety) → adapt → respond
# ---------------------------------------------------------------------------

async def craft_reply(
    session: ConversationSession,
    user_text: str,
    stress: StressContext,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Full pipeline for one user message. Never raises for user-facing errors."""
    from backend.app.services.voice_language import analyze_language

    text = (user_text or "").strip()
    if not text:
        local = generate_local(session, "", {"tags": ["empty"], "key_phrases": []}, stress)
        return _finalize(session, "", local, lang={}, stress=stress)

    lang = analyze_language(text)

    # Safety first — bypasses everything else.
    if bool(lang.get("safety")) or safety_check(text)["safety"]:
        safe = safety_response(text)
        session.add_turn("user", text, tags=lang.get("tags", []))
        session.add_turn("assistant", safe["reply"], safety=True)
        session.last_activity = safe["activity"]
        session.last_stress = stress
        return {
            "reply": safe["reply"],
            "activity": safe["activity"],
            "activity_title": "Support and safety",
            "activity_summary": "Calm support and real-world help options.",
            "activity_steps": safe["activity_steps"],
            "activity_check_in": "Are you safe right now? Would it help to contact someone you trust?",
            "activity_alternative": "We can also just stay here together quietly for a moment.",
            "suggested_action": safe["suggested_action"],
            "safety_notice": safe["safety_notice"],
            "is_safety": True,
            "language_understanding": _public_understanding(lang),
            "stress_adaptation": _public_adaptation(stress),
            "interventions": [],
        }

    # Respect "just wants to talk" across turns.
    if session.wants_advice is False and not detect_requested_activity(text) and not _CALM_DOWN_RE.search(text.lower()):
        local = generate_local(session, text, lang, stress)
        # Force listening mode unless user now asks for help.
        if local["activity"] != "supportive_conversation" and "help-seeking" not in (lang.get("tags", []) or []):
            from backend.app.services.conversation.activities import activity_payload as _ap

            keep_reply = local["reply"]
            local = _ap("supportive_conversation")
            local["reply"] = keep_reply
        return _finalize(session, text, local, lang=lang, stress=stress)

    # Try LLM for natural variation; fall back to local generator.
    if use_llm:
        llm_text = await generate_with_llm(
            history=session.to_history(),
            user_text=text,
            lang_summary=_lang_summary(lang),
            stress_summary=_stress_summary(stress),
            memory_summary=_memory_summary(session),
        )
        if llm_text:
            explicit = detect_requested_activity(text)
            activity_id = select_activity(
                user_text=text,
                tags=list(lang.get("tags", []) or []),
                stress_band=stress.band(),
                wants_advice=session.wants_advice,
                offered_recently=session.recent_phrasings,
                explicit_request=explicit,
            )
            # Safety net: LLM must not push exercises for positive/negated/other-person turns.
            tags = set(lang.get("tags", []) or [])
            if lang.get("subject") in ("other", "mixed") and "distress" not in tags:
                activity_id = "supportive_conversation"
            if ("negated" in tags or _POSITIVE_RE.search(text.lower())) and "distress" not in tags:
                if activity_id not in ("supportive_conversation", "positive_reflection"):
                    activity_id = "positive_reflection"
            payload = activity_payload(activity_id)
            result = {"reply": llm_text, **payload,
                      "suggested_action": "Natural LLM reply with adapted activity.",
                      "safety_notice": None, "is_safety": False}
            _maybe_update_preference(session, text)
            return _finalize(session, text, result, lang=lang, stress=stress)

    local = generate_local(session, text, lang, stress)
    _maybe_update_preference(session, text)
    return _finalize(session, text, local, lang=lang, stress=stress)


def _maybe_update_preference(session: ConversationSession, text: str) -> None:
    if _JUST_TALK_RE.search(text.lower()):
        session.wants_advice = False
    elif _CALM_DOWN_RE.search(text.lower()) or detect_requested_activity(text):
        session.wants_advice = True


def _public_understanding(lang: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tags": list(lang.get("tags", []) or [])[:8],
        "subject": str(lang.get("subject", "self")),
        "key_phrases": list(lang.get("key_phrases", []) or [])[:4],
        "masking": bool(lang.get("masking", False)),
    }


def _public_adaptation(stress: StressContext) -> Dict[str, Any]:
    return {
        "band": stress.band(),
        "trend": stress.trend,
        "uncertain": stress.is_uncertain(),
        "has_detection": bool(stress.stress_score is not None or stress.stress_level),
    }


def _finalize(
    session: ConversationSession,
    user_text: str,
    result: Dict[str, Any],
    lang: Dict[str, Any],
    stress: StressContext,
) -> Dict[str, Any]:
    if user_text:
        session.add_turn("user", user_text, tags=(lang.get("tags", []) if lang else []))
    reply_text = str(result.get("reply", ""))
    session.add_turn("assistant", reply_text, activity=result.get("activity"))
    session.track_phrasing(str(result.get("activity", "")))
    # Anti-repeat + trajectory memory.
    _q = _question_of(reply_text)
    if _q:
        session.ask_question(_q)
    try:
        _ls = float((lang.get("language_score", 0.5) if lang else 0.5))
        session.lang_scores.append(max(0.0, min(1.0, _ls)))
        del session.lang_scores[: max(0, len(session.lang_scores) - 10)]
    except (TypeError, ValueError):
        pass
    session.last_activity = result.get("activity")
    session.last_stress = stress

    interventions: list = []
    try:
        from backend.app.services.voice_service import _retrieve_voice_interventions

        level = {"high": "High", "moderate": "Moderate", "low": "Low"}.get(stress.band(), "Moderate")
        interventions = _retrieve_voice_interventions(level, user_text, "", {}, top_k=2) or []
    except Exception:
        interventions = []

    return {
        "reply": reply_text,
        "activity": result.get("activity", "supportive_conversation"),
        "activity_title": result.get("activity_title", ""),
        "activity_summary": result.get("activity_summary", ""),
        "activity_steps": result.get("activity_steps", []),
        "activity_check_in": result.get("activity_check_in", ""),
        "activity_alternative": result.get("activity_alternative", ""),
        "suggested_action": result.get("suggested_action", ""),
        "safety_notice": result.get("safety_notice"),
        "is_safety": bool(result.get("is_safety", False)),
        "language_understanding": _public_understanding(lang) if lang else {},
        "stress_adaptation": _public_adaptation(stress),
        "interventions": interventions,
    }
