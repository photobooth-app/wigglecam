import io
import logging
import time

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
        self._tick_tock_counter: int = None

        # initializiation
        self._tick_tock_counter = 0

    def start(self, nominal_framerate: int = None):
        super().start(nominal_framerate=nominal_framerate)

    def stop(self):
        super().stop()

    def camera_alive(self):
        return True

    def start_stream(self):
        pass

    def stop_stream(self):
        pass

    def wait_for_lores_image(self):
        time.sleep(1.0 / self._nominal_framerate)

        byte_io = io.BytesIO()
        imarray = numpy.random.rand(200, 200, 3) * 255
        random_image = Image.fromarray(imarray.astype("uint8"), "RGB")
        random_image.save(byte_io, format="JPEG", quality=50)

        return byte_io.getbuffer()

    def do_capture(self, filename: str = None, number_frames: int = 1):
        raise NotImplementedError("not yet supported by virtual camera backend")

    def sync_tick(self, timestamp_ns: int):
        self._tick_tock_counter += 1
        if self._tick_tock_counter > 10:
            self._tick_tock_counter = 0
            logger.debug("tick")

    def request_tick(self):
        pass
