"""The editorial pass: the only place a model influences the edit.

It decides *what* to cut, how to group captions, and where emphasis falls. It
receives index-tagged words and no timestamps, so it cannot express a cut point
that does not correspond to real measured speech.
"""
from __future__ import annotations

from halfheaven.groq.asr import Transcript
from halfheaven.groq.client import GroqClient
from halfheaven.plan.builder import Decisions
from halfheaven.plan.decisions import parse_decisions
from halfheaven.schemas import StyleProfile

SYSTEM = """You are the editorial brain of a short-form video editor.

You receive a transcript as INDEX-TAGGED WORDS. You never see timestamps and
must never output one. Refer to words only by their index.

Decide two things:
1. cuts        - remove DISFLUENCY ONLY: filler words ("um", "uh", "like"),
                 stutters, false starts and immediately repeated restarts.
                 Each cut is typically 1-3 words and never more than {max_cut_words}.
                 NEVER remove narrative, explanation, examples or anecdote, even
                 if it seems long-winded - that is the content. Never cut
                 mid-sentence in a way that breaks grammar.
2. punch_ins   - indices of words that carry emphasis and deserve a push-in.
                 Choose about {punch_count} of them.

Caption grouping is handled elsewhere. Do not return captions.

Style target: the reference edit runs at {words_per_sec:.1f} words/second with a
median shot of {median_shot:.1f}s. Trim aggressiveness is {aggressiveness:.1f}
(0 = keep almost everything, 1 = cut hard).

Return ONLY JSON:
{{"cuts":[{{"from":int,"to":int,"kind":str}}],"punch_ins":[int]}}
"from" is inclusive, "to" is EXCLUSIVE, ranges must not overlap."""


def decide(
    client: GroqClient,
    transcript: Transcript,
    profile: StyleProfile,
    punch_count: int = 4,
) -> Decisions:
    max_cut_words = max(2, round(2 + 12 * profile.trim.aggressiveness))
    system = SYSTEM.format(
        max_cut_words=max_cut_words,
        punch_count=punch_count,
        words_per_sec=(len(transcript.words) / transcript.duration) if transcript.duration else 3.0,
        median_shot=profile.pacing.median_shot,
        aggressiveness=profile.trim.aggressiveness,
    )
    payload = client.chat_json(system, f"Transcript:\n{transcript.numbered()}")
    return parse_decisions(
        payload, n_words=len(transcript.words), max_cut_words=max_cut_words
    )
