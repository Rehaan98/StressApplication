"""
Stress-relief activity guidance (spec section 4, activities A–G).

Each activity has gentle step-by-step guidance. Selection adapts to the
user's situation (language tags, stress band, explicit request, stated
preference) instead of giving everyone the same suggestion. Nothing here
promises a technique will work — alternatives are always offered.
"""

from typing import Dict, Any, List, Optional

ACTIVITY_IDS = (
    "breathing",
    "grounding",
    "thought_organizing",
    "relaxation",
    "positive_reflection",
    "healthy_routine",
    "supportive_conversation",
)

ACTIVITIES: Dict[str, Dict[str, Any]] = {
    "breathing": {
        "title": "Gentle breathing together",
        "summary": "Slow, comfortable breaths at your own pace. Stop anytime.",
        "steps": [
            "Get comfortable — feet flat, shoulders down if that feels okay.",
            "Breathe in gently through your nose for about 4 seconds. No need to force it.",
            "Breathe out slowly through your mouth for about 6 seconds.",
            "Try a few comfortable breaths together. Pause or stop whenever you like.",
            "Notice how your shoulders or chest feel now, without judging it.",
        ],
        "check_in": "How are you feeling now? Has anything changed, even a little?",
        "alternative": "If deep breathing feels uncomfortable, just breathe normally and notice the air moving in and out.",
    },
    "grounding": {
        "title": "5-4-3-2-1 grounding",
        "summary": "Notice the present moment through your senses, one step at a time.",
        "steps": [
            "Name 5 things you can see around you right now.",
            "Notice 4 things you can feel — your feet on the floor, your hands, your clothes.",
            "Listen for 3 things you can hear, near or far.",
            "Notice 2 things you can smell, if any.",
            "Notice 1 thing you can taste, or a sip of water if you have some.",
            "Take one easy breath. There is no rush.",
        ],
        "check_in": "Did that bring you a little more into the present? We can pause here.",
        "alternative": "If any step feels uncomfortable, skip it — even one or two senses is enough.",
    },
    "thought_organizing": {
        "title": "Sorting what's on your mind",
        "summary": "Pick one small thing to focus on first.",
        "steps": [
            "Tell me everything swirling around — just a rough list is fine.",
            "Let's pick the one thing that feels heaviest or most urgent.",
            "What is the smallest first step for that one thing? Something under 5 minutes.",
            "The rest can wait on the list. They are not forgotten, just parked.",
        ],
        "check_in": "Does that one small step feel doable? We can make it even smaller.",
        "alternative": "If listing feels like too much, just name the single thought bothering you most.",
    },
    "relaxation": {
        "title": "Short reset pause",
        "summary": "Release a little tension and take a brief pause.",
        "steps": [
            "Let your shoulders drop a little. Unclench your jaw if it's tight.",
            "Roll your shoulders slowly once or twice.",
            "Notice where you feel tension, without judging yourself for it.",
            "Give yourself a brief pause from work or studying — even 2 minutes counts.",
            "Sip some water if you have it nearby.",
        ],
        "check_in": "Notice anything different in your body, even slightly?",
        "alternative": "If moving feels like too much, just rest your eyes for a few slow breaths.",
    },
    "positive_reflection": {
        "title": "One small win today",
        "summary": "Notice one thing you handled, however small.",
        "steps": [
            "Think of one small thing you handled today — getting up, replying, showing up.",
            "It counts even if the day still felt hard overall.",
            "Try saying to yourself: 'That was difficult, and I got through that part.'",
        ],
        "check_in": "What is one small thing that went okay today?",
        "alternative": "If nothing comes to mind, that is okay — simply being here talking counts.",
    },
    "healthy_routine": {
        "title": "Small care step",
        "summary": "A short walk, water, rest, or a screen break — whatever fits.",
        "steps": [
            "Drink a glass of water.",
            "Step away from the screen for a few minutes if you can.",
            "A short walk or some daylight helps, even briefly.",
            "Tonight, aim to wind down a little earlier than usual.",
            "Just pick the one step that feels easiest — there is no need to do all of these.",
        ],
        "check_in": "Which of these feels most doable right now?",
        "alternative": "Pick just one — there is no need to do all of them.",
    },
    "supportive_conversation": {
        "title": "Just talking it through",
        "summary": "No exercise — simply being heard.",
        "steps": [
            "I'm here to listen. Take your time.",
            "Share as much or as little as feels right.",
            "There is no pressure to fix anything right now.",
        ],
        "check_in": "Would you like to keep talking, or try something calming together?",
        "alternative": "We can also just sit with a quiet moment if you prefer.",
    },
}

