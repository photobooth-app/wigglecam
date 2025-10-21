import asyncio
import io
import logging
import uuid

from libcamera import Transform, controls  # type: ignore
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder, Quality

from wigglecam.backends.cameras.output.pynng import PynngOutput

from ...config.camera_picamera2 import CfgCameraPicamera2
from ...dto import ImageMessage
from .base import CameraBackend

logger = logging.getLogger(__name__)


class Picam(CameraBackend):
    def __init__(self, device_id: int):
        self._config = CfgCameraPicamera2()
        super().__init__(device_id, PynngOutput(f"tcp://{self._config.server}:5556"), PynngOutput(f"tcp://{self._config.server}:5556"))

        self._picamera2: Picamera2 | None = None

        logger.info(f"Picamera2Backend initialized, {device_id=}, connecting to server {self._config.server}")

    async def trigger_hires_capture(self, job_id: uuid.UUID):
        jpeg_bytes = await asyncio.to_thread(self._produce_image)

        msg_bytes = ImageMessage(self._device_id, jpg_bytes=jpeg_bytes, job_id=job_id).to_bytes()
        self._output_hires.write(msg_bytes)  # TODO: improve for async create separate loop for processing to avoid blocking this thread.

    def _produce_image(self) -> bytes:
        assert self._picamera2

        jpeg_buffer = io.BytesIO()
        self._picamera2.capture_file(jpeg_buffer, format="jpeg")
        jpeg_bytes = jpeg_buffer.getvalue()

        return jpeg_bytes

    async def run(self):
        # initialize private props

        logger.debug("starting _camera_fun")

        self._picamera2 = Picamera2(camera_num=self._config.camera_num)

        # configure; camera needs to be stopped before
        append_optmemory_format = {}
        if self._config.optimize_memoryconsumption:
            logger.info("enabled memory optimization by choosing YUV420 format for main/lores streams")
            # if using YUV420 on main, also disable NoisReduction because it's done in software and causes framerate dropping on vc4 devices
            # https://github.com/raspberrypi/picamera2/discussions/1158#discussioncomment-11212355
            append_optmemory_format = {"format": "YUV420"}

        camera_configuration = self._picamera2.create_still_configuration(
            main={"size": (self._config.camera_res_width, self._config.camera_res_height), **append_optmemory_format},
            lores={"size": (self._config.stream_res_width, self._config.stream_res_height), **append_optmemory_format},
            encode="lores",
            display=None,
            buffer_count=2,
            # queue=True,  # TODO: validate. Seems False is working better on slower systems? but also on Pi5?
            controls={"FrameRate": self._config.framerate, "NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Off},
            transform=Transform(hflip=self._config.flip_horizontal, vflip=self._config.flip_vertical),
        )
        self._picamera2.configure(camera_configuration)
        # self._picamera2.start_preview(None)

        # start camera
        self._picamera2.start()

        try:
            self._picamera2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except RuntimeError as exc:
            logger.critical(f"control not available on camera - autofocus not working properly {exc}")

        try:
            self._picamera2.set_controls({"AfSpeed": controls.AfSpeedEnum.Fast})
        except RuntimeError as exc:
            logger.info(f"control not available on all cameras - can ignore {exc}")

        logger.info(f"camera_config: {self._picamera2.camera_config}")
        logger.info(f"camera_controls: {self._picamera2.camera_controls}")
        logger.info(f"controls: {self._picamera2.controls}")
        logger.info(f"camera_properties: {self._picamera2.camera_properties}")

        self._picamera2.start_recording(MJPEGEncoder(), self._output_lores, quality=Quality[self._config.videostream_quality])
        logger.info("encoding stream started")

        logger.debug(f"{self.__module__} started")

        while True:
            # capture metadata blocks until new metadata is avail
            try:
                meta = self._picamera2.capture_metadata()
                print(meta)

            except TimeoutError as exc:
                logger.warning(f"camera timed out: {exc}")
                break

        self._picamera2.stop_recording()
        logger.info("encoding stream stopped")

        logger.info("_camera_fun left")
