"""SAM2 as a video segmenter.

Imported lazily and never at module import time: torch plus a checkpoint is
gigabytes, and the rest of the pipeline runs on CPU with no model at all. Only
a job that asks for the behind-subject effect should pay for it.

SAM2 is prompted once and propagates through the clip with temporal memory,
which is what makes it steadier than per-frame segmentation - flicker at the
shoulder line is what makes a composite look broken. Its memory is meaningless
across a cut, so a clip handed to it should be one continuous shot.

Note it is a segmenter, not a matter: it returns a crisp binary mask. Text
passing behind hair will read as die-cut. If that shows, a matting model such
as RVM is the swap, and this class is the only thing that changes.
"""
from __future__ import annotations

import pathlib
import subprocess
import tempfile
from typing import Iterator

import numpy as np

from halfheaven.analyze.subject import find_subject_prompt
from halfheaven.media.ffmpeg_bin import ffmpeg

DEFAULT_MODEL = "facebook/sam2-hiera-tiny"
OBJECT_ID = 1


def _pick_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class Sam2Segmenter:
    def __init__(self, model: str = DEFAULT_MODEL, device: str | None = None) -> None:
        self.model = model
        self.device = device or _pick_device()
        self._predictor = None

    def _load(self):
        if self._predictor is None:
            from sam2.sam2_video_predictor import SAM2VideoPredictor

            self._predictor = SAM2VideoPredictor.from_pretrained(
                self.model, device=self.device
            )
        return self._predictor

    def masks_for_video(
        self, video: pathlib.Path, size: tuple[int, int]
    ) -> Iterator[np.ndarray]:
        import torch

        width, height = size
        predictor = self._load()
        prompt = find_subject_prompt(video)

        with tempfile.TemporaryDirectory() as frames_dir:
            # SAM2 reads a directory of numbered JPEGs.
            subprocess.run(
                [ffmpeg(), "-v", "error", "-y", "-i", str(video),
                 "-q:v", "2", "-start_number", "0", f"{frames_dir}/%05d.jpg"],
                check=True, capture_output=True,
            )

            state = predictor.init_state(video_path=frames_dir)
            predictor.add_new_points_or_box(
                state,
                frame_idx=0,
                obj_id=OBJECT_ID,
                points=np.array(prompt.points, dtype=np.float32),
                labels=np.array(prompt.labels, dtype=np.int32),
            )

            with torch.inference_mode():
                for _, _, mask_logits in predictor.propagate_in_video(state):
                    mask = (mask_logits[0] > 0.0).squeeze().cpu().numpy()
                    yield (mask.astype(np.uint8) * 255)
