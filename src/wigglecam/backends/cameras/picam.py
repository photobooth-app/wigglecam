import io
import logging
import time
from threading import Condition, Event, current_thread
from typing import cast

import cv2
from libcamera import Transform, controls  # type: ignore
from picamera2 import Picamera2, Preview  # type: ignore
from picamera2.encoders import MJPEGEncoder, Quality  # type: ignore
from picamera2.outputs import FileOutput  # type: ignore
from PIL import Image

from ...config.models import ConfigBackendPicamera2
from ...utils.stoppablethread import StoppableThread
from ..base import CameraBackend, StreamingOutput

logger = logging.getLogger(__name__)


class Picam(CameraBackend):
    def __init__(self, config: ConfigBackendPicamera2):
        super().__init__()
        # init with arguments
        self._config: ConfigBackendPicamera2 = config

        # private props
        self._picamera2: Picamera2 | None = None
        self._streaming_output: StreamingOutput | None = None
        self._hires_data: HiresData | None = None
        self._adjust_cycle_counter: int = 0

        logger.info(f"global_camera_info {Picamera2.global_camera_info()}")

    def start(self, nominal_framerate: int):
        """To start the backend, configure picamera2"""
        super().start(nominal_framerate=nominal_framerate)

        # initialize private props
        self._streaming_output = StreamingOutput()
        self._hires_data = HiresData(frame=None, request_hires_still=Event(), condition=Condition())
        self._adjust_cycle_counter: int = 0

        # https://github.com/raspberrypi/picamera2/issues/576
        if self._picamera2:
            self._picamera2.close()
            del self._picamera2

        self._picamera2 = Picamera2(camera_num=self._config.camera_num)
        assert self._picamera2

        # configure; camera needs to be stopped before
        append_optmemory_format = {}
        if self._config.optimize_memoryconsumption:
            logger.info("enabled memory optimization by choosing YUV420 format for main/lores streams")
            # if using YUV420 on main, also disable NoisReduction because it's done in software and causes framerate dropping on vc4 devices
            # https://github.com/raspberrypi/picamera2/discussions/1158#discussioncomment-11212355
            append_optmemory_format = {"format": "YUV420"}

        camera_configuration = self._picamera2.create_still_configuration(
            main={"size": (self._config.CAPTURE_CAM_RESOLUTION_WIDTH, self._config.CAPTURE_CAM_RESOLUTION_HEIGHT), **append_optmemory_format},
            lores={"size": (self._config.LIVEVIEW_RESOLUTION_WIDTH, self._config.LIVEVIEW_RESOLUTION_HEIGHT), **append_optmemory_format},
            encode="lores",
            display="lores",
            buffer_count=2,
            queue=True,  # TODO: validate. Seems False is working better on slower systems? but also on Pi5?
            controls={"FrameRate": self._nominal_framerate, "NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Off},
            transform=Transform(hflip=False, vflip=False),
        )
        self._picamera2.configure(camera_configuration)

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

        logger.info(f"camera_config: {self._picamera2.camera_config}")
        logger.info(f"camera_controls: {self._picamera2.camera_controls}")
        logger.info(f"controls: {self._picamera2.controls}")
        logger.info(f"camera_properties: {self._picamera2.camera_properties}")
        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        if self._picamera2:
            self._picamera2.stop()
            self._picamera2.close()  # need to close camera so it can be used by other processes also (or be started again)

        logger.debug(f"{self.__module__} stopped")

    def camera_alive(self) -> bool:
        super_alive = super().camera_alive()

        return super_alive and True

    def start_stream(self):
        assert self._picamera2
        self._picamera2.stop_recording()
        encoder = MJPEGEncoder()
        # encoder.frame_skip_count = 2  # every nth frame to save cpu/bandwith on
        # low power devices but this can cause issues with timing it seems and permanent non-synchronizity

        logger.info(f"stream quality {Quality[self._config.videostream_quality]=}")

        self._picamera2.start_recording(encoder, FileOutput(self._streaming_output), quality=Quality[self._config.videostream_quality])
        logger.info("encoding stream started")

    def stop_stream(self):
        assert self._picamera2
        self._picamera2.stop_recording()
        logger.info("encoding stream stopped")

    def wait_for_lores_image(self):
        assert self._streaming_output
        """for other threads to receive a lores JPEG image"""
        with self._streaming_output.condition:
            if not self._streaming_output.condition.wait(timeout=2.0):
                raise TimeoutError("timeout receiving frames")

            assert self._streaming_output.frame
            return self._streaming_output.frame

    def wait_for_hires_frame(self):
        assert self._hires_data
        with self._hires_data.condition:
            self._hires_data.request_hires_still.set()

            if not self._hires_data.condition.wait(timeout=2.0):
                raise TimeoutError("timeout receiving frames")

            # self._hires_data.request_hires_still.clear()
            assert self._hires_data.frame
            return self._hires_data.frame

    def done_hires_frames(self):
        self._hires_data.request_hires_still.clear()

    def wait_for_hires_image(self, format: ImageFormats) -> bytes:
        return super().wait_for_hires_image(format=format)

    def encode_frame_to_image(self, frame, format: ImageFormats) -> bytes:
        assert self._picamera2
        # for picamera2 frame is a picamera2 buffer so conversion needed. can be RGB or YUV420 depending on memory opt
        if format == "jpeg":
            tms = time.time()
            bytes_io = io.BytesIO()

            if self._config.optimize_memoryconsumption:
                logger.info("enabled memory optimization so frame is in YUV420 and converted to RGB now")
                # need to convert from YUV420 to RGB before processing jpg because PIL accepts only RGB
                # currently this is the only place cv2 is used, maybe there is another way to save cv2 from being used on nodes.
                array = self._picamera2.helpers.make_array(frame, self._picamera2.camera_config["main"])
                array = cv2.cvtColor(array, cv2.COLOR_YUV420p2BGR)  # yes, this is correct ^^
                image = Image.fromarray(array, "RGB")
            else:
                image = self._picamera2.helpers.make_image(frame, self._picamera2.camera_config["main"])

            image.save(bytes_io, format="jpeg", quality=self._config.original_still_quality)
            out = bytes_io.getbuffer()

            logger.info(f"jpg encode finished, time taken: {round((time.time() - tms) * 1.0e3, 0)}ms")
            return out

        else:
            raise NotImplementedError

    def _init_autofocus(self):
        assert self._picamera2
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

    async def _device_fun(self):
        assert self._picamera2
        assert self._hires_data
        logger.debug("starting _camera_fun")

        while not cast(StoppableThread, current_thread()).stopped():
            if self._hires_data.request_hires_still.is_set():
                # only capture one pic and return, overlying classes are responsible to ask again if needed fast enough
                # self._hires_data.request_hires_still.clear()

                # capture hq picture
                with self._picamera2.captured_request(wait=1.5) as request:
                    self._hires_data.frame = request.make_buffer("main")
                    picam_metadata = request.get_metadata()

                logger.info("got buffer from cam to send to waiting threads")

                with self._hires_data.condition:
                    self._hires_data.condition.notify_all()
            else:
                # capture metadata blocks until new metadata is avail
                try:
                    picam_metadata = self._picamera2.capture_metadata(wait=2.0)

                except TimeoutError as exc:
                    logger.warning(f"camera timed out: {exc}")
                    break

        logger.info("_camera_fun left")
