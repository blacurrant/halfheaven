"""Reference video -> StyleProfile.

Geometry and colour are measured with OpenCV; only semantic attributes (casing,
words per card, animation) are asked of the vision model, which a live probe
showed to be accurate about style and unreliable about position.
"""
from __future__ import annotations

import pathlib

from halfheaven.analyze.framing import detect_letterbox
from halfheaven.analyze.grade import measure_color_stats
from halfheaven.analyze.shots import detect_shots, pacing
from halfheaven.analyze.text_regions import detect_persistent_caption
from halfheaven.groq.client import GroqClient
from halfheaven.media.probe import probe
from halfheaven.render.video import extract_frame
from halfheaven.media.audio import extract_audio
from halfheaven.schemas import (
    CaptionProfile,
    FramingProfile,
    GradeProfile,
    PacingProfile,
    StyleProfile,
    TrimProfile,
)

VISION_PROMPT = """You are looking at one frame of a short-form vertical video that has a
burned-in caption. Describe only the caption's STYLE. Return ONLY JSON:
{"all_caps": bool, "words_per_card": int, "mode": "word_by_word"|"phrase"|"static_title",
 "anim": "none"|"pop"|"fade"|"slide", "stroke_heavy": bool}
Do not report positions or coordinates."""


def build_style_profile(
    video: str | pathlib.Path,
    client: GroqClient | None = None,
    work_dir: pathlib.Path | None = None,
) -> StyleProfile:
    video = pathlib.Path(video)
    info = probe(video)
    shots = detect_shots(video)
    measured = pacing(shots)

    profile = StyleProfile(
        source=video.name,
        has_audio=info.has_audio,
        kind="speech" if info.has_audio else "montage",
        pacing=PacingProfile(
            shot_count=measured.shot_count,
            median_shot=measured.median_shot,
            p10_shot=measured.p10_shot,
            p90_shot=measured.p90_shot,
            cuts_per_min=measured.cuts_per_min,
        ),
    )

    # Framing first: colour statistics sampled through letterbox bars would
    # darken every grade derived from this reference.
    framing = detect_letterbox(video)
    stats = measure_color_stats(video, framing=framing)
    profile = profile.model_copy(
        update={
            "framing": FramingProfile(
                letterbox_top_pct=framing.top_pct,
                letterbox_bottom_pct=framing.bottom_pct,
            ),
            "grade": GradeProfile(measured=True, lab_mean=stats.mean, lab_std=stats.std),
        }
    )

    # How long a pause the reference tolerates is part of its style, so measure
    # it rather than defaulting. p90 of its own inter-word gaps: most pauses sit
    # below it, and the tail is deliberate breathing room.
    if info.has_audio and client is not None and work_dir is not None:
        try:
            reference_words = client.transcribe(
                extract_audio(video, work_dir / "reference.wav")
            ).words
            gaps = sorted(
                max(0.0, b.start - a.end)
                for a, b in zip(reference_words, reference_words[1:])
            )
            if gaps:
                p90 = gaps[min(len(gaps) - 1, int(0.9 * len(gaps)))]
                profile = profile.model_copy(
                    update={"trim": TrimProfile(max_silence=round(max(0.10, p90), 3))}
                )
        except Exception:
            pass  # the default trim policy is still workable

    band = detect_persistent_caption(video)
    if band is None:
        return profile

    captions = CaptionProfile(
        present=True,
        mode="phrase",
        anchor=(round(band.center_x_pct, 3), round(band.center_y_pct, 3)),
        size_pct=round(band.height_pct, 4),
        fill_hex=band.fill_hex,
    )

    # Semantic attributes only; the numbers above are measured, not asked for.
    if client is not None and work_dir is not None:
        frame = extract_frame(video, info.duration * 0.5, work_dir / "style_frame.png")
        try:
            style = client.vision_json(VISION_PROMPT, [frame])
            captions = captions.model_copy(
                update={
                    "all_caps": bool(style.get("all_caps", False)),
                    "max_words": max(1, int(style.get("words_per_card", 4))),
                    "mode": style.get("mode", "phrase"),
                    "anim": style.get("anim", "pop"),
                    "stroke_heavy": bool(style.get("stroke_heavy", True)),
                }
            )
        except Exception:
            pass  # measured geometry is still usable without the semantic pass

    return profile.model_copy(update={"captions": captions})
