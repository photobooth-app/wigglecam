import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Barrier, BrokenBarrierError, Condition, Event

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


@dataclass
class TimestampSet:
    """Set of timestamps that shall be aligned to each other."""

    reference: int  # in nanoseconds
    camera: int  # in nanoseconds


class AbstractCameraBackend(ABC):
    def __init__(self):
        # declare common abstract props
        self._nominal_framerate: int = None
        self._capture: Event = None
        self._capture_in_progress: bool = None
        self._barrier: Barrier = None
        self._current_timestampset: TimestampSet = None
        self._align_timestampset: TimestampSet = None

    def __repr__(self):
        return f"{self.__class__}"

    def get_timestamps_to_align(self) -> TimestampSet:
        assert self._current_timestampset.reference is not None
        assert self._current_timestampset.camera is not None

        # shift reference to align with camera cycle
        _current_timestampset_reference = self._current_timestampset.reference
        # _current_timestampset_reference -= (1.0 / self._nominal_framerate) * 1e9

        self._align_timestampset = TimestampSet(reference=_current_timestampset_reference, camera=self._current_timestampset.camera)

    @abstractmethod
    def start(self, nominal_framerate: int = None):
        logger.debug(f"{self.__module__} start called")

        if not nominal_framerate:
            # if 0 or None, fail!
            raise RuntimeError("nominal framerate needs to be given!")

        # init common abstract props
        self._nominal_framerate = nominal_framerate
        self._capture = Event()
        self._capture_in_progress = False
        self._barrier = Barrier(3, action=self.get_timestamps_to_align)
        self._current_timestampset = TimestampSet(None, None)
        self._align_timestampset = TimestampSet(None, None)

    @abstractmethod
    def stop(self):
        logger.debug(f"{self.__module__} stop called")

    @abstractmethod
    def camera_alive(self) -> bool:
        pass

    def do_capture(self, filename: str = None, number_frames: int = 1):
        self._capture.set()

    def sync_tick(self, timestamp_ns: int):
        self._current_timestampset.reference = timestamp_ns
        try:
            self._barrier.wait()
        except BrokenBarrierError:
            logger.debug("sync barrier broke")

    @abstractmethod
    def start_stream(self):
        pass

    @abstractmethod
    def stop_stream(self):
        pass

    @abstractmethod
    def wait_for_lores_image(self):
        pass
