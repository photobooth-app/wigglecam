import io
import logging
import time
from threading import BrokenBarrierError, Condition, current_thread

import numpy
from PIL import Image

from ...config.models import ConfigBackendVirtualCamera
from .abstractbackend import AbstractCameraBackend

logger = logging.getLogger(__name__)


class VirtualCameraBackend(AbstractCameraBackend):
    def __init__(self, config: ConfigBackendVirtualCamera):
        super().__init__()
        # init with arguments
        self._config = config

        # declarations
        self._data_bytes: bytes = None
        self._data_condition: Condition = None

        # initializiation
        self._data_bytes: bytes = None
        self._data_condition: Condition = Condition()

    def start(self, nominal_framerate: int = None):
        super().start(nominal_framerate=nominal_framerate)

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

    def wait_for_hires_image(self, format: str):
        return super().wait_for_hires_image(format=format)

    def encode_frame_to_image(self, frame, format: str) -> bytes:
        # for virtualcamera frame == jpeg data, so no convertion needed.
        if format in ("jpg", "jpeg"):
            return frame
        else:
            raise NotImplementedError

    def _produce_dummy_image(self) -> bytes:
        byte_io = io.BytesIO()
        imarray = numpy.random.rand(250, 250, 3) * 255
        random_image = Image.fromarray(imarray.astype("uint8"), "RGB")
        random_image.save(byte_io, format="JPEG", quality=50)

        return byte_io.getbuffer()

    def wait_for_lores_image(self) -> bytes:
        """for other threads to receive a lores JPEG image"""

        with self._data_condition:
            if not self._data_condition.wait(timeout=1.0):
                raise TimeoutError("timeout receiving frames")

            return self._data_bytes

    def _align_fun(self):
        logger.debug("starting _align_fun")

        while not current_thread().stopped():
            try:
                self._barrier.wait()
            except BrokenBarrierError:
                logger.debug("sync barrier broke")
                break

            # simulate some processing and lower cpu use
            time.sleep(0.01)

        logger.info("_align_fun left")

    def _camera_fun(self):
        logger.debug("starting _camera_fun")

        while not current_thread().stopped():
            with self._data_condition:
                self._data_bytes = self._produce_dummy_image()
                self._data_condition.notify_all()

            time.sleep(1.0 / self._nominal_framerate)
            self._current_timestampset.camera = time.monotonic_ns()  # need to set as a backend would do so the align functions work fine

            # part of the alignment functions - that is not implemented, but barrier is needed
            try:
                self._barrier.wait()
            except BrokenBarrierError:
                logger.debug("sync barrier broke")
                break

        logger.info("_camera_fun left")
