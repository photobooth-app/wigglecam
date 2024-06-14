from __future__ import annotations

import logging
import subprocess
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.concatenate_step import ConcatenateStep
from pipeline.inputprepare_step import InputPrepareStep
from pipeline.interpolate_step import InterpolateRifeStep
from pipeline.pipeline import Context, NextStep, Pipeline
from pipeline.register_step import RegisterStep
from pipeline.resize_step import ResizeStep

logger = logging.getLogger(__name__)


@dataclass
class WiggleProcessorContext:
    input_images: list[Path] = field(default_factory=list)
    temp_working_dir: Path = field(default=None)

    workset_images: list[Path] = field(default_factory=list)
    # registered_images: list[Path] = field(default_factory=list)

    output_path: Path = None

    def __post_init__(self):
        # validate data in context on init, create temp dir

        if not isinstance(self.input_images, list) or not len(self.input_images) >= 2:
            raise ValueError("input_frames required of type list and 2 frames minimum.")
        if not all(isinstance(input_frame, Path) for input_frame in self.input_images):
            raise ValueError("input_frames need to be Path objects.")

        self.temp_working_dir = Path(tempfile.mkdtemp(dir="./tmp/", prefix=self.input_images[0].stem))


context = WiggleProcessorContext([Path("tests/input_images/C_00.jpg"), Path("tests/input_images/C_01.jpg")])
steps = [
    InputPrepareStep(),
    ResizeStep((500, 500)),
    RegisterStep(apply_mask=True, crop_to_least_common_intersection=True, register_algorithm="transformecc"),
    InterpolateRifeStep(2),
    ConcatenateStep("video.gif", reverse_append=True),
]


tms = time.time()
pipeline = Pipeline[Context](*steps)  # put it together
logger.debug(f"-- process time: {round((time.time() - tms), 2)}s to process pipeline")


def _error_handler(error: Exception, context: Context, next_step: NextStep) -> None:
    # custom error handler, if none, default built in is used.
    print("ERROR! step could not apply")
    print(error)
    print(traceback.format_exc())
    # here it still continues, but it should reraise probably and break the pipeline process.
    # next_step(context)


# run pipeline
pipeline(context, _error_handler)
print(context)


def video_duration(input_video):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            input_video,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    return float(result.stdout)


def video_frames(input_video):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "csv=p=0",
            input_video,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    return int(result.stdout)


print(video_duration(f"{context.temp_working_dir}/video.gif"))
print(video_frames(f"{context.temp_working_dir}/video.gif"))
