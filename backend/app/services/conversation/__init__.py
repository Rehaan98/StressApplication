"""
Natural AI Stress-Relief Conversation Bot — reusable service package.

Modules (each independently importable so stress detection stays separate):
  safety     — responsible handling of serious-distress / self-harm language.
  context    — per-session conversation memory (history, facts, preferences).
  activities — practical stress-relief activity guidance (A–G in the spec).
  response   — natural response generation (optional LLM + offline fallback).
  manager    — session lifecycle + pipeline orchestration.

Design rules enforced here:
  * NEVER invents stress scores — stress context is only accepted from the
    caller (existing voice/webcam pipelines) and is always optional.
  * NEVER diagnoses or treats mental-health conditions.
  * NEVER pretends to be human.
  * Understanding reuses backend.app.services.voice_language.analyze_language,
    so negation / tense / subject handling matches the existing pipelines.
"""

from backend.app.services.conversation.manager import (
    start_conversation,
    handle_message,
    get_history,
    end_conversation,
)

__all__ = [
    "start_conversation",
    "handle_message",
    "get_history",
    "end_conversation",
]
