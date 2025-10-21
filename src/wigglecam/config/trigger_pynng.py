from pydantic import Field
from pydantic_settings import SettingsConfigDict

from .base import CfgBaseSettings


class CfgTriggerPynng(CfgBaseSettings):
    model_config = SettingsConfigDict(env_prefix="trigger_pynng_")

    server: str = Field(default="0.0.0.0")
