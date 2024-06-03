from __future__ import annotations

## formatter ##
import subprocess
from pathlib import Path


def input_wigglesets(input_dir: Path = Path("./tests/input_images"), glob_str: str = "*_00.jpg"):
    wigglesets: list[list[Path]] = []
    for fileset_file0 in Path(input_dir).glob(glob_str):
        wiggleset = []

        for file in Path(input_dir).glob(f"{(str(fileset_file0.stem))[:-2]}*"):
            wiggleset.append(file)

        assert len(wiggleset) == 2
        wigglesets.append(wiggleset)

    return wigglesets


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
