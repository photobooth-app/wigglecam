import logging
from threading import Thread

from .camera_service import SecondaryCameraService
from .gpio_service import SecondaryGpioService

logger = logging.getLogger(__name__)

FPS_NOMINAL = 10


class SecondarySyncedCameraService:
    def __init__(
        self,
        camera_service: SecondaryCameraService,
        gpio_service: SecondaryGpioService,
        config: dict,
    ):
        self._config: dict = {}  # TODO: pydantic config?

        self._camera_service: SecondaryCameraService = camera_service
        self._gpio_service: SecondaryGpioService = gpio_service

        # worker threads
        self._sync_thread: Thread = None
        self._capture_thread: Thread = None

    def start(self):
        self._gpio_service.start()

        print("waiting for clock input, startup of service on halt!")
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

        print("got it, continue starting...")

        self._camera_service.start(nominal_framerate=FPS_NOMINAL)

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

    def _sync_fun(self):
        while True:
            self._camera_service.sync_tick(self._gpio_service.wait_for_clock_signal(timeout=1))

    def _capture_fun(self):
        while True:
            self._camera_service.do_capture(self._gpio_service.wait_for_trigger_signal(timeout=None))
