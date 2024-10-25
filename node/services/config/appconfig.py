from datetime import datetime

from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import ConfigBackendGpio, ConfigBackendPicamera2, ConfigLogging, ConfigSyncedAcquisition


class AppConfig(BaseSettings):
    """
    AppConfig class glueing all together

    In the case where a value is specified for the same Settings field in multiple ways, the selected value is determined as follows
    (in descending order of priority):

    1 Arguments passed to the Settings class initialiser.
    2 Environment variables, e.g. my_prefix_special_function as described above.
    3 Variables loaded from a dotenv (.env) file.
    4 Variables loaded from the secrets directory.
    5 The default field values for the Settings model.
    """

    _processed_at: datetime = PrivateAttr(default_factory=datetime.now)  # private attributes

    # groups -> setting items
    logging: ConfigLogging = ConfigLogging()
    syncedacquisition: ConfigSyncedAcquisition = ConfigSyncedAcquisition()
    backend_gpio: ConfigBackendGpio = ConfigBackendGpio()
    backend_picamera2: ConfigBackendPicamera2 = ConfigBackendPicamera2()

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        # first in following list is least important; last .env file overwrites the other.
        env_file=[".env.dev", ".env.test", ".env.primary", ".env.node"],
        env_nested_delimiter="__",
        case_sensitive=True,
        extra="ignore",
    )
