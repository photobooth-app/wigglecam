import io
import logging
from abc import ABC, abstractmethod
from queue import Full, Queue
from threading import Condition, Event

logger = logging.getLogger(__name__)


class StreamingOutput(io.BufferedIOBase):
    """Lores data class used for streaming.
    Used in hardware accelerated MJPEGEncoder

    Args:
        io (_type_): _description_
    """

    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class AbstractCameraBackend(ABC):
    def __init__(self):
        # declare common abstract props
        self._nominal_framerate: int = None
        self._queue_timestamp_monotonic_ns: Queue = None
        self._event_request_tick: Event = None
        self._capture: Event = None

        # init common abstract props
        self._event_request_tick: Event = Event()
        self._capture = Event()

    def __repr__(self):
        return f"{self.__class__}"

    @abstractmethod
    def start(self, nominal_framerate: int = None):
        logger.debug(f"{self.__module__} start called")

        if not nominal_framerate:
            # if 0 or None, fail!
            raise RuntimeError("nominal framerate needs to be given!")

        self._nominal_framerate = nominal_framerate
        self._queue_timestamp_monotonic_ns: Queue = Queue(maxsize=1)

    @abstractmethod
    def stop(self):
        logger.debug(f"{self.__module__} stop called")

    @abstractmethod
    def camera_alive(self) -> bool:
        pass

    def do_capture(self, filename: str = None, number_frames: int = 1):
        self._capture.set()

    def sync_tick(self, timestamp_ns: int):
        try:
            self._queue_timestamp_monotonic_ns.put_nowait(timestamp_ns)
        except Full:
            logger.info("could not queue timestamp - camera_thread not started, busy, overload or nominal fps to close to cameras max mode fps?")

    def request_tick(self):
        self._event_request_tick.set()

    @abstractmethod
    def start_stream(self):
        pass

    @abstractmethod
    def stop_stream(self):
        pass

    @abstractmethod
    def wait_for_lores_image(self):
        pass
