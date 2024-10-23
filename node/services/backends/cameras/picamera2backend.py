import logging
import time
from datetime import datetime
from pathlib import Path
from threading import Event, Thread

from libcamera import Transform, controls
from picamera2 import Picamera2, Preview
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

from ....config.models import ConfigPicamera2
from .backend import BaseBackend, StreamingOutput

logger = logging.getLogger(__name__)


ADJUST_EVERY_X_CYCLE = 10


class Picamera2Backend(BaseBackend):
    def __init__(self, config: ConfigPicamera2):
        super().__init__()
        # init with arguments
        self._config: ConfigPicamera2 = config

        # private props
        self._picamera2: Picamera2 = None
        self._timestamp_monotonic_ns = None
        self._nominal_framerate: float = None
        self._adjust_sync_offset: int = 0
        self._capture: Event = None
        self._camera_thread: Thread = None
        self._streaming_output: StreamingOutput = None

        # initialize private props
        self._capture = Event()
        self._streaming_output: StreamingOutput = StreamingOutput()

        print(f"global_camera_info {Picamera2.global_camera_info()}")

    def start(self, nominal_framerate: int = None):
        """To start the backend, configure picamera2"""
        super().start()

        if not nominal_framerate:
            # if 0 or None, fail!
            raise RuntimeError("nominal framerate needs to be given!")

        self._nominal_framerate = nominal_framerate

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
                buffer_count=3,
                queue=False,
                controls={"FrameRate": self._nominal_framerate},
                transform=Transform(hflip=False, vflip=False),
            )
        )
        self._picamera2.options["quality"] = self._config.original_still_quality  # capture_file image quality

        if self._config.enable_preview_display:
            print("starting display preview")
            # Preview.DRM tested, but leads to many dropped frames.
            # Preview.QTGL currently not available on Pi3 according to own testing.
            # Preview.QT seems to work reasonably well, so use this for now hardcoded.
            # Further refs:
            # https://github.com/raspberrypi/picamera2/issues/989
            self._picamera2.start_preview(Preview.QT, x=0, y=0, width=800, height=480)
            # self._qpicamera2 = QPicamera2(self._picamera2, width=800, height=480, keep_ar=True)
        else:
            pass
            # null Preview is automatically initialized and it needs at least one preview to drive the camera

        # start camera
        self._picamera2.start()

        self._init_autofocus()

        self._camera_thread = Thread(name="_camera_thread", target=self._camera_fun, args=(), daemon=True)
        self._camera_thread.start()

        logger.info(f"camera_config: {self._picamera2.camera_config}")
        logger.info(f"camera_controls: {self._picamera2.camera_controls}")
        logger.info(f"controls: {self._picamera2.controls}")
        logger.info(f"camera_properties: {self._picamera2.camera_properties}")
        print(f"nominal framerate set to {self._nominal_framerate}")
        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        if self._picamera2:
            self._picamera2.stop()
            self._picamera2.close()  # need to close camera so it can be used by other processes also (or be started again)

        logger.debug(f"{self.__module__} stopped")

    def start_stream(self):
        self._picamera2.stop_recording()
        encoder = MJPEGEncoder()
        # encoder.frame_skip_count = 1  # every nth frame to save cpu/bandwith on
        # low power devices but this can cause issues with timing it seems and permanent non-synchronizity

        self._picamera2.start_recording(encoder, FileOutput(self._streaming_output))
        print("encoding stream started")

    def stop_stream(self):
        self._picamera2.stop_recording()
        print("encoding stream stopped")

    def wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        with self._streaming_output.condition:
            if not self._streaming_output.condition.wait(timeout=2.0):
                raise TimeoutError("timeout receiving frames")

            return self._streaming_output.frame

    def do_capture(self, number_frames: int = 1):
        self._capture.set()

    def sync_tick(self, timestamp_ns: int):
        self._timestamp_monotonic_ns = timestamp_ns

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
        print("starting _camera_fun")
        timestamp_delta = None
        adjust_cycle_counter = 0
        adjust_amount_us = 0
        adjust_amount_clamped_us = 0
        capture_time_assigned_timestamp_ns = None

        while self._is_running:
            if self._capture.is_set():
                self._capture.clear()
                print("####### capture #######")

                filename = Path(f"img_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')}")
                print(f"filename {filename}")

                if timestamp_delta:
                    print(f"delta right before capture is {round(timestamp_delta/1e6,1)} ms")

                tms = time.time()
                # take pick like following line leads to stalling in camera thread. the below method seems to have no effect on picam's cam thread
                # picam_metadata = picamera2.capture_file(f"{filename}.jpg")
                # It's better to capture the still in this thread, not in the one driving the camera
                request = self._picamera2.capture_request()
                request.save("main", filename.with_suffix(".jpg"))
                request.release()

                print(f"####### capture end, took {round((time.time() - tms), 2)}s #######")
            else:
                if capture_time_assigned_timestamp_ns == self._timestamp_monotonic_ns:
                    print("warning: timestamp monotonic did not increase!")
                    adjust_cycle_counter = 0

                capture_time_assigned_timestamp_ns = self._timestamp_monotonic_ns
                picam_metadata = self._picamera2.capture_metadata()

                nominal_frame_duration_us = 1.0 / self._nominal_framerate * 1.0e6

                if capture_time_assigned_timestamp_ns is not None:
                    timestamp_delta = picam_metadata["SensorTimestamp"] - capture_time_assigned_timestamp_ns  # in ns
                else:
                    print("warning: no sync time available to synchronize to")

                if adjust_cycle_counter >= ADJUST_EVERY_X_CYCLE:
                    adjust_cycle_counter = 0
                    adjust_amount_us = (timestamp_delta or 0) / 1e3
                    adjust_amount_clamped_us = self.clamp(adjust_amount_us, -0.45 * nominal_frame_duration_us, 0.45 * nominal_frame_duration_us)
                else:
                    adjust_cycle_counter += 1
                    adjust_amount_us = 0
                    adjust_amount_clamped_us = 0

                with self._picamera2.controls as ctrl:
                    # set new FrameDurationLimits based on P_controller output.
                    ctrl.FrameDurationLimits = (
                        int((1.0 / self._nominal_framerate * 1.0e6) - adjust_amount_clamped_us),
                        int((1.0 / self._nominal_framerate * 1.0e6) - adjust_amount_clamped_us),
                    )

                print(
                    f"clock_in={round((capture_time_assigned_timestamp_ns or 0)/1e6,1)} ms, "
                    f"sensor_timestamp={round(picam_metadata['SensorTimestamp']/1e6,1)} ms, "
                    f"delta={round((timestamp_delta or 0)/1e6,1)} ms, "
                    f"FrameDuration={round(picam_metadata['FrameDuration']/1e3,1)} ms "
                    f"adjust_amount={round(adjust_amount_us/1e3,1)} ms "
                    f"adjust_amount_clamped={round(adjust_amount_clamped_us/1e3,1)} ms "
                )

        print("_camera_fun left")


if __name__ == "__main__":
    print("should not be started directly")
