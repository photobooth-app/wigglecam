import asyncio
import io
import logging
import uuid

from libcamera import Transform, controls  # type: ignore
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder, Quality
from picamera2.outputs.output import Output

from ...config.camera_picamera2 import CfgCameraPicamera2
from ...dto import ImageMessage
from .base import CameraBackend
from .output.base import CameraOutput

# Suppress debug logs from picamera2
logging.getLogger("picamera2").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


class PicameraEncoderOutputAdapter(Output):
    def __init__(self, device_id: int, output: CameraOutput):
        self.__device_id = device_id
        self.__output = output

    def outputframe(self, frame, keyframe=True, timestamp=None, packet=None, audio=False):
        self.__output.write(ImageMessage(self.__device_id, jpg_bytes=frame, job_id=None).to_bytes())


class Picam(CameraBackend):
    def __init__(self, device_id: int, output_lores: CameraOutput, output_hires: CameraOutput):
        self.__config = CfgCameraPicamera2()
        super().__init__(device_id, output_lores, output_hires)

        self.__picamera2: Picamera2 | None = None
        self.__picamera2_output_lores = PicameraEncoderOutputAdapter(device_id, self._output_lores)

        logger.info(f"Picamera2Backend initialized, {device_id=}, listening for subs")

    async def trigger_hires_capture(self, job_id: uuid.UUID):
        jpeg_bytes = await asyncio.to_thread(self._produce_image)

        msg_bytes = ImageMessage(self._device_id, jpg_bytes=jpeg_bytes, job_id=job_id).to_bytes()
        await self._output_hires.awrite(msg_bytes)

    def _produce_image(self) -> bytes:
        assert self.__picamera2

        jpeg_buffer = io.BytesIO()
        self.__picamera2.capture_file(jpeg_buffer, format="jpeg")
        jpeg_bytes = jpeg_buffer.getvalue()

        return jpeg_bytes

    async def run(self):
        # initialize private props

        logger.debug("starting _camera_fun")

        self.__picamera2 = Picamera2(camera_num=self.__config.camera_num)

        # configure; camera needs to be stopped before
        append_optmemory_format = {}
        if self.__config.optimize_memoryconsumption:
            logger.info("enabled memory optimization by choosing YUV420 format for main/lores streams")
            # if using YUV420 on main, also disable NoisReduction because it's done in software and causes framerate dropping on vc4 devices
            # https://github.com/raspberrypi/picamera2/discussions/1158#discussioncomment-11212355
            append_optmemory_format = {"format": "YUV420"}

        camera_configuration = self.__picamera2.create_still_configuration(
            main={"size": (self.__config.camera_res_width, self.__config.camera_res_height), **append_optmemory_format},
            lores={"size": (self.__config.stream_res_width, self.__config.stream_res_height), **append_optmemory_format},
            encode="lores",
            display=None,
            buffer_count=2,
            # queue=True,  # TODO: validate. Seems False is working better on slower systems? but also on Pi5?
            controls={"FrameRate": self.__config.framerate, "NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Off},
            transform=Transform(hflip=self.__config.flip_horizontal, vflip=self.__config.flip_vertical),
        )
        self.__picamera2.configure(camera_configuration)

        self.__picamera2.start()

        try:
            self.__picamera2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except RuntimeError as exc:
            logger.critical(f"control not available on camera - autofocus not working properly {exc}")

        try:
            self.__picamera2.set_controls({"AfSpeed": controls.AfSpeedEnum.Fast})
        except RuntimeError as exc:
            logger.info(f"control not available on all cameras - can ignore {exc}")

        logger.info(f"{self.__picamera2.camera_config=}")
        logger.info(f"{self.__picamera2.camera_controls=}")
        logger.info(f"{self.__picamera2.controls=}")
        logger.info(f"{self.__picamera2.camera_properties=}")

        self.__picamera2.start_recording(MJPEGEncoder(), self.__picamera2_output_lores, quality=Quality[self.__config.videostream_quality])

        logger.debug(f"{self.__module__} started")

        while True:
            # capture metadata blocks until new metadata is avail
            try:
                _ = await asyncio.to_thread(self.__picamera2.capture_metadata)

                # print(meta["SensorTimestamp"])

            except TimeoutError as exc:
                logger.warning(f"camera timed out: {exc}")
                break
