from typing import Literal

from pydantic import BaseModel, Field


class ConfigLogging(BaseModel):
    level: str = Field(default="DEBUG")


class ConfigBackendVirtualIo(BaseModel):
    fps_nominal: int = Field(default=5)  # needs to be lower than cameras mode max fps to allow for control reserve


class ConfigBackendGpio(BaseModel):
    clock_in_pin_name: str = Field(default="GPIO14")
    trigger_in_pin_name: str = Field(default="GPIO15")

    is_primary: bool = Field(default=False)
    fps_nominal: int = Field(default=9)  # needs to be lower than cameras mode max fps to allow for control reserve
    chip: str = Field(default="/dev/gpiochip0")
    pwmchip: str = Field(default="pwmchip2")  # pi5: pwmchip2, other pwmchip0
    pwm_channel: int = Field(default=2)  # pi5: 2, other 0
    trigger_out_pin_name: str = Field(default="GPIO17")


class ConfigBackendVirtualCamera(BaseModel):
    pass  # nothing to configure


class ConfigBackendPicamera2(BaseModel):
    camera_num: int = Field(default=0)
    CAPTURE_CAM_RESOLUTION_WIDTH: int = Field(default=4608)
    CAPTURE_CAM_RESOLUTION_HEIGHT: int = Field(default=2592)
    enable_preview_display: bool = Field(default=False)
    LIVEVIEW_RESOLUTION_WIDTH: int = Field(default=768)
    LIVEVIEW_RESOLUTION_HEIGHT: int = Field(default=432)
    original_still_quality: int = Field(default=90)
    videostream_quality: Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"] = Field(
        default="MEDIUM",
        description="Lower quality results in less data to be transferred and may reduce load on devices.",
    )


class GroupCameraBackend(BaseModel):
    active_backend: Literal["VirtualCamera", "Picamera2"] = Field(
        title="Active Backend",
        default="Picamera2",
        description="Backend to capture images from.",
    )

    virtualcamera: ConfigBackendVirtualCamera = ConfigBackendVirtualCamera()
    picamera2: ConfigBackendPicamera2 = ConfigBackendPicamera2()


class GroupIoBackend(BaseModel):
    active_backend: Literal["VirtualIo", "Gpio"] = Field(
        title="Active Backend",
        default="Gpio",
        description="Backend to use synchronize camera to.",
    )

    virtualio: ConfigBackendVirtualIo = ConfigBackendVirtualIo()
    gpio: ConfigBackendGpio = ConfigBackendGpio()


class ConfigSyncedAcquisition(BaseModel):
    standalone_mode: bool = Field(default=True)

    camera_backends: GroupCameraBackend = Field(default=GroupCameraBackend())
    io_backends: GroupIoBackend = Field(default=GroupIoBackend())


class ConfigJobConnected(BaseModel):
    pass
