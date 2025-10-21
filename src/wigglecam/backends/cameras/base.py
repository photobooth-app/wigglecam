import abc
import uuid

from .output.base import CameraOutput


class CameraBackend(abc.ABC):
    @abc.abstractmethod
    def __init__(self, device_id: int, output_lores: CameraOutput, output_hires: CameraOutput):
        self._device_id = device_id
        self._output_lores = output_lores
        self._output_hires = output_hires

    @abc.abstractmethod
    async def run(self): ...
    @abc.abstractmethod
    async def trigger_hires_capture(self, job_id: uuid.UUID): ...
