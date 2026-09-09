"""Subject mattes.

A `Segmenter` returns a per-frame alpha mask. Which model produces it - SAM2,
RVM, MediaPipe - is that object's business and nothing else's, so the renderer
and its tests never depend on a multi-gigabyte checkpoint.

The matte is written as an ordinary grayscale video, which lets ffmpeg do the
compositing with alphamerge rather than us pushing frames through Python.
"""
from __future__ import annotations

import pathlib
from typing import Protocol

import cv2
import numpy as np


class FrameSegmenter(Protocol):
    """Judges each frame independently. Cheap, and prone to temporal flicker."""

    def mask_for(self, frame: np.ndarray) -> np.ndarray:
        """A HxW uint8 mask for one BGR frame: 255 subject, 0 background."""


class VideoSegmenter(Protocol):
    """Sees the whole clip. What a model with temporal memory, like SAM2, needs.

    Asking such a model for one frame at a time would throw away the very thing
    that makes it worth its cost, so it is handed the clip and yields masks in
    order.
    """

    def masks_for_video(self, video: pathlib.Path, size: tuple[int, int]):
        """Yield one HxW uint8 mask per frame, in order."""


def write_matte_video(
    video: str | pathlib.Path,
    segmenter: FrameSegmenter | VideoSegmenter,
    out_path: str | pathlib.Path,
    feather: int = 5,
) -> pathlib.Path:
    """Run `segmenter` over every frame and write the masks as a video.

    `feather` blurs the mask edge. A hard binary edge reads as a paper cutout
    where text passes behind hair or a shoulder; a few pixels of falloff is the
    difference between a composite and a collage.
    """
    video, out_path = pathlib.Path(video), pathlib.Path(out_path)
    capture = cv2.VideoCapture(str(video))
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height), isColor=True
        )
        # A video-native model is handed the clip once; a per-frame one is
        # asked frame by frame.
        stream = (
            segmenter.masks_for_video(video, (width, height))
            if hasattr(segmenter, "masks_for_video")
            else None
        )
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if stream is not None:
                    try:
                        mask = next(stream)
                    except StopIteration:
                        break
                else:
                    mask = segmenter.mask_for(frame)
                if mask.shape[:2] != (height, width):
                    mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_LINEAR)
                if feather > 0:
                    radius = feather * 2 + 1
                    mask = cv2.GaussianBlur(mask, (radius, radius), 0)
                # alphamerge reads the luma plane, so write the mask as gray BGR
                writer.write(cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR))
        finally:
            writer.release()
    finally:
        capture.release()
    return out_path
