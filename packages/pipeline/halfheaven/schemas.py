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
    ease: Literal["linear", "outCubic", "inOutCubic"] = "outCubic"

    @property
    def duration(self) -> float:
        return self.end - self.start

    @model_validator(mode="after")
    def _out_point_follows_in_point(self) -> "VideoClip":
        if self.end <= self.start:
            raise ValueError(f"clip out-point {self.end} must be after in-point {self.start}")
        return self


class Caption(BaseModel):
    t: float = Field(ge=0, description="program time, seconds")
    duration: float = Field(gt=0)
    text: str
    style: str = "default"
    anchor: tuple[float, float] = (0.5, 0.72)
    anim: Literal["none", "pop", "fade", "slide"] = "pop"
    emphasis: bool = False


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
    scale_mean: float = Field(default=1.15, ge=1.0)
    ease: Literal["linear", "outCubic", "inOutCubic"] = "outCubic"


class CaptionProfile(BaseModel):
    present: bool = False
    mode: Literal["none", "word_by_word", "phrase", "static_title"] = "none"
    anchor: tuple[float, float] = (0.5, 0.72)
    size_pct: float = Field(default=0.06, gt=0, description="cap height as fraction of frame height")
    fill_hex: str = "#FFFFFF"
    stroke_hex: str = "#000000"
    stroke_heavy: bool = True
    all_caps: bool = False
    max_words: int = Field(default=3, ge=1)
    anim: Literal["none", "pop", "fade", "slide"] = "pop"


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
    sfx: SfxProfile = Field(default_factory=SfxProfile)
    music: MusicProfile = Field(default_factory=MusicProfile)
    grade: GradeProfile = Field(default_factory=GradeProfile)
    framing: FramingProfile = Field(default_factory=FramingProfile)


EditProgram.model_rebuild()
