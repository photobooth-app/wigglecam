import io
import logging
import random
import time
from queue import Empty, Full, Queue
from threading import BrokenBarrierError, Condition, current_thread
from typing import cast

import numpy
from PIL import Image, ImageDraw

from ....utils.stoppablethread import StoppableThread
from ...config.models import ConfigBackendVirtualCamera
from .abstractbackend import AbstractCameraBackend, Formats

logger = logging.getLogger(__name__)


class VirtualCameraBackend(AbstractCameraBackend):
    def __init__(self, config: ConfigBackendVirtualCamera):
        super().__init__()
        # init with arguments
        self._config = config

        # some variability for producer to create images
        self._offset_x: int = 0
        self._offset_y: int = 0
        self._color_current: int = 0

        self._producer_thread: StoppableThread | None = None

        # initializiation
        self._data_bytes: bytes | None = None
        self._data_condition: Condition = Condition()

        self._producer_adjust_amount: float = 0
        self._producer_queue: Queue[tuple[bytes, int]] = Queue(maxsize=1)

    def start(self, nominal_framerate: int):
        super().start(nominal_framerate=nominal_framerate)

        # on every start place the circle slightly different to the center. could be used for feature detection and align algo testing
        self._offset_x = random.randint(5, 20)
        self._offset_y = random.randint(5, 20)

        self._producer_thread = StoppableThread(name="_producer_thread", target=self._producer_fun, args=(), daemon=True)
        self._producer_thread.start()

        logger.info(f"initialized virtual camera with random offset=({self._offset_x},{self._offset_y})")

    def stop(self):
        super().stop()

        if self._producer_thread and self._producer_thread.is_alive():
            self._producer_thread.stop()
            self._producer_thread.join()

    def camera_alive(self) -> bool:
        super_alive = super().camera_alive()
        producer_alive = bool(self._producer_thread) and self._producer_thread.is_alive()

        return super_alive and producer_alive

    def start_stream(self):
        pass

    def stop_stream(self):
        pass

    def wait_for_hires_frame(self):
        return self.wait_for_lores_image()

    def wait_for_hires_image(self, format: Formats):
        return super().wait_for_hires_image(format=format)

    def done_hires_frames(self):
        pass

    def encode_frame_to_image(self, frame, format: Formats) -> bytes:
        if format == "jpeg":
            # for virtualcamera frame == jpeg data, so no convertion needed.
            return frame
        else:
            raise NotImplementedError

    def _produce_dummy_image(self) -> bytes:
        offset_x = self._offset_x
        offset_y = self._offset_y

        size = 250
        ellipse_divider = 3
        color_steps = 100
        byte_io = io.BytesIO()

        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + (size // ellipse_divider, size // ellipse_divider), fill=255)

        time_normalized = self._color_current / color_steps
        self._color_current = self._color_current + 1 if self._color_current < color_steps else 0
        imarray = numpy.empty((size, size, 3))
        imarray[:, :, 0] = 0.5 + 0.5 * numpy.sin(2 * numpy.pi * (0 / 3 + time_normalized))
        imarray[:, :, 1] = 0.5 + 0.5 * numpy.sin(2 * numpy.pi * (1 / 3 + time_normalized))
        imarray[:, :, 2] = 0.5 + 0.5 * numpy.sin(2 * numpy.pi * (2 / 3 + time_normalized))
        imarray = numpy.round(255 * imarray).astype(numpy.uint8)
        random_image = Image.fromarray(imarray, "RGB")

        random_image.paste(mask, (size // ellipse_divider + offset_x, size // ellipse_divider + offset_y), mask=mask)

        random_image.save(byte_io, format="JPEG", quality=50)

        return byte_io.getvalue()
        # getvalue (actual bytes copy) instead getbuffer (memoryview) to avoid Exception ignored in: <_io.BytesIO object at xxx>
        # BufferError: Existing exports of data: object cannot be re-sized

    def _producer_fun(self):
        logger.debug("starting _producer_fun")

        while not cast(StoppableThread, current_thread()).stopped():
            img, exposure_timestamp_ns = self._get_image()

            try:
                self._producer_queue.put_nowait((img, exposure_timestamp_ns))
            except Full:
                logger.warning("virtual captures buffer full, skipping")

        logger.info("_producer_fun left")

    def _get_image(self) -> tuple[bytes, int]:
        regular_sleep = 1.0 / self._nominal_framerate

        # simulate exposure
        start = time.monotonic_ns()
        img = self._produce_dummy_image()

        # to correct exposure time -> less jittery
        exposed = time.monotonic_ns()
        exposure_time = (exposed - start) * 1.0e-9
        exposure_time_corrected_regular_sleep = regular_sleep - exposure_time

        offset_frame_duration = exposure_time_corrected_regular_sleep + self._producer_adjust_amount
        # simulate frameduration/fps
        if offset_frame_duration > 0:
            time.sleep(offset_frame_duration)
        else:
            logger.warning("produce image takes more time than frameduration. cannot deliver frames fast enough. consider lowering the framerate.")

        return img, start

    def wait_for_lores_image(self) -> bytes:
        """for other threads to receive a lores JPEG image"""

        with self._data_condition:
            if not self._data_condition.wait(timeout=1.0):
                raise TimeoutError("timeout receiving frames")

            assert self._data_bytes

            return self._data_bytes

    def _backend_adjust(self, adjust_amount_ns: int):
        self._producer_adjust_amount = adjust_amount_ns * 1.0e-9

    def _camera_fun(self):
        logger.debug("starting _camera_fun")

        while not cast(StoppableThread, current_thread()).stopped():
            # adjust_amount_clamped = 0

            try:
                img, timestamp_exposure_start = self._producer_queue.get(block=True, timeout=1)
            except Empty:
                # if producer did not yet produce something, because thread started delayed, we just continue
                continue

            self._current_timestampset.camera = timestamp_exposure_start

            with self._data_condition:
                self._data_bytes = img

                self._data_condition.notify_all()

            # part of the alignment functions - that is not implemented, but barrier is needed
            try:
                self._barrier.wait()
            except BrokenBarrierError:
                logger.debug("sync barrier broke")
                break

        logger.info("_camera_fun left")
