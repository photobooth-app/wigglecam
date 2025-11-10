from typing import Literal

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from .base import CfgBaseSettings


class CfgCameraPicamera2(CfgBaseSettings):
    model_config = SettingsConfigDict(env_prefix="camera_picamera2_")

    camera_num: int = Field(default=0)
    framerate: int = Field(default=8)
    optimize_memoryconsumption: bool = Field(default=True)
    software_sync: Literal["off", "server", "client"] = Field(default="off")

    camera_res_width: int = Field(default=2304)  # max 2304 if HDR type imx708, otherwise 4608
    camera_res_height: int = Field(default=1296)  # max 1296 if HDR type imx708, otherwise 2592
    hdr_type: Literal["unset", "imx708", "pi5"] = Field(
        default="unset",
        description="Choose whatever hardware is used. Unset does not actively disable, but just do nothing. To disable, unpower.",
    )

    stream_res_width: int = Field(default=1152)
    stream_res_height: int = Field(default=648)
    frame_skip_count: int = Field(
        default=2,
        ge=1,
        le=4,
        description="Reduce the stream framerate by frame_skip_count to save cpu/gpu/network on producing device as well as client devices. Choose 1 to emit every produced frame.",
    )

    flip_horizontal: bool = Field(default=False)
    flip_vertical: bool = Field(default=False)

    videostream_quality: Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"] = Field(default="HIGH")
