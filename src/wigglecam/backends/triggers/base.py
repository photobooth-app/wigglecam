import abc
import uuid


class TriggerBackend(abc.ABC):
    @abc.abstractmethod
    async def run(self): ...
    @abc.abstractmethod
    async def wait_for_trigger(self) -> uuid.UUID: ...
