import logging
from datetime import datetime
from threading import Condition

from gpiozero import Button as ZeroButton
from pydantic import BaseModel, Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .container import container
from .services.baseservice import BaseService

logger = logging.getLogger(__name__)


class ConfigGpioPeripherial(BaseModel):
    shutterbutton_in_pin_name: str = Field(default="GPIO4")


class AppMinimalConfig(BaseSettings):
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
    peripherial_gpio: ConfigGpioPeripherial = ConfigGpioPeripherial()

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        # first in following list is least important; last .env file overwrites the other.
        env_file=[".env.dev", ".env.test", ".env.primary", ".env.node"],
        env_nested_delimiter="__",
        case_sensitive=True,
        extra="ignore",
    )


class Button(ZeroButton):
    def _fire_held(self):
        # workaround for bug in gpiozero https://github.com/gpiozero/gpiozero/issues/697
        # https://github.com/gpiozero/gpiozero/issues/697#issuecomment-1480117579
        # Sometimes the kernel omits edges, so if the last
        # deactivating edge is omitted held keeps firing. So
        # check the current value and send a fake edge to
        # EventsMixin to stop the held events.
        if self.value:
            super()._fire_held()
        else:
            self._fire_events(self.pin_factory.ticks(), False)


class GpioPeripherialService(BaseService):
    def __init__(self, config: ConfigGpioPeripherial):
        super().__init__()

        # init arguments
        self._config: ConfigGpioPeripherial = config

        # define private props
        self._shutterbutton_in: Button = None
        self._shutterbutton_in_condition: Condition = None

        # init private props
        self._shutterbutton_in_condition: Condition = Condition()

    def start(self):
        super().start()

        # shutter button in
        self._shutterbutton_in = Button(pin=self._config.shutterbutton_in_pin_name, bounce_time=0.04)
        self._shutterbutton_in.when_pressed = self._on_shutterbutton
        logger.info(f"external trigger button on {self._shutterbutton_in}")

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        if self._shutterbutton_in:
            self._shutterbutton_in.close()

    def _on_shutterbutton(self):
        logger.info("shutter button pressed")
        with self._shutterbutton_in_condition:
            self._shutterbutton_in_condition.notify_all()

    def wait_for_shutterbutton(self, timeout: float = None) -> None:
        with self._shutterbutton_in_condition:
            self._shutterbutton_in_condition.wait(timeout=timeout)


def main():
    container.start()
    logger.info("starting app")
    appminimalconfig = AppMinimalConfig()
    gpioservice = GpioPeripherialService(appminimalconfig.peripherial_gpio)
    gpioservice.start()

    try:
        while True:
            gpioservice.wait_for_shutterbutton()
            container.synced_acquisition_service.execute_job()

    except KeyboardInterrupt:
        print("got Ctrl+C, exiting")

    # Clean up
    gpioservice.stop()
    logger.info("clean up")
    container.stop()


if __name__ == "__main__":
    main()
