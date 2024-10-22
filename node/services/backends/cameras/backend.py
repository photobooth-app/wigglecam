import io
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


class BaseBackend:
    def __init__(self):
        # used to abort threads when service is stopped.
        self._is_running: bool = None

    def start(self):
        self._is_running: bool = True

    def stop(self):
        self._is_running: bool = False
