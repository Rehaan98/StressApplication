"""
Conversation bot tests — natural replies, context understanding, safety,
stress-aware adaptation, and API contract. Offline path (use_llm=False) so
no network or API keys are needed.
"""

import pytest
from httpx import AsyncClient

from backend.app.main import app
from backend.app.services.conversation import start_conversation, handle_message, end_conversation
from backend.app.services.conversation.activities import select_activity, ACTIVITIES
from backend.app.services.conversation.safety import safety_check


async def _reply(message, stress_context=None):
    sess = start_conversation()
    res = await handle_message(sess["session_id"], message, stress_context=stress_context, use_llm=False)
    return res


@pytest.fixture(scope="module")
def event_loop():
    import asyncio
    loop = asyncio.get_event_loop_policy().new_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def auth_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        res = await client.post("/api/v1/auth/register", json={
            "email": "convobot@stressai.com",
            "full_name": "Convo Bot",
            "password": "ConvoBot@2026",
        })
        if res.status_code != 201:
            res = await client.post("/api/v1/auth/login", json={
                "email": "convobot@stressai.com",
                "password": "ConvoBot@2026",
            })
        return res.json().get("access_token", "")


# --- Required scenario suite (spec section 11) -------------------------------

@pytest.mark.asyncio
async def test_01_greeting():
    r = await _reply("Hi, how are you?")
    low = r["reply"].lower()
    assert "how are you feeling" in low or "how are you doing" in low
    # Honest AI identity, never pretending to be human.
    assert "ai companion" in low or "i'm here" in low or "i am here" in low


@pytest.mark.asyncio
async def test_02_happy_gets_positive_no_exercise():
    r = await _reply("I'm happy today.")
    assert r["activity"] in ("positive_reflection", "supportive_conversation")
    assert "breath" not in r["reply"].lower()
    assert "grounding" not in r["reply"].lower()


@pytest.mark.asyncio
async def test_03_stressed_acknowledged():
    r = await _reply("I'm feeling stressed.")
    assert "stress" in r["reply"].lower()
    assert r["reply"].count("?") <= 2  # one gentle question, not a list


@pytest.mark.asyncio
async def test_04_lonely_supported():
    r = await _reply("I feel so sad and completely alone.")
    low = r["reply"].lower()
    assert "sorry" in low and "listen" in low
    assert r["activity"] == "supportive_conversation"


@pytest.mark.asyncio
async def test_05_exhausted_names_energy():
    r = await _reply("I'm exhausted from studying.")
    low = r["reply"].lower()
    assert "energy" in low or "carrying a lot" in low
    assert r["activity"] == "relaxation"


@pytest.mark.asyncio
async def test_06_overthinking_simplifies():
    r = await _reply("I can't stop overthinking.")
    low = r["reply"].lower()
    assert "one thought" in low or "simpler" in low
    assert r["activity"] == "thought_organizing"


@pytest.mark.asyncio
async def test_07_fine_no_pressure():
    r = await _reply("I'm fine.")
    low = r["reply"].lower()
    assert "no pressure" in low
    assert "depress" not in low and "diagnos" not in low


@pytest.mark.asyncio
async def test_08_calm_down_breathing():
    r = await _reply("Can you help me calm down?")
    assert r["activity"] == "breathing"
    assert len(r["activity_steps"]) >= 3
    assert "stop anytime" in r["reply"].lower() or "stop whenever" in r["reply"].lower()
    assert r["activity_check_in"]


@pytest.mark.asyncio
async def test_09_just_want_to_talk_listens():
    sess = start_conversation()
    r = await handle_message(sess["session_id"], "I don't want advice; I just want to talk.", use_llm=False)
    assert "listen" in r["reply"].lower()
    assert r["activity"] == "supportive_conversation"
    # Preference persists: next turn still listens rather than advising.
    r2 = await handle_message(sess["session_id"], "Work has been rough.", use_llm=False)
    assert r2["activity"] == "supportive_conversation"


@pytest.mark.asyncio
async def test_10_better_acknowledges_progress():
    r = await _reply("I'm feeling better now.")
    low = r["reply"].lower()
    assert "glad" in low or "good sign" in low


@pytest.mark.asyncio
async def test_11_not_stressed_not_treated_as_stress():
    r = await _reply("I'm not stressed.")
    low = r["reply"].lower()
    assert "would you like to tell me what's been on your mind" not in low
    assert "breath" not in low


@pytest.mark.asyncio
async def test_12_friend_lonely_not_user():
    r = await _reply("My friend is feeling lonely.")
    low = r["reply"].lower()
    assert "your friend" in low
    assert "sorry you're feeling" not in low  # must not claim the user is lonely


@pytest.mark.asyncio
async def test_past_stress_vs_present():
    r = await _reply("I was stressed yesterday, but I'm okay today.")
    low = r["reply"].lower()
    assert "then" in low or "today" in low
    assert r["activity"] != "breathing"


