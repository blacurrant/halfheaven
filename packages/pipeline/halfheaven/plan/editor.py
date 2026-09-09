"""The editorial pass: the only place a model influences the edit.

It decides *what* to cut, how to group captions, and where emphasis falls. It
receives index-tagged words and no timestamps, so it cannot express a cut point
that does not correspond to real measured speech.
"""
from __future__ import annotations

from halfheaven.groq.asr import Transcript
from halfheaven.groq.client import GroqClient
from halfheaven.plan.builder import Decisions
import dataclasses

from halfheaven.plan.decisions import parse_decisions
from halfheaven.plan.emphasis import meaningful_emphasis
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
2. punch_ins   - indices of words worth a camera push-in. About {punch_count}.
3. emphasis    - indices of individual words the speaker leans on: the ones a
                 viewer should register even with the sound off. These get a
                 larger, different typeface. Choose about {emphasis_count},
                 spread across the video, and prefer concrete nouns and
                 numbers over connecting words.

Caption grouping is handled elsewhere. Do not return captions.

Style target: the reference edit runs at {words_per_sec:.1f} words/second with a
median shot of {median_shot:.1f}s. Trim aggressiveness is {aggressiveness:.1f}
(0 = keep almost everything, 1 = cut hard).

Return ONLY JSON:
{{"cuts":[{{"from":int,"to":int,"kind":str}}],"punch_ins":[int],"emphasis":[int]}}
"from" is inclusive, "to" is EXCLUSIVE, ranges must not overlap."""


def decide(
    client: GroqClient,
    transcript: Transcript,
    profile: StyleProfile,
    punch_count: int = 4,
    emphasis_per_minute: float = 8.0,
) -> Decisions:
    max_cut_words = max(2, round(2 + 12 * profile.trim.aggressiveness))
    emphasis_count = max(2, round(emphasis_per_minute * transcript.duration / 60.0))
    system = SYSTEM.format(
        max_cut_words=max_cut_words,
        punch_count=punch_count,
        emphasis_count=emphasis_count,
        words_per_sec=(len(transcript.words) / transcript.duration) if transcript.duration else 3.0,
        median_shot=profile.pacing.median_shot,
        aggressiveness=profile.trim.aggressiveness,
    )
    payload = client.chat_json(system, f"Transcript:\n{transcript.numbered()}")
    decisions = parse_decisions(
        payload, n_words=len(transcript.words), max_cut_words=max_cut_words
    )
    # The model is asked for content words and still returns conjunctions, so
    # the choice is filtered rather than trusted.
    return dataclasses.replace(
        decisions,
        emphasis_word_indices=meaningful_emphasis(
            decisions.emphasis_word_indices, transcript.words
        ),
    )
