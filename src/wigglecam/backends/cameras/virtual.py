import asyncio
import io
import logging
import uuid

import numpy
from PIL import Image, ImageDraw

from ...config.camera_virtual import CfgCameraVirtual
from ...dto import ImageMessage
from .base import CameraBackend
from .output.base import CameraOutput

logger = logging.getLogger(__name__)


class Virtual(CameraBackend):
    """
    A fake camera backend that generates synthetic frames.
    Produces both 'lores' and 'hires' frames as byte strings.
    """

    def __init__(self, device_id: int, output_lores: CameraOutput, output_hires: CameraOutput):
        self.__config = CfgCameraVirtual()
        super().__init__(device_id, output_lores, output_hires)

        self.__offset_x = 0
        self.__offset_y = 0
        self.__color_current = 0

        logger.info(f"VirtualBackend initialized, {device_id=}, listening for subs")

    async def run(self):
        while True:
            # Offload CPU‑bound work to a thread
            produced_frame = await asyncio.to_thread(self._produce_dummy_image)

            # For demo, use same image for lores and hires
            msg_bytes = ImageMessage(self._device_id, jpg_bytes=produced_frame).to_bytes()
            await self._output_lores.awrite(msg_bytes)

            await asyncio.sleep(1.0 / self.__config.fps_nominal)

    async def trigger_hires_capture(self, job_id: uuid.UUID):
        produced_frame = await asyncio.to_thread(self._produce_dummy_image)

        msg_bytes = ImageMessage(self._device_id, jpg_bytes=produced_frame, job_id=job_id).to_bytes()
        await self._output_hires.awrite(msg_bytes)

    def _produce_dummy_image(self) -> bytes:
        """CPU-intensive image generator — run in a worker thread."""
        offset_x = self.__offset_x
        offset_y = self.__offset_y

        size = 250
        ellipse_divider = 3
        color_steps = 100
        byte_io = io.BytesIO()

        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size // ellipse_divider, size // ellipse_divider), fill=255)

        time_normalized = self.__color_current / color_steps
        self.__color_current = self.__color_current + 1 if self.__color_current < color_steps else 0

        imarray = numpy.empty((size, size, 3))
        imarray[:, :, 0] = 0.5 + 0.5 * numpy.sin(2 * numpy.pi * (0 / 3 + time_normalized))
        imarray[:, :, 1] = 0.5 + 0.5 * numpy.sin(2 * numpy.pi * (1 / 3 + time_normalized))
        imarray[:, :, 2] = 0.5 + 0.5 * numpy.sin(2 * numpy.pi * (2 / 3 + time_normalized))
        imarray = numpy.round(255 * imarray).astype(numpy.uint8)

        random_image = Image.fromarray(imarray, "RGB")
        random_image.paste(mask, (size // ellipse_divider + offset_x, size // ellipse_divider + offset_y), mask=mask)

        random_image.save(byte_io, format="JPEG", quality=70)
        return byte_io.getvalue()
