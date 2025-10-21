import pynng

from .base import CameraOutput


class PynngOutput(CameraOutput):
    def __init__(self, address: str):
        self.pub = pynng.Pub0()  # using pub instead push because we just want to broadcast and push would queue if not pulled
        self.pub.dial(address, block=False)

    def write(self, buf: bytes) -> int:
        self.pub.send(buf)

        return len(buf)
