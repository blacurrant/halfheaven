"""Text an editor writes, for references whose text is not a transcript.

A caption reel puts what was said on screen. A listicle does something else: a
hook title, then a short numbered heading held for each point while the
speaker talks it through. Copying the second kind as the first turned a
four-card list into seventy-nine flashing word captions - the style was matched
and the edit was not.

So when the reference's text is written rather than spoken, the new clip gets
written text too: the reference's cards are read for their shape (a title of
how many lines, numbered or not, a smaller line under each heading) and their
look (fill, size, where the block sits), a model writes the equivalent cards
for what this speaker actually says, and each card is held from the word where
its point begins until the next one does.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable

from halfheaven.analyze.onscreen_text import TextEvent, TextLine
from halfheaven.groq.asr import Transcript
from halfheaven.plan.timeline import Timeline
from halfheaven.plan.transcript import kept_spans
from halfheaven.schemas import Caption, CaptionProfile, StyleProfile, TextRun, VideoClip

NUMBERED = re.compile(r"^\s*\d+\s*[).:\-]")
# A title opens the reel; a card that first shows after this share of the
# runtime is part of the body, whatever it looks like.
TITLE_BY = 0.25
# Shorter than this and a card was a flash - a sticker or a transition - not
# a title or a heading anyone was meant to read.
MIN_CARD = 1.0
# Rendered font size over the height of the box a reader draws round a line.
BOX_TO_SIZE = 1 / 1.15
# A sub-line is set this much smaller than the heading when the reference had
# none to measure.
SUB_RATIO = 0.65
MIN_TITLE_HOLD = 2.5
GAP = 0.25
LINE_BREAK = "\n"
MAX_POINTS = 6
MAX_HEADING_WORDS = 6
MAX_TITLE_WORDS = 9


@dataclass
class CardTemplate:
    """The shape and look of a reference's written text."""

    title: list[TextLine] | None
    heading: list[TextLine]           # main lines of a representative card
    sub: TextLine | None              # its smaller supporting line
    numbered: bool
    examples: list[str] = field(default_factory=list)
    centre_y: float = 0.22
    hold: float = 4.0                 # median seconds a heading stays up


def _is_sub(line: TextLine, tallest: float) -> bool:
    return line.text.lstrip().startswith("(") or line.height_pct < 0.75 * tallest


def template_from(events: list[TextEvent], duration: float) -> CardTemplate | None:
    """What the reference's cards look like, or None when it has none worth copying."""
    cards = [e for e in events if e.end - e.start >= MIN_CARD and e.lines]
    if not cards:
        return None
    title = None
    first = cards[0]
    if first.start <= TITLE_BY * duration and not NUMBERED.match(first.lines[0].text):
        title, cards = first, cards[1:]
    headings = cards or ([title] if title else [])
    if not headings:
        return None
    # The card with the most lines shows every part a heading can have.
    fullest = max(headings, key=lambda e: len(e.lines))
    tallest = max(line.height_pct for line in fullest.lines)
    main = [line for line in fullest.lines if not _is_sub(line, tallest)] or fullest.lines[:1]
    subs = [line for line in fullest.lines if _is_sub(line, tallest)]
    everything = [line for e in headings for line in e.lines]
    return CardTemplate(
        title=title.lines if title else None,
        heading=main,
        sub=subs[0] if subs else None,
        numbered=sum(bool(NUMBERED.match(e.lines[0].text)) for e in headings) * 2 >= len(headings),
        examples=[" / ".join(line.text for line in e.lines) for e in ([title] if title else []) + headings],
        centre_y=statistics.median(line.centre[1] for line in everything),
        hold=statistics.median(e.end - e.start for e in headings),
    )


# --------------------------------------------------------------------------
# writing the cards
# --------------------------------------------------------------------------