@pytest.mark.asyncio
async def test_overwhelm_picks_one_small_thing():
    r = await _reply("I've got too many things to do.")
    assert "one small thing" in r["reply"].lower()
    assert r["activity"] == "thought_organizing"


# --- Safety -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_safety_response_is_calibrated():
    assert safety_check("I want to disappear.")["safety"] is True
    assert safety_check("I'm tired.").get("safety", False) is False
    assert safety_check("I give up on this puzzle.").get("safety", False) is False
    r = await _reply("I want to disappear.")
    assert r["is_safety"] is True
    assert r["safety_notice"]
    assert "trusted person" in r["reply"].lower() or "crisis" in r["reply"].lower()
    assert "diagnos" not in r["reply"].lower()


# --- Stress-aware adaptation ----------------------------------------------------

@pytest.mark.asyncio
async def test_stress_context_adapts_without_dictating():
    low_ctx = {"stress_score": 0.15, "stress_level": "Low", "confidence": 0.8, "trend": "stable"}
    high_ctx = {"stress_score": 0.9, "stress_level": "High", "confidence": 0.85, "trend": "increasing"}
    # Deterministic band split: high band adds a slow-down prefix + grounding.
    r_low = await _reply("I'm feeling stressed.", stress_context=low_ctx)
    r_high = await _reply("I'm feeling stressed.", stress_context=high_ctx)
    assert r_low["stress_adaptation"]["band"] == "low"
    assert r_high["stress_adaptation"]["band"] == "high"
    assert r_low["reply"] != r_high["reply"] or r_low["activity"] != r_high["activity"]
    assert r_high["activity"] == "grounding"
    # Uncertain prediction is flagged, not obeyed blindly.
    r_unc = await _reply("I'm fine.", stress_context={"stress_score": 0.9, "confidence": 0.1})
    assert r_unc["stress_adaptation"]["uncertain"] is True
    assert "no pressure" in r_unc["reply"].lower()


@pytest.mark.asyncio
async def test_no_detection_still_helpful():
    r = await _reply("I've had a long day.")
    assert len(r["reply"]) > 20
    assert r["stress_adaptation"]["has_detection"] is False


@pytest.mark.asyncio
async def test_score_scale_0_100_accepted():
    r = await _reply("Hello there.", stress_context={"stress_score": 75})
    assert r["stress_adaptation"]["band"] == "high"


# --- Activities ------------------------------------------------------------------

def test_all_activities_have_gentle_guidance():
    for act_id, spec in ACTIVITIES.items():
        assert len(spec["steps"]) >= 3, act_id
        joined = " ".join(spec["steps"]).lower()
        assert "stop" in joined or "skip" in joined or "no need" in joined or "whenever" in joined or \
            "pressure" in joined or "counts" in joined or "one" in joined, act_id


def test_activity_selection_varies_by_situation():
    assert select_activity(user_text="help me calm down", tags=[], stress_band="high",
                           wants_advice=None, offered_recently=[]) == "breathing"
    assert select_activity(user_text="too many things to do", tags=[], stress_band="moderate",
                           wants_advice=None, offered_recently=[]) == "thought_organizing"
    assert select_activity(user_text="i feel lonely", tags=[], stress_band="moderate",
                           wants_advice=None, offered_recently=[]) == "supportive_conversation"
    assert select_activity(user_text="whatever", tags=[], stress_band="low",
                           wants_advice=False, offered_recently=[]) == "supportive_conversation"


# --- API contract -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_start_message_history_end(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(app=app, base_url="http://test") as client:
        start = await client.post("/api/v1/conversation/start", json={}, headers=headers)
        assert start.status_code == 200, start.text
        sid = start.json()["session_id"]
        assert "how are you feeling" in start.json()["reply"].lower()

        msg = await client.post("/api/v1/conversation/message", json={
            "session_id": sid,
            "message": "I'm feeling stressed.",
            "stress_context": {"stress_level": "Moderate", "confidence": 0.7, "trend": "stable"},
        }, headers=headers)
        assert msg.status_code == 200, msg.text
        body = msg.json()
        for key in ("reply", "activity", "activity_steps", "language_understanding",
                    "stress_adaptation", "interventions"):
            assert key in body, key

        hist = await client.get(f"/api/v1/conversation/{sid}", headers=headers)
        assert hist.status_code == 200
        assert hist.json()["turn_count"] >= 3

        empty = await client.post("/api/v1/conversation/message", json={
            "session_id": sid, "message": "   ",
        }, headers=headers)
        assert empty.status_code in (400, 422)

        end = await client.delete(f"/api/v1/conversation/{sid}", headers=headers)
        assert end.status_code == 200
        assert end.json()["ended"] is True

        gone = await client.get(f"/api/v1/conversation/{sid}", headers=headers)
        assert gone.status_code == 404


def test_end_conversation_unit():
    sess = start_conversation()
    res = end_conversation(sess["session_id"])
    assert res["ended"] is True


# --- Upgraded companion behaviors (spec section 5-6) ---------------------------

