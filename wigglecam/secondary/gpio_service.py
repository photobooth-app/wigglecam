import logging
import time
from threading import Condition, Thread

import gpiod

logger = logging.getLogger(__name__)


class SecondaryGpioService:
    def __init__(self, config: dict):
        self._config: dict = {
            "chip": "/dev/gpiochip0",
            "clock_in_pin_name": "GPIO14",
            "trigger_in_pin_name": "GPIO15",
        }  # TODO: pydantic config?

        # private props
        self._gpiod_chip = gpiod.Chip(self._config["chip"])
        self._gpiod_clock_in = gpiod.find_line(self._config["clock_in_pin_name"]).offset()
        self._gpiod_trigger_in = gpiod.find_line(self._config["trigger_in_pin_name"]).offset()

        self._clock_in_timestamp_ns = None
        self._clock_in_condition: Condition = Condition()
        self._trigger_in_condition: Condition = Condition()

        # worker threads
        self._gpio_thread: Thread = None

    def start(self):
        self._gpio_thread = Thread(name="_gpio_thread", target=self._gpio_fun, args=(), daemon=True)
        self._gpio_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        pass

    def clock_signal_valid(self) -> bool:
        return False

    def get_nominal_framerate(self) -> int:
        return 10  # TODO: implement derive from clock

    def _derive_framerate_from_clock(self) -> float:
        """calc the framerate derived by monitoring the clock signal for some time.
        needs to set the nominal frame duration running freely while no adjustments are made to sync up

        Returns:
            float: _description_
        """
        pass
        # TODO: implement.

    def _on_clock_in(self):
        with self._clock_in_condition:
            self._clock_in_timestamp_ns = time.monotonic_ns()
            self._clock_in_condition.notify_all()

    def wait_for_clock_signal(self, timeout: float = 1.0) -> int:
        with self._clock_in_condition:
            if not self._clock_in_condition.wait(timeout=timeout):
                raise TimeoutError("timeout receiving clock signal")

            return self._clock_in_timestamp_ns

    def _on_trigger_in(self):
        with self._trigger_in_condition:
            self._trigger_in_condition.notify_all()

    def wait_for_trigger_signal(self, timeout: float = None) -> int:
        with self._trigger_in_condition:
            self._trigger_in_condition.wait(timeout=timeout)

    def _event_callback(self, event):
        # print(f"offset: {event.source.offset()} timestamp: [{event.sec}.{event.nsec}]")
        if event.type == gpiod.LineEvent.RISING_EDGE:
            if event.source.offset() == self._gpiod_clock_in:
                self._on_clock_in()
            elif event.source.offset() == self._gpiod_trigger_in:
                self._on_trigger_in()
            else:
                raise ValueError("Invalid event source")
        else:
            raise TypeError("Invalid event type")

    def _gpio_fun(self):
        print("starting _gpio_fun")

        # setup lines
        lines_in = self._gpiod_chip.get_lines([self._gpiod_clock_in, self._gpiod_trigger_in])
        lines_in.request(consumer="clock_trigger_in", type=gpiod.LINE_REQ_EV_RISING_EDGE, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_DOWN)

        while True:
            ev_lines = lines_in.event_wait(sec=1)
            if ev_lines:
                for line in ev_lines:
                    event = line.event_read()
                    self._event_callback(event)
            else:
                pass  # nothing to do if no event came in

        print("_gpio_fun left")


if __name__ == "__main__":
    print("should not be started directly")
