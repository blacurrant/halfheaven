"""The two contracts the whole system is built around.

StyleProfile  - what analysis extracts from a reference. Content-agnostic.
EditProgram   - what planning produces for the renderer. The renderer sees
                nothing else, and no model output reaches it unvalidated.

Both are plain JSON so they can be logged, diffed, hand-edited, replayed in
tests, and later exported to FCPXML or a CapCut draft without a rewrite.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --------------------------------------------------------------------------
# EditProgram
# --------------------------------------------------------------------------


class Canvas(BaseModel):
    model_config = ConfigDict(frozen=True)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0)


class VideoClip(BaseModel):
    """One piece of source footage on the program timeline."""

    src: str
    start: float = Field(ge=0, description="source in-point, seconds")
    end: float = Field(gt=0, description="source out-point, seconds")
    scale_to: float | None = Field(
        default=None, ge=1.0, description="punch-in target scale; >=1, None means no move"
    )
    # The point the frame is centred on, as fractions of the source frame: usually
    # the speaker's face. The renderer centres its crop and its punch-in here and
    # then keeps the window inside the picture, so a subject near an edge lands
    # off-centre rather than the crop running into black. 0.5, 0.5 is the middle.
    crop_x: float = Field(default=0.5, ge=0.0, le=1.0)
    crop_y: float = Field(default=0.5, ge=0.0, le=1.0)
    ease: Literal["linear", "outCubic", "inOutCubic"] = "outCubic"

    @property
    def duration(self) -> float:
        return self.end - self.start

    @model_validator(mode="after")
    def _out_point_follows_in_point(self) -> "VideoClip":
        if self.end <= self.start:
            raise ValueError(f"clip out-point {self.end} must be after in-point {self.start}")
        return self


class TextRun(BaseModel):
    """One styled span of a caption - in practice, one word.

    `style` names an entry in EditProgram.styles, which is what lets a single
    card mix a monospace body with a large serif emphasis. `t` is the program
    time the word appears; when set on every run, the card is revealed word by
    word rather than all at once.
    """

    text: str
    style: str = "default"
    t: float | None = Field(default=None, ge=0)


class Caption(BaseModel):
    t: float = Field(ge=0, description="program time, seconds")
    duration: float = Field(gt=0)
    # `text` is the simple case; `runs` the styled one. Exactly one is required
    # and runs is what the renderer reads, so text is normalised into it.
    text: str | None = None
    runs: list[TextRun] = Field(default_factory=list)
    style: str = "default"
    anchor: tuple[float, float] = (0.5, 0.72)
    anim: Literal["none", "pop", "fade", "slide"] = "pop"
    emphasis: bool = False

    @property
    def plain_text(self) -> str:
        return " ".join(run.text for run in self.runs)

    @property
    def reveals_word_by_word(self) -> bool:
        return len(self.runs) > 1 and all(run.t is not None for run in self.runs)

    @model_validator(mode="after")
    def _normalise_runs(self) -> "Caption":
        if not self.runs:
            if not self.text:
                raise ValueError("a caption needs either text or runs")
            object.__setattr__(
                self, "runs", [TextRun(text=word, style=self.style) for word in self.text.split()]
            )
        return self


class SfxHit(BaseModel):
    t: float = Field(ge=0, description="program time, seconds")
    family: str = Field(description="whoosh | impact | riser | pop - resolved to a licensed asset")
    gain_db: float = -6.0


class MusicBed(BaseModel):
    src: str
    gain_db: float = -18.0
    duck_db: float = Field(default=-9.0, le=0.0)
    duck_attack: float = Field(default=0.08, gt=0)
    duck_release: float = Field(default=0.35, gt=0)


class Look(BaseModel):
    """The reference's appearance, applied to the whole program.

    `lut` is a path to a .cube baked from a statistical LAB match; letterbox
    percentages are of full frame height and are filled with black.
    """

    lut: str | None = None
    letterbox_top_pct: float = Field(default=0.0, ge=0.0, lt=0.5)
    letterbox_bottom_pct: float = Field(default=0.0, ge=0.0, lt=0.5)
    # A grayscale video marking the subject. When set, captions are composited
    # underneath it, so the speaker occludes the text.
    matte: str | None = None

    @property
    def is_letterboxed(self) -> bool:
        return self.letterbox_top_pct > 0.0 or self.letterbox_bottom_pct > 0.0


class EditProgram(BaseModel):
    version: int = 1
    canvas: Canvas
    video: list[VideoClip] = Field(min_length=1)
    captions: list[Caption] = Field(default_factory=list)
    sfx: list[SfxHit] = Field(default_factory=list)
    music: MusicBed | None = None
    look: Look = Field(default_factory=Look)
    # Caption.style names an entry here. Carrying the visual style inside the
    # program is what lets the renderer be a pure function of it.
    styles: dict[str, "CaptionProfile"] = Field(default_factory=dict)

    @property
    def duration(self) -> float:
        return sum(clip.duration for clip in self.video)

    @model_validator(mode="after")
    def _overlays_land_inside_the_program(self) -> "EditProgram":
        total = self.duration
        for caption in self.captions:
            if caption.t > total:
                raise ValueError(f"caption at {caption.t}s is past program end {total:.2f}s")
        for hit in self.sfx:
            if hit.t > total:
                raise ValueError(f"sfx at {hit.t}s is past program end {total:.2f}s")
        return self


# --------------------------------------------------------------------------
# StyleProfile
# --------------------------------------------------------------------------


class PacingProfile(BaseModel):
    shot_count: int = 0
    median_shot: float = 0.0
    p10_shot: float = 0.0
    p90_shot: float = 0.0
    cuts_per_min: float = 0.0


class TrimProfile(BaseModel):
    """Only meaningful for speech-driven references."""

    max_silence: float = 0.20
    remove_filler: bool = True
    # how eagerly to cut discourse markers ("so", "like"); a taste dial, not a
    # correctness one, which is why it lives in the profile and not the prompt.
    aggressiveness: float = Field(default=0.5, ge=0.0, le=1.0)


class PunchProfile(BaseModel):
    rate: float = Field(default=0.0, ge=0.0, le=1.0, description="fraction of cuts with a punch-in")
    # How much the framing changes between segments. A single-camera talking
    # head has no cuts to inherit, so the reframe has to supply the rhythm.
    variety: float = Field(default=0.7, ge=0.0, le=1.0)
    scale_mean: float = Field(default=1.15, ge=1.0)
    ease: Literal["linear", "outCubic", "inOutCubic"] = "outCubic"


class CaptionProfile(BaseModel):
    """How captions look, as independent axes rather than named styles.

    Every look creators name is a combination of these: Hormozi is
    phrase + karaoke + pop + colour-active + heavy stroke in a black grotesque;
    MrBeast is single + instant + hard shadow; a documentary caption is
    phrase + append + no enter + thin stroke in mono. Building the axes rather
    than the looks means a new style is a few fields, not a new renderer.
    """

    present: bool = False
    # A type category, not a typeface: identifying a specific font from pixels
    # is unreliable, so we match character using faces we may embed.
    font_category: str = "grotesque"
    # A specific shipped face, when the reference's character was measured
    # closely enough to choose one. Wins over font_category, which stays the
    # fallback for a missing file and for programs written before it existed.
    font_file: str | None = None
    font_weight: int = 800

    # how many words share a card
    grouping: Literal["single", "phrase", "rolling"] = "phrase"
    max_words: int = Field(default=3, ge=1)

    # how the words of a card arrive
    reveal: Literal["instant", "append", "karaoke"] = "append"

    # how each word enters
    enter: Literal["none", "pop", "slide", "fade"] = "pop"
    pop_from: float = Field(default=0.82, gt=0, le=1)
    enter_ms: int = Field(default=110, ge=0)

    # how the word being spoken is marked
    active: Literal["none", "colour", "scale", "marker"] = "none"
    active_fill_hex: str = "#FFE94A"
    active_scale: float = Field(default=1.18, ge=1.0, le=2.0)
    active_box_hex: str = "#22C55E"

    # how the text sits on the footage
    decor: Literal["stroke", "shadow_soft", "shadow_hard", "box", "pill", "none"] = "stroke"
    stroke_hex: str = "#000000"
    stroke_heavy: bool = True
    shadow_hex: str = "#000000"
    shadow_offset_pct: float = Field(default=0.07, ge=0, le=0.4)
    box_hex: str = "#000000"
    box_alpha: float = Field(default=0.6, ge=0, le=1)
    box_radius_pct: float = Field(default=0.22, ge=0, le=0.5)

    layout: Literal["flow", "stack"] = "flow"

    anchor: tuple[float, float] = (0.5, 0.72)
    size_pct: float = Field(default=0.06, gt=0, description="cap height as fraction of frame height")
    fill_hex: str = "#FFFFFF"
    all_caps: bool = False


class SfxProfile(BaseModel):
    rate_at_cuts: float = Field(default=0.0, ge=0.0, le=1.0)
    families: list[str] = Field(default_factory=list)


class MusicProfile(BaseModel):
    present: bool = False
    gain_db: float = -18.0
    duck_db: float = -9.0


class GradeProfile(BaseModel):
    """Measured LAB statistics of the reference's content band."""

    measured: bool = False
    lab_mean: tuple[float, float, float] = (50.0, 0.0, 0.0)
    lab_std: tuple[float, float, float] = (20.0, 10.0, 10.0)
    # How hard to push the target toward the reference. Full strength can turn
    # bright footage muddy, so this is a dial rather than a constant.
    strength: float = Field(default=0.7, ge=0.0, le=1.0)


