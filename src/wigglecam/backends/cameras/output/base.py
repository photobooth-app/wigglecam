import abc


class CameraOutput(abc.ABC):
    @abc.abstractmethod
    def __init__(self, *args, **kwargs):
        """Base init to setup a camera output for high/lores images"""

    @abc.abstractmethod
    def write(self, buf: bytes) -> int:
        """Camera encoder/producer writes bytes to the buffer which is then transmitted in the instance"""

    @abc.abstractmethod
    async def awrite(self, buf: bytes) -> int:
        """Camera encoder/producer writes bytes to the buffer which is then transmitted in the instance"""
