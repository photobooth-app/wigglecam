import time
from abc import ABC, abstractmethod
from threading import Condition


class AbstractIoBackend(ABC):
    def __init__(self):
        # used to abort threads when service is stopped.
        self._is_running: bool = None

        # abstract properties
        self._clock_rise_in_condition: Condition = None
        self._clock_fall_in_condition: Condition = None
        self._trigger_in_condition: Condition = None
        self._clock_in_timestamp_ns = None

        # abstract common properties init
        self._clock_rise_in_condition: Condition = Condition()
        self._clock_fall_in_condition: Condition = Condition()
        self._trigger_in_condition: Condition = Condition()

    def __repr__(self):
        return f"{self.__class__}"

    @abstractmethod
    def start(self):
        self._is_running: bool = True

    @abstractmethod
    def stop(self):
        self._is_running: bool = False

    @abstractmethod
    def derive_nominal_framerate_from_clock(self) -> int:
        pass

    @abstractmethod
    def set_trigger_out(self, on: bool):
        # forward to output trigger
        pass

    def clock_signal_valid(self) -> bool:
        TIMEOUT_CLOCK_SIGNAL_INVALID = 0.5 * 1e9  # 0.5sec
        if not self._clock_in_timestamp_ns:
            return False
        return (time.monotonic_ns() - self._clock_in_timestamp_ns) < TIMEOUT_CLOCK_SIGNAL_INVALID

    def _on_clock_rise_in(self, timestamp_ns: int):
        # print(f"kernel={timestamp_ns}, monotonic={time.monotonic_ns()}")

        with self._clock_rise_in_condition:
            self._clock_in_timestamp_ns = timestamp_ns
            self._clock_rise_in_condition.notify_all()

    def _on_clock_fall_in(self):
        with self._clock_fall_in_condition:
            self._clock_fall_in_condition.notify_all()

    def _on_trigger_in(self):
        with self._trigger_in_condition:
            self._trigger_in_condition.notify_all()

    def wait_for_clock_rise_signal(self, timeout: float = 1.0) -> int:
        with self._clock_rise_in_condition:
            if not self._clock_rise_in_condition.wait(timeout=timeout):
                raise TimeoutError("timeout receiving clock signal")

            return self._clock_in_timestamp_ns

    def wait_for_clock_fall_signal(self, timeout: float = 1.0):
        with self._clock_fall_in_condition:
            if not self._clock_fall_in_condition.wait(timeout=timeout):
                raise TimeoutError("timeout receiving clock signal")

    def wait_for_trigger_signal(self, timeout: float = None):
        with self._trigger_in_condition:
            self._trigger_in_condition.wait(timeout=timeout)
