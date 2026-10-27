"""
Conversation session lifecycle + pipeline orchestration.

Public functions used by the API layer:
  start_conversation(user_name) -> session + greeting
  handle_message(session_id, message, stress_context) -> reply payload
  get_history(session_id) -> turns + facts
  end_conversation(session_id) -> goodbye + drop
"""

from typing import Dict, Any, Optional

from backend.app.services.conversation.context import (
    ConversationSession,
    StressContext,
    create_session,
    fetch_session,
    drop_session,
)
from backend.app.services.conversation.response import craft_reply


GREETING = "Hey! I'm here with you. How are you feeling today?"


def start_conversation(user_name: Optional[str] = None) -> Dict[str, Any]:
    sess = create_session(user_name=user_name)
    sess.add_turn("assistant", GREETING, greeting=True)
    sess.track_phrasing("greeting")
    return {
        "session_id": sess.session_id,
        "reply": GREETING,
        "activity": "supportive_conversation",
        "message": GREETING,
    }


async def handle_message(
    session_id: str,
    message: str,
    stress_context: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    sess = fetch_session(session_id)
    if sess is None:
        raise KeyError(f"Unknown conversation session: {session_id}")
    stress = StressContext.from_payload(stress_context)
    result = await craft_reply(sess, message or "", stress, use_llm=use_llm)
    return {"session_id": session_id, **result}


def get_history(session_id: str) -> Dict[str, Any]:
    sess = fetch_session(session_id)
    if sess is None:
        raise KeyError(f"Unknown conversation session: {session_id}")
    return {
        "session_id": session_id,
        "turns": sess.to_history(),
        "facts": dict(sess.facts),
        "last_activity": sess.last_activity,
        "turn_count": len(sess.turns),
        "tone": sess.tone,
        "exercise_status": dict(sess.exercise),
    }


def end_conversation(session_id: str) -> Dict[str, Any]:
    sess = fetch_session(session_id)
    goodbye = "Take care. Be gentle with yourself today. I'm here whenever you want to talk."
    turns = sess.to_history() if sess else []
    drop_session(session_id)
    return {"session_id": session_id, "reply": goodbye, "ended": True, "turns": turns}
