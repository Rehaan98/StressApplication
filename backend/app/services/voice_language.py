"""
Contextual Spoken-Language Analysis
====================================

Understands WHAT the user says in context — not a keyword counter.

For every sentence it considers:
  * WHO the statement is about (self vs someone else vs mixed)
  * WHEN it applies (right now vs a memory: "used to", "was", "before")
  * NEGATION scope ("I am NOT lonely" ≠ "I am lonely")
  * severity / shutdown / help-seeking / positive / masking patterns
  * safety-relevant statements (handled supportively, never as diagnosis)

Deterministic and explainable: every score can be traced to the sentence,
subject, tense and phrases that produced it. No randomness, no hard-coded
sentence → score mapping.
"""

import re
from typing import Dict, Any, List, Tuple

# ---------------------------------------------------------------------------
# Pattern inventories (matched as phrases inside a sentence, not lone words)
# ---------------------------------------------------------------------------

# Strong distress expressions — everyday emotional statements.
SEVERITY_PHRASES = (
    # exhaustion / depletion
    "i'm tired", "i am tired", "so tired", "really tired", "completely exhausted",
    "i'm exhausted", "i am exhausted", "burned out", "burnt out", "wiped out",
    "no energy", "can't keep going", "cannot keep going",
    # loneliness / emptiness / hurt
    "i feel alone", "feel alone", "i am alone", "so alone", "all alone",
    "i feel lonely", "feel lonely", "i am lonely", "so lonely",
    "i feel empty", "feel empty", "feel hollow", "feel numb",
    "i feel hurt", "feel hurt", "it hurts", "this hurts", "in pain",
    "nothing feels right", "nothing is right", "everything feels wrong",
    "something is wrong", "something feels off",
    # disappointment / hopelessness
    "i'm disappointed", "i am disappointed", "so disappointed",
    "i feel hopeless", "feel hopeless", "no hope", "lost hope",
    "what's the point", "what is the point", "no point", "pointless",
    "things will never", "never get better", "can't get better",
    # feeling unseen / unwanted
    "i feel ignored", "feel ignored", "nobody listens", "no one listens",
    "i feel unwanted", "feel unwanted", "nobody cares", "no one cares",
    "i feel invisible", "like i don't matter", "don't matter",
    # overwhelm / can't cope
    "i can't handle this", "cant handle this", "cannot handle this",
    "too much", "can't take this", "cant take this", "cannot take it",
    "overwhelmed", "drowning", "falling apart", "losing it",
    "can't do this anymore", "cant do this anymore", "cannot do this anymore",
    "i give up", "giving up", "i'm done", "i am done",
    # anger / frustration at boiling point
    "i'm furious", "i am furious", "so furious", "furious",
    "livid", "enraged", "i snapped", "i exploded",
    # stress / pressure / worry
    "very stressed", "so stressed", "really stressed", "extremely stressed",
    "so anxious", "really anxious", "panic", "panicking", "freaking out",
    "panicky", "feeling panicky", "heart is racing", "heart racing",
    "heart pounding", "my heart is pounding",
    "can't sleep", "cannot sleep", "cant sleep", "haven't slept",
    "racing thoughts", "can't stop thinking", "overthinking everything",
    "so much pressure", "under pressure", "deadline", "work is killing",
    # sadness / grief-flavoured (incl. gerunds STT often produces)
    "i feel sad", "feel sad", "feeling sad", "so sad", "really sad", "want to cry",
    "feeling lonely", "feeling tired", "feeling hopeless", "feeling alone",
    "feeling empty", "feeling hurt", "feeling ignored", "feeling unwanted",
    "feel like crying", "been crying", "heartbroken", "missing",
    "i miss", "things aren't the same", "things are not the same",
    "you've changed", "you have changed", "not the same anymore",
    "i wish things were different", "wish things were different",
    "maybe i expected too much", "expected too much",
)

