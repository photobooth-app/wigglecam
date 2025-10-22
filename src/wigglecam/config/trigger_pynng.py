from pydantic_settings import SettingsConfigDict

from .base import CfgBaseSettings


class CfgTriggerPynng(CfgBaseSettings):
    model_config = SettingsConfigDict(env_prefix="trigger_")

    # server: str = Field(default="0.0.0.0")
