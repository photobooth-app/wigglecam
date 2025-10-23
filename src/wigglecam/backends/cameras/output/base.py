import abc


class CameraOutput(abc.ABC):
    @abc.abstractmethod
    def __init__(self, *args, **kwargs): ...
    @abc.abstractmethod
    def write(self, buf: bytes) -> int: ...
    @abc.abstractmethod
    async def awrite(self, buf: bytes) -> int: ...