class FramingProfile(BaseModel):
    letterbox_top_pct: float = Field(default=0.0, ge=0.0, lt=0.5)
    letterbox_bottom_pct: float = Field(default=0.0, ge=0.0, lt=0.5)


class TypePlan(BaseModel):
    """How the reference uses type across the edit, beyond how one card looks.

    Measured by the fingerprint and carried here so the planner can act on it:
    how much of the runtime carries type, whether it stays put or moves around
    the frame, and how often a word breaks into the accent colour.
    """

    duty_cycle: float = Field(default=1.0, ge=0.0, le=1.0)
    placement: Literal["fixed", "banded", "composed"] = "fixed"
    centroid: tuple[float, float] = (0.5, 0.72)
    spread: float = Field(default=0.0, ge=0.0)
    accent_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class StyleProfile(BaseModel):
    """Everything we recovered from a reference video, content-agnostic."""

    version: int = 1
    source: str = ""
    # which cut engine this profile drives: speech-driven (talking head) or
    # rhythm-driven (b-roll montage). Set from whether the reference has speech.
    kind: Literal["speech", "montage"] = "montage"
    has_audio: bool = False
    pacing: PacingProfile = Field(default_factory=PacingProfile)
    trim: TrimProfile = Field(default_factory=TrimProfile)
    punch: PunchProfile = Field(default_factory=PunchProfile)
    captions: CaptionProfile = Field(default_factory=CaptionProfile)
    # The face used for single stressed words. The reference pairs a monospace
    # body with a large high-contrast serif; this is that second system.
    emphasis: CaptionProfile = Field(
        default_factory=lambda: CaptionProfile(
            present=True, font_category="didone", size_pct=0.13, all_caps=True
        )
    )
    sfx: SfxProfile = Field(default_factory=SfxProfile)
    music: MusicProfile = Field(default_factory=MusicProfile)
    grade: GradeProfile = Field(default_factory=GradeProfile)
    framing: FramingProfile = Field(default_factory=FramingProfile)
    type_plan: TypePlan | None = None


EditProgram.model_rebuild()