# Withdrawal / shutdown language ("leave me alone" energy).
SHUTDOWN_PHRASES = (
    "i need some space", "need space", "leave it", "forget it", "never mind",
    "i don't care anymore", "dont care anymore", "do not care anymore",
    "doesn't matter", "does not matter", "whatever", "what's the use",
    "i don't want to talk about it", "dont want to talk", "do not want to talk",
    "leave me alone", "just leave", "go away",
)

# Help-seeking / uncertainty.
HELP_PHRASES = (
    "what should i do", "what do i do", "i don't know what to do",
    "dont know what to do", "do not know what to do", "help me",
    "need help", "need advice", "any advice", "how do i cope",
    "tell me what to do",
)

# Calm / positive / recovering language.
POSITIVE_PHRASES = (
    "feeling better", "feel better", "a little better", "much better",
    "taking a breath", "take a breath", "deep breath", "breathing",
    "i can handle", "i've got this", "i got this", "it will pass",
    "things will get better", "grateful", "thankful", "hopeful",
    "calm", "relaxed", "peaceful", "rested", "energized", "happy",
    "laugh", "fun", "enjoy", "love", "good day", "great day", "went well",
)

# Masking language: "fine" is NOT automatically low stress — flagged so the
# fusion layer lets voice + webcam decide.
MASKING_PHRASES = (
    "i'm fine", "i am fine", "im fine", "i'm okay", "i am okay",
    "it's okay", "it is okay", "its okay", "i'm good", "i am good",
    "all good", "doing fine", "doing okay", "no worries", "don't worry about me",
)

# Safety-relevant statements → supportive safety response (never diagnosis).
SAFETY_PHRASES = (
    "don't want to be here", "dont want to be here", "do not want to be here",
    "want to disappear", "wish i could disappear", "better off dead",
    "no reason to live", "no point in living", "point in living",
    "want to die", "wish i were dead", "kill myself", "end my life",
    "end it all", "hurt myself", "hurting myself", "harm myself",
    "don't want to live", "dont want to live", "do not want to live",
    "can't go on", "cant go on", "cannot go on",
)

NEGATORS = {
    "not", "no", "never", "n't", "dont", "doesnt",
    "didnt", "cannot", "cant", "wont", "wouldn't",
    "without", "hardly", "barely", "neither", "nor",
}

# Past framing that is strong enough to override present-tense verbs
# ("I USED TO feel hopeless" is a memory, even though "feel" is present-form).
STRONG_PAST = (
    "used to", "was ", "were ", "back then", "in the past",
    "yesterday", "last week", "last month", "growing up", "as a kid",
    "when i was",
)

PRESENT_CUES = (
    "right now", "lately", "these days", "today", "at the moment",
    "keeps happening", "keeps",
)

# Other-person markers (regex, word boundaries — never plain substrings).
OTHER_PERSON_RE = re.compile(
    r"\b(my friend|my mom|my dad|my mother|my father|my brother|my sister|"
    r"my son|my daughter|my husband|my wife|my partner|my boss|"
    r"my colleague|my neighbour|my neighbor|he|she|him|her|they|them|"
    r"his|hers|theirs)\b"
)
# Strong first-person clause ("I feel…", "I am…") → mixed, not purely other.
STRONG_SELF_RE = re.compile(r"\bi(\s+(am|feel|think|want|need|ve|m|was|wish|miss)|'m|'ve)\b|\bme\b")

# Bare distress nouns/adjectives: count when NOT part of a matched phrase,
# so "I am lonely" still registers even without a longer pattern.
DISTRESS_WORDS = {
    "alone", "lonely", "hopeless", "helpless", "empty", "hurt", "hurting",
    "tired", "exhausted", "sad", "unhappy", "miserable", "anxious",
    "stressed", "depressed", "afraid", "scared", "worried", "angry",
    "frustrated", "tearful", "numb", "hollow", "stuck", "trapped",
    "worthless", "miserable", "drained", "weary", "furious", "livid",
    "enraged", "panicky",
}