SYSTEM = """You write the on-screen text for a short vertical talking-head video, the way
its editor would: a hook title at the start, then one short heading for each point
the speaker makes, held on screen while they talk it through.

A reference reel shows the format to copy. Match its shape and tone, not its topic:
write about what THIS speaker says, and never invent a point they do not make.

The transcript is machine-heard and may be Hinglish spelled phonetically; understand
what was meant and write clean, correctly spelled English. No profanity, even if the
speaker uses it.

Return ONLY JSON:
{{"title": [lines of the hook title, {title_lines} lines, at most {title_words} words in total],
 "points": [{{"at": index of the word where this point begins,
             "text": "heading, at most {heading_words} words",
             "sub": "a short supporting line, or null"}}]}}

Rules:
- {count_rule}
- "at" values are word indices from the transcript, in increasing order.
- {number_rule}
- {sub_rule}
- {title_rule}"""


def _prompt(template: CardTemplate, transcript: Transcript) -> tuple[str, str]:
    title_lines = len(template.title) if template.title else 0
    system = SYSTEM.format(
        title_lines=max(1, title_lines),
        title_words=MAX_TITLE_WORDS,
        heading_words=MAX_HEADING_WORDS,
        count_rule=(f"Between 2 and {MAX_POINTS} points: one per distinct idea or step the "
                    "speaker actually gives, in the order they give them."),
        number_rule=("Number each heading like the reference does, \"1) ...\", \"2) ...\"."
                     if template.numbered else "Do not number the headings."),
        sub_rule=("Give each heading a short sub line in brackets, as the reference does, "
                  "when the speaker gives a detail worth it; otherwise null."
                  if template.sub else "Always set \"sub\" to null."),
        title_rule=("Write the title as a hook for the whole video."
                    if template.title else "Return an empty title list."),
    )
    user = ("Reference reel's on-screen text, card by card:\n"
            + "\n".join(f"- {example}" for example in template.examples)
            + f"\n\nTranscript of the new video:\n{transcript.numbered()}")
    return system, user


@dataclass(frozen=True)
class Point:
    at: int
    text: str
    sub: str | None = None


@dataclass(frozen=True)
class Cards:
    title: list[str]
    points: list[Point]


