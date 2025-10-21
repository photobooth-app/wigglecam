from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict


class CfgCameraPicamera2(BaseModel):
    model_config = SettingsConfigDict(env_prefix="camera_picamera2_")

    camera_num: int = Field(default=0)
    optimize_memoryconsumption: bool = Field(default=True)

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
