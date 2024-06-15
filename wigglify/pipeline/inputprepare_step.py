from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .context import WiggleProcessorContext
from .pipeline import NextStep

logger = logging.getLogger(__name__)


class InputPrepareStep:
    def __init__(self) -> None:
        # no parameters for step currently.
        pass

    def __call__(self, context: WiggleProcessorContext, next_step: NextStep) -> None:
        logger.debug("copy input files to tmp workdir")
        updated_paths: list[Path] = []

        for index, processing_path in enumerate(context.processing_paths):
            inputd_path = Path(context.temp_working_dir, f"input_{index:08}{processing_path.suffix}")
            logger.debug(f"copy input file {processing_path} to {inputd_path}")

            shutil.copy(processing_path, inputd_path)
            updated_paths.append(inputd_path)

        context.processing_paths = updated_paths
        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__
