from pydantic import Field
from pydantic_settings import SettingsConfigDict

from .base import CfgBaseSettings


class CfgApp(CfgBaseSettings):
    model_config = SettingsConfigDict(env_prefix="app_")

    device_id: int = Field(default=0)
    server: str = Field(default="0.0.0.0")
