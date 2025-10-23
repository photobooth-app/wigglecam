import pynng

from .base import CameraOutput


class PynngCameraOutput(CameraOutput):
    def __init__(self, address: str):
        self.__pub = pynng.Pub0()  # using pub instead push because we just want to broadcast and push would queue if not pulled
        self.__pub.listen(address)  # , block=False)
        # self.pub.listen("ipc:///home/michael/test.sock")

    def write(self, buf: bytes) -> int:
        """Synchronous send."""
        self.__pub.send(buf)

        return len(buf)

    async def awrite(self, buf: bytes) -> int:
        """Asynchronous send."""
        await self.__pub.asend(buf)
        return len(buf)
