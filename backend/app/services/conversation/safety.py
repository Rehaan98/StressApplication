"""
Safety handling for the conversation bot.

Uses the existing contextual language analyzer (voice_language) for detection
so safety signals stay consistent with the voice/live pipelines. Responds
calmly, acknowledges distress, asks a direct compassionate safety question
when appropriate, and encourages real-world support. Never diagnoses.
"""

from typing import Dict, Any, Optional

CRISIS_GUIDANCE = (
    "If you feel you might act on these thoughts, please reach out right away — "
    "to someone you trust, a mental-health professional, or your local emergency "
    "number or crisis helpline. You don't have to go through this alone."
)

SAFETY_NOTICE = (
    "If you feel unsafe, please contact someone you trust, a mental-health "
    "professional, or your local emergency services / crisis helpline immediately."
)


def safety_check(transcript: str) -> Dict[str, Any]:
    """Return safety analysis for a user message. Never raises."""
    try:
        from backend.app.services.voice_language import analyze_language

        lang = analyze_language(transcript or "")
        safety = bool(lang.get("safety"))
        phrases = list(lang.get("safety_phrases", []) or [])
        return {"safety": safety, "safety_phrases": phrases}
    except Exception:
        # Fail closed-but-gentle: no crash, no false alarm.
        return {"safety": False, "safety_phrases": []}


def safety_response(transcript: str) -> Dict[str, Any]:
    """Calm, supportive response for possible immediate danger / self-harm."""
    _ = transcript  # acknowledged implicitly; details never repeated back
    reply = (
        "Thank you for trusting me with that. I'm really glad you told me. "
        "It sounds like things feel unbearable right now. "
        "Are you safe at this moment? "
        + CRISIS_GUIDANCE
    )
    return {
        "reply": reply,
        "activity": "supportive_conversation",
        "activity_steps": [
            "Pause with me for a moment — there's no rush here.",
            "If someone you trust is nearby, consider letting them know how you feel.",
            "If you feel you might act on these thoughts, contact a trusted person, "
            "a professional, or your local emergency / crisis line now.",
        ],
        "suggested_action": "Consider contacting someone you trust or local support now.",
        "safety_notice": SAFETY_NOTICE,
        "is_safety": True,
    }
