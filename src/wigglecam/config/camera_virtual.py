from pydantic import Field
from pydantic_settings import SettingsConfigDict

from .base import CfgBaseSettings


class CfgCameraVirtual(CfgBaseSettings):
    model_config = SettingsConfigDict(env_prefix="camera_virtual_")

    fps_nominal: int = Field(default=10)
