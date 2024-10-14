import logging

from gpiozero import Button as ZeroButton
from gpiozero import DigitalOutputDevice, PWMOutputDevice

logger = logging.getLogger(__name__)


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


class PrimaryGpioService:
    def __init__(self, config: dict):
        self._config: dict = {
            "chip": "/dev/gpiochip0",
            "clock_out_pin_name": "GPIO27",
            "trigger_out_pin_name": "GPIO22",
            "ext_trigger_in_pin_name": "GPIO17",
            "FPS_NOMINAL": 10,
        }  # TODO: pydantic config?

        # private props
        self._clock_out = None
        self._trigger_out = None
        self._ext_trigger_in = None

    def start(self):
        self._clock_out = PWMOutputDevice(pin=self._config["clock_out_pin_name"], initial_value=0, frequency=self._config["FPS_NOMINAL"])
        self._clock_out.value = 0.5

        self._trigger_out = DigitalOutputDevice(pin=self._config["trigger_out_pin_name"], initial_value=0)

        self._ext_trigger_in = Button(pin=self._config["ext_trigger_in_pin_name"], bounce_time=0.04)
        self._ext_trigger_in.when_pressed = self._trigger_out.on
        self._ext_trigger_in.when_released = self._trigger_out.off

        logger.debug(f"{self.__module__} started")

    def stop(self):
        if self._clock_out:
            self._clock_out.close()

        if self._trigger_out:
            self._trigger_out.close()

        if self._ext_trigger_in:
            self._ext_trigger_in.close()


if __name__ == "__main__":
    print("should not be started directly")
