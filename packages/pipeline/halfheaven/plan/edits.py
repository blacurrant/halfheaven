"""Fixing individual caption cards.

Whisper mishears things, and a wrong word on screen is the most visible flaw an
auto-caption has. A correction must not re-run the pipeline: re-transcribing
would discard the very fix that prompted it. The EditProgram is the document,
so an edit patches the program and only the render repeats - which is also why
a fix takes seconds rather than the full job.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from halfheaven.plan.builder import BODY_STYLE, EMPHASIS_STYLE
from halfheaven.schemas import Caption, EditProgram, TextRun


@dataclass(frozen=True)
class CaptionEdit:
    """One change to one card, addressed as the caller saw the program."""

    index: int
    text: str | None = None
    emphasis: list[int] | None = None
    delete: bool = False


def _respace(card: Caption, words: list[str], previous: list[TextRun]) -> list[TextRun]:
    """Lay new words across the card's existing span.

    Where the word count is unchanged the original timings are kept, so a
    one-word correction does not retime the rest of the card. Otherwise the
    words are spread evenly - the card holds its place on the timeline either
    way, because moving it would desynchronise everything after it.
    """
    if len(words) == len(previous):
        return [TextRun(text=w, style=p.style, t=p.t) for w, p in zip(words, previous)]

    span = card.duration
    step = span / max(1, len(words))
    return [
        TextRun(text=word, style=BODY_STYLE, t=round(card.t + index * step, 4))
        for index, word in enumerate(words)
    ]


def _apply(card: Caption, edit: CaptionEdit) -> Caption:
    runs = list(card.runs)

    if edit.text is not None:
        words = edit.text.split()
        # A blank card is never what someone meant; deleting is the way to
        # remove one.
        if words:
            runs = _respace(card, words, runs)

    if edit.emphasis is not None:
        marked = {i for i in edit.emphasis if 0 <= i < len(runs)}
        runs = [
            run.model_copy(update={"style": EMPHASIS_STYLE if i in marked else BODY_STYLE})
            for i, run in enumerate(runs)
        ]

    return card.model_copy(update={"runs": runs, "text": None})


def apply_caption_edits(program: EditProgram, edits: list[CaptionEdit]) -> EditProgram:
    """A copy of `program` with `edits` applied.

    Indices address the program as the caller saw it, so a delete does not
    shift the target of the edits beside it.
    """
    by_index: dict[int, list[CaptionEdit]] = {}
    for edit in edits:
        by_index.setdefault(edit.index, []).append(edit)

    captions: list[Caption] = []
    for index, card in enumerate(program.captions):
        applicable = by_index.get(index, [])
        if any(e.delete for e in applicable):
            continue
        for edit in applicable:
            card = _apply(card, edit)
        captions.append(card)

    return program.model_copy(update={"captions": captions})
