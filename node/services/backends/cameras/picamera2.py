import logging
import time
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from threading import BrokenBarrierError, current_thread

from libcamera import Transform, controls
from picamera2 import Picamera2, Preview
from picamera2.encoders import MJPEGEncoder, Quality
from picamera2.outputs import FileOutput

from ....utils.stoppablethread import StoppableThread
from ...config.models import ConfigBackendPicamera2
from .abstractbackend import AbstractCameraBackend, BackendItem, BackendRequest, StreamingOutput

logger = logging.getLogger(__name__)


ADJUST_EVERY_X_CYCLE = 10


class Picamera2Backend(AbstractCameraBackend):
    def __init__(self, config: ConfigBackendPicamera2):
        super().__init__()
        # init with arguments
        self._config: ConfigBackendPicamera2 = config

        # private props
        self._picamera2: Picamera2 = None
        self._nominal_framerate: float = None
        self._processing_thread: StoppableThread = None
        self._queue_processing: Queue[tuple[BackendRequest, object]] = None
        self._streaming_output: StreamingOutput = None

        logger.info(f"global_camera_info {Picamera2.global_camera_info()}")

    def start(self, nominal_framerate: int = None):
        """To start the backend, configure picamera2"""
        super().start(nominal_framerate=nominal_framerate)

        # initialize private props
        self._streaming_output: StreamingOutput = StreamingOutput()
        self._queue_processing: Queue[tuple[BackendRequest, object]] = Queue()

        # https://github.com/raspberrypi/picamera2/issues/576
        if self._picamera2:
            self._picamera2.close()
            del self._picamera2

        self._picamera2: Picamera2 = Picamera2(camera_num=self._config.camera_num)

        # configure; camera needs to be stopped before
        self._picamera2.configure(
            self._picamera2.create_still_configuration(
                main={"size": (self._config.CAPTURE_CAM_RESOLUTION_WIDTH, self._config.CAPTURE_CAM_RESOLUTION_HEIGHT)},
                lores={"size": (self._config.LIVEVIEW_RESOLUTION_WIDTH, self._config.LIVEVIEW_RESOLUTION_HEIGHT)},
                encode="lores",
                display="lores",
                buffer_count=2,
                queue=True,  # TODO: validate. Seems False is working better on slower systems? but also on Pi5?
                controls={"FrameRate": self._nominal_framerate},
                transform=Transform(hflip=False, vflip=False),
            )
        )

        if self._config.enable_preview_display:
            logger.info("starting display preview")
            # INFO: QT catches the Ctrl-C listener, so the app is not shut down properly with the display enabled.
            # use for testing purposes only!
            # Preview.DRM tested, but leads to many dropped frames.
            # Preview.QTGL currently not available on Pi3 according to own testing.
            # Preview.QT seems to work reasonably well, so use this for now hardcoded.
            # Further refs:
            # https://github.com/raspberrypi/picamera2/issues/989
            self._picamera2.start_preview(Preview.QT, x=0, y=0, width=400, height=240)
            # self._qpicamera2 = QPicamera2(self._picamera2, width=800, height=480, keep_ar=True)
        else:
            pass
            logger.info("preview disabled in config")
            # null Preview is automatically initialized and it needs at least one preview to drive the camera

        # at this point we can receive the framedurationlimits valid for the selected configuration
        # -> use to validate mode is possible, error if not possible, warn if very close
        self._check_framerate()

        # start camera
        self._picamera2.start()

        self._init_autofocus()

        self._processing_thread = StoppableThread(name="_processing_thread", target=self._processing_fun, args=(), daemon=True)
        self._processing_thread.start()

        logger.info(f"camera_config: {self._picamera2.camera_config}")
        logger.info(f"camera_controls: {self._picamera2.camera_controls}")
        logger.info(f"controls: {self._picamera2.controls}")
        logger.info(f"camera_properties: {self._picamera2.camera_properties}")
        logger.info(f"nominal framerate set to {self._nominal_framerate}")
        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        if self._picamera2:
            self._picamera2.stop()
            self._picamera2.close()  # need to close camera so it can be used by other processes also (or be started again)

        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.stop()
            self._processing_thread.join()

        logger.debug(f"{self.__module__} stopped")

    def camera_alive(self) -> bool:
        super_alive = super().camera_alive()
        processing_alive = self._processing_thread and self._processing_thread.is_alive()

        return super_alive and processing_alive

    def start_stream(self):
        self._picamera2.stop_recording()
        encoder = MJPEGEncoder()
        # encoder.frame_skip_count = 2  # every nth frame to save cpu/bandwith on
        # low power devices but this can cause issues with timing it seems and permanent non-synchronizity

        logger.info(f"stream quality {Quality[self._config.videostream_quality]=}")

        self._picamera2.start_recording(encoder, FileOutput(self._streaming_output), quality=Quality[self._config.videostream_quality])
        logger.info("encoding stream started")

    def stop_stream(self):
        self._picamera2.stop_recording()
        logger.info("encoding stream stopped")

    def wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        with self._streaming_output.condition:
            if not self._streaming_output.condition.wait(timeout=2.0):
                raise TimeoutError("timeout receiving frames")

            return self._streaming_output.frame

    def _check_framerate(self):
        assert self._nominal_framerate is not None

        framedurationlimits = self._picamera2.camera_controls["FrameDurationLimits"][:2]  # limits is in µs (min,max)
        fpslimits = tuple([round(1.0 / (val * 1.0e-6), 1) for val in framedurationlimits])  # converted to frames per second fps

        logger.info(f"min frame duration {framedurationlimits[0]}, max frame duration {framedurationlimits[1]}")
        logger.info(f"max fps {fpslimits[0]}, min fps {fpslimits[1]}")

        if self._nominal_framerate >= fpslimits[0] or self._nominal_framerate <= fpslimits[1]:
            raise RuntimeError("nominal framerate is out of camera limits!")

        WARNING_THRESHOLD = 0.1
        if self._nominal_framerate > (fpslimits[0] * (1 - WARNING_THRESHOLD)) or self._nominal_framerate < fpslimits[1] * (1 + WARNING_THRESHOLD):
            logger.warning("nominal framerate is close to cameras capabilities, this might have effect on sync performance!")

    def _init_autofocus(self):
        """
        on start set autofocus to continuous if requested by config or
        auto and trigger regularly
        """

        try:
            self._picamera2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except RuntimeError as exc:
            logger.critical(f"control not available on camera - autofocus not working properly {exc}")

        try:
            self._picamera2.set_controls({"AfSpeed": controls.AfSpeedEnum.Fast})
        except RuntimeError as exc:
            logger.info(f"control not available on all cameras - can ignore {exc}")

        logger.debug("autofocus set")

    def recover(self):
        tms = time.time()
        try:
            self._picamera2.drop_frames(2)
        except Exception:
            pass

        logger.info(f"recovered, time taken: {round((time.time() - tms)*1.0e3, 0)}ms")

    def _align_fun(self):
        logger.debug("starting _align_fun")
        timestamp_delta_ns = 0
        adjust_cycle_counter = 0
        adjust_amount_us = 0
        # capture_time_assigned_timestamp_ns = None
        nominal_frame_duration = 1.0 / self._nominal_framerate

        self.recover()

        while not current_thread().stopped():
            # if self._capture_in_progress:
            #     adjust_cycle_counter = 0  # keep counter 0 until something is in progress and wait X_CYCLES until adjustment is done afterwards

            try:
                self._barrier.wait()
                # at this point we got an updated self._align_timestampset set in barriers action.
            except BrokenBarrierError:
                logger.debug("sync barrier broke")
                break

            timestamp_delta_ns = self._align_timestampset.camera - self._align_timestampset.reference  # in ns

            if adjust_cycle_counter >= ADJUST_EVERY_X_CYCLE:
                adjust_cycle_counter = 0
                adjust_amount_us = -timestamp_delta_ns / 1.0e3
            else:
                adjust_cycle_counter += 1
                adjust_amount_us = 0

            with self._picamera2.controls as ctrl:
                fixed_frame_duration = int(nominal_frame_duration * 1e6 + adjust_amount_us)
                ctrl.FrameDurationLimits = (fixed_frame_duration,) * 2

            THRESHOLD_LOG = 0
            if abs(timestamp_delta_ns / 1.0e6) > THRESHOLD_LOG:
                # even in debug reduce verbosity a bit if all is fine and within 2ms tolerance
                logger.debug(
                    f"🕑 clk/cam/Δ/adjust=( "
                    f"{(self._align_timestampset.reference)/1e6:.1f} / "
                    f"{self._align_timestampset.camera/1e6:.1f} / "
                    f"{timestamp_delta_ns/1e6:5.1f} / "
                    f"{adjust_amount_us/1e3:5.1f}) ms"
                    # f"FrameDuration={round(picam_metadata['FrameDuration']/1e3,1)} ms "
                )
            else:
                pass
                # silent

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
                # TODO: check if capable to keep up with the framerate or something get lost? for now we only use 1 frame so it's ok
                tms = time.time()
                buffer = self._picamera2.capture_buffer("main", wait=2.0)
                self._queue_processing.put((backendrequest, buffer))
                logger.info(f"queued up buffer to process image, time taken: {round((time.time() - tms)*1.0e3, 0)}ms")
            else:
                try:
                    picam_metadata = self._picamera2.capture_metadata(wait=2.0)
                    self._current_timestampset.camera = picam_metadata["SensorTimestamp"]
                except TimeoutError as exc:
                    logger.warning(f"camera timed out: {exc}")
                    break

                try:
                    self._barrier.wait()
                except BrokenBarrierError:
                    logger.debug("sync barrier broke")
                    break

        logger.info("_camera_fun left")

    def _processing_fun(self):
        # TODO: this might be better in multiprocessing or use some lib that is in c++ releasing the gil during processing...
        logger.debug("starting _processing_fun")
        buffer_to_proc = None

        while not current_thread().stopped():
            try:
                (backendrequest, buffer_to_proc) = self._queue_processing.get(block=True, timeout=1.0)
                logger.info("got img off queue, jpg proc start")
            except Empty:
                continue  # just continue but allow .stopped to exit after 1.0 sec latest...

            # start processing here...
            folder = Path("./tmp/")
            filename = Path(f"img_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')}")
            filepath = folder / filename
            logger.info(f"{filepath=}")

            tms = time.time()
            image = self._picamera2.helpers.make_image(buffer_to_proc, self._picamera2.camera_config["main"])
            image.save(filepath.with_suffix(".jpg"), quality=self._config.original_still_quality)
            logger.info(f"jpg compression finished, time taken: {round((time.time() - tms)*1.0e3, 0)}ms")

            backenditem = BackendItem(
                filepath=filepath,
            )
            self._queue_out.put(backenditem)
            logger.info(f"result item put on output queue: {backenditem}")

            self._queue_in.task_done()

        logger.info("_processing_fun left")