FIRST_PERSON = {"i", "me", "my", "mine", "myself", "we", "us", "our", "im", "ive"}

BASE_SENTENCE = 0.22
SEV_W = 0.20
SEV_CAP = 3

# Fillers that may sit inside a distress expression without changing it
# ("feeling COMPLETELY alone" == "feeling alone"). Stripped only for a
# second matching pass — the raw text is always matched first.
INTENSIFIERS = {
    "so", "very", "really", "extremely", "quite", "pretty", "completely",
    "totally", "utterly", "truly", "deeply", "highly", "particularly",
    "too", "super", "incredibly", "highly",
}

AMPLIFIER_WORDS = {
    "very", "so", "really", "extremely", "super", "too", "totally",
    "completely", "utterly", "incredibly", "always", "never", "constantly",
}

# Strong distress patterns: on their own they mark the transcript severe,
# so a low acoustic score can never drag the final result down to ~40%.
# (Same canonical list used by every text pipeline — typed or spoken.)
SEVERE_PATTERNS = (
    "very stressed", "so stressed", "really stressed", "extremely stressed",
    "super stressed", "too stressed", "very sad", "so sad", "really sad",
    "feeling sad", "feel sad", "feeling tired", "feel tired", "so tired",
    "very tired", "really tired", "feeling unhappy", "feel unhappy",
    "very unhappy", "so unhappy", "feeling overwhelmed", "feel overwhelmed",
    "so overwhelmed", "cant cope", "cannot cope", "breaking down",
    "mental breakdown", "need help", "help me", "what should i do",
    "what do i do", "cant sleep", "cannot sleep", "no sleep",
    "havent slept", "have not slept", "crying all", "cry all",
    "give up", "hopeless",
    "feel alone", "feeling alone", "completely alone", "all alone", "so alone",
    "nothing feels right", "nothing is right", "feel lonely", "feeling lonely",
    "feel empty", "feeling empty", "cant do this anymore", "cannot do this anymore",
    "cant go on", "cannot go on",
)

# Emotion hint mapping shared by all pipelines (typed + spoken).
EMOTION_HINT_MAP = {
    "anger": {"angry", "anger", "furious", "frustrated", "irritated", "annoyed", "rage", "hate"},
    "fear": {"afraid", "scared", "fear", "anxious", "anxiety", "panic", "worried", "nervous", "dread"},
    "sadness": {"sad", "sadness", "unhappy", "miserable", "depressed", "depression", "hopeless", "lonely", "loneliness", "crying", "cry", "cried", "tearful", "down", "empty", "grief", "heartbroken", "despair", "tired", "weary", "exhausted", "drained", "alone"},
    "joy": {"happy", "joy", "great", "excited", "grateful", "love", "laugh", "relaxed", "calm"},
    "surprise": {"shocked", "surprised", "sudden", "unexpected", "overwhelmed"},
}


def _norm_phrases(phrases: Tuple[str, ...]) -> Tuple[str, ...]:
    """Normalize + longest-first so overlaps resolve to the longest match."""
    normed = sorted({_normalize(p) for p in phrases if _normalize(p)}, key=len, reverse=True)
    return tuple(normed)


def _normalize(text: str) -> str:
    t = (text or "").lower()
    t = t.replace("can't", "cant").replace("cannot", "cant")
    t = t.replace("don't", "dont").replace("doesn't", "doesnt")
    t = t.replace("didn't", "didnt").replace("won't", "wont")
    t = re.sub(r"[^a-z\s']", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"[.!?;]+|\bbut\b|\bhowever\b", text or "")
    return [p.strip() for p in parts if p.strip()]


# Normalized once at import (apostrophes unified: don't→dont, can't→cant).
_SEV = _norm_phrases(SEVERITY_PHRASES)
_SHUT = _norm_phrases(SHUTDOWN_PHRASES)
_HELP = _norm_phrases(HELP_PHRASES)
_POS = _norm_phrases(POSITIVE_PHRASES)
_MASK = _norm_phrases(MASKING_PHRASES)
_SAFE = _norm_phrases(SAFETY_PHRASES)
_SEVERE_N = _norm_phrases(SEVERE_PATTERNS)


