import asyncio
import io

import numpy
from PIL import Image, ImageDraw

from ..base import CameraBackend, StreamingOutput


class Virtual(CameraBackend):
    """
    A fake camera backend that generates synthetic frames.
    Produces both 'lores' and 'hires' frames as byte strings.
    """

    def __init__(self, interval: float = 0.25):
        self._stream_output = StreamingOutput()
        self._interval = interval
        self._offset_x = 0
        self._offset_y = 0
        self._color_current = 0
        self._task = None

    async def run(self):
        while True:
            # Offload CPU‑bound work to a thread
            produced_frame = await asyncio.to_thread(self._produce_dummy_image)

            # For demo, use same image for lores and hires
            await self._stream_output.write(produced_frame)

            await asyncio.sleep(self._interval)

    async def wait_for_lores_image(self) -> bytes:
        return await self._stream_output.wait_for_frame(timeout=2.0)

    async def wait_for_hires_image(self) -> bytes:
        return await self._stream_output.wait_for_frame(timeout=2.0)

    def _produce_dummy_image(self) -> bytes:
        """CPU-intensive image generator — run in a worker thread."""
        offset_x = self._offset_x
        offset_y = self._offset_y

        size = 250
        ellipse_divider = 3
        color_steps = 100
        byte_io = io.BytesIO()

        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size // ellipse_divider, size // ellipse_divider), fill=255)

        time_normalized = self._color_current / color_steps
        self._color_current = self._color_current + 1 if self._color_current < color_steps else 0

        imarray = numpy.empty((size, size, 3))
        imarray[:, :, 0] = 0.5 + 0.5 * numpy.sin(2 * numpy.pi * (0 / 3 + time_normalized))
        imarray[:, :, 1] = 0.5 + 0.5 * numpy.sin(2 * numpy.pi * (1 / 3 + time_normalized))
        imarray[:, :, 2] = 0.5 + 0.5 * numpy.sin(2 * numpy.pi * (2 / 3 + time_normalized))
        imarray = numpy.round(255 * imarray).astype(numpy.uint8)

        random_image = Image.fromarray(imarray, "RGB")
        random_image.paste(
            mask,
            (size // ellipse_divider + offset_x, size // ellipse_divider + offset_y),
            mask=mask,
        )

        random_image.save(byte_io, format="JPEG", quality=70)
        return byte_io.getvalue()
