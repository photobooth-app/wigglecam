import logging
import time
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from threading import current_thread

from libcamera import Transform, controls
from picamera2 import Picamera2, Preview
from picamera2.encoders import MJPEGEncoder, Quality
from picamera2.outputs import FileOutput
from PIL import Image

from ....utils.stoppablethread import StoppableThread
from ...config.models import ConfigBackendPicamera2
from .abstractbackend import AbstractCameraBackend, StreamingOutput

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
        self._adjust_sync_offset: int = 0
        self._camera_thread: StoppableThread = None
        self._processing_thread: StoppableThread = None
        self._queue_processing: Queue = None
        self._streaming_output: StreamingOutput = None

        # initialize private props
        self._streaming_output: StreamingOutput = StreamingOutput()
        self._queue_processing: Queue = Queue()

        logger.info(f"global_camera_info {Picamera2.global_camera_info()}")

    def start(self, nominal_framerate: int = None):
        """To start the backend, configure picamera2"""
        super().start(nominal_framerate=nominal_framerate)

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

        self._camera_thread = StoppableThread(name="_camera_thread", target=self._camera_fun, args=(), daemon=True)
        self._camera_thread.start()

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

        if self._camera_thread and self._camera_thread.is_alive():
            self._camera_thread.stop()
            self._camera_thread.join()

        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.stop()
            self._processing_thread.join()

        logger.debug(f"{self.__module__} stopped")

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

    @staticmethod
    def clamp(n, min_value, max_value):
        return max(min_value, min(n, max_value))

    def _camera_fun(self):
        logger.debug("starting _camera_fun")
        timestamp_delta_ns = 0
        adjust_cycle_counter = 0
        adjust_amount_us = 0
        adjust_amount_clamped_us = 0
        capture_time_assigned_timestamp_ns = None
        nominal_frame_duration_us = 1.0 / self._nominal_framerate * 1.0e6

        while not current_thread().stopped():
            self._event_request_tick.wait(timeout=2.0)
            self._event_request_tick.clear()
            capture_time_assigned_timestamp_ns = 0

            job = self._picamera2.capture_request(wait=False)

            try:
                request = self._picamera2.wait(job, timeout=2.0)
                capture_time_assigned_timestamp_ns = self._queue_timestamp_monotonic_ns.get(block=True, timeout=2.0)
            except (Empty, TimeoutError):  # no information in exc avail so omitted
                logger.warning("timeout while waiting for clock/camera")
                # break thread run loop, so the function will quit and .alive is false for this thread -
                # supervisor could then decide to start it again.
                break

            if self._capture.is_set():
                self._capture.clear()
                adjust_cycle_counter = 0  # don't adjust right after capture.
                self._queue_processing.put(request.make_image("main"))  # make_array/make_buffer/make_image: what is most efficient?
                logger.info("queued up buffer to process image")

            picam_metadata = request.get_metadata()
            request.release()

            timestamp_delta_ns = picam_metadata["SensorTimestamp"] - capture_time_assigned_timestamp_ns  # in ns

            if (timestamp_delta_ns / 1.0e9) < -(0.5 / self._nominal_framerate):
                logger.warning("image is older than 1/2 frameduration. dropping one frame trying to catch up")
                self._picamera2.capture_metadata()
                adjust_cycle_counter = 0  # don't adjust right after capture.

            if (timestamp_delta_ns / 1.0e9) > +(0.5 / self._nominal_framerate):
                logger.warning("ref clock is older than 1/2 frameduration. dropping timestamp queue until catched up")
                while True:
                    try:
                        self._queue_timestamp_monotonic_ns.get_nowait()
                    except Empty:
                        adjust_cycle_counter = 0  # don't adjust right after capture.
                        break

            if adjust_cycle_counter >= ADJUST_EVERY_X_CYCLE:
                adjust_cycle_counter = 0
                adjust_amount_us = timestamp_delta_ns / 1.0e3
                adjust_amount_clamped_us = self.clamp(adjust_amount_us, -0.9 * nominal_frame_duration_us, 0.9 * nominal_frame_duration_us)
            else:
                adjust_cycle_counter += 1
                adjust_amount_us = 0
                adjust_amount_clamped_us = 0

            with self._picamera2.controls as ctrl:
                fixed_frame_duration = int(nominal_frame_duration_us - adjust_amount_clamped_us)
                ctrl.FrameDurationLimits = (fixed_frame_duration,) * 2

            THRESHOLD_LOG = 1.0
            if abs(timestamp_delta_ns / 1.0e6) > THRESHOLD_LOG:
                # even in debug reduce verbosity a bit if all is fine and within 2ms tolerance
                logger.debug(
                    f"timestamp clk/sensor=({round((capture_time_assigned_timestamp_ns)/1e6,1)}/"
                    f"{round(picam_metadata['SensorTimestamp']/1e6,1)}) ms, "
                    f"delta={round((timestamp_delta_ns)/1e6,1)} ms, "
                    f"adj_cycle_cntr={adjust_cycle_counter}, "
                    f"adjust_amount={round(adjust_amount_us/1e3,1)} ms "
                    f"adjust_amount_clamped={round(adjust_amount_clamped_us/1e3,1)} ms "
                    f"FrameDuration={round(picam_metadata['FrameDuration']/1e3,1)} ms "
                )
            else:
                pass
                # silent

        logger.info("_camera_fun left")

    def _processing_fun(self):
        logger.debug("starting _processing_fun")
        img_to_compress: Image = None

        while not current_thread().stopped():
            try:
                img_to_compress: Image = self._queue_processing.get(block=True, timeout=1.0)
                logger.info("got img off queue, jpg proc start")
            except Empty:
                continue  # just continue but allow .stopped to exit after 1.0 sec latest...

            # start processing here...
            folder = Path("./tmp/")
            filename = Path(f"img_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')}")
            filepath = folder / filename
            logger.info(f"{filepath=}")

            tms = time.time()
            img_to_compress.save(filepath.with_suffix(".jpg"), quality=self._config.original_still_quality)
            logger.info(f"jpg compression finished, time taken: {round((time.time() - tms)*1.0e3, 0)}ms")

        logger.error("left _processing_fun. it's not restarted...")