def _strip_intensifiers(sentence: str) -> str:
    kept = [w for w in sentence.split() if w not in INTENSIFIERS]
    return " ".join(kept)


def _find_phrases(sentence: str, phrases: Tuple[str, ...]) -> List[str]:
    """Regex word-boundary match, longest-first, dropping subsumed overlaps
    (so 'i feel hopeless' wins and 'feel hopeless' isn't double-counted).

    A second pass runs on the sentence with filler intensifiers removed, so
    'feeling COMPLETELY alone' still matches 'feeling alone'.
    """
    hits: List[str] = []
    covered: set = set()
    for variant_i, text in enumerate((sentence, _strip_intensifiers(sentence))):
        for p in phrases:
            if re.search(r"\b" + re.escape(p) + r"\b", text):
                if variant_i == 1:
                    # Stripped pass: only count if it surfaces a distress word
                    # the raw pass missed (avoids "so sad"+"feel sad" doubles).
                    new_words = {w for w in p.split() if w in DISTRESS_WORDS} - covered
                    if not new_words:
                        continue
                if not any(p != h and p in h for h in hits):
                    hits = [h for h in hits if not (h != p and h in p)]
                    hits.append(p)
                    covered.update(p.split())
    return hits


def _negated_spans(words: List[str], span: int = 4) -> List[bool]:
    """Mark tokens that fall inside a negation scope."""
    negated = [False] * len(words)
    for i, w in enumerate(words):
        if w in NEGATORS or w.endswith("n't"):
            for j in range(i + 1, min(len(words), i + 1 + span)):
                if words[j] in {"but", "however", "although"}:
                    break
                negated[j] = True
    return negated


