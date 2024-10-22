import logging
from threading import Thread

from .camera_service import Picamera2Service
from .gpio_secondary_node import GpioSecondaryNodeService

logger = logging.getLogger(__name__)


class SyncedCameraService:
    def __init__(self, camera_service: Picamera2Service, gpio_service: GpioSecondaryNodeService):
        # init the arguments
        self._camera_service: Picamera2Service = camera_service
        self._gpio_service: GpioSecondaryNodeService = gpio_service

        # define private props
        self._sync_thread: Thread = None
        self._capture_thread: Thread = None

    def start(self):
        self._gpio_service.start()

        print("waiting for clock input, startup of service on halt!")
        self._wait_for_clock()
        print("got it, continue starting...")

        print("deriving nominal framerate from clock signal, counting 10 ticks...")
        derived_fps = self._gpio_service.derive_nominal_framerate_from_clock()
        print(f"got it, derived {derived_fps}fps...")

        self._camera_service.start(nominal_framerate=derived_fps)

        self._sync_thread = Thread(name="_sync_thread", target=self._sync_fun, args=(), daemon=True)
        self._sync_thread.start()
        self._capture_thread = Thread(name="_capture_thread", target=self._capture_fun, args=(), daemon=True)
        self._capture_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        # self._capture_thread.stop()
        # self._sync_thread.stop()
        self._camera_service.stop()
        self._gpio_service.stop()

        logger.debug(f"{self.__module__} stopped")

    def _wait_for_clock(self):
        while True:
            try:
                if self._gpio_service.wait_for_clock_signal(timeout=2.0):
                    print("clock signal received, continue...")
                    break
            except TimeoutError:
                print("waiting for clock signal in...")
            except Exception as e:
                print(e)
                print("unexpected error while waiting for sync clock in")

    def _sync_fun(self):
        while True:
            try:
                timestamp_ns = self._gpio_service.wait_for_clock_signal(timeout=1)
                self._camera_service.sync_tick(timestamp_ns)
            except TimeoutError:
                self._wait_for_clock()
                # TODO: implement some kind of going to standby and stop also camera to save energy...

    def _capture_fun(self):
        while True:
            self._gpio_service.wait_for_trigger_signal(timeout=None)
            if self._gpio_service.clock_signal_valid():
                self._camera_service.do_capture()
            else:
                print("capture request ignored because no valid clock signal")
