from pydantic_settings import BaseSettings, SettingsConfigDict


class CfgBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        # first in following list is least important; last .env file overwrites the other.
        env_file=[".env.dev", ".env.test", ".env.primary", ".env.node"],
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )
