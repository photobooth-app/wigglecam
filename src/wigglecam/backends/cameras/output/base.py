import abc


class CameraOutput:
    @abc.abstractmethod
    def __init__(self, *args, **kwargs): ...
    @abc.abstractmethod
    def write(self, buf: bytes) -> int: ...
