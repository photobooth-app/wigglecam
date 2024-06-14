from __future__ import annotations

import shutil
from pathlib import Path

from .pipeline import Context, NextStep


class InputPrepareStep:
    def __init__(self) -> None:
        # no parameters for step currently.
        pass

    def __call__(self, context: Context, next_step: NextStep) -> None:
        print("copy input files to the folder using generic filename input_xxxxxxxx.suffix")

        for index, input_image in enumerate(context.input_images):
            workset_image = Path(context.temp_working_dir, f"input_{index:08}{input_image.suffix}")
            print(f"copy input file {input_image} to {workset_image}")

            shutil.copy(input_image, workset_image)
            context.workset_images.append(workset_image)

        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__
