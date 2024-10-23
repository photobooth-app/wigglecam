import logging
import time
from threading import Condition, Thread

import gpiod

from ....config.models import ConfigGpioSecondaryNode

logger = logging.getLogger(__name__)


class GpioSecondaryNodeService:
    def __init__(self, config: ConfigGpioSecondaryNode):
        # init with arguments
        self._config: ConfigGpioSecondaryNode = config

        # private props
        self._gpiod_chip = None
        self._gpiod_clock_in = None
        self._gpiod_trigger_in = None
        self._clock_in_condition: Condition = None
        self._trigger_in_condition: Condition = None
        self._clock_in_timestamp_ns = None
        self._gpio_thread: Thread = None

        # init private props
        self._gpiod_chip = gpiod.Chip(self._config.chip)
        self._gpiod_clock_in = gpiod.find_line(self._config.clock_in_pin_name).offset()
        self._gpiod_trigger_in = gpiod.find_line(self._config.trigger_in_pin_name).offset()
        self._clock_in_condition: Condition = Condition()
        self._trigger_in_condition: Condition = Condition()

    def start(self):
        self._gpio_thread = Thread(name="_gpio_thread", target=self._gpio_fun, args=(), daemon=True)
        self._gpio_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        pass

    def clock_signal_valid(self) -> bool:
        TIMEOUT_CLOCK_SIGNAL_INVALID = 0.5 * 1e9  # 0.5sec
        if not self._clock_in_timestamp_ns:
            return False
        return (time.monotonic_ns() - self._clock_in_timestamp_ns) < TIMEOUT_CLOCK_SIGNAL_INVALID

    def derive_nominal_framerate_from_clock(self) -> int:
        """calc the framerate derived by monitoring the clock signal for 11 ticks (means 10 intervals).
        needs to set the nominal frame duration running freely while no adjustments are made to sync up

        Returns:
            int: _description_
        """
        try:
            first_timestamp_ns = self.wait_for_clock_signal(timeout=1)
            for _ in range(10):
                last_timestamp_ns = self.wait_for_clock_signal(timeout=1)
        except TimeoutError as exc:
            raise RuntimeError("no clock, cannot derive nominal framerate!") from exc
        else:
            duration_10_ticks_s = (last_timestamp_ns - first_timestamp_ns) * 1.0e-9
            fps = round(10.0 / duration_10_ticks_s)  # duration/10ticks = duration per tick so ^-1 is fps

            return fps

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
