import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Event, Thread

from .backends.cameras.picamera2backend import Picamera2Backend
from .backends.io.gpiobackend import GpioSecondaryNodeService
from .baseservice import BaseService
from .config import appconfig
from .config.models import ConfigSyncedAcquisition

logger = logging.getLogger(__name__)


@dataclass
class CaptureJob:
    id: str = field(default_factory=datetime.now)
    number_captures: int = 1


@dataclass
class CaptureJobResult:
    id: str = None
    filenames: list[Path] = field(default_factory=list)


class SyncedAcquisitionService(BaseService):
    def __init__(self, config: ConfigSyncedAcquisition):
        super().__init__()

        # init the arguments
        self._config: ConfigSyncedAcquisition = config

        # define private props
        # to sync, a camera backend and io backend is used.
        self._camera_backend: Picamera2Backend = None
        self._gpio_backend: GpioSecondaryNodeService = None
        self._sync_thread: Thread = None
        self._capture_thread: Thread = None
        self._trigger_thread: Thread = None
        self._job: CaptureJob = None
        self._device_is_running: bool = None
        self._flag_execute_job: Event = None

        # initialize private properties.
        # currently only picamera2 and gpio backend are supported, may be extended in the future
        self._camera_backend: Picamera2Backend = Picamera2Backend(appconfig.backend_picamera2)
        self._gpio_backend: GpioSecondaryNodeService = GpioSecondaryNodeService(appconfig.backend_gpio)
        self._flag_execute_job: Event = Event()

    def start(self):
        super().start()

        self._gpio_backend.start()

        self._supervisor_thread = Thread(name="_supervisor_thread", target=self._supervisor_fun, args=(), daemon=True)
        self._supervisor_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        self._gpio_backend.stop()

        logger.debug(f"{self.__module__} stopped")

    def gen_stream(self):
        """
        yield jpeg images to stream to client (if not created otherwise)
        this function may be overriden by backends, but this is the default one
        relies on the backends implementation of _wait_for_lores_image to return a buffer
        """
        logger.info("livestream requested")
        self._camera_backend.start_stream()

        if not self._device_is_running or not self._is_running:
            raise RuntimeError("device not started, cannot deliver stream")

        while self._is_running and self._device_is_running:
            try:
                output_jpeg_bytes = self._camera_backend.wait_for_lores_image()
            except StopIteration:
                logger.info("stream ends due to shutdown acquisitionservice")
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

    def setup_job(self, job: CaptureJob):
        self._job = job

    def execute_job(self):
        self._flag_execute_job.set()

    def _device_start(self, derived_fps: int):
        self._device_is_running = True

        self._camera_backend.start(nominal_framerate=derived_fps)

        self._sync_thread = Thread(name="_sync_thread", target=self._sync_fun, args=(), daemon=True)
        self._sync_thread.start()
        self._capture_thread = Thread(name="_capture_thread", target=self._capture_fun, args=(), daemon=True)
        self._capture_thread.start()
        self._trigger_thread = Thread(name="_trigger_thread", target=self._trigger_fun, args=(), daemon=True)
        self._trigger_thread.start()

    def _device_stop(self):
        self._device_is_running = False

        self._camera_backend.stop()

    def _wait_for_clock(self, timeout: float = 2.0):
        assert self._is_running is True  # ensure to never call this function when not already started.

        while self._is_running:
            try:
                if self._gpio_backend.wait_for_clock_rise_signal(timeout=timeout):
                    logger.info("clock signal received, continue...")
                    break
            except TimeoutError:
                logger.info("waiting for clock signal in...")
            except Exception as exc:
                logger.exception(exc)
                logger.error("unexpected error while waiting for sync clock in")

    def _supervisor_fun(self):
        logger.info("device supervisor started, checking for clock, then starting device")
        while self._is_running:
            if not self._device_is_running:
                self._wait_for_clock()
                logger.info("got it, continue starting...")

                logger.info("deriving nominal framerate from clock signal, counting 10 ticks...")
                derived_fps = self._gpio_backend.derive_nominal_framerate_from_clock()
                logger.info(f"got it, derived {derived_fps}fps...")

                self._device_start(derived_fps)
            else:
                time.sleep(1)

        logger.info("device supervisor exit, stopping devices")
        self._device_stop()
        logger.info("device supervisor exit, stopped devices")

    def _sync_fun(self):
        while self._device_is_running:
            try:
                timestamp_ns = self._gpio_backend.wait_for_clock_rise_signal(timeout=1)
            except TimeoutError:
                # stop devices when no clock is avail, supervisor enables again after clock is received, derives new framerate ans starts backends
                logger.error("no clock signal received within timeout! stopping devices.")
                self._device_stop()
            else:
                self._camera_backend.sync_tick(timestamp_ns)

    def _capture_fun(self):
        while self._device_is_running:
            self._gpio_backend.wait_for_trigger_signal(timeout=None)

            # useful if mobile camera is without any interconnection to a concentrator that could setup a job
            if self._config.allow_standalone_job:
                logger.info("using default capture job")
                self._job = CaptureJob()

            if self._job:
                self._camera_backend.do_capture(self._job.id, self._job.number_captures)
                self._job = None
            else:
                logger.warning("capture request ignored because no job set!")

    def _trigger_fun(self):
        while self._device_is_running:
            # wait until execute job is requested
            if self._flag_execute_job.wait(timeout=1):
                # first clear to avoid endless loops
                self._flag_execute_job.clear()
                # timeout=anything so it doesnt block shutdown. If flag is set during timeout it will be catched during next run and is not lost
                # there is a job that shall be processed, now wait until we get a falling clock
                # timeout not None (to avoid blocking) but longer than any frame could ever take
                self._gpio_backend.wait_for_clock_fall_signal(timeout=1)
                # clock is fallen, this is the sync point to send out trigger to other clients. chosen to send on falling clock because capture
                # shall be on rising clock and this is with 1/2 frame distance far enough that all clients can prepare to capture
                self._gpio_backend._trigger_out.on()  # clients detect rising edge on trigger_in and invoke capture.
                # now we wait until next falling clock and turn off the trigger
                # timeout not None (to avoid blocking) but longer than any frame could ever take
                self._gpio_backend.wait_for_clock_fall_signal(timeout=1)
                self._gpio_backend._trigger_out.off()
                # done, restart waiting for flag...
            else:
                pass
                # just timed out, nothing to take care about.