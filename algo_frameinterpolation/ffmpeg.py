#
import shutil
import subprocess
import tempfile
from pathlib import Path


# https://stackoverflow.com/questions/63152626/is-it-good-to-use-minterpolate-in-ffmpeg-for-reducing-blurred-frames
# https://ffmpeg.org/ffmpeg-filters.html#minterpolate
# ffmpeg -y -r 0.3 -stream_loop 1 -i test02_01.png -r 0.3 -stream_loop 2 -i test02_02.png -filter_complex "[0][1]concat=n=2:v=1:a=0[v];[v]minterpolate=fps=24:scd=none,trim=3:7,setpts=PTS-STARTPTS" -pix_fmt yuv420p test02.mp4
# ffmpeg  -i %02d.png -framerate 10 -vf minterpolate=fps=20:mi_mode=mci test-%02d.png
def ffmpeg(images: list[Path], video_out: Path):
    base_filename = "ffmpeg_wiggle_tmp_"

    if len(images) < 3:
        print("info: ffmpeg minterpolate needs three frames, so duplicating the last image")
        images.append(images[-1])

    with tempfile.TemporaryDirectory() as tmpdirname:
        print("created temporary directory", tmpdirname)
        for index, image in enumerate(images):
            shutil.copy(image, Path(tmpdirname, f"{base_filename}{index:04}{image.suffix}"))

        command_general_options = [
            "-hide_banner",
            "-y",
        ]
        command_video_input = [
            "-framerate",
            "5",
            "-i",
            f"{tmpdirname}/{base_filename}%04d{image.suffix}",
        ]
        command_video_output = [
            "-filter:v",
            "minterpolate=scd=none:fps=20:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=0:me=epzs",
            # "minterpolate=fps=60:mi_mode=mci",
            "-pix_fmt",
            "yuv420p",
        ]

        ffmpeg_command = ["ffmpeg"] + command_general_options + command_video_input + command_video_output + [str(video_out)]
        print(" ".join(ffmpeg_command))
        try:
            subprocess.run(
                args=ffmpeg_command,
                check=True,
            )
        except Exception as exc:
            raise RuntimeError(f"error: {exc}") from exc
