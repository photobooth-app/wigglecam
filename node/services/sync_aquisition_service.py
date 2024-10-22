import logging
from threading import Thread

from ..config import appconfig
from .backends.cameras.picamera2backend import Picamera2Backend
from .backends.io.gpio_secondary_node import GpioSecondaryNodeService
from .baseservice import BaseService

logger = logging.getLogger(__name__)


class SyncedAcquisitionService(BaseService):
    def __init__(self):
        super().__init__()

        # init the arguments
        pass

        # define private props
        # to sync, a camera backend and io backend is used.
        self._camera_backend: Picamera2Backend = None
        self._gpio_backend: GpioSecondaryNodeService = None
        self._sync_thread: Thread = None
        self._capture_thread: Thread = None

        # initialize private properties.
        # currently only picamera2 and gpio backend are supported, may be extended in the future
        self._camera_backend: Picamera2Backend = Picamera2Backend(appconfig.picamera2)
        self._gpio_backend: GpioSecondaryNodeService = GpioSecondaryNodeService(appconfig.secondary_gpio)

    def start(self):
        super().start()

        self._gpio_backend.start()

        print("waiting for clock input, startup of service on halt!")
        self._wait_for_clock()
        print("got it, continue starting...")

        print("deriving nominal framerate from clock signal, counting 10 ticks...")
        derived_fps = self._gpio_backend.derive_nominal_framerate_from_clock()
        print(f"got it, derived {derived_fps}fps...")

        self._camera_backend.start(nominal_framerate=derived_fps)

        self._sync_thread = Thread(name="_sync_thread", target=self._sync_fun, args=(), daemon=True)
        self._sync_thread.start()
        self._capture_thread = Thread(name="_capture_thread", target=self._capture_fun, args=(), daemon=True)
        self._capture_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        # self._capture_thread.stop()
        # self._sync_thread.stop()
        self._camera_backend.stop()
        self._gpio_backend.stop()

        logger.debug(f"{self.__module__} stopped")

    def gen_stream(self):
        """
        yield jpeg images to stream to client (if not created otherwise)
        this function may be overriden by backends, but this is the default one
        relies on the backends implementation of _wait_for_lores_image to return a buffer
        """
        print("livestream started on backend")
        self._camera_backend.start_stream()

        while self._is_running:
            try:
                output_jpeg_bytes = self._camera_backend.wait_for_lores_image()
            except StopIteration:
                logger.info("stream ends due to shutdown aquisitionservice")
                self._camera_backend.stop_stream()
                return
            except Exception as exc:
                # this error probably cannot recover.
                logger.exception(exc)
                logger.error(f"streaming exception: {exc}")
                self._camera_backend.stop_stream()
                raise RuntimeError(f"Stream error {exc}") from exc

            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + output_jpeg_bytes + b"\r\n\r\n")

        self._camera_backend.stop_stream()

    def _wait_for_clock(self):
        assert self._is_running is True  # ensure to never call this function when not already started.

        while self._is_running:
            try:
                if self._gpio_backend.wait_for_clock_signal(timeout=2.0):
                    print("clock signal received, continue...")
                    break
            except TimeoutError:
                print("waiting for clock signal in...")
            except Exception as e:
                print(e)
                print("unexpected error while waiting for sync clock in")

    def _sync_fun(self):
        while self._is_running:
            try:
                timestamp_ns = self._gpio_backend.wait_for_clock_signal(timeout=1)
                self._camera_backend.sync_tick(timestamp_ns)
            except TimeoutError:
                self._wait_for_clock()
                # TODO: implement some kind of going to standby and stop also camera to save energy...

    def _capture_fun(self):
        while self._is_running:
            self._gpio_backend.wait_for_trigger_signal(timeout=None)
            if self._gpio_backend.clock_signal_valid():
                self._camera_backend.do_capture()
            else:
                print("capture request ignored because no valid clock signal")
