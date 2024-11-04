import logging
import os
import time
from datetime import datetime
from importlib import import_module
from pathlib import Path
from threading import Event, current_thread

from ..utils.stoppablethread import StoppableThread
from .backends.cameras.abstractbackend import AbstractCameraBackend
from .backends.io.abstractbackend import AbstractIoBackend
from .baseservice import BaseService
from .config.models import ConfigSyncedAcquisition

logger = logging.getLogger(__name__)


DATA_PATH = Path("./media")
# as from image source
PATH_STANDALONE = DATA_PATH / "standalone"


class AcquisitionService(BaseService):
    def __init__(self, config: ConfigSyncedAcquisition):
        super().__init__()

        # init the arguments
        self._config: ConfigSyncedAcquisition = config

        # define private props
        # to sync, a camera backend and io backend is used.
        self._camera_backend: AbstractCameraBackend = None
        self._gpio_backend: AbstractIoBackend = None
        self._sync_thread: StoppableThread = None
        self._trigger_in_thread: StoppableThread = None
        self._trigger_out_thread: StoppableThread = None
        self._supervisor_thread: StoppableThread = None

        self._flag_trigger_job: Event = None
        self._flag_trigger_out: Event = None
        self._device_initialized_once: bool = False

        # initialize private properties.
        self._flag_trigger_job: Event = Event()
        self._flag_trigger_out: Event = Event()

        # ensure data directories exist
        os.makedirs(f"{PATH_STANDALONE}", exist_ok=True)

    def start(self):
        super().start()

        self._gpio_backend: AbstractIoBackend = self._import_backend("io", self._config.io_backends.active_backend)(
            getattr(self._config.io_backends, str(self._config.io_backends.active_backend).lower())
        )
        logger.debug(f"loaded {self._gpio_backend}")

        self._camera_backend: AbstractCameraBackend = self._import_backend("cameras", self._config.camera_backends.active_backend)(
            getattr(self._config.camera_backends, str(self._config.camera_backends.active_backend).lower())
        )
        logger.debug(f"loaded {self._camera_backend}")

        self._gpio_backend.start()

        self._supervisor_thread = StoppableThread(name="_supervisor_thread", target=self._supervisor_fun, args=(), daemon=True)
        self._supervisor_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        if self._gpio_backend:
            self._gpio_backend.stop()

        if self._supervisor_thread and self._supervisor_thread.is_alive():
            self._supervisor_thread.stop()
            self._supervisor_thread.join()

        logger.debug(f"{self.__module__} stopped")

    @staticmethod
    def _import_backend(package: str, backend: str):
        # dynamic import of backend

        module_path = f".backends.{package.lower()}.{backend.lower()}"
        class_name = f"{backend}Backend"
        pkg = ".".join(__name__.split(".")[:-1])  # to allow relative imports

        module = import_module(module_path, package=pkg)
        return getattr(module, class_name)

    def wait_for_hires_frame(self):
        return self._camera_backend.wait_for_hires_frame()

    def done_hires_frames(self):
        return self._camera_backend.done_hires_frames()

    def wait_for_hires_image(self, format: str):
        return self._camera_backend.wait_for_hires_image(format=format)

    def encode_frame_to_image(self, frame, format: str):
        return self._camera_backend.encode_frame_to_image(frame, format)

    def gen_stream(self):
        """
        yield jpeg images to stream to client (if not created otherwise)
        this function may be overriden by backends, but this is the default one
        relies on the backends implementation of _wait_for_lores_image to return a buffer
        """
        logger.info("livestream requested")
        self._camera_backend.start_stream()

        while True:
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

    def trigger_execute_job(self):
        # TODO: all this should run only on primary device! it's not validated, the connector needs to ensure to call the right device currently.
        # maybe config can be changed in future and so also the _tirgger_out_thread is not started on secondary nodes.
        self._flag_trigger_out.set()

    def wait_for_trigger_job(self, timeout: float = None):
        # maybe in future replace by this? lets see... https://superfastpython.com/thread-race-condition-timing/
        # there is only one thread allowed to listen to this event: the jobXservice. Otherwise the event could be missed.
        # standalone mode could process it also, so need to clarify in
        # TODO: check how to allow two listening threads.
        val = self._flag_trigger_job.wait(timeout)
        if val:
            # if true, directly clear, because we trigger only once!
            self._flag_trigger_job.clear()
        return val

    def clear_trigger_job_flag(self):
        self._flag_trigger_job.clear()

    def _device_start(self, derived_fps: int):
        logger.info("starting device")

        if self._device_initialized_once:
            logger.info("device already initialized once, stopping all first before starting again")
            self._device_stop()
        else:
            self._device_initialized_once = True

        self._camera_backend.start(nominal_framerate=derived_fps)

        # sync clock and camera thread
        self._sync_thread = StoppableThread(name="_sync_thread", target=self._sync_fun, args=(), daemon=True)
        self._sync_thread.start()
        # capture thread
        self._trigger_in_thread = StoppableThread(name="_trigger_in_thread", target=self._trigger_in_fun, args=(), daemon=True)
        self._trigger_in_thread.start()
        # forward trigger to other devices thread
        self._trigger_out_thread = StoppableThread(name="_trigger_out_thread", target=self._trigger_out_fun, args=(), daemon=True)
        self._trigger_out_thread.start()

        logger.info("device started")

    def _device_stop(self):
        self._camera_backend.stop()

        if self._trigger_out_thread and self._trigger_out_thread.is_alive():
            self._trigger_out_thread.stop()
            self._trigger_out_thread.join()

        if self._trigger_in_thread and self._trigger_in_thread.is_alive():
            self._trigger_in_thread.stop()
            self._trigger_in_thread.join()

        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.stop()
            self._sync_thread.join()

    def _device_alive(self):
        camera_alive = self._camera_backend.camera_alive()
        trigger_out_alive = self._trigger_out_thread and self._trigger_out_thread.is_alive()
        trigger_in_alive = self._trigger_in_thread and self._trigger_in_thread.is_alive()
        sync_alive = self._sync_thread and self._sync_thread.is_alive()

        return camera_alive and trigger_out_alive and trigger_in_alive and sync_alive

    def _clock_impulse_detected(self, timeout: float = None):
        try:
            if self._gpio_backend.wait_for_clock_rise_signal(timeout=timeout):
                logger.info("clock signal received, continue...")
                return True

        except TimeoutError:
            logger.info("waiting for clock signal in...")
        except Exception as exc:
            logger.exception(exc)
            logger.error("unexpected error while waiting for sync clock in")

        return False

    def _supervisor_fun(self):
        logger.info("device supervisor started, checking for clock, then starting device")

        while not current_thread().stopped():
            if not self._device_alive():
                if not self._clock_impulse_detected(timeout=2.0):
                    # loop restart until we got an impulse from master
                    time.sleep(1)
                    continue

                logger.info("got clock impulse, continue starting...")

                try:
                    logger.info("deriving nominal framerate from clock signal...")
                    derived_fps = self._gpio_backend.derive_nominal_framerate_from_clock()
                    logger.info(f"got it, derived {derived_fps}fps...")
                except Exception as exc:
                    logger.exception(exc)
                    logger.error(f"error deriving framerate: {exc}")

                    self._device_stop()

                try:
                    self._device_start(derived_fps)
                except Exception as exc:
                    logger.exception(exc)
                    logger.error(f"error starting device: {exc}")

                    self._device_stop()

                time.sleep(2)  # just do not try too often...

            time.sleep(1)

        logger.info("device supervisor exit, stopping devices")
        self._device_stop()  # safety first, maybe it's double stopped, but prevent any stalling of device-threads

        logger.info("left _supervisor_fun")

    def _sync_fun(self):
        while not current_thread().stopped():
            try:
                timestamp_ns = self._gpio_backend.wait_for_clock_rise_signal(timeout=1)
            except TimeoutError:
                # stop devices when no clock is avail, supervisor enables again after clock is received, derives new framerate ans starts backends
                logger.error("clock signal missing.")
                break
            else:
                self._camera_backend.sync_tick(timestamp_ns)

        logger.info("left _sync_fun")  # if left, it allows supervisor to restart if needed.

    def _trigger_in_fun(self):
        logger.info("_trigger_in_fun started")
        while not current_thread().stopped():
            if self._gpio_backend._trigger_in_flag.wait(timeout=1.0):
                # if true, directly clear, because we trigger only once!
                self._gpio_backend._trigger_in_flag.clear()
                # maybe in future replace by this? lets see... https://superfastpython.com/thread-race-condition-timing/

                # job is triggered by this flag.
                self._flag_trigger_job.set()

                if self._config.standalone_mode:
                    # recommended to disable in production.
                    logger.info("standalone mode is enabled! to use the job processor and connectivity, disable standalone mode in config!")
                    frame = self.wait_for_hires_frame()
                    frame = self.done_hires_frames()

                    filename = Path(f"img_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')}").with_suffix(".jpg")
                    filepath = PATH_STANDALONE / filename

                    with open(filepath, "wb") as f:
                        f.write(self.encode_frame_to_image(frame, "jpeg"))

                    logger.info(f"image saved to {filepath}")

        logger.info("left _trigger_in_fun")  # if left, it allows supervisor to restart if needed.

    def _trigger_out_fun(self):
        while not current_thread().stopped():
            # wait until execute job is requested
            if self._flag_trigger_out.wait(timeout=1):
                # first clear to avoid endless loops
                self._flag_trigger_out.clear()

                logger.info("send trigger_out to start processing job")
                # timeout=anything so it doesnt block shutdown. If flag is set during timeout it will be catched during next run and is not lost
                # there is a job that shall be processed, now wait until we get a falling clock
                # timeout not None (to avoid blocking) but longer than any frame could ever take
                try:
                    self._gpio_backend.wait_for_clock_fall_signal(timeout=1)
                except TimeoutError:
                    logger.error("clock signal missing.")
                    break  # leave and allow to restart device.
                # clock is fallen, this is the sync point to send out trigger to other clients. chosen to send on falling clock because capture
                # shall be on rising clock and this is with 1/2 frame distance far enough that all clients can prepare to capture
                self._gpio_backend.set_trigger_out(True)  # clients detect rising edge on trigger_in and invoke capture.
                # now we wait until next falling clock and turn off the trigger
                # timeout not None (to avoid blocking) but longer than any frame could ever take
                try:
                    self._gpio_backend.wait_for_clock_fall_signal(timeout=1)
                except TimeoutError:
                    logger.error("clock signal missing.")
                    break  # leave and allow to restart device.

                self._gpio_backend.set_trigger_out(False)
                # done, restart waiting for flag...
            else:
                pass
                # just timed out, nothing to take care about.

        logger.info("left _trigger_out_fun")  # if left, it allows supervisor to restart if needed.
