"""Base service and resources module."""


class BaseService:
    """ """

    def __init__(self):
        # used to abort threads when service is stopped.
        self._is_running: bool = None

    def start(self):
        self._is_running: bool = True

    def stop(self):
        self._is_running: bool = False
