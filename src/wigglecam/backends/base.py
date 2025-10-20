import abc
import asyncio


class StreamingOutput:
    """
    Async frame buffer for camera backends.
    Supports multiple concurrent consumers waiting for frames.

    - Producer calls `write(buf)` to store a new frame.
    - Consumers call `wait_for_frame(timeout)` to get the latest frame.
    """

    def __init__(self):
        self._frame: bytes | None = None
        self._condition = asyncio.Condition()
        self._frame_counter = 0  # increments on each new frame

    async def write(self, buf: bytes) -> int:
        """Store a new frame and notify all waiting consumers."""
        async with self._condition:
            self._frame = buf
            self._frame_counter += 1
            self._condition.notify_all()
            return len(buf)

    async def wait_for_frame(self, timeout: float | None = None) -> bytes:
        """
        Wait until a new frame is available.
        Raises TimeoutError if no frame arrives within `timeout`.
        """
        last_seen = self._frame_counter
        async with self._condition:
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(lambda: self._frame_counter > last_seen),
                    timeout=timeout,
                )
            except asyncio.TimeoutError as exc:
                raise TimeoutError("timeout waiting for frame") from exc

            assert self._frame is not None
            return self._frame


class CameraBackend(abc.ABC):
    @abc.abstractmethod
    async def run(self): ...
    @abc.abstractmethod
    async def wait_for_lores_image(self) -> bytes: ...
    @abc.abstractmethod
    async def wait_for_hires_image(self) -> bytes: ...


class TriggerBackend(abc.ABC):
    @abc.abstractmethod
    async def run(self): ...
    @abc.abstractmethod
    async def wait_for_trigger(self): ...

    # @abc.abstractmethod
    # async def send_response(self, msg): ...
