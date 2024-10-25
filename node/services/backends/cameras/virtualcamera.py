import io
import logging
import time

import numpy
from PIL import Image

from ...config.models import ConfigBackendVirtualcamera
from .abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)


class VirtualCameraBackend(AbstractBackend):
    def __init__(self, config: ConfigBackendVirtualcamera):
        super().__init__()
        # init with arguments
        self._config = config

    def start(self, nominal_framerate: int = None):
        super().start()

    def stop(self):
        super().stop()

    def start_stream(self):
        pass

    def stop_stream(self):
        pass

    def wait_for_lores_image(self):
        time.sleep(0.05)

        byte_io = io.BytesIO()
        imarray = numpy.random.rand(200, 200, 3) * 255
        random_image = Image.fromarray(imarray.astype("uint8"), "RGB")
        random_image.save(byte_io, format="JPEG", quality=50)
        # random_image = Image.new("RGB", (64, 64), color="green")
        # random_image.save(byte_io, format="JPEG", quality=50)

        return byte_io.getbuffer()

    def do_capture(self, filename: str = None, number_frames: int = 1):
        pass

    def sync_tick(self, timestamp_ns: int):
        pass
