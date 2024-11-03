import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Barrier, BrokenBarrierError, Condition, Event

from ....utils.stoppablethread import StoppableThread

logger = logging.getLogger(__name__)


@dataclass
class BackendRequest:
    pass
    #   nothing to align here until today... maybe here we could add later a skip-frame command or something...


@dataclass
class BackendItem:
    # request: BackendRequest
    filepath: Path = None
    # metadata: dict = None


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
        self._started_evt: Event = None
        self._camera_thread: StoppableThread = None
        self._align_thread: StoppableThread = None
        self._barrier: Barrier = None
        self._current_timestampset: TimestampSet = None
        self._align_timestampset: TimestampSet = None
        self._queue_in: Queue[BackendRequest] = None
        self._queue_out: Queue[BackendItem] = None

        # init
        self._started_evt = Event()

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
        self._barrier = Barrier(3, action=self.get_timestamps_to_align)
        self._current_timestampset = TimestampSet(None, None)
        self._align_timestampset = TimestampSet(None, None)
        self._queue_in: Queue[BackendRequest] = Queue()
        self._queue_out: Queue[BackendItem] = Queue()

        self._camera_thread = StoppableThread(name="_camera_thread", target=self._camera_fun, args=(), daemon=True)
        self._camera_thread.start()

        self._align_thread = StoppableThread(name="_align_thread", target=self._align_fun, args=(), daemon=True)
        self._align_thread.start()

    @abstractmethod
    def stop(self):
        logger.debug(f"{self.__module__} stop called")
        self._started_evt.clear()

        if self._barrier:
            self._barrier.abort()

        if self._align_thread and self._align_thread.is_alive():
            self._align_thread.stop()
            self._align_thread.join()

        if self._camera_thread and self._camera_thread.is_alive():
            self._camera_thread.stop()
            self._camera_thread.join()

    @abstractmethod
    def camera_alive(self) -> bool:
        camera_alive = self._camera_thread and self._camera_thread.is_alive()
        align_alive = self._align_thread and self._align_thread.is_alive()

        return camera_alive and align_alive

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
    def wait_for_lores_image(self) -> bytes:
        pass

    @abstractmethod
    def wait_for_hires_frame(self):
        pass

    @abstractmethod
    def wait_for_hires_image(self, format: str) -> bytes:
        return self.encode_frame_to_image(self.wait_for_hires_frame(), format)

    @abstractmethod
    def encode_frame_to_image(self, frame, format: str) -> bytes:
        pass

    @abstractmethod
    def _camera_fun(self):
        pass

    @abstractmethod
    def _align_fun(self):
        pass
