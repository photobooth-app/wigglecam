import io
from abc import ABC, abstractmethod
from threading import Condition


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


class AbstractBackend(ABC):
    def __init__(self):
        # used to abort threads when service is stopped.
        self._is_running: bool = None

    def __repr__(self):
        return f"{self.__class__}"

    @abstractmethod
    def start(self, nominal_framerate: int = None):
        self._is_running: bool = True

    @abstractmethod
    def stop(self):
        self._is_running: bool = False

    @abstractmethod
    def start_stream(self):
        pass

    @abstractmethod
    def stop_stream(self):
        pass

    @abstractmethod
    def wait_for_lores_image(self):
        pass

    @abstractmethod
    def do_capture(self, filename: str = None, number_frames: int = 1):
        pass

    @abstractmethod
    def sync_tick(self, timestamp_ns: int):
        pass
