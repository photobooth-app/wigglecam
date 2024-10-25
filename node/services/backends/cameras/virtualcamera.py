import logging

from .abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)


class VirtualcameraBackend(AbstractBackend):
    def __init__(self):
        super().__init__()
        # init with arguments

    def start(self):
        pass

    def stop(self):
        pass
