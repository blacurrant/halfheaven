"""What a reference's on-screen text says, where it sits, and what colour it is.

The fingerprint finds type by its shape - bright or saturated marks sitting in
rows. On a reference shot against a white brick wall in a red floral dress,
the bricks and the print pass that test as well as the captions do: it read the
wall as the caption fill and the dress as the accent colour, and put the type
in the middle of the frame when every word of it sat in the top quarter.
Pixel stability cannot separate them either - a wall on a tripod holds as
still as an overlay.

What separates text from scenery is that it reads as words. A text detector
answers that directly, and reading the words answers the question the rest of
the pipeline needs most: whether the reference's text is what was *said* (a
caption track) or something an editor *wrote* (a title, a numbered list).

Optional: without the `ocr` extra every function here reports "unavailable"
and the pipeline keeps its pixel-only measurements.
"""
from __future__ import annotations

import difflib
import logging
import pathlib
import re
from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np

# Text lasts at least a second on screen in any edit meant to be read, so two
# looks a second are enough to catch every card, at ~150ms a look.
SAMPLE_EVERY = 0.5
# Below this the recogniser is guessing, and what it guesses at is usually
# texture - a floral print, an eye - rather than type.
READ_SCORE = 0.6
# How alike two looks' text must be to count as the same card. Loose, because
# the recogniser drops a character here and there between frames.
SAME_CARD = 0.6


@dataclass(frozen=True)
class TextLine:
    text: str
    box: tuple[float, float, float, float]    # x0, y0, x1, y1 as frame fractions
    fill_hex: str
    score: float

    @property
    def height_pct(self) -> float:
        return self.box[3] - self.box[1]

    @property
    def centre(self) -> tuple[float, float]:
        return ((self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2)


@dataclass
class TextEvent:
    """One card: the same text held on screen from `start` to `end`."""

    start: float
    end: float
    lines: list[TextLine] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines)


def available() -> bool:
    try:
        import rapidocr  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _engine():
    from rapidocr import RapidOCR

    engine = RapidOCR(params={"Global.text_score": 0.3, "Global.use_cls": False})
    # It warns on every frame with no text, which is most frames of most reels.
    # Set after construction, which resets the level.
    logging.getLogger("RapidOCR").setLevel(logging.ERROR)
    return engine


def _fill(frame: np.ndarray, box: tuple[int, int, int, int]) -> str:
    """The colour the letters are filled with.

    Inside a text box are three things: the fill, its outline or shadow, and
    whatever the text sits on. The ground is what surrounds the box; of the
    colours inside, the fill is the commonest one that is neither that ground
    nor near-black (an outline is almost always black).
    """
    x0, y0, x1, y1 = box
    h, w = frame.shape[:2]
    inner = frame[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32)
    if len(inner) < 30:
        return "#FFFFFF"
    pad = max(3, (y1 - y0) // 3)
    outer = frame[max(0, y0 - pad):min(h, y1 + pad), max(0, x0 - pad):min(w, x1 + pad)].copy()
    outer[pad:pad + (y1 - y0), pad:pad + (x1 - x0)] = 0
    ring = outer.reshape(-1, 3)
    ring = ring[ring.sum(1) > 0]

    lab = cv2.cvtColor(inner.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB).reshape(-1, 3)
    lab = lab.astype(np.float32)
    _, labels, centres = cv2.kmeans(lab, 4, None,
                                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0),
                                    3, cv2.KMEANS_PP_CENTERS)
    ground = None
    if len(ring):
        ring_lab = cv2.cvtColor(ring.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3)
        ground = np.median(ring_lab.astype(np.float32), 0)

    counts = np.bincount(labels.reshape(-1), minlength=4)
    best, best_count = None, -1
    for k in range(4):
        centre = centres[k]
        if centre[0] < 60:                      # outline or drop shadow (L of 255)
            continue
        if ground is not None and np.linalg.norm(centre - ground) < 30:
            continue
        if counts[k] > best_count:
            best, best_count = k, counts[k]
    if best is None:
        best = int(counts.argmax())
    pixels = inner[labels.reshape(-1) == best]
    b, g, r = (int(v) for v in np.median(pixels, 0))
    return f"#{r:02X}{g:02X}{b:02X}"