def _analyze_sentence(sentence: str) -> Dict[str, Any]:
    norm = _normalize(sentence)
    words = norm.split()
    if not words:
        return {"score": 0.0, "weight": 0.0, "tags": ["empty"], "phrases": []}

    neg = _negated_spans(words)

    # --- subject: who is this about? (regex, never substrings)
    other_hit = OTHER_PERSON_RE.search(norm)
    strong_self = bool(STRONG_SELF_RE.search(norm))
    if other_hit and not strong_self:
        subject, subj_weight = "other", 0.25
    elif other_hit and strong_self:
        subject, subj_weight = "mixed", 0.6
    else:
        subject, subj_weight = "self", 1.0

    # --- tense: strong past framing wins ("I USED TO feel hopeless").
    tense = "past" if any(m in norm for m in STRONG_PAST) else "present"
    tense_weight = 0.5 if tense == "past" else 1.0

    safety = _find_phrases(norm, _SAFE)
    sev = _find_phrases(norm, _SEV)
    shut = _find_phrases(norm, _SHUT)
    help_hits = _find_phrases(norm, _HELP)
    pos = _find_phrases(norm, _POS)
    mask = _find_phrases(norm, _MASK)

    # Drop severity hits whose distress content is genuinely negated
    # ("not lonely", "never hopeless") — but a negator that is PART of the
    # matched phrase itself ("can't do this anymore") does NOT negate it.
    effective_sev = []
    negated_hit = False
    for p in sev:
        pw = set(p.split())
        neg_inside = bool(pw & NEGATORS)
        neg_outside = False
        for i, w in enumerate(words):
            if w in pw and neg[i]:
                # is the negator itself outside this phrase?
                neg_outside = True
                break
        if neg_outside and not neg_inside:
            negated_hit = True
            continue
        effective_sev.append(p)

    # Bare distress nouns/adjectives outside any matched phrase
    # ("I am lonely") — skipped when negated in scope; negated ones are
    # tracked so the transcript level never counts them as distress.
    phrase_words = {w for p in effective_sev for w in p.split()}
    bare_hits = []
    negated_words = []
    for i, w in enumerate(words):
        if w in DISTRESS_WORDS and w not in phrase_words:
            if neg[i]:
                negated_words.append(w)
            else:
                bare_hits.append(w)
    bare_hits = sorted(set(bare_hits))
    negated_words = sorted(set(negated_words))

    score = BASE_SENTENCE
    score += SEV_W * min(len(effective_sev), SEV_CAP)
    score += 0.10 * min(len(bare_hits), 3)
    score += 0.10 * min(len(shut), 2)
    score += 0.08 * min(len(help_hits), 1)
    score -= 0.12 * min(len(pos), 2)
    # Amplifier intensifying distress ("SO sad", "VERY tired") — same
    # sentence, real intensification, not double counting.
    if any(w in AMPLIFIER_WORDS for w in words) and (effective_sev or bare_hits):
        score += 0.06

    masking = len(mask) > 0 and len(effective_sev) == 0 and len(shut) == 0 and len(bare_hits) == 0
    if masking:
        score = 0.30  # neutral placeholder — voice + webcam decide

    score = max(0.02, min(0.97, score))
    if subject != "self" or tense == "past":
        # Context dampens: a memory, or someone else's pain, is not the
        # user's current pain.
        score = round(0.15 + (score - 0.15) * subj_weight * tense_weight, 4)
    else:
        score = round(score, 4)

    if safety:
        score = max(score, 0.75)

    tags = []
    if effective_sev or bare_hits:
        tags.append("distress")
    if shut:
        tags.append("withdrawal")
    if help_hits:
        tags.append("help-seeking")
    if pos:
        tags.append("positive")
    if masking:
        tags.append("masking")
    if negated_hit and not effective_sev and not bare_hits:
        tags.append("negated")
    if subject != "self":
        tags.append(f"subject:{subject}")
    if tense == "past":
        tags.append("tense:past")
    if safety:
        tags.append("safety")

    return {
        "score": score,
        "weight": 1.0,
        "tags": tags or ["neutral"],
        "phrases": (effective_sev + bare_hits + shut + help_hits + mask)[:6],
        "subject": subject,
        "tense": tense,
        "masking": masking,
        "safety": safety,
        "negated_words": negated_words,
    }


