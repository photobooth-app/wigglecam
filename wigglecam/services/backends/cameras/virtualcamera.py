import io
import logging
import random
import time
from threading import BrokenBarrierError, Condition, current_thread

import numpy
from PIL import Image

from ...config.models import ConfigBackendVirtualCamera
from .abstractbackend import AbstractCameraBackend, Formats

logger = logging.getLogger(__name__)


class VirtualCameraBackend(AbstractCameraBackend):
    def __init__(self, config: ConfigBackendVirtualCamera):
        super().__init__()
        # init with arguments
        self._config = config

        # declarations
        self._data_bytes: bytes = None
        self._data_condition: Condition = None
        self._offset_x: int = None
        self._offset_y: int = None
        self._adjust_amount: float = None

        # initializiation
        self._data_bytes: bytes = None
        self._data_condition: Condition = Condition()
        self._adjust_amount: float = 0

    def start(self, nominal_framerate: int = None):
        super().start(nominal_framerate=nominal_framerate)

        # on every start place the circle slightly different to the center. could be used for feature detection and align algo testing
        self._offset_x = random.randint(5, 20)
        self._offset_y = random.randint(5, 20)

        logger.info(f"initialized virtual camera with random offset=({self._offset_x},{self._offset_y})")

    def stop(self):
        super().stop()

    def camera_alive(self) -> bool:
        super_alive = super().camera_alive()

        return super_alive

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
        from PIL import ImageDraw

        offset_x = self._offset_x
        offset_y = self._offset_y

        size = 250
        ellipse_divider = 3
        byte_io = io.BytesIO()

        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + (size // ellipse_divider, size // ellipse_divider), fill=255)

        imarray = numpy.random.rand(size, size, 3) * 255
        random_image = Image.fromarray(imarray.astype("uint8"), "RGB")
        random_image.paste(mask, (size // ellipse_divider + offset_x, size // ellipse_divider + offset_y), mask=mask)

        random_image.save(byte_io, format="JPEG", quality=50)
        return byte_io.getbuffer()

    def wait_for_lores_image(self) -> bytes:
        """for other threads to receive a lores JPEG image"""

        with self._data_condition:
            if not self._data_condition.wait(timeout=1.0):
                raise TimeoutError("timeout receiving frames")

            return self._data_bytes

    def _backend_align(self):
        # called after barrier is waiting for all as action.
        # since a thread is calling this, delay in this function lead to constant offset for virtual camera
        timestamp_delta_ns = self._current_timestampset.camera - self._current_timestampset.reference  # in ns

        self._adjust_amount = -timestamp_delta_ns / 1.0e9

        THRESHOLD_LOG = 0
        if abs(timestamp_delta_ns / 1.0e6) > THRESHOLD_LOG:
            # even in debug reduce verbosity a bit if all is fine and within 2ms tolerance
            logger.debug(
                f"🕑 clk/cam/Δ/adjust=( "
                f"{self._current_timestampset.reference/1e6:.1f} / "
                f"{self._current_timestampset.camera/1e6:.1f} / "
                f"{timestamp_delta_ns/1e6:5.1f} / "
                f"{self._adjust_amount*1e3:5.1f}) ms"
            )
        else:
            pass
            # silent

    def _camera_fun(self):
        logger.debug("starting _camera_fun")

        while not current_thread().stopped():
            regular_sleep = 1.0 / self._nominal_framerate
            adjust_amount_clamped = max(min(0.5 / self._nominal_framerate, self._adjust_amount), -0.5 / self._nominal_framerate)

            time.sleep(regular_sleep + adjust_amount_clamped)

            with self._data_condition:
                self._current_timestampset.camera = time.monotonic_ns()  # need to set as a backend would do so the align functions work fine
                # because image is produced in same thread that is responsible for timing, it's jittery but ok for virtual cam
                self._data_bytes = self._produce_dummy_image()

                self._data_condition.notify_all()

            # part of the alignment functions - that is not implemented, but barrier is needed
            try:
                self._barrier.wait()
            except BrokenBarrierError:
                logger.debug("sync barrier broke")
                break

        logger.info("_camera_fun left")
