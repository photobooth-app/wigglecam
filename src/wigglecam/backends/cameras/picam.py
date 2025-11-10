import asyncio
import io
import logging
import uuid

from libcamera import Transform, controls  # type: ignore
from picamera2 import Picamera2
from picamera2.devices.imx708 import IMX708
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

    def _set_pi5_hdr(self, enable: bool):
        """enable/disable Pi5 specific HDR."""
        assert self.__picamera2
        if enable:
            self.__picamera2.set_controls({"HdrMode": controls.HdrModeEnum.SingleExposure})
        else:
            self.__picamera2.set_controls({"HdrMode": controls.HdrModeEnum.Off})

    def _set_imx708_hdr(self, enable: bool):
        """enable/disable imx708 (camera module 3) specific HDR. Resolution if enabled is max (Wxxxx,Hyyyy).
        Call before opening a Picamera2 object for regular use."""
        try:
            with IMX708(camera_num=self.__config.camera_num) as cam:
                if enable:
                    cam.set_sensor_hdr_mode(True)
                else:
                    cam.set_sensor_hdr_mode(False)
        except Exception as exc:
            logger.warning(f"could not set imx708 hdr mode, error: {exc}")

    async def run(self):
        # initialize private props

        logger.debug("starting _camera_fun")

        if self.__config.hdr_type == "imx708":
            self._set_imx708_hdr(True)

        self.__picamera2 = Picamera2(camera_num=self.__config.camera_num)

        if self.__config.hdr_type == "pi5":
            self._set_pi5_hdr(True)

        # configure; camera needs to be stopped before
        append_optmemory_format = {}
        if self.__config.optimize_memoryconsumption:
            logger.info("enabled memory optimization by choosing YUV420 format for main/lores streams")
            # if using YUV420 on main, also disable NoisReduction because it's done in software and causes framerate dropping on vc4 devices
            # https://github.com/raspberrypi/picamera2/discussions/1158#discussioncomment-11212355
            append_optmemory_format = {"format": "YUV420"}

        # configure; synchronization enabled?
        append_software_sync_control = {}
        if self.__config.software_sync == "server":
            logger.info("enabled synchronization, this node is configured as SERVER")
            append_software_sync_control = {"SyncMode": controls.rpi.SyncModeEnum.Server}
        elif self.__config.software_sync == "client":
            logger.info("enabled synchronization, this node is configured as CLIENT")
            append_software_sync_control = {"SyncMode": controls.rpi.SyncModeEnum.Client}
        else:
            logger.info("synchronization disabled.")

        camera_configuration = self.__picamera2.create_still_configuration(
            main={"size": (self.__config.camera_res_width, self.__config.camera_res_height), **append_optmemory_format},
            lores={"size": (self.__config.stream_res_width, self.__config.stream_res_height), **append_optmemory_format},
            encode="lores",
            display=None,
            buffer_count=3,  # 3 recommended if sync is used
            controls={
                "FrameRate": self.__config.framerate,
                # noise reduction might have impact on performance https://github.com/raspberrypi/picamera2/discussions/1158
                "NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Minimal,
                **append_software_sync_control,
            },
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

        mjpeg_encoder = MJPEGEncoder()
        mjpeg_encoder.frame_skip_count = self.__config.frame_skip_count
        self.__picamera2.start_recording(mjpeg_encoder, self.__picamera2_output_lores, quality=Quality[self.__config.videostream_quality])

        logger.debug(f"{self.__module__} started")

        if self.__config.software_sync != "off":
            logger.info("the node is configured to sync. ensure there is 1 server to sync to!")

        while True:
            # capture metadata blocks until new metadata is avail
            try:
                _ = await asyncio.to_thread(self.__picamera2.capture_metadata)

                # when sync client/server is enabled, the captures are synchronized by libcamera in the background
                # at one point there is the SyncTimer true. We do not supvervise it for now, so if there is no server
                # we don't know that the cameras are out of sync. Might improve later...
                # print("Sync ready:", meta.get("SyncReady"), "    Sync lag:", meta.get("SyncTimer"))

            except TimeoutError as exc:
                logger.warning(f"camera timed out: {exc}")
                break
