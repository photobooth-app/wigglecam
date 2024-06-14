from __future__ import annotations

from PIL import Image

from .pipeline import Context, NextStep


class ResizeStep:
    def __init__(self, max_size: tuple[int, int]) -> None:
        self.max_size = max_size  # W x H

    def __call__(self, context: Context, next_step: NextStep) -> None:
        print("resize images")

        for workset_image in context.workset_images:
            print(f"resizing image {workset_image}")

            image = Image.open(workset_image)
            image.thumbnail(self.max_size)  # TODO, check quality parameters and speed.
            image.save(workset_image)  # TODO: check quality parameters
            # image.show()

        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__
