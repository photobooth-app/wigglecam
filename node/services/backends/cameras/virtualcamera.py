import io
import logging
import time
from datetime import datetime
from pathlib import Path
from queue import Empty
from threading import BrokenBarrierError, current_thread

import numpy
from PIL import Image

from ...config.models import ConfigBackendVirtualCamera
from .abstractbackend import AbstractCameraBackend, BackendItem

logger = logging.getLogger(__name__)


class VirtualCameraBackend(AbstractCameraBackend):
    def __init__(self, config: ConfigBackendVirtualCamera):
        super().__init__()
        # init with arguments
        self._config = config

        # declarations
        #

        # initializiation
        #

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

    def _produce_dummy_image(self):
        byte_io = io.BytesIO()
        imarray = numpy.random.rand(250, 250, 3) * 255
        random_image = Image.fromarray(imarray.astype("uint8"), "RGB")
        random_image.save(byte_io, format="JPEG", quality=50)

        return byte_io.getbuffer()

    def wait_for_lores_image(self):
        time.sleep(1.0 / self._nominal_framerate)

        return self._produce_dummy_image()

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
            backendrequest = None

            try:
                backendrequest = self._queue_in.get_nowait()
            except Empty:
                pass  # no actual job to process...

            if backendrequest:
                folder = Path("./tmp/")
                filename = Path(f"img_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')}").with_suffix(".jpg")
                filepath = folder / filename
                logger.info(f"{filepath=}")

                with open(filepath, "wb") as f:
                    f.write(self.wait_for_lores_image())

                backenditem = BackendItem(
                    filepath=filepath,
                )
                self._queue_out.put(backenditem)
                logger.info(f"result item put on output queue: {backenditem}")

                self._queue_in.task_done()
            else:
                time.sleep(1.0 / self._nominal_framerate)
                self._current_timestampset.camera = time.monotonic_ns()

                try:
                    self._barrier.wait()
                except BrokenBarrierError:
                    logger.debug("sync barrier broke")
                    break

        logger.info("_camera_fun left")
