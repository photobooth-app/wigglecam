from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from .context import WiggleProcessorContext
from .pipeline import NextStep

logger = logging.getLogger(__name__)


class ConcatenateStep:
    def __init__(
        self,
        video_out: Path,
        speed_factor: float = 1.0,
        reverse_append: bool = False,
        mp4_compat_mode: bool = True,
        gif_highquality_mode: bool = True,
    ) -> None:
        self.video_out = video_out
        self.speed_factor = speed_factor
        self.reverse_append = reverse_append
        self.mp4_compat_mode = mp4_compat_mode
        self.gif_highquality_mode = gif_highquality_mode

    def __call__(self, context: WiggleProcessorContext, next_step: NextStep) -> None:
        # https://stackoverflow.com/questions/63152626/is-it-good-to-use-minterpolate-in-ffmpeg-for-reducing-blurred-frames
        # https://ffmpeg.org/ffmpeg-filters.html#minterpolate
        # ffmpeg -y -r 0.3 -stream_loop 1 -i test02_01.png -r 0.3 -stream_loop 2 -i test02_02.png
        # -filter_complex "[0][1]concat=n=2:v=1:a=0[v];[v]minterpolate=fps=24:scd=none,trim=3:7,setpts=PTS-STARTPTS" -pix_fmt yuv420p test02.mp4
        # ffmpeg  -i %02d.png -framerate 10 -vf minterpolate=fps=20:mi_mode=mci test-%02d.png
        base_filename = "ffmpeg_concat_"
        filename_extension = context.processing_paths[0].suffix  # derive file format from first in list
        output_path = Path(self.video_out)

        if any(dim % 2 for dim in Image.open(context.processing_paths[0]).size):
            # height odd, checking only for one image because it's assumed every image is same shape
            raise RuntimeError("Error, processing restricted to image width/height even")

        # nominal is what people would consider as looking good
        nominal_number_of_frames = 4.0
        nominal_frame_delay = 0.15
        nominal_duration = nominal_number_of_frames * nominal_frame_delay  # 0.6sec

        # if more images are interpolated, the resulting video looks smoother. The user can adjust the speed by choosing different factor.
        number_of_frames = len(context.processing_paths)
        resulting_duration = nominal_duration / self.speed_factor  # factor=2 twice as fast, factor=0.5 half as fast, double duration
        resulting_fps = float(number_of_frames) / resulting_duration

        if resulting_fps < 1:
            logger.warning("warning, FPS calculated to less than 1, forcing 1.")
            resulting_fps = 1

        logger.info(f"Calculated {resulting_duration=}, {resulting_fps=}, {number_of_frames=}")

        for index, processing_path in enumerate(context.processing_paths):
            concatenate_path = Path(context.temp_working_dir, f"{base_filename}{index:08}{processing_path.suffix}")
            shutil.copy(processing_path, concatenate_path)

        command_general_options = [
            "-hide_banner",
            "-y",
        ]
        command_video_input = [
            "-framerate",
            f"{resulting_fps:.2f}",
            "-i",
            str(Path(context.temp_working_dir, f"{base_filename}%08d{filename_extension}")),  # only all files same format supported!
        ]

        command_video_output = []
        filter_complex = []

        if output_path.suffix.lower() == ".mp4" and self.mp4_compat_mode:  # compat mode for mp4 (always on here for iPhones mostly)
            command_video_output += "-pix_fmt", "yuv420p"
        if self.reverse_append:  # if enabled, reverse but trim first frame and last from reversed sequence because it would be double
            filter_complex.append(f"[0]trim=start_frame=1:end_frame={(number_of_frames)-1},setpts=PTS-STARTPTS,reverse[r];[0][r]concat=n=2:v=1:a=0")
        if output_path.suffix.lower() == ".gif" and self.gif_highquality_mode:  # if gif, create HQ gif (needs more cpu)
            filter_complex.append("split[a][b]; [a]palettegen[palette]; [b][palette]paletteuse")

        if filter_complex:
            command_video_output += "-filter_complex", ",".join(filter_complex)

        ffmpeg_command = ["ffmpeg"] + command_general_options + command_video_input + command_video_output + [str(output_path)]

        logger.debug(" ".join(ffmpeg_command))

        subprocess.run(
            args=ffmpeg_command,
            check=True,
        )

        if not output_path.exists():
            raise RuntimeError("error, output file was not created. check logs!")

        context.processing_paths = [output_path]  # keep it a list for consistency

        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__
