from pydantic_settings import SettingsConfigDict

from .base import CfgBaseSettings


class CfgApp(CfgBaseSettings):
    model_config = SettingsConfigDict(env_prefix="app_")
