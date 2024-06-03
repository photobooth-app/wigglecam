from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from .context import WiggleProcessorContext
from .pipeline import NextStep

logger = logging.getLogger(__name__)


class ResizeStep:
    def __init__(self, max_size: tuple[int, int]) -> None:
        self.max_size = max_size  # W x H

    def __call__(self, context: WiggleProcessorContext, next_step: NextStep) -> None:
        updated_paths: list[Path] = []

        for index, processing_path in enumerate(context.processing_paths):
            resized_path = Path(context.temp_working_dir, f"resized_{index:08}{processing_path.suffix}")
            logger.info(f"resizing image {processing_path}, storing in {resized_path}")

            image = Image.open(processing_path)
            image.thumbnail(self.max_size)  # TODO, check quality parameters and speed.
            image.save(resized_path)  # TODO: check quality parameters
            # image.show()
            updated_paths.append(resized_path)

        context.processing_paths = updated_paths
        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__
