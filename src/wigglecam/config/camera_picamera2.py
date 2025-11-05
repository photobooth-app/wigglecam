from typing import Literal

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from .base import CfgBaseSettings


class CfgCameraPicamera2(CfgBaseSettings):
    model_config = SettingsConfigDict(env_prefix="camera_picamera2_")

    camera_num: int = Field(default=0)
    framerate: int = Field(default=8)
    optimize_memoryconsumption: bool = Field(default=True)

    camera_res_width: int = Field(default=4608)
    camera_res_height: int = Field(default=2592)
    activate_hdr_imx708: bool = Field(default=False)  # TODO: implement use of this?

    stream_res_width: int = Field(default=1152)
    stream_res_height: int = Field(default=648)
    stream_framerate: int = Field(default=4)  # TODO: make use of this?

    flip_horizontal: bool = Field(default=False)
    flip_vertical: bool = Field(default=False)

    videostream_quality: Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"] = Field(default="HIGH")