def _clean(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    words = text.split()
    return " ".join(words[:limit])


def parse_cards(payload: dict[str, Any], n_words: int) -> Cards:
    """Model output, validated. Unusable points are dropped, never repaired."""
    title_lines = [_clean(line, MAX_TITLE_WORDS) for line in payload.get("title") or []
                   if isinstance(line, str)]
    title_lines = [line for line in title_lines if line][:4]
    points: list[Point] = []
    for entry in payload.get("points") or []:
        if not isinstance(entry, dict):
            continue
        try:
            at = int(entry.get("at"))
        except (TypeError, ValueError):
            continue
        text = _clean(entry.get("text"), MAX_HEADING_WORDS + 1)
        if not (0 <= at < n_words) or not text:
            continue
        if points and at <= points[-1].at:
            continue
        sub = _clean(entry.get("sub"), MAX_HEADING_WORDS + 2) or None
        points.append(Point(at=at, text=text, sub=sub))
    return Cards(title=title_lines, points=points[:MAX_POINTS])


def write_cards(client, template: CardTemplate, transcript: Transcript) -> Cards:
    system, user = _prompt(template, transcript)
    return parse_cards(client.chat_json(system, user, temperature=0.3), len(transcript.words))


# --------------------------------------------------------------------------
# setting them on the timeline
# --------------------------------------------------------------------------


def _style(line: TextLine, base: CaptionProfile, *, face: str | None, weight: int,
           size: float | None = None) -> CaptionProfile:
    letters = [c for c in line.text if c.isalpha()]
    return base.model_copy(update={
        "present": True,
        "font_file": face,
        "font_weight": weight,
        "size_pct": round(size or line.height_pct * BOX_TO_SIZE, 4),
        "fill_hex": line.fill_hex,
        "all_caps": bool(letters) and sum(c.isupper() for c in letters) > 0.8 * len(letters),
        "decor": "stroke",
        "stroke_hex": "#000000",
        "stroke_heavy": True,
        "reveal": "instant",
        "layout": "flow",
    })


def card_styles(template: CardTemplate, profile: StyleProfile) -> dict[str, CaptionProfile]:
    """One named style per kind of line, each in the reference's own colour and size.

    The face is the one the fingerprint matched to the reference's type. A title
    line set in lowercase between capitals is the reference changing voice, so
    it takes the stressed-word face, as a stressed word does.
    """
    body, stressed = profile.captions, profile.emphasis
    styles: dict[str, CaptionProfile] = {}
    for index, line in enumerate(template.title or []):
        style = _style(line, body, face=body.font_file, weight=900)
        if index and not style.all_caps and stressed.font_file:
            style = _style(line, stressed, face=stressed.font_file, weight=stressed.font_weight)
        styles[f"title_{index}"] = style
    head = template.heading[0]
    styles["heading"] = _style(head, body, face=body.font_file, weight=900)
    if template.sub:
        styles["sub"] = _style(template.sub, body, face=body.font_file, weight=700)
    else:
        styles["sub"] = _style(head, body, face=body.font_file, weight=700,
                               size=head.height_pct * BOX_TO_SIZE * SUB_RATIO)
        styles["sub"] = styles["sub"].model_copy(update={"all_caps": False})
    return styles


def _runs(parts: list[tuple[str, str]], t: float) -> list[TextRun]:
    runs: list[TextRun] = []
    for text, style in parts:
        if runs:
            runs.append(TextRun(text=LINE_BREAK, style=style, t=t))
        runs.append(TextRun(text=text, style=style, t=t))
    return runs


def _block_height(parts: list[tuple[str, str]], styles: dict[str, CaptionProfile]) -> float:
    # Lines wrap on a phone-width frame; two lines each is a fair allowance
    # for a heading, and what matters is only clearing the face.
    return sum(styles[style].size_pct * 1.18 * (2 if len(text) > 18 else 1)
               for text, style in parts)


# Samples per card when looking for the face it must stay off.
FACE_LOOKS = 3


def face_finder(video: list[VideoClip], canvas) -> Callable[[float, float], tuple[float, float] | None]:
    """Where the eyes and mouth are in the *output* frame over a stretch of program time.

    The builder's estimate assumes a talking head at medium distance, and on a
    phone selfie - a face filling most of the frame - it put a heading straight
    across the eyes. So the face is found in the footage and carried through
    the same crop and zoom the renderer applies. Returns (top, bottom) of the
    band from brows to lower lip as frame fractions, or None if no face seen.
    """
    import cv2

    from halfheaven.analyze.subject import default_detector
    from halfheaven.render.video import _placement, _source_size

    detector = default_detector()
    captures: dict[str, Any] = {}

    def at(t: float) -> tuple[VideoClip, float] | None:
        elapsed = 0.0
        for clip in video:
            length = clip.end - clip.start
            if t < elapsed + length:
                return clip, clip.start + (t - elapsed)
            elapsed += length
        return None

    def to_output(clip: VideoClip, y: float) -> float:
        size = _source_size(str(clip.src))
        cover_h = canvas.height
        if size:
            cover = max(canvas.width / size[0], canvas.height / size[1])
            cover_h = max(canvas.height, 2 * -(-size[1] * cover // 2))
        top, inside = _placement(int(cover_h), canvas.height, clip.crop_y)
        y = (y * cover_h - top) / canvas.height
        zoom = clip.scale_to or 1.0
        if zoom > 1.0:
            window = min(max(inside - 0.5 / zoom, 0.0), 1.0 - 1.0 / zoom)
            y = (y - window) * zoom
        return y

    def find(start: float, end: float) -> tuple[float, float] | None:
        if detector is None:
            return None
        spans = []
        for k in range(FACE_LOOKS):
            found = at(start + (end - start) * (k + 0.5) / FACE_LOOKS)
            if found is None:
                continue
            clip, source_t = found
            capture = captures.get(clip.src) or captures.setdefault(clip.src, cv2.VideoCapture(clip.src))
            capture.set(cv2.CAP_PROP_POS_MSEC, source_t * 1000)
            ok, frame = capture.read()
            faces = detector.faces(frame) if ok else []
            if not faces:
                continue
            face = max(faces, key=lambda f: f.height)
            # Brows to lower lip: a little above the eyes, a little below the mouth.
            eyes = face.eyes_y if face.eyes_y is not None else face.y - 0.15 * face.height
            mouth = face.mouth_y if face.mouth_y is not None else face.y + 0.25 * face.height
            spans.append((to_output(clip, eyes - 0.12 * face.height),
                          to_output(clip, mouth + 0.08 * face.height)))
        if not spans:
            return None
        # The median look, not the union: a speaker who leans in and out over
        # a long card would otherwise claim the whole frame.
        return (float(statistics.median(a for a, _ in spans)),
                float(statistics.median(b for _, b in spans)))

    return find


def _place(centre: float, half: float, face: tuple[float, float] | None) -> float:
    """The block's centre: where the reference put it, unless that covers the face.

    Above the face first, where the reference's type sat; below the chin when
    there is no room above. Over hair or forehead is acceptable, over the eyes
    never - so when neither fits, the block rides as high as it can.
    """
    edge = 0.04
    if face is not None:
        top, bottom = face
        if centre + half > top and centre - half < bottom:
            if top - 0.015 - 2 * half >= edge:
                centre = top - 0.015 - half
            elif bottom + 0.02 + 2 * half <= 1 - edge:
                centre = bottom + 0.02 + half
            else:
                centre = edge + half
    return min(max(centre, edge + half), 1 - edge - half)


def card_captions(cards: Cards, template: CardTemplate, styles: dict[str, CaptionProfile],
                  transcript: Transcript, cuts: list[tuple[int, int]], max_silence: float,
                  video: list[VideoClip], program_end: float,
                  face: Callable[[float, float], tuple[float, float] | None] | None = None,
                  ) -> list[Caption]:
    """The written cards, timed to the words they introduce and kept off the face."""
    from halfheaven.plan.builder import _is_cut

    timeline = Timeline(kept_spans(transcript.words, cuts, max_silence=max_silence))

    def starts(index: int) -> float | None:
        # A point whose first word was cut begins at the next word that stayed.
        for k in range(index, len(transcript.words)):
            if not _is_cut(k, cuts):
                t = timeline.to_program(transcript.words[k].start)
                if t is not None:
                    return t
        return None

    timed = [(t, point) for point in cards.points if (t := starts(point.at)) is not None]
    blocks: list[tuple[float, list[tuple[str, str]]]] = []
    if cards.title and template.title:
        title_parts = [(line, f"title_{min(i, len(template.title) - 1)}")
                       for i, line in enumerate(cards.title)]
        blocks.append((0.0, title_parts))
        # A title needs time to be read; a first point that starts too soon
        # waits for it.
        timed = [(max(t, MIN_TITLE_HOLD), point) for t, point in timed]
    for t, point in timed:
        parts = [(point.text, "heading")]
        if point.sub:
            parts.append((point.sub, "sub"))
        blocks.append((t, parts))

    captions: list[Caption] = []
    for index, (t, parts) in enumerate(blocks):
        following = blocks[index + 1][0] if index + 1 < len(blocks) else None
        # The last card stays about as long as the others did, not to the end:
        # a reference's list stops, and its close plays out clean.
        end = following - GAP if following is not None else min(program_end, t + 3 * template.hold)
        if end - t < 0.5:
            continue
        half = _block_height(parts, styles) / 2
        y = _place(template.centre_y, half, face(t, end) if face else None)
        captions.append(Caption(t=t, duration=end - t, runs=_runs(parts, t),
                                style=parts[0][1], anchor=(0.5, round(y, 4)), anim="pop"))
    return captions