# Explicit user requests → activity (checked before any inference).
_REQUEST_KEYWORDS: Dict[str, str] = {
    "breathing": "breathing",
    "breathe": "breathing",
    "breath": "breathing",
    "calm down": "breathing",
    "grounding": "grounding",
    "ground myself": "grounding",
    "5-4-3-2-1": "grounding",
    "organize": "thought_organizing",
    "priorit": "thought_organizing",
    "overwhelm": "thought_organizing",
    "to-do": "thought_organizing",
    "todo": "thought_organizing",
    "relax": "relaxation",
    "tense": "relaxation",
    "shoulders": "relaxation",
    "break": "relaxation",
    "walk": "healthy_routine",
    "water": "healthy_routine",
    "sleep": "healthy_routine",
    "screen": "healthy_routine",
    "good thing": "positive_reflection",
    "grateful": "positive_reflection",
    "just listen": "supportive_conversation",
    "just want to talk": "supportive_conversation",
    "don't want advice": "supportive_conversation",
    "dont want advice": "supportive_conversation",
    "no advice": "supportive_conversation",
    "just talk": "supportive_conversation",
}


def detect_requested_activity(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    for phrase, activity in _REQUEST_KEYWORDS.items():
        if phrase in lowered:
            return activity
    return None


def select_activity(
    *,
    user_text: str,
    tags: List[str],
    stress_band: str,
    wants_advice: Optional[bool],
    offered_recently: List[str],
    explicit_request: Optional[str] = None,
) -> str:
    """Pick one activity id for this turn. Never raises."""
    if explicit_request in ACTIVITIES:
        return explicit_request
    if wants_advice is False:
        return "supportive_conversation"

    lowered = (user_text or "").lower()
    tagset = set(tags or [])

    # Situation-driven mapping (first match wins, in priority order).
    if any(k in lowered for k in ("overthink", "can't stop thinking", "racing thoughts", "too many things", "everything piles")):
        choice = "thought_organizing"
    elif any(k in lowered for k in ("lonely", "alone", "sad", "miss ", "missing", "empty")):
        choice = "supportive_conversation"
    elif any(k in lowered for k in ("tired", "exhausted", "drained", "no energy", "weary")):
        choice = "relaxation"
    elif any(k in lowered for k in ("panic", "anxious", "anxiety", "calm down", "freaking out", "can't breathe")):
        choice = "breathing"
    elif "help-seeking" in tagset:
        choice = "breathing" if stress_band == "high" else "thought_organizing"
    elif "positive" in tagset and "distress" not in tagset:
        choice = "positive_reflection"
    elif stress_band == "high":
        choice = "grounding"
    elif stress_band == "moderate":
        choice = "relaxation"
    else:
        choice = "supportive_conversation"

    # Avoid offering the same activity twice in a row when alternatives exist.
    if offered_recently and offered_recently[-1:] == [choice]:
        fallbacks = {
            "breathing": "grounding",
            "grounding": "breathing",
            "thought_organizing": "relaxation",
            "relaxation": "breathing",
            "supportive_conversation": "relaxation",
            "positive_reflection": "healthy_routine",
            "healthy_routine": "relaxation",
        }
        choice = fallbacks.get(choice, "supportive_conversation")
    return choice


def activity_payload(activity_id: str) -> Dict[str, Any]:
    spec = ACTIVITIES.get(activity_id, ACTIVITIES["supportive_conversation"])
    return {
        "activity": activity_id,
        "activity_title": spec["title"],
        "activity_summary": spec["summary"],
        "activity_steps": list(spec["steps"]),
        "activity_check_in": spec["check_in"],
        "activity_alternative": spec["alternative"],
    }
