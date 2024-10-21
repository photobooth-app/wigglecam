from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from .context import WiggleProcessorContext
from .pipeline import NextStep

logger = logging.getLogger(__name__)

PATH_RIFE_NCNN_VULKAN_EXECUTABLE = r".\vendor\ai_algorithms\rife-ncnn-vulkan-20221029-windows\rife-ncnn-vulkan.exe"


# RIFE implementation using nccn: https://github.com/nihui/rife-ncnn-vulkan
# same as used in flowframes under the hood
class InterpolateRifeStep:
    def __init__(self, passes: int = 1) -> None:
        self.passes = passes

    def __call__(self, context: WiggleProcessorContext, next_step: NextStep) -> None:
        updated_paths: list[Path] = context.processing_paths.copy()

        for pass_ in range(self.passes):
            # on start of each outer loop update process_images to latest out_images,
            # so .insert will update process_images while output remains constant
            process_images = updated_paths.copy()

            for step in range(0, len(updated_paths) - 1):
                logger.debug(f"pass {pass_=}, {step=}")

                interpolated_frame_path = Path(
                    context.temp_working_dir,
                    context.processing_paths[0]
                    .with_name(f"{context.processing_paths[0].stem}_pass{pass_}step{step}{context.processing_paths[0].suffix}")
                    .name,
                )
                self.interpolate(process_images[step : step + 2], interpolated_frame_path)
                updated_paths.insert(2 * step + 1, interpolated_frame_path)

        logger.info(updated_paths)

        context.processing_paths = updated_paths
        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__

    @staticmethod
    def interpolate(images: list[Path], interpolated_image: Path) -> list[Path]:
        if len(images) != 2:
            raise RuntimeError(f"need exactly two images to interpolate between, given {images}")

        command_input_images = [
            "-0",
            str(images[0]),
            "-1",
            str(images[1]),
        ]
        command_output_path = [
            "-o",
            str(interpolated_image),
        ]
        command_options = [
            "-m",
            "rife-v4.6",
        ]

        interpolate_command = [PATH_RIFE_NCNN_VULKAN_EXECUTABLE] + command_input_images + command_output_path + command_options
        logger.debug(" ".join(interpolate_command))

        subprocess.run(args=interpolate_command, check=True)


class InterpolateFfmpegStep:
    def __init__(self, passes: int = 1) -> None:
        self.passes = passes

    def __call__(self, context: WiggleProcessorContext, next_step: NextStep) -> None:
        # https://stackoverflow.com/questions/63152626/is-it-good-to-use-minterpolate-in-ffmpeg-for-reducing-blurred-frames
        # https://ffmpeg.org/ffmpeg-filters.html#minterpolate
        # ffmpeg -y -r 0.3 -stream_loop 1 -i test02_01.png -r 0.3 -stream_loop 2 -i test02_02.png -filter_complex
        # "[0][1]concat=n=2:v=1:a=0[v];[v]minterpolate=fps=24:scd=none,trim=3:7,setpts=PTS-STARTPTS" -pix_fmt yuv420p test02.mp4
        # ffmpeg  -i %02d.png -framerate 10 -vf minterpolate=fps=20:mi_mode=mci test-%02d.png
        base_filename = "ffmpeg_interpolate_"
        filename_extension = context.processing_paths[0].suffix  # derive file format from first in list

        images: list[Path] = context.processing_paths.copy()
        logger.warn(images)
        if len(images) < 3:
            logger.debug("info: ffmpeg minterpolate needs three frames, so feeding the last image twice")
            images.append(images[-1])

        if self.passes < 1:
            raise RuntimeError("minimum 1 pass to interpolate")

        for index, image in enumerate(images):
            interpolate_path = Path(context.temp_working_dir, f"{base_filename}{index:08}{image.suffix}")
            shutil.copy(image, interpolate_path)

        command_general_options = [
            "-hide_banner",
            "-y",
        ]
        command_video_input = [
            "-framerate",
            "1",
            "-i",
            str(Path(context.temp_working_dir, f"{base_filename}%08d{filename_extension}")),
        ]
        command_video_output = [
            "-filter:v",
            f"minterpolate=scd=none:fps={((self.passes+1)*2)}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=0:me=epzs",
        ]  # *2 for consistency with other algos

        ffmpeg_command = (
            ["ffmpeg"]
            + command_general_options
            + command_video_input
            + command_video_output
            + [str(Path(context.temp_working_dir, "ffmpeg_interpolated-%08d.png"))]
        )
        logger.debug(" ".join(ffmpeg_command))
        subprocess.run(args=ffmpeg_command, check=True)

        context.processing_paths = self.get_outputfiles(context.temp_working_dir, "ffmpeg_interpolated-*")

        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__

    @staticmethod
    def get_outputfiles(dir: Path, glob_str: str = "out-*"):
        output_filepaths: list[Path] = []
        for filepath in Path(dir).glob(glob_str):
            output_filepaths.append(filepath)

        return output_filepaths
