from typing import Literal

from pydantic import BaseModel, Field


class ConfigLogging(BaseModel):
    level: str = Field(default="DEBUG")


class ConfigBackendGpio(BaseModel):
    chip: str = Field(default="/dev/gpiochip0")
    clock_in_pin_name: str = Field(default="GPIO14")
    trigger_in_pin_name: str = Field(default="GPIO15")
    trigger_out_pin_name: str = Field(default="GPIO17")

    enable_clock: bool = Field(default=False)
    fps_nominal: int = Field(default=9)  # needs to be lower than cameras mode max fps to allow for control reserve
    pwmchip: str = Field(default="pwmchip2")  # pi5: pwmchip2, other pwmchip0
    pwm_channel: int = Field(default=2)  # pi5: 2, other 0


class ConfigBackendVirtualcamera(BaseModel):
    pass  # nothing to configure


class ConfigBackendPicamera2(BaseModel):
    camera_num: int = Field(default=0)
    CAPTURE_CAM_RESOLUTION_WIDTH: int = Field(default=4608)
    CAPTURE_CAM_RESOLUTION_HEIGHT: int = Field(default=2592)
    enable_preview_display: bool = Field(default=False)
    LIVEVIEW_RESOLUTION_WIDTH: int = Field(default=768)
    LIVEVIEW_RESOLUTION_HEIGHT: int = Field(default=432)
    original_still_quality: int = Field(default=90)


class GroupBackend(BaseModel):
    active_backend: Literal["VirtualCamera", "Picamera2"] = Field(
        title="Active Backend",
        default="Picamera2",
        description="Backend to capture images from.",
    )

    virtualcamera: ConfigBackendVirtualcamera = ConfigBackendVirtualcamera()
    picamera2: ConfigBackendPicamera2 = ConfigBackendPicamera2()


class ConfigSyncedAcquisition(BaseModel):
    allow_standalone_job: bool = Field(default=True)
    backends: GroupBackend = Field(default=GroupBackend())