@pytest.mark.asyncio
async def test_misunderstood_validated():
    r = await _reply("Nobody understands me. I'm tired of explaining everything.")
    low = r["reply"].lower()
    assert "exhausting" in low
    assert "don't have to explain everything perfectly" in low


@pytest.mark.asyncio
async def test_no_start_offers_three_doors():
    r = await _reply("I don't even know where to start.")
    low = r["reply"].lower()
    assert "start small" in low
    assert "someone" in low and ("work" in low or "stud" in low)


@pytest.mark.asyncio
async def test_listen_only_variants():
    for msg in ("I just need someone to listen.",
                "I don't want advice; I just want to talk.",
                "Hear me out, please."):
        r = await _reply(msg)
        assert "listen" in r["reply"].lower(), msg
        assert r["activity"] == "supportive_conversation", msg


@pytest.mark.asyncio
async def test_tone_preference_stored_and_acknowledged():
    from backend.app.services.conversation import get_history
    sess = start_conversation()
    r = await handle_message(sess["session_id"], "Please be more practical with me.", use_llm=False)
    assert "practical" in r["reply"].lower()
    hist = get_history(sess["session_id"])
    assert hist["tone"] == "practical"


@pytest.mark.asyncio
async def test_no_repeat_questions_across_turns():
    from backend.app.services.conversation import handle_message
    sess = start_conversation()
    r1 = await handle_message(sess["session_id"], "I feel so alone.", use_llm=False)
    r2 = await handle_message(sess["session_id"], "Nobody cares about me.", use_llm=False)
    q1 = [s for s in r1["reply"].split("? ")]
    # The two lonely turns must not ask the identical follow-up.
    assert r1["reply"] != r2["reply"]


@pytest.mark.asyncio
async def test_no_bogus_health_memory():
    from backend.app.services.conversation import handle_message, get_history
    sess = start_conversation()
    await handle_message(sess["session_id"], "I'm exhausted from studying.", use_llm=False)
    hist = get_history(sess["session_id"])
    assert hist["facts"].get("topic") != "health"


@pytest.mark.asyncio
async def test_exercise_permission_flow():
    from backend.app.services.conversation import handle_message
    sess = start_conversation()
    sid = sess["session_id"]
    # High-band stress triggers a permission-style offer, not uninvited guiding.
    r = await handle_message(
        sid, "I'm feeling stressed.",
        stress_context={"stress_level": "High", "confidence": 0.85, "trend": "increasing"},
        use_llm=False,
    )
    assert r["activity"] == "grounding"
    assert "would" in r["reply"].lower() and "?" in r["reply"]
    assert "name 5 things" not in r["reply"].lower()  # steps not spoken yet
    # Accept → guided steps, stop option included.
    r2 = await handle_message(sid, "yes", use_llm=False)
    assert "stop anytime" in r2["reply"].lower()
    # Positive feedback → celebrated, flow closed.
    r3 = await handle_message(sid, "I feel a bit better now", use_llm=False)
    assert "glad" in r3["reply"].lower()


@pytest.mark.asyncio
async def test_exercise_decline_and_alternative():
    from backend.app.services.conversation import handle_message
    sess = start_conversation()
    sid = sess["session_id"]
    await handle_message(
        sid, "I'm feeling stressed.",
        stress_context={"stress_level": "High", "confidence": 0.85},
        use_llm=False,
    )
    r_no = await handle_message(sid, "no, I'd rather just talk", use_llm=False)
    assert "listen" in r_no["reply"].lower()

    sess2 = start_conversation()
    sid2 = sess2["session_id"]
    await handle_message(sid2, "Can we do a breathing exercise together?", use_llm=False)
    r_worse = await handle_message(sid2, "That is not helping, I feel worse", use_llm=False)
    assert "not for everyone" in r_worse["reply"].lower()


@pytest.mark.asyncio
async def test_explicit_exercise_guides_directly():
    r = await _reply("Can you guide me through a grounding exercise?")
    assert r["activity"] == "grounding"
    assert len(r["activity_steps"]) >= 3
    assert "stop anytime" in r["reply"].lower()


@pytest.mark.asyncio
async def test_trajectory_noted_when_heavier():
    from backend.app.services.conversation import handle_message
    sess = start_conversation()
    sid = sess["session_id"]
    await handle_message(sid, "Work is busy today.", use_llm=False)
    await handle_message(sid, "Honestly everything is piling up.", use_llm=False)
    r = await handle_message(sid, "I feel completely alone and hopeless.", use_llm=False)
    assert "getting heavier" in r["reply"].lower()


def test_session_ttl_expiry_and_prune():
    from backend.app.services.conversation import context as conv_ctx

    s = start_conversation()
    assert conv_ctx.fetch_session(s["session_id"]) is not None
    conv_ctx._sessions[s["session_id"]].last_active -= 31 * 60
    assert conv_ctx.fetch_session(s["session_id"]) is None  # lazily expired
    assert conv_ctx.prune_expired() >= 0