def read_frame(frame: np.ndarray) -> list[TextLine]:
    """Every line of text in one frame, top to bottom."""
    result = _engine()(frame)
    if result.boxes is None:
        return []
    h, w = frame.shape[:2]
    lines = []
    for text, score, quad in zip(result.txts, result.scores, result.boxes):
        quad = np.asarray(quad)
        x0, y0 = np.clip(quad.min(0), 0, [w, h]).astype(int)
        x1, y1 = np.clip(quad.max(0), 0, [w, h]).astype(int)
        # A box that reads as no words is a patterned shirt or a face, not
        # type: the detector finds texture, the recogniser finds nothing in it.
        if x1 - x0 < 4 or y1 - y0 < 4 or score < READ_SCORE or not words_of(text, 1):
            continue
        lines.append(TextLine(
            text=text.strip(),
            box=(x0 / w, y0 / h, x1 / w, y1 / h),
            fill_hex=_fill(frame, (x0, y0, x1, y1)),
            score=float(score),
        ))
    return sorted(lines, key=lambda line: line.box[1])


def _key(lines: list[TextLine]) -> str:
    return re.sub(r"[^a-z0-9]+", "", " ".join(line.text for line in lines).lower())


def read_text(video: str | pathlib.Path, every: float = SAMPLE_EVERY) -> list[TextEvent] | None:
    """The reference's text as timed cards, or None when no reader is installed."""
    if not available():
        return None
    capture = cv2.VideoCapture(str(video))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(every * fps))
    looks: list[tuple[float, list[TextLine]]] = []
    index = 0
    try:
        while True:
            ok = capture.grab()
            if not ok:
                break
            if index % step == 0:
                ok, frame = capture.retrieve()
                if ok:
                    looks.append((index / fps, read_frame(frame)))
            index += 1
    finally:
        capture.release()
    return group(looks, every)


def group(looks: list[tuple[float, list[TextLine]]], every: float) -> list[TextEvent]:
    """Consecutive looks at the same text, joined into one card."""
    events: list[TextEvent] = []
    for t, lines in looks:
        if not lines:
            continue
        key = _key(lines)
        last = events[-1] if events else None
        # The same card continues when the text matches the last look and
        # there was no gap. A card revealing a line at a time also continues:
        # its earlier text is a prefix of the fuller version.
        if last is not None and t - last.end <= every * 1.5:
            previous = _key(last.lines)
            similar = difflib.SequenceMatcher(None, previous, key).ratio() >= SAME_CARD
            matcher = difflib.SequenceMatcher(None, previous, key)
            kept = sum(block.size for block in matcher.get_matching_blocks())
            growing = bool(previous) and kept >= 0.6 * len(previous)
            if similar or growing:
                last.end = t + every
                if len(key) > len(previous):      # keep the fullest look of the card
                    last.lines = lines
                continue
        events.append(TextEvent(start=t, end=t + every, lines=lines))
    return events


def words_of(text: str, shortest: int = 3) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()) if len(w) >= shortest]


# Share of what was said that a caption track puts on screen as it is said.
# A caption reel shows most of it; titles and lists echo a few key words.
CAPTION_COVERAGE = 0.5


def coverage(events: list[TextEvent], spoken: list[tuple[str, float]],
             window: float = 1.0) -> float:
    """Share of spoken words shown on screen while they were being said.

    Asked this way round because the other way misleads: a numbered list's
    headings are mostly words the speaker also says ("proof of skill"), so
    "was the shown text spoken?" answers yes for a list. What a list does not
    do is show *everything* said.
    """
    heard = [(w, t) for text, t in spoken for w in words_of(text)]
    if not heard:
        return 0.0
    shown = 0
    for word, t in heard:
        if any(event.start - window <= t <= event.end + window and word in words_of(event.text)
               for event in events):
            shown += 1
    return shown / len(heard)


def text_kind(events: list[TextEvent], spoken: list[tuple[str, float]]) -> str:
    """Whether the reference's text is a caption of its speech, or written.

    "spoken"    most of what was said is on screen as it is said
    "authored"  text is on screen, but it is not a transcript
    "none"      no readable text
    """
    if sum(len(words_of(e.text)) for e in events) < 3:
        return "none"
    if spoken and coverage(events, spoken) >= CAPTION_COVERAGE:
        return "spoken"
    return "authored" if spoken else "spoken"


def text_mask(lines: list[TextLine], shape: tuple[int, int], pad: float = 0.25) -> np.ndarray:
    """1 inside every text box (grown by `pad` of its height), 0 elsewhere."""
    h, w = shape
    mask = np.zeros((h, w), np.uint8)
    for line in lines:
        x0, y0, x1, y1 = line.box
        grow = (y1 - y0) * pad
        mask[max(0, int((y0 - grow) * h)):min(h, int((y1 + grow) * h) + 1),
             max(0, int((x0 - grow) * w)):min(w, int((x1 + grow) * w) + 1)] = 1
    return mask
