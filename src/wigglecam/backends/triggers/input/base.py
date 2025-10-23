import abc
import uuid


class TriggerInput(abc.ABC):
    @abc.abstractmethod
    def __init__(self, *args, **kwargs): ...
    @abc.abstractmethod
    async def receive_job_id(self) -> uuid.UUID: ...
