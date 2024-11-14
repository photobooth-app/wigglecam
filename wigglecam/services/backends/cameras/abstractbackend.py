import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from queue import Full, Queue
from threading import Barrier, BrokenBarrierError, Condition, Event, current_thread
from typing import Literal

from ....utils.stoppablethread import StoppableThread

logger = logging.getLogger(__name__)
Formats = Literal["jpeg"]  # only jpeg for now


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
        self._ticker_thread: StoppableThread = None
        self._barrier: Barrier = None
        self._current_timestamp_reference_in_queue: Queue[int] = None
        self._current_timestampset: TimestampSet = None

        # init
        self._started_evt = Event()

    def __repr__(self):
        return f"{self.__class__}"

    @abstractmethod
    def _backend_align():
        pass

    @abstractmethod
    def start(self, nominal_framerate: int = None):
        logger.debug(f"{self.__module__} start called")

        if not nominal_framerate:
            # if 0 or None, fail!
            raise RuntimeError("nominal framerate needs to be given!")

        # init common abstract props
        self._nominal_framerate = nominal_framerate
        self._barrier = Barrier(2, action=self._backend_align)
        self._current_timestamp_reference_in_queue: Queue[int] = Queue(maxsize=1)
        self._current_timestampset = TimestampSet(None, None)

        self._camera_thread = StoppableThread(name="_camera_thread", target=self._camera_fun, args=(), daemon=True)
        self._camera_thread.start()

        self._ticker_thread = StoppableThread(name="_ticker_thread", target=self._ticker_fun, args=(), daemon=True)
        self._ticker_thread.start()

    @abstractmethod
    def stop(self):
        logger.debug(f"{self.__module__} stop called")
        self._started_evt.clear()

        if self._barrier:
            self._barrier.abort()

        if self._ticker_thread and self._ticker_thread.is_alive():
            self._ticker_thread.stop()
            self._ticker_thread.join()

        if self._camera_thread and self._camera_thread.is_alive():
            self._camera_thread.stop()
            self._camera_thread.join()

    @abstractmethod
    def camera_alive(self) -> bool:
        camera_alive = self._camera_thread and self._camera_thread.is_alive()
        ticker_alive = self._ticker_thread and self._ticker_thread.is_alive()

        return camera_alive and ticker_alive

    def sync_tick(self, timestamp_ns: int):
        # use a queue maxlen=1 to decouple the thread calling sync_tick and the consuming thread
        try:
            self._current_timestamp_reference_in_queue.put(timestamp_ns, block=True, timeout=0.5 / self._nominal_framerate)
        except Full:
            # this happens if the reference and camera are totally out of sync. It should recover from this state or maybe need to remove old timestamp and place new always?
            print("queue full, could not place updated ref time, skip and continue...")

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
    def done_hires_frames(self):
        pass

    @abstractmethod
    def wait_for_hires_image(self, format: Formats) -> bytes:
        out = self.encode_frame_to_image(self.wait_for_hires_frame(), format)
        self.done_hires_frames()  # means with direct encoding this is really only for one-time shots, otherwise better wait_for_hires_frames
        return out

    @abstractmethod
    def encode_frame_to_image(self, frame, format: Formats) -> bytes:
        pass

    @abstractmethod
    def _camera_fun(self):
        pass

    def _ticker_fun(self):
        logger.debug("starting _ticker_fun")

        while not current_thread().stopped():
            self._current_timestampset.reference = self._current_timestamp_reference_in_queue.get(block=True, timeout=1.0)

            try:
                self._barrier.wait()
            except BrokenBarrierError:
                logger.debug("sync barrier broke")

        logger.debug("left _ticker_fun")
