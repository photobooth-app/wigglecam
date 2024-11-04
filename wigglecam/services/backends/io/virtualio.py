import logging
import time
from threading import current_thread

from ....utils.stoppablethread import StoppableThread
from ...config.models import ConfigBackendVirtualIo
from .abstractbackend import AbstractIoBackend

logger = logging.getLogger(__name__)


class VirtualIoBackend(AbstractIoBackend):
    def __init__(self, config: ConfigBackendVirtualIo):
        super().__init__()

        self._config: ConfigBackendVirtualIo = config

        self._gpio_thread: StoppableThread = None

    def start(self):
        super().start()

        self._gpio_thread = StoppableThread(name="_gpio_thread", target=self._gpio_fun, args=(), daemon=True)
        self._gpio_thread.start()

    def stop(self):
        super().stop()

        if self._gpio_thread and self._gpio_thread.is_alive():
            self._gpio_thread.stop()
            self._gpio_thread.join()

    def derive_nominal_framerate_from_clock(self) -> int:
        return self._config.fps_nominal

    def set_trigger_out(self, on: bool):
        # trigger out is forwarded in virtual mode directly to trigger in again
        if on:
            self._on_trigger_in()
            logger.debug("forwarded trigger_out to trigger_in")

    def _gpio_fun(self):
        logger.debug("starting _gpio_fun simulating clock")
        logger.info("virtual clock is very basic and suffers from high jitter")

        while not current_thread().stopped():
            time.sleep((1.0 / self._config.fps_nominal) / 2.0)
            self._on_clock_rise_in(time.monotonic_ns())
            time.sleep((1.0 / self._config.fps_nominal) / 2.0)
            self._on_clock_fall_in()

        logger.info("_gpio_fun left")