def analyze_language(transcript: str) -> Dict[str, Any]:
    """Context-aware language stress analysis for a full transcript."""
    text = (transcript or "").strip()
    if len(text.split()) < 1 or not text:
        return {
            "language_score": 0.5, "language_level": "Moderate",
            "confidence": 0.1, "usable": False, "tags": ["empty"],
            "key_phrases": [], "subject": "self", "masking": False,
            "safety": False, "safety_phrases": [], "sentences": [],
            "note": "No words captured — language carries no weight.",
        }

    sentences = [_analyze_sentence(s) for s in _split_sentences(text)]
    sentences = [s for s in sentences if "empty" not in s["tags"]]
    if not sentences:
        return {
            "language_score": 0.5, "language_level": "Moderate",
            "confidence": 0.1, "usable": False, "tags": ["empty"],
            "key_phrases": [], "subject": "self", "masking": False,
            "safety": False, "safety_phrases": [], "sentences": [],
            "note": "No words captured — language carries no weight.",
        }

    scores = [s["score"] for s in sentences]
    agg = 0.55 * max(scores) + 0.45 * (sum(scores) / len(scores))
    agg = max(0.02, min(0.97, round(agg, 4)))

    tags: List[str] = []
    for s in sentences:
        for t in s["tags"]:
            if t not in tags:
                tags.append(t)
    key_phrases: List[str] = []
    for s in sentences:
        for p in s["phrases"]:
            if p not in key_phrases:
                key_phrases.append(p)
            if len(key_phrases) >= 8:
                break
        if len(key_phrases) >= 8:
            break

    safety_hits: List[str] = []
    for s in sentences:
        for p in (s.get("safety") or []):
            if p not in safety_hits:
                safety_hits.append(p)

    masking = any(s.get("masking") for s in sentences)
    subjects = {s.get("subject", "self") for s in sentences}
    subject = "self" if subjects == {"self"} else ("mixed" if "self" in subjects else next(iter(subjects)))

    n_words = len(text.split())
    confidence = max(0.3, min(0.9, round(0.4 + 0.04 * n_words + (0.1 if safety_hits else 0.0), 4)))

    # --- severity machinery shared by EVERY text pipeline (typed or spoken).
    # Strong distress language must survive fusion with a low acoustic score.
    flat_norm = _normalize(text)
    flat_stripped = _strip_intensifiers(flat_norm)
    severe_phrases = _find_phrases(flat_norm, _SEVERE_N)
    if flat_stripped != flat_norm:
        for p in _find_phrases(flat_stripped, _SEVERE_N):
            if p not in severe_phrases:
                severe_phrases.append(p)
    # Negation-aware distress vocabulary: "not lonely" contributes nothing.
    negated_words = sorted({w for s in sentences for w in (s.get("negated_words") or [])})
    distress_words = sorted(
        {w for w in re.findall(r"[a-z]+", flat_norm) if w in DISTRESS_WORDS} - set(negated_words)
    )
    if negated_words and not distress_words and not severe_phrases and not safety_hits:
        if "negated" not in tags:
            tags = tags + ["negated"]
    short_distress = (
        n_words <= 4
        and len(distress_words) >= 1
        and subject == "self"
    )
    severe_raw = bool(safety_hits or severe_phrases or short_distress or len(distress_words) >= 3)
    # Severity floors only apply to the speaker's CURRENT state — never to
    # memories ("I used to…") or someone else's pain ("my friend…"), which
    # are already dampened above.
    present_self_distress = any(
        (s.get("subject") == "self" and s.get("tense") == "present"
         and any(t in (s.get("tags") or []) for t in ("distress", "withdrawal", "help-seeking", "safety")))
        for s in sentences
    )
    severe = bool(severe_raw and present_self_distress)
    if severe and not safety_hits:
        # A clearly severe reading should never sit below ~60%.
        agg = max(agg, 0.62)
        agg = max(0.02, min(0.97, round(agg, 4)))

    wordset = set(re.findall(r"[a-z]+", flat_norm))
    emotion_hint = ""
    best = 0
    for emo, kws in EMOTION_HINT_MAP.items():
        hits = len(wordset & kws)
        if hits > best:
            best = hits
            emotion_hint = emo if hits > 0 else ""
    keywords = list(key_phrases[:4]) + [w for w in distress_words if w not in key_phrases]
    keywords = keywords[:8]
    calm_hits = sum(1 for p in _find_phrases(flat_norm, _POS) for _ in [0]) + sum(
        1 for w in wordset if w in {"calm", "relaxed", "peaceful", "rested", "happy", "grateful", "hopeful", "fine", "okay", "good"}
    )

    from backend.app.services.voice_service import _classify_score
    return {
        "language_score": agg,
        "language_level": _classify_score(agg),
        "confidence": confidence,
        "usable": True,
        "tags": tags,
        "key_phrases": key_phrases,
        "subject": subject,
        "masking": masking,
        "safety": len(safety_hits) > 0,
        "safety_phrases": safety_hits,
        "sentences": [
            {"text": s, "score": r["score"], "tags": r["tags"]}
            for s, r in zip(_split_sentences(text), sentences)
        ],
        "n_sentences": len(sentences),
        # Unified cross-pipeline fields (typed input and spoken transcripts
        # MUST produce identical values for identical text):
        "severe": severe,
        "severe_phrases": severe_phrases[:3],
        "help_seeking": ("help-seeking" in tags) and not severe,
        "keywords": keywords,
        "emotion_hint": emotion_hint,
        "counts": {"high": len(distress_words), "calm": calm_hits},
    }
